#!/usr/bin/env python3
"""Производная геометрия для карты (не меняет D).

    python3 tools/derive_geo.py src/data/D.json src/data/geo-derived.json

Требует shapely>=2. Результат коммитится, поэтому обычной сборке shapely не нужен.
Что считается:
  outline  — внешняя граница объединения всех 63 МО (контур региона);
  seams    — внутренние границы: каждый отрезок колец один раз (дубликаты общих
             стыков удалены), без отрезков, лежащих на внешнем контуре; склеены в полилинии;
  gaps     — щели в объединении (участки внутри контура, не покрытые ни одним МО);
  overlaps — пары соседей с пересечением площадью > 0.001 км².
D.geo не изменяется: исходные кольца и координаты используются только для чтения.
"""
import json, math, sys, collections
from shapely.geometry import shape, Polygon, LineString, mapping
from shapely.ops import unary_union

KM2 = 111.32 * 111.32 * math.cos(math.radians(54.5))
src, dst = sys.argv[1], sys.argv[2]
D = json.load(open(src, encoding='utf-8'))
F = D['geo']['features']; N = D['nodes']
geoms = {f['properties']['i']: shape(f['geometry']) for f in F}
U = unary_union(list(geoms.values()))
assert U.geom_type == 'Polygon', U.geom_type
ext = LineString(U.exterior.coords)
r6 = lambda c: (round(c[0], 6), round(c[1], 6))

segs = collections.OrderedDict()
for f in F:
    polys = f['geometry']['coordinates'] if f['geometry']['type'] == 'MultiPolygon' else [f['geometry']['coordinates']]
    for p in polys:
        for ring in p:
            for k in range(len(ring) - 1):
                a, b = r6(ring[k]), r6(ring[k + 1])
                if a == b: continue
                key = (a, b) if a < b else (b, a)
                segs.setdefault(key, 0); segs[key] += 1
inner = []
for (a, b), cnt in segs.items():
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if cnt == 1 and ext.distance(LineString([a, b]).interpolate(0.5, normalized=True)) < 1e-9:
        continue                        # отрезок внешнего контура
    inner.append((a, b))
# склейка отрезков в полилинии по вершинам степени 2
adj = collections.defaultdict(list)
for k, (a, b) in enumerate(inner):
    adj[a].append(k); adj[b].append(k)
used = [False] * len(inner); lines = []
def walk(start, k):
    path = [start]; cur = start
    while True:
        used[k] = True
        a, b = inner[k]; nxt = b if a == cur else a
        path.append(nxt); cur = nxt
        cand = [j for j in adj[cur] if not used[j]]
        if len(adj[cur]) != 2 or not cand: return path
        k = cand[0]
for v in adj:
    if len(adj[v]) != 2:
        for k in adj[v]:
            if not used[k]: lines.append(walk(v, k))
for k in range(len(inner)):
    if not used[k]: lines.append(walk(inner[k][0], k))

gaps = []
for h in U.interiors:
    hp = Polygon(h); c = hp.representative_point()
    near = sorted((geoms[j].distance(c), j) for j in geoms)[:2]
    gaps.append({'km2': round(hp.area * KM2, 4), 'near': [j for _, j in near], 'ring': [list(r6(x)) for x in h.coords]})
ov = []
ids = sorted(geoms)
for x in range(len(ids)):
    for y in range(x + 1, len(ids)):
        a, b = geoms[ids[x]], geoms[ids[y]]
        if a.intersects(b):
            km2 = a.intersection(b).area * KM2
            if km2 > 0.001: ov.append({'a': ids[x], 'b': ids[y], 'km2': round(km2, 3)})
holes = []
for i, g in geoms.items():
    for p in (g.geoms if g.geom_type == 'MultiPolygon' else [g]):
        for h in p.interiors:
            hp = Polygon(h)
            cov = sum(hp.intersection(geoms[j]).area for j in geoms if j != i) / hp.area
            holes.append({'mo': i, 'km2': round(hp.area * KM2, 2), 'covered': round(cov, 4)})
seg_mult = collections.Counter(segs.values())
out = {
  'about': 'Производная геометрия из D.geo (tools/derive_geo.py, shapely). D не изменён.',
  'outline': [[list(r6(c)) for c in U.exterior.coords]],
  'seams': [[list(c) for c in l] for l in lines],
  'gaps': sorted(gaps, key=lambda g: -g['km2']),
  'overlaps': sorted(ov, key=lambda o: -o['km2']),
  'holes': holes,
  'stats': {'features': len(F), 'polygon': sum(f['geometry']['type'] == 'Polygon' for f in F),
            'multipolygon': sum(f['geometry']['type'] == 'MultiPolygon' for f in F),
            'inner_rings': sum(len(h) for h in [[1 for _ in []]]) + len(holes),
            'segments_shared_twice': seg_mult.get(2, 0), 'segments_single': seg_mult.get(1, 0),
            'gaps': len(gaps), 'gaps_km2': round(sum(g['km2'] for g in gaps), 2),
            'overlaps': len(ov), 'overlaps_km2': round(sum(o['km2'] for o in ov), 2),
            'region_km2': round(U.area * KM2, 0)}
}
json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(out['stats'], ensure_ascii=False), 'seams', len(lines), 'pts', sum(len(l) for l in lines))
