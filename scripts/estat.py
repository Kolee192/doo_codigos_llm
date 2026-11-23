import itertools, json
import numpy as np, pandas as pd
from scipy import stats

R = pd.read_pickle("resposta.pkl")
MOD = ["deepseek", "gemini", "openai"]
W = {m: R[R.modelo == m].set_index("esp") for m in MOD}
comuns_all = sorted(set.intersection(*[set(W[m].index) for m in MOD]))
compilam3 = [e for e in comuns_all if all(W[m].loc[e, "compilou"] for m in MOD)]
sem24 = [e for e in comuns_all if e != "ESP24"]

def holm(ps):
    ps = np.array(ps, float); o = np.argsort(ps); n = len(ps); aj = np.empty(n); run = 0
    for rank, i in enumerate(o):
        run = max(run, (n - rank) * ps[i]); aj[i] = min(1, run)
    return aj

def friedman(metrica, specs):
    X = np.column_stack([W[m].loc[specs, metrica].values for m in MOD])
    st_, p = stats.friedmanchisquare(*X.T)
    n, k = X.shape
    return st_, p, st_ / (n * (k - 1)), X          # Kendall's W

def rb(d):
    d = d[d != 0]
    if len(d) == 0: return 0.0
    r = stats.rankdata(np.abs(d)); wp = r[d > 0].sum(); wm = r[d < 0].sum()
    return (wp - wm) / (wp + wm)                   # correlacao rank-biserial

def pares(X, metrica):
    out = []
    for (i, a), (j, b) in itertools.combinations(enumerate(MOD), 2):
        d = X[:, i] - X[:, j]
        p = stats.wilcoxon(d, zero_method="wilcox", method="auto").pvalue if np.any(d != 0) else 1.0
        out.append((a, b, np.median(d), rb(d), p))
    adj = holm([o[4] for o in out])
    return [(a, b, md, r, p, pa) for (a, b, md, r, p), pa in zip(out, adj)]

METRICAS = [("cc_medio", "QP2 ciclomatica media por metodo"), ("cc_total", "QP2 ciclomatica total"),
            ("cog_medio", "QP3 cognitiva media por metodo"), ("cog_total", "QP3 cognitiva total"),
            ("nom_total", "QP4 NOM total"), ("npm_total", "QP4 NPM total"), ("nom_medio", "NOM medio por tipo"),
            ("lcom_medio", "LCOM-HS medio"), ("pct_publicos", "% metodos publicos"), ("linhas", "tamanho (linhas)")]

linhas = []
fam = []
for met, desc in METRICAS:
    s, p, w, X = friedman(met, comuns_all)
    fam.append(p); linhas.append(dict(metrica=met, descricao=desc, n=len(comuns_all), friedman_chi2=s, p=p, kendall_W=w,
        med_deepseek=np.median(X[:, 0]), med_gemini=np.median(X[:, 1]), med_openai=np.median(X[:, 2])))
adj = holm(fam)
T = pd.DataFrame(linhas); T["p_holm_familia"] = adj
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
print("=== ANALISE PRINCIPAL: Friedman, n =", len(comuns_all), "especificacoes comuns aos 3 modelos ===")
print(T.assign(p=T.p.map("{:.4g}".format), p_holm_familia=T.p_holm_familia.map("{:.4g}".format),
               friedman_chi2=T.friedman_chi2.round(2), kendall_W=T.kendall_W.round(2)).round(3).to_string(index=False))
T.to_csv("estatisticas_friedman.csv", index=False, encoding="utf-8-sig", float_format="%.5g")

print("\n=== COMPARACOES DOIS A DOIS (Wilcoxon pareado, Holm dentro da metrica), so onde Friedman p < 0.05 ===")
PP = []
for met, desc in METRICAS:
    s, p, w, X = friedman(met, comuns_all)
    for a, b, md, r, pp, pa in pares(X, met):
        PP.append(dict(metrica=met, a=a, b=b, mediana_dif_a_menos_b=md, rank_biserial=r, p=pp, p_holm=pa, friedman_p=p))
        if p < 0.05: print(f"{met:13} {a:8} vs {b:8}: mediana(a-b) = {md:9.3f} | r_rb = {r:+.2f} | p = {pp:.4g} | p Holm = {pa:.4g}")
pd.DataFrame(PP).to_csv("estatisticas_pares.csv", index=False, encoding="utf-8-sig", float_format="%.5g")

print("\n=== SENSIBILIDADE: Friedman p-valor por conjunto de especificacoes ===")
res = {"todas (%d)" % len(comuns_all): comuns_all, "sem ESP24 parcial (%d)" % len(sem24): sem24, "compilam nos 3 (%d)" % len(compilam3): compilam3}
S = {nome: {} for nome in res}
for met, _ in METRICAS:
    for nome, specs in res.items(): S[nome][met] = friedman(met, specs)[1]
print(pd.DataFrame(S).map("{:.4g}".format).to_string())
pd.DataFrame(S).to_csv("estatisticas_sensibilidade.csv", encoding="utf-8-sig", float_format="%.5g")
