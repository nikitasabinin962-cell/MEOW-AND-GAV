"""Модульные тесты: справочник МО, сети, ICVI, база данных, FDR, сопоставление границ."""
import numpy as np
import pandas as pd
import pytest

from econtypes import correlations, db, geo, icvi, networks
from econtypes.mo_directory import mo_key


def test_mo_key():
    assert mo_key("Муниципальный район Белебеевский район") == "МР Белебеевский"
    assert mo_key("Городской округ город Уфа") == "ГО Уфа"
    assert mo_key("Фёдоровский район") == "МР Федоровский"


def test_knn_sparsify_symmetric():
    rng = np.random.default_rng(0)
    S = rng.random((20, 20)); S = (S + S.T) / 2
    K = networks.knn_sparsify(S, 3)
    assert np.allclose(K, K.T)
    assert (np.diag(K) == 0).all()
    assert ((K > 0).sum(1) >= 3).all()


def _blobs(seed=0):
    rng = np.random.default_rng(seed)
    X = np.vstack([rng.normal(c, .3, (15, 2)) for c in ([0, 0], [4, 0], [0, 4])])
    y = np.repeat([0, 1, 2], 15)
    W = networks.knn_sparsify(networks.attr_similarity(X), 5)
    return X, W, y


def test_icvi_prefers_true_partition():
    X, W, y = _blobs()
    true = icvi.all_indices(X, W, y)
    rnd = icvi.all_indices(X, W, np.random.default_rng(1).permutation(y))
    assert true["SW"] > rnd["SW"] and true["CH"] > rnd["CH"] and true["MQ"] > rnd["MQ"]
    assert true["DB"] < rnd["DB"]


def test_baseline_normalized_positive():
    X, W, y = _blobs()
    z = icvi.baseline_normalized(X, W, y, n_perm=10)
    assert all(v > 1 for k, v in z.items() if np.isfinite(v))   # все индексы лучше случайных меток


def test_bh_monotone():
    p = np.array([.001, .01, .02, .04, .5])
    q = correlations.bh(p)
    assert (q >= p).all() and (np.diff(q[np.argsort(p)]) >= 0).all() and q.max() <= 1


def test_db_roundtrip(tmp_path):
    eng = db.engine(f"sqlite:///{tmp_path}/t.db")
    df = pd.DataFrame({"mo": ["ГО Уфа", "МР Иглинский"], "period": pd.PeriodIndex(["2024Q1", "2024Q2"], freq="Q"), "v": [1.5, 2.0]})
    db.write(eng, "res_test", df)
    back = db.read(eng, "res_test")
    assert back.period.tolist() == ["2024Q1", "2024Q2"] and back.v.sum() == pytest.approx(3.5)
    assert "res_test" in db.tables(eng)


@pytest.mark.parametrize("src,mo", [("Salavatsky District", "МР Салаватский"), ("Fyodorovsky District", "МР Федоровский"),
                                    ("Yermekeyevsky District", "МР Ермекеевский"), ("городской округ Стерлитама", "ГО Стерлитамак")])
def test_geo_keys(src, mo):
    import difflib
    assert difflib.SequenceMatcher(None, geo._key(src), geo._key(mo)).ratio() > .8
