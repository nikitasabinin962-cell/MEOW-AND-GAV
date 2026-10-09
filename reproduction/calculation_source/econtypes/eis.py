"""Загрузка и очистка выгрузки реестра контрактов ЕИС (44-ФЗ).

Выгрузка ЕИС — одна строка на позицию контракта (объект закупки). Строим две таблицы:
  contracts  — одна строка на контракт (дата, заказчик, поставщик, цена, способ);
  positions  — позиции с кодом ОКПД2 и суммой (для отраслевой структуры).
"""
from __future__ import annotations

import re
import numpy as np
import pandas as pd

COL = {
    "Номер реестровой записи контракта": "contract_id",
    "Заказчик: наименование": "customer_name",
    "Заказчик: ИНН": "customer_inn",
    "Уровень бюджета": "budget_level",
    "Способ размещения заказа": "method",
    "Контракт: дата": "date",
    "Цена контракта": "price",
    "Объект закупки: код позиции": "okpd2",
    "Объект закупки: сумма, рублей": "pos_sum",
    "Информация о поставщиках (исполнителях, подрядчиках) по контракту: наименование юридического лица (ф.и.о. физического лица)": "supplier_name",
    "Информация о поставщиках (исполнителях, подрядчиках) по контракту: ИНН": "supplier_inn",
}

# Государственные (республиканские и федеральные) заказчики. Муниципальные учреждения тоже
# содержат в названии «Республики Башкортостан», поэтому отбор — по типу учреждения.
STATE = re.compile(r"ГОСУДАРСТВЕНН|ФЕДЕРАЛЬН|МИНИСТЕРСТВ|ФОНД|^ФГ|^ФК|^ГБУ|^ГКУ|^ГАУ|^ГУП|КОМИТЕТ (?:РЕСПУБЛИКИ|.*ОБЛАСТИ|.*КРАЯ|.*ОКРУГА)|УПРАВЛЕНИЕ .*ПО (?:РЕСПУБЛИКЕ|.*ОБЛАСТИ|.*КРАЮ|.*ОКРУГУ)")
MUNICIPAL = re.compile(r"МУНИЦИПАЛЬН|АДМИНИСТРАЦИЯ|СЕЛЬСКОГО ПОСЕЛЕНИЯ|СОВЕТ ГОРОДСКОГО")
from . import region as R


def _num(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip("' ").str.replace(" ", "").str.replace(" ", "")
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def load(paths: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    raw = raw.rename(columns=COL)[list(COL.values())].drop_duplicates()
    for c in ["contract_id", "customer_inn", "supplier_inn", "okpd2"]:
        raw[c] = raw[c].astype(str).str.strip("' ")
    raw["date"] = pd.to_datetime(raw["date"], dayfirst=True, errors="coerce")
    raw["price"] = _num(raw["price"])
    raw["pos_sum"] = _num(raw["pos_sum"])

    contracts = (
        raw.sort_values("contract_id")
        .drop_duplicates("contract_id")
        [["contract_id", "date", "customer_inn", "customer_name", "budget_level",
          "method", "price", "supplier_inn", "supplier_name"]]
        .dropna(subset=["date", "price"])
        .reset_index(drop=True)
    )
    contracts["single_supplier"] = contracts["method"].str.contains("единствен|статьи 93", case=False, na=False)
    nm = contracts["customer_name"].fillna("").str.upper()
    # «республиканский» = государственный заказчик без привязки к конкретному городу/району;
    # флаг используется только для заказчиков, зарегистрированных в Уфе (см. config)
    contracts["republican"] = nm.str.contains(STATE) & ~nm.str.contains(MUNICIPAL) & ~nm.str.contains(R.CAPITAL_REGEX)

    positions = raw[["contract_id", "okpd2", "pos_sum"]].dropna(subset=["pos_sum"]).copy()
    positions["okpd2_2"] = positions["okpd2"].str[:2]
    # сумма позиций не всегда равна цене контракта (изменения, единичные расценки) —
    # используем позиции только для долей отраслевой структуры внутри контракта
    tot = positions.groupby("contract_id")["pos_sum"].transform("sum")
    positions["weight"] = np.where(tot > 0, positions["pos_sum"] / tot, 0.0)
    return contracts, positions
