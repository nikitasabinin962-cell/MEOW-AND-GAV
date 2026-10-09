"""Перенос на другой регион: региональные настройки берутся только из конфига."""
import importlib

import numpy as np
import pandas as pd

from econtypes import region as R


def _reset():
    importlib.reload(R)


def test_configure_other_region():
    try:
        R.configure({"region": {"name": "Республика Татарстан", "inn_code": "16", "capital": "ГО Казань",
                                "capital_inn_prefixes": ["1655", "1656"], "capital_name_regex": "КАЗАН",
                                "manual_inn_prefixes": {}, "enclaves": {},
                                "orient_anchors": {"ГО Казань": [55.79, 49.12], "ГО Набережные Челны": [55.74, 52.40]}}})
        assert R.INN_CODE == "16" and R.CAPITAL == "ГО Казань" and R.ENCLAVES == {}
        assert abs(R.MID_LAT - 55.765) < 1e-6
        from econtypes.mo_directory import build_prefix_map
        cust = pd.DataFrame({"inn": ["1655000001", "1644000002", "1644000003", "0274000004"],
                             "name": ["МКУ г. Казани", "АДМИНИСТРАЦИЯ АЛЬМЕТЬЕВСКОГО МУНИЦИПАЛЬНОГО РАЙОНА",
                                      "МБОУ СОШ АЛЬМЕТЬЕВСКОГО РАЙОНА", "чужой регион"]})
        pm = build_prefix_map(cust, ["ГО Казань", "МР Альметьевский"]).set_index("prefix")["mo"]
        assert pm["1655"] == "ГО Казань"
        assert "0274" not in pm.index            # заказчики других субъектов отсеиваются по коду ИНН
        from econtypes.labels import label
        assert "Казань" in label("proc_ufa_sh")
    finally:
        _reset()


def test_auto_cluster_names_without_anchors():
    from econtypes.pipeline import name_clusters
    nodes = [f"МР {i}" for i in range(6)]
    tab = pd.DataFrame({"urban_share": [.9, .8, .85, .1, .2, .15], "birth_rate": [9, 8, 9, 13, 12, 14]}, index=nodes)
    names = name_clusters(np.array([0, 0, 0, 1, 1, 1]), nodes, {}, tab)
    assert names[0].startswith("Тип 1:") and "выше доля горожан" in names[0]
    assert names[1].startswith("Тип 2:")
