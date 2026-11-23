import json, glob
import numpy as np, pandas as pd

M = pd.read_pickle("metodos.pkl"); O = pd.read_csv("oo.csv")
comp = pd.read_csv("/tmp/med/resultados_medicao/compilacao_jdk17.csv", encoding="utf-8-sig")
comp["compilou"] = comp["compilou"].eq("sim")
linhas = pd.DataFrame([{"modelo": r["prov"], "esp": r["esp"], "linhas": r["linhas"], "tokens_saida": r["saida"]}
                       for p in ("deepseek", "gemini", "openai") for r in json.load(open(f"/tmp/all/res_{p}.json"))])

# --- por resposta: complexidade (PMD, por metodo/construtor) ---
g = M.groupby(["modelo", "esp"])
R = g.agg(n_metodos=("cc", "size"), cc_total=("cc", "sum"), cc_medio=("cc", "mean"), cc_max=("cc", "max"),
          cog_total=("cog", "sum"), cog_medio=("cog", "mean"), cog_max=("cog", "max")).reset_index()

# --- por resposta: metricas OO (tipos com ao menos 1 metodo) ---
Ou = O[O["nom"] >= 1].copy()
Ou["lcom_hs"] = pd.to_numeric(Ou["lcom_hs"], errors="coerce")
go = Ou.groupby(["modelo", "esp"])
R2 = go.agg(n_tipos=("classe", "size"), nom_total=("nom", "sum"), nom_medio=("nom", "mean"),
            npm_total=("npm", "sum"), npm_medio=("npm", "mean"), lcom_medio=("lcom_hs", "mean"),
            n_tipos_lcom=("lcom_hs", "count")).reset_index()
R2["pct_publicos"] = R2["npm_total"] / R2["nom_total"]
R = R.merge(R2, on=["modelo", "esp"], how="outer").merge(comp[["modelo", "especificacao", "arquivos", "compilou"]]
    .rename(columns={"especificacao": "esp"}), on=["modelo", "esp"], how="left").merge(linhas, on=["modelo", "esp"], how="left")
R["parcial_parse"] = (R["modelo"].eq("gemini") & R["esp"].eq("ESP24"))
R.to_pickle("resposta.pkl")
R.to_csv("metricas_por_resposta.csv", index=False, encoding="utf-8-sig", float_format="%.4f")

cols = ["n_metodos", "cc_medio", "cc_total", "cog_medio", "cog_total", "nom_total", "npm_total", "nom_medio", "lcom_medio", "pct_publicos", "linhas"]
print("respostas por modelo:", R.groupby("modelo").size().to_dict())
print("\nMEDIANA por modelo"); print(R.groupby("modelo")[cols].median().round(2).T)
print("\nMEDIA por modelo");   print(R.groupby("modelo")[cols].mean().round(2).T)
print("\nvalores ausentes por coluna:", R[cols].isna().sum()[lambda s: s > 0].to_dict())
