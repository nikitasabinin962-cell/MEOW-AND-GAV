#!/usr/bin/env python3
"""Сборка автономного econtypes.html из исходников.

    python3 build.py                     # → econtypes.html
    python3 build.py --out dist/x.html   # другой выходной файл (параллельная работа)
    python3 build.py --check             # + сводка состава данных

Что встраивается (без внешних запросов при обычном просмотре):
  src/template.html              разметка семи вкладок
  src/css/*.css                  стили по вкладкам (порядок по имени файла)
  src/fonts/*.woff2              Golos Text, JetBrains Mono (OFL) → @font-face data:
  src/vendor/*.js                Leaflet 1.9.4 (2D-резерв), D3 7.9.0, ECharts 6.1.0, deck.gl 9.4.0
  src/js/*.js                    модули приложения (порядок по имени файла)
  src/data/D.json                блок данных D — байт в байт
  src/data/geo-derived.json      производная геометрия (контур, швы, дефекты) — отдельно от D

После записи блок D извлекается из готового файла и сверяется по SHA-1 с эталоном.
"""
import base64
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / 'src'
D_SHA1_EXPECTED = 'd849169e16d7d2c42c1f210426b1490b6832b76a'
VENDOR = ['leaflet-1.9.4.js', 'd3-7.9.0.min.js', 'echarts-6.1.0.min.js', 'deck.gl-9.4.0.min.js']
FONTS = [('Golos Text', 'golos-text', [400, 500, 600, 700]), ('JetBrains Mono', 'jetbrains-mono', [400, 500])]
RANGES = {'cyrillic': 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116',
          'latin': 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD'}


def sha1(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def fonts_css() -> str:
    out = []
    for fam, stem, weights in FONTS:
        for w in weights:
            for sub in ('cyrillic', 'latin'):
                b = (SRC / 'fonts' / f'{stem}-{sub}-{w}-normal.woff2').read_bytes()
                out.append("@font-face{font-family:'%s';font-style:normal;font-weight:%d;font-display:swap;"
                           "src:url(data:font/woff2;base64,%s) format('woff2');unicode-range:%s}"
                           % (fam, w, base64.b64encode(b).decode(), RANGES[sub]))
    return '\n'.join(out)


def main() -> int:
    out = ROOT / 'econtypes.html'
    if '--out' in sys.argv:
        out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1]).resolve()
    d_bytes = (SRC / 'data' / 'D.json').read_bytes()
    d_text = d_bytes.decode('utf-8')
    json.loads(d_text)
    if sha1(d_bytes) != D_SHA1_EXPECTED:
        print(f'ОШИБКА: SHA-1 исходного D {sha1(d_bytes)} != {D_SHA1_EXPECTED}', file=sys.stderr)
        return 1
    geo_text = (SRC / 'data' / 'geo-derived.json').read_text('utf-8')
    json.loads(geo_text)

    tpl = (SRC / 'template.html').read_text('utf-8')
    css = '\n'.join(p.read_text('utf-8') for p in sorted((SRC / 'css').glob('*.css')))
    js = '\n;\n'.join(f'/* ---- {p.name} ---- */\n' + p.read_text('utf-8') for p in sorted((SRC / 'js').glob('*.js')))
    js = js.replace('__D_SHA1__', D_SHA1_EXPECTED)
    import datetime
    js = js.replace('__BUILD_TIME__', datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5))).strftime('%d.%m.%Y %H:%M (Екатеринбург, UTC+5)'))
    vendor = '\n'.join(f'<script>/* {name} */\n' + (SRC / 'vendor' / name).read_text('utf-8') + '\n</script>' for name in VENDOR)
    parts = {
        '/*__FONTS__*/': fonts_css(),
        '/*__LEAFLET_CSS__*/': (SRC / 'vendor' / 'leaflet-1.9.4.css').read_text('utf-8'),
        '/*__APP_CSS__*/': css,
        '<!--__VENDOR_JS__-->': vendor,
        '/*__APP_JS__*/': js,
        '__GEO__': geo_text,
    }
    html = tpl
    for k, v in parts.items():
        assert html.count(k) == 1, k
        html = html.replace(k, v)
    assert html.count('__D__') == 1
    html = html.replace('__D__', d_text)          # D вставляется последним
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, 'utf-8')

    built = out.read_text('utf-8')
    i = built.index('const D = ') + len('const D = ')
    _, end = json.JSONDecoder().raw_decode(built, i)
    got = sha1(built[i:end].encode('utf-8'))
    print(f'{out.name}: {out.stat().st_size:,} байт; D SHA-1 {got}')
    if got != D_SHA1_EXPECTED:
        print('ОШИБКА: блок D в готовом файле изменён', file=sys.stderr)
        return 1
    if '--check' in sys.argv:
        D = json.loads(d_text)
        print(f"МО {len(D['nodes'])}, типов {len(D['types'])}, индексов {len(D['metrics'])}, признаков {len(D['feats'])}, "
              f"слоёв {len(D['layers'])} ({', '.join(f'{k} {len(v)}' for k, v in D['layers'].items())}), "
              f"переменных корреляции {len(D['corr']['vars'])}, фактов {len(D['findings'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
