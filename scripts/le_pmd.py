import re, pandas as pd
from collections import Counter

rx = re.compile(r'^(?P<file>java\\(?P<modelo>[a-z]+)\\(?P<esp>ESP\d+)\\(?P<arq>[^:\\]+\.java)):(?P<linha>\d+):\s+'
                r'(?P<regra>CyclomaticComplexity|CognitiveComplexity):\s+(?P<msg>.*?)\s*$')
rx_class = re.compile(r"^The (?P<tipo>\w+) '(?P<nome>.+)' has a total cyclomatic complexity of (?P<total>\d+) \(highest (?P<max>\d+)\)\.?$")
rx_cc = re.compile(r"^The (?P<tipo>\w+) '(?P<nome>.+)' has a cyclomatic complexity of (?P<v>\d+)\.?$")
rx_cog = re.compile(r"^The (?P<tipo>\w+) '(?P<nome>.+)' has a cognitive complexity of (?P<v>\d+), current threshold is \d+$")

met, cls, cog, estranhas = [], [], [], Counter()
for modelo in ("deepseek", "gemini", "openai"):
    with open(f"/tmp/med/resultados_medicao/pmd_{modelo}.txt", encoding="utf-8", errors="replace") as f:
        for linha in f:
            m = rx.match(linha.rstrip("\r\n"))
            if not m:
                continue
            d = m.groupdict(); msg = d["msg"]
            base = dict(modelo=d["modelo"], esp=d["esp"], arquivo=d["arq"], linha=int(d["linha"]))
            if d["regra"] == "CyclomaticComplexity":
                a = rx_class.match(msg)
                if a:
                    cls.append({**base, "tipo": a["tipo"], "classe": a["nome"], "cc_total": int(a["total"]), "cc_max": int(a["max"])}); continue
                b = rx_cc.match(msg)
                if b:
                    met.append({**base, "tipo": b["tipo"], "nome": b["nome"], "cc": int(b["v"])}); continue
                estranhas[msg[:60]] += 1
            else:
                c = rx_cog.match(msg)
                if c:
                    cog.append({**base, "tipo": c["tipo"], "nome": c["nome"], "cog": int(c["v"])}); continue
                estranhas[msg[:60]] += 1

M = pd.DataFrame(met); C = pd.DataFrame(cls); G = pd.DataFrame(cog)
print("metodos (cc):", len(M), "| classes:", len(C), "| linhas de cognitiva:", len(G), "| nao reconhecidas:", sum(estranhas.values()))
print("tipos em M:", M["tipo"].value_counts().to_dict()); print("tipos em C:", C["tipo"].value_counts().to_dict()); print("tipos em G:", G["tipo"].value_counts().to_dict())
chave = ["modelo", "esp", "arquivo", "linha", "nome"]
print("duplicatas de chave em M:", M.duplicated(chave).sum(), "| em G:", G.duplicated(chave).sum())
M = M.merge(G[chave + ["cog"]], on=chave, how="left")
orfas = len(G) - M["cog"].notna().sum()
M["cog"] = M["cog"].fillna(0).astype(int)
print("cognitivas sem metodo correspondente:", orfas)
M.to_pickle("metodos.pkl"); C.to_pickle("classes.pkl")
print(M.groupby("modelo").agg(metodos=("cc", "size"), cc_medio=("cc", "mean"), cog_medio=("cog", "mean"), cc_max=("cc", "max"), cog_max=("cog", "max")).round(2))
