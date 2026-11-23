import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = pd.read_pickle("resposta.pkl")
MOD = ["deepseek", "gemini", "openai"]
NOMES = {"deepseek": "DeepSeek", "gemini": "Gemini", "openai": "OpenAI"}
COR = {"deepseek": "#1b6ca8", "gemini": "#e69f00", "openai": "#4c9a6a"}
rng = np.random.default_rng(7)
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans"})

def painel(ax, met, titulo, ylabel=None):
    dados = [R.loc[R.modelo == m, met].dropna().values for m in MOD]
    bp = ax.boxplot(dados, widths=0.55, patch_artist=True, showfliers=False, medianprops=dict(color="black", lw=1.6))
    for patch, m in zip(bp["boxes"], MOD):
        patch.set_facecolor(COR[m]); patch.set_alpha(0.35); patch.set_edgecolor(COR[m])
    for i, (m, d) in enumerate(zip(MOD, dados), 1):
        ax.scatter(rng.normal(i, 0.06, len(d)), d, s=14, color=COR[m], alpha=0.85, zorder=3, edgecolor="white", linewidth=0.3)
    ax.set_xticks([1, 2, 3]); ax.set_xticklabels([NOMES[m] for m in MOD])
    ax.set_title(titulo, fontsize=10.5); ax.set_ylabel(ylabel or "")
    ax.grid(axis="y", alpha=0.25)

fig, ax = plt.subplots(1, 4, figsize=(14, 3.6))
painel(ax[0], "cc_medio", "Ciclomática média por método", "valor por resposta")
painel(ax[1], "cog_medio", "Cognitiva média por método")
painel(ax[2], "cc_total", "Ciclomática total")
painel(ax[3], "cog_total", "Cognitiva total")
fig.tight_layout(); fig.savefig("figuras/fig1_complexidade.png", dpi=300); fig.savefig("figuras/fig1_complexidade.pdf"); plt.close(fig)

fig, ax = plt.subplots(1, 4, figsize=(14, 3.6))
painel(ax[0], "nom_total", "NOM total (métodos)", "valor por resposta")
painel(ax[1], "nom_medio", "NOM médio por tipo")
painel(ax[2], "lcom_medio", "LCOM-HS médio (menor = mais coeso)")
painel(ax[3], "pct_publicos", "Proporção de métodos públicos")
fig.tight_layout(); fig.savefig("figuras/fig2_orientacao_a_objetos.png", dpi=300); fig.savefig("figuras/fig2_orientacao_a_objetos.pdf"); plt.close(fig)

# compilabilidade
comp = R.groupby("modelo")["compilou"].agg(["sum", "count"])
fig, ax = plt.subplots(figsize=(4.6, 3.4))
taxas = [100 * comp.loc[m, "sum"] / comp.loc[m, "count"] for m in MOD]
b = ax.bar([NOMES[m] for m in MOD], taxas, color=[COR[m] for m in MOD], alpha=0.8)
for rect, m in zip(b, MOD):
    ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 1.5, f"{int(comp.loc[m, 'sum'])}/{int(comp.loc[m, 'count'])}", ha="center", fontsize=10)
ax.set_ylim(0, 105); ax.set_ylabel("% de respostas que compilam (JDK 17)"); ax.set_title("Compilabilidade")
ax.grid(axis="y", alpha=0.25); fig.tight_layout(); fig.savefig("figuras/fig3_compilabilidade.png", dpi=300); fig.savefig("figuras/fig3_compilabilidade.pdf"); plt.close(fig)
print("ok")
