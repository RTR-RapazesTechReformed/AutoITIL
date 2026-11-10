"""Gera as figuras analíticas do artigo (boxplot de comprimento, matrizes de confusão, gráficos de
resultados por modelo, forest plot e análise de confiança).

Uso, a partir de pesquisa_dos_modelos/:
    python scripts/gerar_figuras.py

Dados:
- data/dataset_nivel_2.csv (852 chamados)
- results/matrizes_confusao.json: matrizes OOF do SVM (recalculadas com a mesma
  validação cruzada, semente 42) e do BERTimbau/SetFit (saída dos notebooks de
  treino no Colab).
- F1 por fold: notebooks/*_cv_results.json (SVM e BERTimbau) e o log do SetFit.
Requer: numpy, pandas, matplotlib e scipy.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "figs"
SAIDA.mkdir(exist_ok=True)

# Paleta categórica validada (separação para daltonismo): SVM / BERT / SetFit
AZUL, LARANJA, VERDE = "#4C72B0", "#E0922F", "#2A9D8F"
TEXTO, TEXTO2, GRADE = "#1f1f1f", "#52514e", "#e4e3df"
RAMPA = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#5598e7", "#256abf", "#184f95"]
CMAP = LinearSegmentedColormap.from_list("azul", RAMPA)
# Eixos com vírgula decimal (padrão do artigo)
VIRG2 = FuncFormatter(lambda v, _: f"{v:.2f}".replace(".", ","))
VIRG1 = FuncFormatter(lambda v, _: f"{v:.1f}".replace(".", ","))

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.edgecolor": "#b8b7b2",
        "axes.labelcolor": TEXTO2,
        "xtick.color": TEXTO2,
        "ytick.color": TEXTO2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def salvar(fig, nome):
    fig.savefig(SAIDA / nome, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- comprimento
def fig_comprimento():
    d = pd.read_csv(RAIZ / "data" / "dataset_nivel_2.csv")
    d["palavras"] = d["descricao"].fillna("").str.split().str.len()
    o = d["id"].str[0]
    grupos = [
        ("Escritos à mão", d.loc[o == "T", "palavras"], AZUL),
        ("1ª fase sintéticos", d.loc[o.isin(["A", "B"]), "palavras"], VERDE),
        ("Expansão", d.loc[o.isin(["C", "D"]), "palavras"], LARANJA),
    ]
    fig, ax = plt.subplots(figsize=(6.4, 2.9))
    for i, (nome, v, cor) in enumerate(grupos):
        pos = len(grupos) - 1 - i
        bp = ax.boxplot(
            v, vert=False, positions=[pos], widths=0.5, patch_artist=True,
            showfliers=False, whis=(5, 95),
            boxprops=dict(facecolor=cor, alpha=0.35, edgecolor=cor, linewidth=1.2),
            medianprops=dict(color=cor, linewidth=2.2),
            whiskerprops=dict(color=cor, linewidth=1.2),
            capprops=dict(color=cor, linewidth=1.2),
        )
        rng = np.random.default_rng(7)
        y = pos + rng.uniform(-0.18, 0.18, len(v))
        ax.scatter(v, y, s=5, color=cor, alpha=0.28, linewidths=0, zorder=1)
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        ax.text(
            101, pos,
            f"mediana {med:.0f}  ·  metade entre {q1:.0f} e {q3:.0f}\nn = {len(v)}",
            va="center", ha="left", fontsize=8, color=TEXTO,
        )
    ax.set_yticks(range(len(grupos)))
    ax.set_yticklabels([g[0] for g in grupos][::-1], color=TEXTO)
    ax.set_xlim(0, 150)
    ax.set_xlabel("Comprimento do chamado (palavras)")
    ax.xaxis.grid(True, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    salvar(fig, "fig_comprimento.png")
    return {n: v.describe(percentiles=[0.25, 0.5, 0.75]).round(1).to_dict() for n, v, _ in grupos}


# ---------------------------------------------------------------------- folds
FOLDS = {
    "n1": {
        "SVM": [0.879, 0.9012, 0.931, 0.9539, 0.8908],
        "BERTimbau": [0.9652, 0.9299, 0.9718, 0.9831, 0.9472],
    },
    "n2": {
        "SVM": [0.7394, 0.7637, 0.7469, 0.6913, 0.774],
        "SetFit": [0.765, 0.785, 0.717, 0.704, 0.794],
        "BERTimbau": [0.7772, 0.7951, 0.7877, 0.7885, 0.8755],
    },
}
COR = {"SVM": AZUL, "BERTimbau": LARANJA, "SetFit": VERDE}
MARC = {"SVM": "o", "BERTimbau": "s", "SetFit": "D"}


# ------------------------------------------------------------------ confusão
def heat(ax, cm, classes, titulo):
    cm = np.array(cm)
    frac = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(frac, cmap=CMAP, vmin=0, vmax=1)
    for i in range(len(classes)):
        for j in range(len(classes)):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=8,
                    color="white" if frac[i, j] > 0.5 else TEXTO,
                    fontweight="bold" if i == j else "normal")
    ax.set_xticks(range(len(classes)))
    ax.set_yticks(range(len(classes)))
    ax.set_xticklabels(classes, rotation=40, ha="right", fontsize=8, color=TEXTO)
    ax.set_yticklabels(classes, fontsize=8, color=TEXTO)
    ax.set_title(titulo, fontsize=9.5, color=TEXTO, loc="left")
    ax.set_xticks(np.arange(-0.5, len(classes), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(classes), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)


def fig_confusao(m):
    for chave, painel, nome, larg in [
        ("n1", ["SVM", "BERTimbau"], "fig_confusao_n1.png", (6.4, 3.3)),
        ("n2", ["SVM", "SetFit", "BERTimbau"], "fig_confusao_n2.png", (7.2, 3.1)),
    ]:
        classes = m[chave]["classes"]
        fig, axs = plt.subplots(1, len(painel), figsize=larg)
        for ax, mod in zip(axs, painel):
            heat(ax, m[chave][mod], classes, mod)
        axs[0].set_ylabel("Classe real", color=TEXTO2)
        for ax in axs[1:]:
            ax.set_yticklabels([])
        fig.subplots_adjust(wspace=0.06)
        for ax in axs:
            ax.set_xlabel("Classe prevista", color=TEXTO2)
        sm = plt.cm.ScalarMappable(cmap=CMAP, norm=plt.Normalize(0, 1))
        cb = fig.colorbar(sm, ax=list(axs), fraction=0.025, pad=0.02)
        cb.set_label("Fração da classe real", color=TEXTO2, fontsize=8)
        cb.ax.tick_params(labelsize=7)
        cb.ax.yaxis.set_major_formatter(VIRG1)
        cb.outline.set_visible(False)
        salvar(fig, nome)


def pares(m, chave, mod):
    cm = np.array(m[chave][mod])
    cl = m[chave]["classes"]
    out = {}
    for i in range(len(cl)):
        for j in range(i + 1, len(cl)):
            out[f"{cl[i]}↔{cl[j]}"] = int(cm[i, j] + cm[j, i])
    return out


# ------------------------------------------------- gráficos de resultados (F1)
# Fontes: Seções 10.1 a 10.4 do artigo (validação cruzada de 5 folds, 852 chamados).
F1_852 = {  # (média, desvio)
    "n1": {"SVM": (0.9112, 0.0274), "BERTimbau": (0.9594, 0.0188)},
    "n2": {"SVM": (0.7431, 0.0286), "SetFit": (0.7532, 0.0361), "BERTimbau": (0.8048, 0.0358)},
}
CONGELADO = {"n1": (0.9426, 0.0186), "n2": (0.7169, 0.0199)}  # BERTimbau pré-treinado, sem fine-tuning
ESCALA = {  # F1 macro com 185 e com 852 chamados
    "n1": {"SVM": (0.842, 0.9112), "BERTimbau": (0.759, 0.9594)},
    "n2": {"SVM": (0.651, 0.7431), "SetFit": (0.616, 0.7532), "BERTimbau": (0.522, 0.8048)},
}
LIM = {"n1": (0.85, 1.0), "n2": (0.66, 0.90)}
TIT = {"n1": "Nível 1 – tipo ITIL", "n2": "Nível 2 – área responsável"}


def pt(v, casas=3):
    return f"{v:.{casas}f}".replace(".", ",")


def ponto(ax, x, media, desvio, cor, marca, vazio=False, rotulo=True):
    ax.errorbar(
        x, media, yerr=desvio, fmt="none", ecolor=cor, elinewidth=1.4, capsize=4, capthick=1.4, zorder=2,
    )
    ax.scatter(
        [x], [media], s=70, marker=marca, zorder=3, linewidth=1.8,
        facecolor="white" if vazio else cor, edgecolor=cor,
    )
    if rotulo:
        ax.text(x, media + desvio + (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.025, pt(media),
                ha="center", va="bottom", fontsize=8.5, color=TEXTO)


def estilo_y(ax, nivel):
    ax.set_ylim(*LIM[nivel])
    ax.yaxis.set_major_formatter(VIRG2)
    ax.yaxis.grid(True, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(TIT[nivel], fontsize=9.5, color=TEXTO, loc="left")


def fig_f1_modelos():  # Figura 21 – desempenho no dataset atual
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.3), gridspec_kw={"width_ratios": [2, 3]})
    for ax, nivel in zip(axs, ["n1", "n2"]):
        estilo_y(ax, nivel)
        mods = list(F1_852[nivel])
        for j, m in enumerate(mods):
            ponto(ax, j, *F1_852[nivel][m], COR[m], MARC[m])
        ax.set_xticks(range(len(mods)))
        ax.set_xticklabels(mods, color=TEXTO)
        ax.set_xlim(-0.6, len(mods) - 0.4)
    axs[0].set_ylabel("F1 macro (média ± desvio entre folds)")
    fig.tight_layout()
    salvar(fig, "fig_f1_modelos.png")



def fig_finetuning():  # Figura 24 – quanto o fine-tuning agrega
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 3.5))
    nomes = ["SVM\n(TF-IDF)", "BERTimbau\npré-treinado\n(congelado)", "BERTimbau\nfine-tuned"]
    for ax, nivel in zip(axs, ["n1", "n2"]):
        estilo_y(ax, nivel)
        ponto(ax, 0, *F1_852[nivel]["SVM"], AZUL, "o")
        ponto(ax, 1, *CONGELADO[nivel], LARANJA, "s", vazio=True)
        ponto(ax, 2, *F1_852[nivel]["BERTimbau"], LARANJA, "s")
        ax.set_xticks(range(3))
        ax.set_xticklabels(nomes, color=TEXTO, fontsize=8)
        ax.set_xlim(-0.6, 2.6)
    axs[0].set_ylabel("F1 macro (média ± desvio entre folds)")
    fig.tight_layout()
    salvar(fig, "fig_finetuning.png")


def afastar(ys, minimo):
    """Afasta rótulos que ficariam um em cima do outro (mantém a ordem vertical)."""
    ordem = sorted(range(len(ys)), key=lambda i: ys[i])
    pos = [ys[i] for i in ordem]
    for k in range(1, len(pos)):
        if pos[k] - pos[k - 1] < minimo:
            pos[k] = pos[k - 1] + minimo
    return {ordem[k]: pos[k] for k in range(len(pos))}


def fig_escala():  # Figura 23 – o modelo que vence depende do tamanho do dataset
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.5))
    lims = {"n1": (0.72, 1.0), "n2": (0.45, 0.85)}
    for ax, nivel in zip(axs, ["n1", "n2"]):
        mods = list(ESCALA[nivel])
        lo, hi = lims[nivel]
        gap = (hi - lo) * 0.065
        for m in mods:
            ax.plot([185, 852], ESCALA[nivel][m], color=COR[m], linewidth=2, marker=MARC[m], markersize=8,
                    markeredgecolor="white", markeredgewidth=1, zorder=3)
        esq = afastar([ESCALA[nivel][m][0] for m in mods], gap)
        dire = afastar([ESCALA[nivel][m][1] for m in mods], gap)
        for k, m in enumerate(mods):
            ax.text(185 / 1.09, esq[k], pt(ESCALA[nivel][m][0]), ha="right", va="center", fontsize=8.5, color=TEXTO)
            ax.text(852 * 1.09, dire[k], f"{m}  {pt(ESCALA[nivel][m][1])}", ha="left", va="center",
                    fontsize=8.5, color=TEXTO)
        ax.set_xscale("log")
        ax.set_xlim(75, 3600)
        ax.set_ylim(lo, hi)
        ax.yaxis.set_major_formatter(VIRG2)
        ax.set_xticks([185, 852])
        ax.set_xticklabels(["185 chamados", "852 chamados"], color=TEXTO)
        ax.minorticks_off()
        ax.set_xlabel("Tamanho do dataset (escala log)", color=TEXTO2)
        ax.yaxis.grid(True, color=GRADE, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_title(TIT[nivel], fontsize=9.5, color=TEXTO, loc="left")
    axs[0].set_ylabel("F1 macro (média, 5 folds)")
    fig.tight_layout()
    salvar(fig, "fig_escala.png")


# --------------------------------------------------------------- forest plot
def fig_forest():
    """Diferença pareada de F1 macro entre modelos (mesmos folds) com IC de 95%.

    Barra grossa: t pareado simples. Linha fina: com a correção de Nadeau e Bengio (2003),
    que leva em conta a sobreposição dos conjuntos de treino entre os folds
    (variância multiplicada por 1/k + n_teste/n_treino = 1/5 + 1/4).
    """
    from scipy import stats

    comps = [
        ("n1", "BERTimbau", "SVM", "Nível 1: BERTimbau − SVM"),
        ("n2", "BERTimbau", "SVM", "Nível 2: BERTimbau − SVM"),
        ("n2", "BERTimbau", "SetFit", "Nível 2: BERTimbau − SetFit"),
        ("n2", "SetFit", "SVM", "Nível 2: SetFit − SVM"),
    ]
    k, tq = 5, stats.t.ppf(0.975, 4)
    linhas = []
    for nivel, a, b, rot in comps:
        d = np.array(FOLDS[nivel][a]) - np.array(FOLDS[nivel][b])
        m, sd = d.mean(), d.std(ddof=1)
        ep, epc = sd / np.sqrt(k), sd * np.sqrt(1 / k + 1 / (k - 1))
        linhas.append((rot, m, tq * ep, tq * epc,
                       2 * stats.t.sf(abs(m / ep), 4), 2 * stats.t.sf(abs(m / epc), 4)))
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    n = len(linhas)
    for i, (rot, m, ic, icc, p1, p2) in enumerate(linhas):
        y = n - 1 - i
        ax.plot([m - icc, m + icc], [y, y], color="#8a8985", linewidth=1.2, zorder=1)
        for xx in (m - icc, m + icc):
            ax.plot([xx, xx], [y - 0.12, y + 0.12], color="#8a8985", linewidth=1.2, zorder=1)
        ax.plot([m - ic, m + ic], [y, y], color=AZUL, linewidth=4.5, solid_capstyle="butt", zorder=2)
        ax.scatter([m], [y], s=70, color="white", edgecolor=AZUL, linewidth=2, zorder=3)
        ax.text(1.03, y, pt(p1) if False else f"{pt(m, 3)}", transform=ax.get_yaxis_transform(), va="center",
                fontsize=8.5, color=TEXTO)
        ax.text(1.17, y, pt(p1), transform=ax.get_yaxis_transform(), va="center", fontsize=8.5, color=TEXTO)
        ax.text(1.31, y, pt(p2), transform=ax.get_yaxis_transform(), va="center", fontsize=8.5, color=TEXTO)
    ax.axvline(0, color=TEXTO2, linewidth=1.0, linestyle=(0, (4, 3)), zorder=0)
    for x, t in ((1.03, "Diferença\nmédia"), (1.17, "p\n(t pareado)"), (1.31, "p\n(corrigido)")):
        ax.text(x, n - 0.35, t, transform=ax.get_yaxis_transform(), va="bottom", fontsize=8, color=TEXTO2)
    ax.set_yticks(range(n))
    ax.set_yticklabels([l[0] for l in linhas][::-1], color=TEXTO)
    ax.set_ylim(-0.6, n - 0.1)
    ax.set_xlim(-0.05, 0.13)
    ax.xaxis.set_major_formatter(VIRG2)
    ax.set_xlabel("Diferença no F1 macro (à direita de zero, o primeiro modelo vence)", color=TEXTO2)
    ax.xaxis.grid(True, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.plot([], [], color=AZUL, linewidth=4.5, label="IC 95%, t pareado")
    ax.plot([], [], color="#8a8985", linewidth=1.2, label="IC 95%, com correção de Nadeau e Bengio")
    ax.legend(loc="lower left", fontsize=8, frameon=False, bbox_to_anchor=(-0.02, 1.0), ncol=2)
    salvar(fig, "fig_forest.png")
    return linhas


# ------------------------------------------------------ confiança e limiar (N1)
def fig_confianca():
    """Confiança do BERTimbau (Nível 1) fora do fold: acertos x erros e curva do limiar.

    Dados: results/bert_nivel1_oof_probs.csv (notebooks/bert_nivel1_training.ipynb, célula de CV).
    """
    d = pd.read_csv(RAIZ / "results" / "bert_nivel1_oof_probs.csv")
    d["acerto"] = d["classe_real"] == d["classe_prevista"]
    ac, er = d.loc[d.acerto, "confianca"].values, d.loc[~d.acerto, "confianca"].values
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.6, 3.4), gridspec_kw={"width_ratios": [1.15, 1]})
    # painel 1: boxplot + pontos
    rng = np.random.default_rng(3)
    for pos, v, cor, nome in ((0, ac, AZUL, f"Acertos (n = {len(ac)})"), (1, er, LARANJA, f"Erros (n = {len(er)})")):
        a1.boxplot(v, positions=[pos], widths=0.5, patch_artist=True, showfliers=False, whis=(5, 95),
                   boxprops=dict(facecolor=cor, alpha=0.3, edgecolor=cor, linewidth=1.2),
                   medianprops=dict(color=cor, linewidth=2.2), whiskerprops=dict(color=cor, linewidth=1.2),
                   capprops=dict(color=cor, linewidth=1.2))
        a1.scatter(pos + rng.uniform(-0.2, 0.2, len(v)), v, s=7, color=cor, alpha=0.35, linewidths=0, zorder=1)
        a1.text(pos, 0.385, f"mediana {pt(np.median(v), 2)}", ha="center", fontsize=8, color=TEXTO)
    for lim in (0.75, 0.90):
        a1.axhline(lim, color=TEXTO2, linewidth=1, linestyle=(0, (4, 3)), zorder=0)
        a1.text(1.52, lim, f"limiar {pt(lim, 2)}", va="bottom", ha="right", fontsize=8, color=TEXTO2)
    a1.set_xticks([0, 1])
    a1.set_xticklabels([f"Acertos\n(n = {len(ac)})", f"Erros\n(n = {len(er)})"], color=TEXTO)
    a1.set_xlim(-0.6, 1.6)
    a1.set_ylim(0.35, 1.0)
    a1.yaxis.set_major_formatter(VIRG2)
    a1.set_ylabel("Confiança do modelo (maior probabilidade)", color=TEXTO2)
    a1.set_title("Confiança de acertos e erros", fontsize=9.5, color=TEXTO, loc="left")
    a1.yaxis.grid(True, color=GRADE, linewidth=0.8)
    a1.set_axisbelow(True)
    # painel 2: curva do limiar
    ts = np.linspace(0.30, 1.0, 141)
    x = [100 * (d.confianca < t).mean() for t in ts]
    y = [100 * ((d.confianca < t) & ~d.acerto).sum() / (~d.acerto).sum() for t in ts]
    a2.plot([0, 100], [0, 100], color="#b8b7b2", linewidth=1, linestyle=(0, (4, 3)), zorder=0)
    a2.text(62, 56, "revisão ao acaso", fontsize=8, color=TEXTO2, rotation=0, ha="center")
    a2.plot(x, y, color=AZUL, linewidth=2.2, zorder=2)
    for t, dx, dy in ((0.60, 2.2, -5), (0.70, 2.2, -5), (0.75, 2.2, -6), (0.80, 2.2, -5), (0.90, 2.2, -5)):
        xi, yi = 100 * (d.confianca < t).mean(), 100 * ((d.confianca < t) & ~d.acerto).sum() / (~d.acerto).sum()
        destaque = t in (0.75, 0.90)
        a2.scatter([xi], [yi], s=60 if destaque else 28, color="white" if destaque else AZUL, edgecolor=AZUL,
                   linewidth=2 if destaque else 0, zorder=3)
        if destaque:
            a2.text(xi + dx, yi + dy, f"limiar {pt(t, 2)}\n{pt(xi, 1)}% revisados · {pt(yi, 1)}% dos erros",
                    fontsize=8, color=TEXTO, va="center")
    a2.set_xlim(0, 100)
    a2.set_ylim(0, 100)
    a2.set_xlabel("Chamados encaminhados para revisão (%)", color=TEXTO2)
    a2.set_ylabel("Erros capturados (%)", color=TEXTO2)
    a2.set_title("O que cada limiar captura", fontsize=9.5, color=TEXTO, loc="left")
    a2.yaxis.grid(True, color=GRADE, linewidth=0.8)
    a2.set_axisbelow(True)
    fig.tight_layout()
    salvar(fig, "fig_confianca.png")


# ------------------------------------------------ F1 por fold (mapa de calor)
def fig_folds_calor():
    """F1 macro de cada fold e modelo; a cor é relativa dentro de cada nível."""
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.5), gridspec_kw={"width_ratios": [2, 3]})
    for ax, (nivel, titulo) in zip(axs, [("n1", TIT["n1"]), ("n2", TIT["n2"])]):
        mods = list(FOLDS[nivel])
        M = np.array([FOLDS[nivel][m] for m in mods]).T  # folds x modelos
        ax.imshow(M, cmap=CMAP, vmin=M.min() - 0.01, vmax=M.max() + 0.005, aspect="auto")
        for i in range(5):
            for j in range(len(mods)):
                claro = (M[i, j] - M.min()) / (M.max() - M.min()) > 0.62
                ax.text(j, i, pt(M[i, j]), ha="center", va="center", fontsize=8.5,
                        color="white" if claro else TEXTO)
        for j in range(len(mods)):
            ax.text(j, 5.15, pt(M[:, j].mean()), ha="center", va="center", fontsize=8.5,
                    fontweight="bold", color=TEXTO)
        ax.text(-0.62, 5.15, "Média", ha="right", va="center", fontsize=8.5, fontweight="bold", color=TEXTO)
        ax.set_xticks(range(len(mods)))
        ax.set_xticklabels(mods, color=TEXTO)
        ax.xaxis.tick_top()
        ax.set_yticks(range(5))
        ax.set_yticklabels([f"Fold {k}" for k in range(1, 6)], color=TEXTO)
        ax.set_xticks(np.arange(-0.5, len(mods), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, 5, 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.5)
        ax.tick_params(which="both", length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_ylim(5.5, -0.5)
        ax.set_title(titulo, fontsize=9.5, color=TEXTO, loc="left", pad=22)
    fig.tight_layout()
    salvar(fig, "fig_folds_calor.png")


if __name__ == "__main__":
    m = json.loads((RAIZ / "results" / "matrizes_confusao.json").read_text(encoding="utf8"))
    print(json.dumps(fig_comprimento(), ensure_ascii=False, indent=1))
    fig_confusao(m)
    fig_f1_modelos()
    fig_finetuning()
    fig_escala()
    fig_folds_calor()
    fig_confianca()
    for l in fig_forest():
        print(l[0], [round(float(x), 4) for x in l[1:]])
    for ch, mods in (("n1", ["SVM", "BERTimbau"]), ("n2", ["SVM", "SetFit", "BERTimbau"])):
        for mod in mods:
            p = sorted(pares(m, ch, mod).items(), key=lambda x: -x[1])[:3]
            print(ch, mod, p)
