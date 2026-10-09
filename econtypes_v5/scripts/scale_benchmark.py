"""Нагрузочная проверка математического ядра на синтетике национального размера (п. 10 «Нагрузка»).

Измеряется реально исполненное: построение блочного расстояния и self-tuning kNN-графа, спектральная
кластеризация и Leiden, ICVI (включая S_Dbw и AVU), DTW на кандидатных парах. Это НЕ запуск полного
национального конвейера на данных СберИндекса (данных нет) — только масштабирование алгоритмов.
Результат: outputs/SCALE_BENCHMARK.json
"""
import json
import os
import platform
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from econtypes5 import clustering as CL, graphs as G, icvi as I, timeseries as TS  # noqa: E402


def rss_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def run(n, p=18, K=7, T=24, seed=0):
    rng = np.random.default_rng(seed)
    centers = rng.normal(0, 3, (K, p))
    lab_true = rng.integers(0, K, n)
    X = centers[lab_true] + rng.normal(0, 1.5, (n, p))
    rec = dict(N=n, p=p, K=K)
    t = time.perf_counter()
    D = np.sqrt(G.pairwise_sq_dist(X))
    W, _ = G.self_tuning_affinity(D, 8, 7, "union")
    rec["graph_s"] = round(time.perf_counter() - t, 3)
    rec["edges"] = int(np.count_nonzero(np.triu(W, 1)))
    rec["dense_bytes"] = int(W.nbytes)
    t = time.perf_counter()
    lab, _ = CL.spectral(W, K, seed)
    rec["spectral_s"] = round(time.perf_counter() - t, 3)
    t = time.perf_counter()
    lab2 = CL.leiden(W, 1.0, seed)
    rec["leiden_s"] = round(time.perf_counter() - t, 3)
    rec["leiden_k"] = int(len(np.unique(lab2)))
    t = time.perf_counter()
    r = I.all_indices(X, W, lab)
    rec["icvi_s"] = round(time.perf_counter() - t, 3)
    rec["AVU"] = round(r["AVU"], 4)
    rec["S_Dbw_status"] = r["_status"]["S_Dbw"]
    # DTW: время на пару и оценка all-pairs против кандидатных пар (kNN по корреляции)
    Y = pd.DataFrame(np.exp(rng.normal(10, 0.1, (min(n, 200), T)) + np.linspace(0, 0.2, T)))
    R, _ = TS.residual_series(Y)
    t = time.perf_counter()
    TS.dtw_similarity(R, 2)
    m = len(Y)
    per_pair = (time.perf_counter() - t) / (m * (m - 1) / 2)
    rec["dtw_per_pair_ms"] = round(per_pair * 1000, 4)
    rec["dtw_all_pairs_est_s"] = round(per_pair * n * (n - 1) / 2, 1)
    rec["dtw_knn_candidates_est_s"] = round(per_pair * n * 30, 1)
    rec["peak_rss_mib"] = round(rss_mib(), 1)
    return rec


if __name__ == "__main__":
    out = []
    for n in [63, 500, 2016]:
        r = run(n)
        print(r, flush=True)
        out.append(r)
    res = dict(host=dict(cpus=os.cpu_count(), platform=platform.platform(), python=platform.python_version()),
               note="Синтетика; измерено ядро алгоритмов. Полный национальный конвейер не запускался (нет входов СберИндекса по всем МО).",
               runs=out)
    p = Path(__file__).resolve().parents[1] / "outputs" / "SCALE_BENCHMARK.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=1))
