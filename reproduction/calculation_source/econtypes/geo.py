"""Границы муниципальных образований для карт.

Источник: geoBoundaries (gbOpen, лицензия ODbL/CC BY, данные OpenStreetMap) — уровни ADM1 (регионы)
и ADM2 (районы и городские округа). Скрипт сам выбирает МО нужного региона (точка внутри границы
субъекта), сопоставляет их с названиями из справочника МО (транслитерация + нечёткое сравнение)
и сохраняет компактный GeoJSON с полем `mo`.

    econtypes geo            # скачать (если нет) и подготовить data/geo/<region>.geojson

Для другого региона достаточно поменять `geo.adm1_name` в config.yaml.
"""
from __future__ import annotations

import difflib
import json
import re
import urllib.request
from pathlib import Path

GB = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/RUS/{lvl}/geoBoundaries-RUS-{lvl}_simplified.geojson"

TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
               "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"]))


def translit(s: str) -> str:
    return "".join(TR.get(ch, ch) for ch in s.lower())


def _key(s: str) -> str:
    """Нормализованный ключ: без типа МО, латиницей, без гласных-окончаний."""
    s = s.lower()
    s = re.sub(r"городской округ|город|муниципальный район|district|rayon|zato|зато|^го |^мр ", " ", s)
    s = re.sub(r"(ский|ской|sky|skiy|ski|sk)\b", "", s)
    s = translit(s.strip())
    s = s.replace("yo", "e").replace("ye", "e").replace("iy", "i").replace("y", "i")
    return re.sub(r"[^a-z]", "", s)


def _fetch(path: Path, lvl: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(GB.format(lvl=lvl), path)


def build(cfg: dict, mo_list: list[str]) -> Path:
    from shapely.geometry import mapping, shape

    g = cfg.get("geo", {})
    d = Path(g.get("dir", "data/geo"))
    a1p, a2p = d / "gb_rus_adm1.geojson", d / "gb_rus_adm2.geojson"
    _fetch(a1p, "ADM1"), _fetch(a2p, "ADM2")
    name = g.get("adm1_name", "Bashkortostan")
    a1 = json.load(open(a1p))
    reg = [f for f in a1["features"] if name.lower() in f["properties"]["shapeName"].lower()]
    if not reg:
        raise ValueError(f"регион {name!r} не найден в geoBoundaries ADM1")
    R = shape(reg[0]["geometry"]).buffer(0.02)
    feats = [f for f in json.load(open(a2p))["features"]
             if R.contains(shape(f["geometry"]).representative_point())]
    keys = {m: _key(m) for m in mo_list}
    tol = float(g.get("simplify", 0.004))
    out, used = [], set()
    for f in feats:
        src = f["properties"]["shapeName"]
        k = _key(src)
        typ = "МР" if re.search(r"district|rayon|район", src, re.I) else "ГО"   # район ↔ одноимённый город
        cand = [m for m in keys if m not in used and m.startswith(typ)] or [m for m in keys if m not in used]
        best = max(cand, key=lambda m: difflib.SequenceMatcher(None, k, keys[m]).ratio())
        score = difflib.SequenceMatcher(None, k, keys[best]).ratio()
        if score < 0.6:
            print("не сопоставлено:", f["properties"]["shapeName"])
            continue
        used.add(best)
        geom = shape(f["geometry"]).simplify(tol, preserve_topology=True)
        gj = json.loads(json.dumps(mapping(geom)), parse_float=lambda x: round(float(x), 4))
        c = geom.representative_point()
        out.append({"type": "Feature", "properties": {"mo": best, "src": f["properties"]["shapeName"],
                                                      "lon": round(c.x, 4), "lat": round(c.y, 4)}, "geometry": gj})
    miss = sorted(set(mo_list) - used)
    if miss:
        print("МО без границ:", miss)
    p = d / f"{_key(name)}_mo.geojson"
    json.dump({"type": "FeatureCollection", "features": out}, open(p, "w"), ensure_ascii=False, separators=(",", ":"))
    return p


def load(cfg: dict) -> dict | None:
    g = cfg.get("geo", {})
    p = Path(g.get("dir", "data/geo")) / f"{_key(g.get('adm1_name', 'Bashkortostan'))}_mo.geojson"
    return json.load(open(p)) if p.exists() else None
