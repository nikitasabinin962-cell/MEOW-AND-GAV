"""Стресс-тесты данных (п. 10 задания): кодировки, BOM, пустые/повреждённые файлы, деньги, валюты,
ОКТМО, дубли/конфликты, идентичность между системами, YTD, ИНН, топонимы, HTTP-пагинация с ошибками."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pandas as pd
import pytest

from econtypes5 import geography as GE
from econtypes5 import ingest as ING
from econtypes5 import io_robust as IO


# ---------- файлы ----------
@pytest.mark.parametrize("enc,bom", [("utf-8", False), ("utf-8", True), ("cp1251", False)])
def test_csv_encodings(tmp_path, enc, bom):
    txt = "инн;сумма;валюта\n0201002110;1 234,56;RUB\n"
    raw = txt.encode(enc)
    if bom:
        raw = b"\xef\xbb\xbf" + raw
    p = tmp_path / "a.csv"
    p.write_bytes(raw)
    df, rep = IO.read_csv_robust(p)
    assert list(df.columns) == ["инн", "сумма", "валюта"] and df.iloc[0]["инн"] == "0201002110"
    assert rep["bom"] == bom and rep["sep"] == ";"


def test_empty_and_corrupted_files(tmp_path):
    e = tmp_path / "empty.csv"
    e.write_bytes(b"")
    df, rep = IO.read_csv_robust(e)
    assert rep["status"] == "empty_file" and df.empty
    c = tmp_path / "bad.csv"
    c.write_text("a,b\n1,2\n3,4,5,6\n7,8\n")
    df, rep = IO.read_csv_robust(c)
    assert rep["bad_lines"] == 1 and len(df) == 2
    u = tmp_path / "bin.csv"
    u.write_bytes(b"\xff\xfe\x00\x81\x8d\x9d" * 10)
    df, rep = IO.read_csv_robust(u)
    assert rep["status"] in ("undecodable", "ok", "ok_with_bad_lines")


def test_mirrored_files_same_hash(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("x;y\n1;2\n")
    b.write_bytes(a.read_bytes())
    assert IO.read_csv_robust(a)[1]["sha256"] == IO.read_csv_robust(b)[1]["sha256"]  # зеркало распознаётся по хешу


# ---------- деньги, валюты ----------
@pytest.mark.parametrize("s,k", [("1 234,56", 123456), ("1234.56", 123456), ("0,005", 1), ("1,234.50", 123450), (1234.5, 123450), ("-5,00", -500)])
def test_money_kopecks(s, k):
    assert IO.parse_money_kopecks(s)[0] == k


def test_money_invalid_and_currency_not_mixed():
    assert IO.parse_money_kopecks("abc") == (None, "invalid")
    assert IO.parse_money_kopecks("") == (None, "missing")
    s = IO.sum_by_currency([100, 200, 300, None], ["RUB", "USD", "RUB", "EUR"])
    assert s == {"RUB": 400, "USD": 200}
    assert ING.rub_to_kopecks("58000.00") == 5800000


def test_oktmo_leading_zeros():
    assert IO.normalize_oktmo("1234567") == ("01234567", "ok_8")
    assert IO.normalize_oktmo(80701000001) == ("80701000001", "ok_11")
    assert IO.normalize_oktmo("8070100000.0") == ("08070100000", "ok_11")
    assert IO.normalize_oktmo("80A") == (None, "invalid")


# ---------- дубли, конфликты, идентичность ----------
def test_duplicate_ids_and_price_conflict():
    df = pd.DataFrame([dict(id="1", sum=10), dict(id="1", sum=10), dict(id="2", sum=5), dict(id="2", sum=7), dict(id="3", sum=1)])
    u, c, s = IO.split_duplicates(df, ["id"])
    assert s == dict(rows=5, exact_duplicates=1, conflict_keys=1, conflict_rows=2, unique=2)
    assert set(u.id) == {"1", "3"} and set(c["sum"]) == {5, 7}


def test_same_number_different_systems_not_merged():
    assert IO.identity_key("EIS", "0301300000123000001") != IO.identity_key("ATMO", "0301300000123000001")
    with pytest.raises(ValueError):
        IO.identity_key("", "1")


def test_full_year_vs_ytd():
    full = pd.Series(pd.date_range("2024-01-01", "2024-12-31", freq="MS"))
    ytd = pd.Series(pd.date_range("2026-01-01", "2026-09-30", freq="MS"))
    assert IO.period_coverage(full, 2024)["kind"] == "full_year"
    assert IO.period_coverage(ytd, 2026)["kind"] == "ytd"


# ---------- ИНН ----------
@pytest.mark.parametrize("inn,ok", [("0201002110", True), ("0201002111", False), ("020100005573", True), ("02010000557", False), (None, False), ("abc", False)])
def test_inn_checksum(inn, ok):
    assert ING.inn_valid(inn) == ok


def test_okved_sections():
    assert ING.okved_section("47.91") == "G" and ING.okved_section("01.11") == "A" and ING.okved_section("") is None


# ---------- топонимы ----------
MOS = ["ГО Уфа", "ГО Октябрьский", "ГО Салават", "ГО Сибай", "ГО Межгорье", "ГО Стерлитамак", "МР Салаватский",
       "МР Уфимский", "МР Баймакский", "МР Стерлитамакский", "МР Абзелиловский"]


@pytest.mark.parametrize("name,mo", [
    ("Администрация ГО г. Октябрьский РБ", "ГО Октябрьский"), ("СОШ № 3 г. Октябрьского", "ГО Октябрьский"),
    ("Детсад г.Салавата", "ГО Салават"), ("Салаватский район, Администрация", "МР Салаватский"),
    ("школа г.Уфы", "ГО Уфа"), ("Уфимский Район", "МР Уфимский"), ("СОШ с. Старый Сибай", None),
    ('"Управление" зато Межгорье', "ГО Межгорье"), ("Стерлитамакского района", "МР Стерлитамакский"),
    ("Администрация Сельского Поселения Гусевский Сельсовет Муниципального Района Абзелиловский Район", "МР Абзелиловский"),
])
def test_toponyms(name, mo):
    pats = GE.build_patterns(MOS)
    assert GE.name_evidence(name, pats)[0] == mo


def test_tax_office_loo():
    df = pd.DataFrame(dict(code=["0201"] * 6 + ["0202"] * 6, mo=["A"] * 6 + ["B"] * 5 + ["A"]))
    r = GE.loo_accuracy(df, "code", min_n=3, min_purity=0.8)
    assert r["evaluated"] == 12 and r["correct"] == 11 and r["accuracy"] < 1


# ---------- HTTP: backoff, Retry-After, HTML, повтор страницы, возобновление ----------
class _Srv(BaseHTTPRequestHandler):
    script: dict = {}
    calls: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.calls.append(self.path)
        step = self.script.get(self.path, [])
        n = sum(1 for c in self.calls if c == self.path)
        code, ctype, body, headers = step[min(n, len(step)) - 1] if step else (404, "text/plain", b"nf", {})
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def server():
    _Srv.calls = []
    srv = HTTPServer(("127.0.0.1", 0), _Srv)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()


def page(items):
    return (200, "application/json", json.dumps(dict(items=items)).encode(), {})


def test_retry_after_and_backoff(server):
    _Srv.script = {"/p1": [(429, "text/plain", b"slow", {"Retry-After": "2"}), (503, "text/plain", b"x", {}), page([1, 2])]}
    waits = []
    f = IO.Fetcher(sleep=waits.append, base_delay=0.5)
    data, h = f.get_json(f"http://127.0.0.1:{server.server_port}/p1")
    assert data["items"] == [1, 2] and waits[0] == 2.0 and len(waits) == 2
    assert [x["status"] for x in f.log] == [429, 503]


def test_html_instead_of_json_rejected(server):
    _Srv.script = {"/h": [(200, "text/html", b"<!DOCTYPE html><html>oops</html>", {})]}
    with pytest.raises(IO.FetchError, match="not JSON"):
        IO.Fetcher(sleep=lambda s: None).get_json(f"http://127.0.0.1:{server.server_port}/h")


def test_truncated_json_and_captcha(server):
    _Srv.script = {"/t": [(200, "application/json", b'{"items": [1, 2', {})],
                   "/c": [(200, "application/json", b'{"captcha": "solve me"}', {})]}
    f = IO.Fetcher(sleep=lambda s: None)
    with pytest.raises(IO.FetchError, match="truncated"):
        f.get_json(f"http://127.0.0.1:{server.server_port}/t")
    with pytest.raises(IO.FetchError, match="captcha"):
        f.get_json(f"http://127.0.0.1:{server.server_port}/c")


def test_exhausted_retries(server):
    _Srv.script = {"/e": [(500, "text/plain", b"x", {})] * 10}
    with pytest.raises(IO.FetchError):
        IO.Fetcher(sleep=lambda s: None, max_attempts=3).get_json(f"http://127.0.0.1:{server.server_port}/e")


def test_pagination_repeated_page_detected(server, tmp_path):
    _Srv.script = {"/page/1": [page([1, 2])], "/page/2": [page([1, 2])]}
    f = IO.Fetcher(sleep=lambda s: None)
    with pytest.raises(IO.FetchError, match="repeats"):
        IO.paginate(f, lambda p: f"http://127.0.0.1:{server.server_port}/page/{p}", tmp_path / "s.json")


def test_pagination_resume_after_break(server, tmp_path):
    base = f"http://127.0.0.1:{server.server_port}"
    _Srv.script = {"/page/1": [page([1, 2])], "/page/2": [(500, "text/plain", b"x", {})] * 3 + [page([3])],
                   "/page/3": [page([])]}
    st = tmp_path / "state.json"
    f = IO.Fetcher(sleep=lambda s: None, max_attempts=2)
    with pytest.raises(IO.FetchError):
        IO.paginate(f, lambda p: f"{base}/page/{p}", st)          # обрыв на странице 2
    assert list(json.loads(st.read_text())["pages"]) == ["1"]      # контрольная точка сохранена
    f2 = IO.Fetcher(sleep=lambda s: None, max_attempts=5)
    r = IO.paginate(f2, lambda p: f"{base}/page/{p}", st)          # продолжение со страницы 2
    assert r["done"] and r["records"] == 3 and sorted(r["pages"]) == ["1", "2", "3"]
    assert _Srv.calls.count("/page/1") == 1                        # страница 1 не перезагружалась
