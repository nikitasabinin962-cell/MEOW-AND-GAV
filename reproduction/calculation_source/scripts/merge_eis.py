"""Склейка выгрузок реестра контрактов ЕИС (поиск контрактов → «Выгрузить», файлы ContractSearch*.csv)
в один parquet с контролем полноты.

    python scripts/merge_eis.py <папка_с_csv> data/raw/eis_2024.parquet

Скрипт ищет CSV рекурсивно, удаляет дубли (одни и те же страницы, скачанные дважды) и
печатает число контрактов по месяцам, а также проверку страниц: по последней странице
каждого запроса (например, ContractSearch(2001-2335)) видно, сколько страниц должно быть.
"""
import glob
import math
import re
import sys
from collections import Counter

import pandas as pd

src, out = sys.argv[1], sys.argv[2]
fs = glob.glob(src + "/**/*ContractSearch*.csv", recursive=True)
df = pd.concat([pd.read_csv(f, sep=";", encoding="cp1251", dtype=str) for f in fs]).drop_duplicates()
k = df.drop_duplicates("Номер реестровой записи контракта")
print(f"файлов {len(fs)}, строк {len(df)}, контрактов {len(k)}")
print(pd.to_datetime(k["Контракт: дата"], dayfirst=True).dt.to_period("M").value_counts().sort_index().to_string())

pages = [tuple(map(int, m.groups())) for f in fs if (m := re.search(r"ContractSearch\(?(\d+)-(\d+)", f))]
ends = [b for a, b in pages if b % 500]
have = Counter(a for a, b in pages)
need = sum(math.ceil(x / 500) for x in ends)
print(f"запросов (по последним страницам): {len(ends)}; ожидается страниц ≥ {need}, есть {len(pages)}")
for s in sorted(have):
    exp = sum(1 for x in ends if x >= s)
    if have[s] < exp:
        print(f"  не хватает страниц «{s}-{s + 499}»: {exp - have[s]}")
df.to_parquet(out)
