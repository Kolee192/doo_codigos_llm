"""Compila cada resposta com JDK 17 e roda o PMD nos tres modelos.

Rode na pasta que contem 'java' e 'regras_metricas.xml':
    py medir.py

Cria a pasta 'resultados_medicao' com:
    compilacao_jdk17.csv   se cada resposta compila com --release 17
    pmd_deepseek.txt, pmd_gemini.txt, pmd_openai.txt   relatorios do PMD
"""
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PMD = os.environ.get("PMD_BAT", os.path.join(os.path.expanduser("~"), "pmd", "bin", "pmd.bat"))
JAVAC = os.environ.get("JAVAC", "javac")
JAVAC_FLAGS = os.environ.get("JAVAC_FLAGS", "--release 17").split()
MODELOS = ["deepseek", "gemini", "openai"]

raiz = Path("java")
regras = Path("regras_metricas.xml")
if not raiz.is_dir() or not regras.is_file():
    sys.exit("Rode este script dentro da pasta que contem 'java' e 'regras_metricas.xml'.")

saida = Path("resultados_medicao")
saida.mkdir(exist_ok=True)
tmp = saida / "_classes"

# ---------- 1) compilacao ----------
print("== Compilando com JDK 17 ==", flush=True)
try:
    v = subprocess.run([JAVAC, "-version"], capture_output=True, text=True)
    print("   ", (v.stdout + v.stderr).strip(), flush=True)
except FileNotFoundError:
    sys.exit("Nao encontrei o 'javac'. Abra um terminal novo e confira com: javac -version")

linhas = []
for modelo in MODELOS:
    for pasta in sorted((raiz / modelo).glob("ESP*")):
        arquivos = sorted(str(p) for p in pasta.glob("*.java"))
        destino = tmp / modelo / pasta.name
        destino.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([JAVAC, *JAVAC_FLAGS, "-encoding", "UTF-8", "-Xmaxerrs", "1000",
                            "-d", str(destino), *arquivos], capture_output=True, text=True, errors="replace")
        erros = re.findall(r"^.*error:.*$", r.stderr, flags=re.M)
        linhas.append([modelo, pasta.name, len(arquivos), "sim" if r.returncode == 0 else "nao",
                       len(erros), (erros[0].strip()[:300] if erros else "")])
        print(f"   {modelo} {pasta.name}: {'ok' if r.returncode == 0 else 'ERRO (%d)' % len(erros)}", flush=True)
shutil.rmtree(tmp, ignore_errors=True)
with open(saida / "compilacao_jdk17.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["modelo", "especificacao", "arquivos", "compilou", "erros", "primeiro_erro"])
    w.writerows(linhas)

# ---------- 2) PMD ----------
print("\n== Rodando o PMD ==", flush=True)
for modelo in MODELOS:
    rel = saida / f"pmd_{modelo}.txt"
    r = subprocess.run([PMD, "check", "-d", str(raiz / modelo), "-R", str(regras), "-f", "text", "-r", str(rel)],
                       capture_output=True, text=True, errors="replace")
    tamanho = rel.stat().st_size if rel.exists() else 0
    print(f"   {modelo}: codigo de saida {r.returncode}, relatorio com {tamanho} bytes", flush=True)
    if tamanho == 0:
        print("   AVISO: relatorio vazio. Mensagem do PMD:\n", (r.stdout + r.stderr)[-1500:])

print("\nPronto. Compacte a pasta 'resultados_medicao' e envie.")
