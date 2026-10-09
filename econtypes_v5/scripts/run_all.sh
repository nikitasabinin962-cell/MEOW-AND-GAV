#!/usr/bin/env bash
# econtypes v5 — одна команда: окружение → база → тесты → расчёт → проверки → экспорт → дашборд → отчёты.
# Использование (из каталога econtypes_v5):  bash scripts/run_all.sh [--quick] [--keep-db]
set -euo pipefail
cd "$(dirname "$0")/.."
QUICK=""; KEEP=""
for a in "$@"; do case "$a" in --quick) QUICK="--quick";; --keep-db) KEEP=1;; esac; done
PY=${PY:-python3}
VENV=${VENV:-.venv}                # можно указать готовое окружение: VENV=/path/to/venv
if [ ! -x "$VENV/bin/python" ]; then $PY -m venv "$VENV" && "$VENV/bin/pip" install -q -r requirements.lock && "$VENV/bin/pip" install -q -e . ; fi
P=$VENV/bin/python
FRONT=${FRONT:-../../-}            # репозиторий дашборда (nikitasabinin962-cell/-)
RESEARCH=${RESEARCH:-../econtypes_research_20261009.sqlite}
echo "== 1/9 база v5 (идемпотентный ingest; исходники не меняются)"
if [ -z "$KEEP" ]; then rm -f data/econtypes_v5.sqlite data/econtypes_v5.sqlite-wal data/econtypes_v5.sqlite-shm; fi
$P scripts/measure.py outputs/ingest_measure.json $P -m econtypes5.ingest --research "$RESEARCH" > outputs/ingest_log.json
echo "== 2/9 тесты (pytest)"
$P -m pytest -q tests | tee outputs/pytest_log.txt
echo "== 3/9 полный расчёт"
$P scripts/measure.py outputs/pipeline_full_measure.json $P -m econtypes5.pipeline $QUICK | tee outputs/pipeline_full_log.txt
echo "== 4/9 повтор проверок аудитора на v5"
$P scripts/audit_v5.py
echo "== 5/9 нагрузка на синтетике (N=63/500/2016)"
$P scripts/scale_benchmark.py
echo "== 6/9 идемпотентность ingest (два прохода во временную базу)"
$P scripts/idempotency_check.py
echo "== 7/9 матрицы требований и формул"
$P scripts/make_matrices.py
echo "== 8/9 экспорт D5 и сборка дашборда v5"
if [ -d "$FRONT" ]; then
  $P -m econtypes5.dashboard_export --out "$FRONT/src/v5/D5.json"
  (cd "$FRONT" && python3 build.py --version v5 --update-manifest && python3 build.py --out "${TMPDIR:-/tmp}/econtypes_v4_check.html")
  if [ -d "$FRONT/node_modules/playwright" ]; then (cd "$FRONT" && node tests/v5-check.js econtypes_v5.html > /dev/null && echo "v5-checks OK" || echo "v5-checks: есть FAIL — см. docs/v5-checks.json"); fi
fi
echo "== 9/9 отчёт (Markdown + Word)"
$P scripts/make_report.py
echo "готово: outputs/latest/, docs/, $FRONT/econtypes_v5.html"
