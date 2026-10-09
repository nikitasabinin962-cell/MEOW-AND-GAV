"""Региональные настройки — единственное место, где модель «знает» про конкретный регион.

Все значения берутся из раздела `region` в config.yaml (см. config/region_template.yaml).
Значения по умолчанию — для Республики Башкортостан, чтобы старые конфиги работали без изменений.
Остальной код региона не знает: признаки, сети, кластеризация, индексы и отчёты одинаковы для любого субъекта.
"""
from __future__ import annotations
import re

NAME = "Республика Башкортостан"
INN_CODE = "02"                       # код субъекта в ИНН (первые 2 цифры)
CAPITAL = "ГО Уфа"                    # региональный центр
CAPITAL_PREFIXES: set[str] = {"0272", "0273", "0274", "0275", "0276", "0277", "0278"}  # инспекции ФНС центра
CAPITAL_REGEX = re.compile(r"УФА|УФЫ|УФЕ|УФИМ")  # падежные формы названия центра в наименованиях заказчиков
MANUAL_PREFIXES: dict[str, str] = {"0279": "ГО Межгорье"}  # ЗАТО и иные МО, которые не определить по названию
ENCLAVES: dict[str, tuple[str, float]] = {"ГО Межгорье": ("МР Белорецкий", 40.0)}  # МО без расстояний: (сосед, км)
ORIENT_ANCHORS: dict[str, tuple[float, float]] = {    # (широта, долгота) для поворота «карты по дорогам»
    "ГО Уфа": (54.73, 55.95), "ГО Стерлитамак": (53.63, 55.95), "ГО Нефтекамск": (56.09, 54.25),
    "ГО Сибай": (52.72, 58.66), "ГО Октябрьский": (54.48, 53.47)}
MID_LAT = 54.5                         # средняя широта региона (масштаб долготы на карте)


def configure(cfg: dict) -> None:
    """Применить раздел `region` конфига. Вызывается один раз при старте CLI."""
    global NAME, INN_CODE, CAPITAL, CAPITAL_PREFIXES, CAPITAL_REGEX, MANUAL_PREFIXES, ENCLAVES, ORIENT_ANCHORS, MID_LAT
    r = cfg.get("region", {}) or {}
    NAME = r.get("name", NAME)
    INN_CODE = str(r.get("inn_code", INN_CODE)).zfill(2)
    CAPITAL = r.get("capital", CAPITAL)
    if "capital_inn_prefixes" in r:
        CAPITAL_PREFIXES = {str(p) for p in r["capital_inn_prefixes"]}
    if "capital_name_regex" in r:
        CAPITAL_REGEX = re.compile(r["capital_name_regex"])
    if "manual_inn_prefixes" in r:
        MANUAL_PREFIXES = {str(k): v for k, v in (r["manual_inn_prefixes"] or {}).items()}
    if "enclaves" in r:
        ENCLAVES = {k: (v["neighbour"], float(v["km"])) for k, v in (r["enclaves"] or {}).items()}
    if "orient_anchors" in r:
        ORIENT_ANCHORS = {k: (float(v[0]), float(v[1])) for k, v in (r["orient_anchors"] or {}).items()}
        if ORIENT_ANCHORS:
            MID_LAT = sum(v[0] for v in ORIENT_ANCHORS.values()) / len(ORIENT_ANCHORS)
    if "mid_lat" in r:
        MID_LAT = float(r["mid_lat"])
