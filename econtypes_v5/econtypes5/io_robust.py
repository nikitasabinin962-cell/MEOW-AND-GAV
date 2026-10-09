"""Устойчивое чтение файлов и загрузка API (п. 4.4, 5.10 задания).

  * read_csv_robust — пустой/повреждённый файл, BOM, UTF-8/cp1251, разделитель ';' или ','; плохие строки
    возвращаются в отчёте, а не молча отбрасываются;
  * parse_money_kopecks — денежные строки → целые копейки (Decimal, ROUND_HALF_UP), валюта отдельно;
  * normalize_oktmo — ОКТМО как текст с ведущими нулями (8 или 11 знаков);
  * split_duplicates — точные повторы против конфликтующих версий одной записи (конфликты не «выбираются»);
  * identity_key — ключ записи включает систему-источник: одинаковый номер в разных системах не сливается;
  * period_coverage — полный год или YTD (по числу месяцев с наблюдениями);
  * Fetcher/paginate — ограниченный экспоненциальный backoff с jitter и Retry-After (429/500/502/503/504),
    отказ принимать HTML вместо JSON, детектор повторённой страницы, контрольные суммы страниц,
    контрольная точка и продолжение после обрыва. Капча/платный доступ не обходятся: при признаке капчи — стоп.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

RETRY_STATUS = {429, 500, 502, 503, 504}


# ------------------------------------------------------------------ файлы
def read_csv_robust(path: str | Path, dtype=str) -> tuple[pd.DataFrame, dict]:
    p = Path(path)
    rep = dict(path=str(p), bytes=p.stat().st_size if p.exists() else None)
    if not p.exists():
        raise FileNotFoundError(p)
    raw = p.read_bytes()
    if len(raw) == 0 or not raw.strip():
        rep.update(status="empty_file", rows=0)
        return pd.DataFrame(), rep
    bom = raw.startswith(b"\xef\xbb\xbf")
    text, enc = None, None
    for e in (["utf-8-sig"] if bom else ["utf-8", "cp1251"]):
        try:
            text, enc = raw.decode(e), e
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        rep.update(status="undecodable", rows=0)
        return pd.DataFrame(), rep
    head = text[:4096]
    try:
        sep = csv.Sniffer().sniff(head, delimiters=";,\t").delimiter
    except csv.Error:
        sep = ";" if head.count(";") > head.count(",") else ","
    bad, good = [], []
    reader = csv.reader(io.StringIO(text), delimiter=sep)
    try:
        header = next(reader)
    except StopIteration:
        rep.update(status="empty_file", rows=0)
        return pd.DataFrame(), rep
    for i, row in enumerate(reader, start=2):
        if not row:
            continue
        if len(row) != len(header):
            bad.append(dict(line=i, fields=len(row), expected=len(header)))
            continue
        good.append(row)
    df = pd.DataFrame(good, columns=header).replace("", None)
    rep.update(status="ok" if not bad else "ok_with_bad_lines", encoding=enc, bom=bom, sep=sep, rows=len(df),
               columns=list(df.columns), bad_lines=len(bad), bad_sample=bad[:3],
               sha256=hashlib.sha256(raw).hexdigest())
    return df, rep


def parse_money_kopecks(v) -> tuple[int | None, str]:
    """'1 234,56' | '1234.56' | 1234.56 → копейки. Возвращает (значение, статус)."""
    if v is None or (isinstance(v, float) and v != v) or str(v).strip() == "":
        return None, "missing"
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    elif s.count(",") >= 1 and s.count(".") == 1:
        s = s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, "invalid"
    k = int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return k, ("negative" if k < 0 else "ok")


def sum_by_currency(amounts_kopecks: list, currencies: list) -> dict:
    """Суммы только внутри валюты; смешение валют не складывается."""
    out: dict = {}
    for a, c in zip(amounts_kopecks, currencies):
        if a is None:
            continue
        out[c or "UNKNOWN"] = out.get(c or "UNKNOWN", 0) + a
    return out


def normalize_oktmo(v) -> tuple[str | None, str]:
    if v is None or str(v).strip() == "":
        return None, "missing"
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if not s.isdigit():
        return None, "invalid"
    if len(s) <= 8:
        return s.zfill(8), "ok_8"
    if len(s) <= 11:
        return s.zfill(11), "ok_11"
    return None, "too_long"


def identity_key(system: str, number: str) -> str:
    if not system:
        raise ValueError("system обязателен: номер без системы-источника не является идентификатором")
    return f"{system}:{str(number).strip()}"


def split_duplicates(df: pd.DataFrame, key: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Возвращает (уникальные записи без конфликтов, конфликтующие версии, сводку).
    Точные повторы удаляются; записи с одним ключом и разным содержимым уходят в конфликты целиком."""
    exact = df.duplicated(keep="first")
    d = df[~exact]
    g = d.groupby(key, dropna=False).size()
    conflict_keys = g[g > 1].index
    is_conf = d.set_index(key).index.isin(conflict_keys)
    return d[~is_conf], d[is_conf], dict(rows=len(df), exact_duplicates=int(exact.sum()), conflict_keys=int(len(conflict_keys)),
                                         conflict_rows=int(is_conf.sum()), unique=int((~is_conf).sum()))


def period_coverage(dates: pd.Series, year: int) -> dict:
    m = pd.to_datetime(dates, errors="coerce")
    months = sorted(m[m.dt.year == year].dt.month.unique().tolist())
    return dict(year=year, months_observed=months, n_months=len(months),
                kind="full_year" if len(months) == 12 else ("ytd" if months and months[0] == 1 and months == list(range(1, months[-1] + 1)) else "partial_gaps"))


# ------------------------------------------------------------------ HTTP
class FetchError(RuntimeError):
    pass


@dataclass
class Fetcher:
    max_attempts: int = 6
    base_delay: float = 1.0
    max_delay: float = 60.0
    timeout: float = 60.0
    jitter: float = 0.3
    sleep: callable = time.sleep
    log: list = field(default_factory=list)

    def get_json(self, url: str):
        for attempt in range(1, self.max_attempts + 1):
            try:
                with urllib.request.urlopen(url, timeout=self.timeout) as r:
                    body = r.read()
                    ctype = r.headers.get("Content-Type", "")
                status = 200
            except urllib.error.HTTPError as e:
                status, body, ctype = e.code, e.read(), e.headers.get("Content-Type", "")
                if status in RETRY_STATUS and attempt < self.max_attempts:
                    ra = e.headers.get("Retry-After")
                    delay = float(ra) if ra and ra.isdigit() else min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
                    delay *= 1 + random.uniform(-self.jitter, self.jitter) if not ra else 1
                    self.log.append(dict(url=url, status=status, attempt=attempt, wait=round(delay, 2)))
                    self.sleep(delay)
                    continue
                raise FetchError(f"HTTP {status} for {url}")
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                if attempt < self.max_attempts:
                    delay = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
                    self.log.append(dict(url=url, error=str(e)[:100], attempt=attempt, wait=delay))
                    self.sleep(delay)
                    continue
                raise FetchError(f"network error {e} for {url}")
            text = body.decode("utf-8", errors="replace")
            low = text.lstrip()[:200].lower()
            if "captcha" in text.lower()[:5000]:
                raise FetchError("captcha detected — stop; обход не выполняется")
            if "json" not in ctype.lower() or low.startswith("<!doctype") or low.startswith("<html"):
                raise FetchError(f"not JSON (Content-Type={ctype!r}) for {url}")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise FetchError(f"invalid/truncated JSON for {url}: {e}")
            return data, hashlib.sha256(body).hexdigest()
        raise FetchError(f"exhausted attempts for {url}")


def paginate(fetcher: Fetcher, url_for_page, state_path: Path, last_page: int | None = None,
             items_key: str = "items", stop_on_empty: bool = True) -> dict:
    """Постраничная загрузка с контрольной точкой (JSON state): страницы, их sha256, число записей.
    Повтор содержимого предыдущей страницы — ошибка пагинации (не успех). Повторный запуск продолжает
    с первой незавершённой страницы."""
    state = json.loads(state_path.read_text()) if state_path.exists() else dict(pages={}, done=False)
    page = max([int(k) for k in state["pages"]] + [0]) + 1
    prev_hash = state["pages"].get(str(page - 1), {}).get("sha256")
    while not state["done"] and (last_page is None or page <= last_page):
        data, h = fetcher.get_json(url_for_page(page))
        if h == prev_hash:
            raise FetchError(f"page {page} repeats page {page - 1} (sha256 {h[:12]}) — пагинация некорректна")
        items = data.get(items_key, []) if isinstance(data, dict) else data
        state["pages"][str(page)] = dict(sha256=h, n=len(items))
        state_path.write_text(json.dumps(state))
        if stop_on_empty and len(items) == 0:
            state["done"] = True
            state_path.write_text(json.dumps(state))
            break
        prev_hash = h
        page += 1
    if last_page is not None and page > last_page:
        state["done"] = True
        state_path.write_text(json.dumps(state))
    state["records"] = sum(v["n"] for v in state["pages"].values())
    return state
