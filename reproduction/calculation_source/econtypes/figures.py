"""Статические рисунки для отчёта и README (outputs/figures/*.png).
Запуск после run_pipeline.py:  python make_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from matplotlib.colors import LinearSegmentedColormap

def make(cfg: dict) -> None:
    out = Path(cfg["paths"]["outputs"]); fig_dir = out / "figures"; fig_dir.mkdir(parents=True, exist_ok=True)
    T = out / "tables"
    R = json.load(open(out / "results.json"))

    # палитра: категориальные слоты (проверены валидатором CVD), чернила, сетка
    SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
    INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
    SEQ = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#6da7ec", "#256abf", "#0d366b"])
    DIV = LinearSegmentedColormap.from_list("div", ["#256abf", "#9ec5f4", "#f0efec", "#f4a59d", "#c4302f"])
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF, "axes.facecolor": SURF,
                         "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 180})

    names = {int(k): v for k, v in R["names"].items()}
    order = sorted(names, key=lambda c: -sum(n["cluster"] == c for n in R["nodes"]))
    color = {c: SLOTS[i] for i, c in enumerate(sorted(names))}
    nodes = pd.DataFrame(R["nodes"]).set_index("mo")
    # только для отображения: раздвигаем совпадающие центры (Уфа и Уфимский р-н и т.п.)
    _xy = nodes[["x", "y"]].values.copy() + np.random.default_rng(0).normal(0, 1e-3, (len(nodes), 2))
    for _ in range(200):
        d = _xy[:, None, :] - _xy[None, :, :]
        r = np.sqrt((d ** 2).sum(-1)) + np.eye(len(_xy)) + 1e-9
        push = np.clip(0.16 - r, 0, None)[..., None] * d / r[..., None]
        _xy += 0.25 * push.sum(1)
    nodes["x"], nodes["y"] = _xy[:, 0], _xy[:, 1]
    short = lambda m: m.replace("МР ", "").replace("ГО ", "г. ").replace("ский", "ск.").replace("цкий", "цк.")


    def road_map(ax, edges=True, flows=False, title=""):
        if edges:
            for e in R["edges"]:
                a, b = nodes.loc[e["s"]], nodes.loc[e["t"]]
                same = a.cluster == b.cluster
                ax.plot([a.x, b.x], [a.y, b.y], color=color[a.cluster] if same else GRID,
                        alpha=0.35 if same else 0.5, lw=(0.5 + 1.8 * e["w"]), zorder=1)
        if flows:
            fl = pd.DataFrame(R["flows"]).head(60)
            mx = fl.rub.max()
            for f in fl.itertuples():
                a, b = nodes.loc[f.s], nodes.loc[f.t]
                ax.annotate("", xy=(b.x, b.y), xytext=(a.x, a.y),
                            arrowprops=dict(arrowstyle="-|>", color="#256abf", alpha=0.55, lw=0.4 + 3 * np.sqrt(f.rub / mx),
                                            shrinkA=4, shrinkB=4, connectionstyle="arc3,rad=0.15"), zorder=2)
        s = 18 + 260 * np.sqrt(nodes["pop"] / nodes["pop"].max())
        ax.scatter(nodes.x, nodes.y, s=s, c=[color[c] for c in nodes.cluster], edgecolors=SURF, linewidths=1.2, zorder=3)
        for m, r in nodes.iterrows():
            ax.text(r.x, r.y - 0.075, short(m), fontsize=5.6, ha="center", va="top", color=INK2, zorder=4)
            ax.text(r.x, r.y, str(r.cluster + 1), fontsize=5.5, ha="center", va="center", color="white", weight="bold", zorder=5)
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(title, loc="left", fontsize=11, color=INK)


    # 1. Карта типов по дорожным расстояниям
    fig, ax = plt.subplots(figsize=(12, 8.2))
    road_map(ax, edges=True, title="Экономические типы МО Башкортостана, 2023–2024")
    h = [plt.Line2D([], [], marker="o", ls="", color=color[c], ms=8, label=f"{c + 1}. {names[c]}") for c in sorted(names)]
    ax.legend(handles=h, loc="upper left", fontsize=7.5, frameon=False, bbox_to_anchor=(1.0, 1.0))
    ax.text(1.0, 0.02, "Раскладка: многомерное шкалирование автодорожных расстояний СберИндекса (север сверху).\n"
            "Линии — сильнейшие связи совмещённой сети\n(цветные — внутри типа); размер круга — население.",
            transform=ax.transAxes, fontsize=6.5, color=MUTED, ha="left")
    fig.savefig(fig_dir / "01_map_clusters.png", bbox_inches="tight"); plt.close(fig)

    # 2. Потоки госзаказа
    fig, ax = plt.subplots(figsize=(9, 8.2))
    road_map(ax, edges=False, flows=True, title="Потоки госзаказа между МО: поставщик → заказчик (60 крупнейших)")
    fig.savefig(fig_dir / "02_map_flows.png", bbox_inches="tight"); plt.close(fig)

    # 3. Профили кластеров (z-оценки признаков)
    feat_lbl = {"spend_total": "Безнал. траты на жителя", "sh_Продовольствие": "Доля трат: продукты", "sh_Общественное питание": "Доля трат: общепит",
                "sh_Маркетплейсы": "Доля трат: маркетплейсы", "sh_Транспорт": "Доля трат: транспорт", "sh_Здоровье": "Доля трат: здоровье",
                "proc_pc": "Госзаказ на жителя", "proc_local_sh": "Госзаказ: местные поставщики", "proc_ufa_sh": "Госзаказ: поставщики из Уфы",
                "proc_out_sh": "Госзаказ: другие регионы", "proc_single_sh": "Госзаказ: ед. поставщик", "supply_out_pc": "Поставки в другие МО на жителя",
                "okpd_construction_sh": "ОКПД2: строительство", "okpd_fuel_transport_sh": "ОКПД2: топливо, транспорт", "okpd_health_sh": "ОКПД2: медицина",
                "urban_share": "Доля горожан", "market_access": "Доступность рынков", "birth_rate": "Рождаемость", "death_rate": "Смертность",
                "migr_rate": "Миграционный прирост", "grants_pc": "Дотации на жителя",
                "wage": "Средняя зарплата", "emp_per_1000": "Работники на 1000 жителей", "emp_sh_industry": "Занятые: промышленность и стройка",
                "emp_sh_budget": "Занятые: бюджетный сектор", "emp_sh_agri": "Занятые: сельское хозяйство", "log_density": "Плотность населения"}
    f = pd.read_csv(T / "features_raw_2023_2024.csv", index_col=0)
    cl = pd.read_csv(T / "clusters_final.csv").set_index("mo")["cluster"]
    z = (f[list(feat_lbl)] - f[list(feat_lbl)].mean()) / f[list(feat_lbl)].std()
    Z = z.groupby(cl).mean().T.clip(-2, 2)
    fig, ax = plt.subplots(figsize=(9, 9.2))
    im = ax.imshow(Z.values, cmap=DIV, vmin=-1.6, vmax=1.6, aspect="auto")
    ax.set_yticks(range(len(Z)), [feat_lbl[i] for i in Z.index], fontsize=8)
    ax.set_xticks(range(Z.shape[1]), [f"{c + 1}. {names[c]}" for c in Z.columns], rotation=30, ha="right", fontsize=7.5)
    for i in range(Z.shape[0]):
        for j in range(Z.shape[1]):
            v = Z.values[i, j]
            ax.text(j, i, f"{v:+.1f}", ha="center", va="center", fontsize=6.5, color="white" if abs(v) > 1 else INK)
    ax.spines[:].set_visible(False); ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, shrink=0.5); cb.set_label("отклонение от среднего по МО, ст. откл.", color=INK2)
    ax.set_title("Профили типов: чем каждый тип отличается от среднего района", loc="left", fontsize=11)
    fig.savefig(fig_dir / "03_profiles.png", bbox_inches="tight"); plt.close(fig)

    # 4. Сравнение методов: нормированный ICVI по k
    icv = pd.read_csv(T / "icvi_methods_by_k.csv")
    mlbl = {"spectral_fused": "Спектральная, атриб. сеть", "louvain_fused": "Louvain, атриб. сеть", "kmeans_attr": "k-means, атрибуты",
            "ward_attr": "Ward, атрибуты", "gmm_attr": "GMM, атрибуты", "spectral_struct": "Спектральная, только сеть", "louvain_struct": "Louvain, только сеть"}
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw=dict(width_ratios=[1.2, 1]))
    ax = axs[0]
    for i, m in enumerate(mlbl):
        d = icv[icv.method == m]
        ax.plot(d.k, d.z_mean, marker="o", ms=4, lw=2 if "fused" in m else 1.2, color=SLOTS[i], label=mlbl[m])
    ax.axvline(R["k"], color=MUTED, lw=0.8, ls="--"); ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_xlabel("число кластеров k"); ax.set_ylabel("средний z-ICVI (выше — лучше)")
    ax.legend(fontsize=7, frameon=False, ncol=1, loc="lower left")
    ax.set_title("Качество против случайной базовой линии", loc="left", fontsize=10)
    at = pd.read_csv(T / "icvi_methods_at_k.csv").set_index("method")
    zc = [c for c in at.columns if c.startswith("z_") and c != "z_mean"]
    ax = axs[1]
    M = at[zc]
    im = ax.imshow(M.values, cmap=SEQ, aspect="auto")
    ax.set_yticks(range(len(M)), [mlbl[m] for m in M.index], fontsize=7.5)
    ax.set_xticks(range(len(zc)), [c[2:] for c in zc], fontsize=8)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M.values[i, j]:.0f}", ha="center", va="center", fontsize=7, color="white" if M.values[i, j] > M.values.max() * 0.6 else INK)
    ax.spines[:].set_visible(False); ax.tick_params(length=0)
    ax.set_title(f"z-оценки семи ICVI при k = {R['k']}", loc="left", fontsize=10)
    fig.tight_layout(); fig.savefig(fig_dir / "04_methods_icvi.png", bbox_inches="tight"); plt.close(fig)

    # 5. Влияние способа построения рёбер
    ea = pd.read_csv(T / "ari_between_edge_types.csv", index_col=0)
    elbl = {"attr": "Косинус атрибутов", "comovement": "Корреляция рядов", "lead_lag": "Лаговая корреляция", "dtw": "DTW",
            "procurement_flow": "Потоки госзаказа", "distance": "Расстояние по дорогам", "fused (итог)": "Совмещённая (итог)"}
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    im = ax.imshow(ea.values, cmap=SEQ, vmin=0, vmax=1)
    ax.set_xticks(range(len(ea)), [elbl[c] for c in ea.columns], rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(ea)), [elbl[c] for c in ea.index], fontsize=8)
    for i in range(len(ea)):
        for j in range(len(ea)):
            ax.text(j, i, f"{ea.values[i, j]:.2f}", ha="center", va="center", fontsize=7, color="white" if ea.values[i, j] > 0.55 else INK)
    ax.spines[:].set_visible(False); ax.tick_params(length=0)
    ax.set_title("Согласие разбиений при разных правилах рёбер (ARI)", loc="left", fontsize=10)
    fig.savefig(fig_dir / "05_edges_ari.png", bbox_inches="tight"); plt.close(fig)

    # 6. Динамика: тип каждого МО по кварталам
    q = pd.read_csv(T / "clusters_by_quarter.csv", index_col=0)
    q = q.loc[cl.sort_values().index]
    fig, ax = plt.subplots(figsize=(7.5, 11))
    for i, (m, row) in enumerate(q.iterrows()):
        for j, v in enumerate(row.values):
            ax.add_patch(plt.Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, color=color.get(int(v), MUTED), lw=0))
        ax.text(-0.1, i + 0.5, short(m), ha="right", va="center", fontsize=6.3, color=INK2)
        ax.add_patch(plt.Rectangle((len(q.columns) + 0.25, i + 0.06), 0.5, 0.88, color=color[cl[m]], lw=0))
    ax.set_xlim(-0.05, len(q.columns) + 0.9); ax.set_ylim(len(q), 0)
    ax.set_xticks(np.arange(len(q.columns)) + 0.5, list(q.columns), fontsize=7.5)
    ax.text(len(q.columns) + 0.5, -0.3, "итог", ha="center", fontsize=7, color=INK2)
    ax.set_yticks([]); ax.spines[:].set_visible(False); ax.tick_params(length=0)
    ax.set_title("Тип каждого МО по кварталам (скользящее окно 4 кв., β = 0.5)", loc="left", fontsize=10)
    fig.savefig(fig_dir / "06_dynamics.png", bbox_inches="tight"); plt.close(fig)

    # 7. Компромисс гладкости
    b = pd.read_csv(T / "dynamics_beta_sensitivity.csv")
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    ax.plot(b.beta, b.temporal_ARI, marker="o", color=SLOTS[0], lw=2, label="согласованность кварталов (ARI)")
    ax.plot(b.beta, b.ARI_vs_static, marker="o", color=SLOTS[1], lw=2, label="согласие со статичной разбивкой (ARI)")
    ax.plot(b.beta, b.snapshot_MQ, marker="o", color=SLOTS[2], lw=2, label="модулярность снимка квартала")
    ax.axvline(cfg["dynamics"]["smoothing_beta"], color=MUTED, ls="--", lw=0.8)
    ax.set_xlabel("β — вес истории"); ax.grid(axis="y", color=GRID, lw=0.6); ax.legend(fontsize=7, frameon=False)
    ax.set_title("Выбор сглаживания во времени", loc="left", fontsize=10)
    fig.savefig(fig_dir / "07_beta.png", bbox_inches="tight"); plt.close(fig)
    print("рисунки:", sorted(p.name for p in fig_dir.glob("*.png")))
