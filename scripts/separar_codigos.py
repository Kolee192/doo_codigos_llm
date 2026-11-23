"""Separa a resposta de um LLM em arquivos .java e tenta compilar.

Uso:
    python separar_codigos.py resposta.txt PASTA_DE_SAIDA

- Remove as cercas de markdown (```java ... ```), se existirem.
- Divide o texto nas linhas '// File: NomeDaClasse.java'.
- Grava um .java por arquivo em PASTA_DE_SAIDA.
- Roda 'javac' na pasta e mostra se compilou (precisa do JDK instalado).
- Avisa se a resposta parece cortada ou sem Main.
"""
import re
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3:
    sys.exit(__doc__)

entrada, saida = Path(sys.argv[1]), Path(sys.argv[2])
texto = entrada.read_text(encoding="utf-8", errors="replace")

# remove cercas de markdown
texto = re.sub(r"^\s*```[a-zA-Z]*\s*$", "", texto, flags=re.M)

partes = re.split(r"^[ \t]*//\s*File:\s*(\S+\.java)\s*$", texto, flags=re.M)
# partes = [lixo_inicial, nome1, corpo1, nome2, corpo2, ...]
arquivos = list(zip(partes[1::2], partes[2::2]))
if not arquivos:
    sys.exit("Nenhum '// File: X.java' encontrado. O formato do prompt não foi seguido.")

saida.mkdir(parents=True, exist_ok=True)
for nome, corpo in arquivos:
    (saida / nome).write_text(corpo.strip() + "\n", encoding="utf-8")
print(f"{len(arquivos)} arquivos gravados em {saida}/")

# checagens simples
tem_main = any(re.search(r"public\s+static\s+void\s+main", c) for _, c in arquivos)
ultimo = arquivos[-1][1].strip()
equilibrado = ultimo.count("{") == ultimo.count("}")
print("Tem método main:", "sim" if tem_main else "NÃO")
print("Último arquivo com chaves balanceadas:", "sim" if equilibrado else "NÃO (provável corte)")

# compilação
try:
    r = subprocess.run(["javac", "-d", str(saida / "out")] + [str(saida / n) for n, _ in arquivos],
                       capture_output=True, text=True)
    print("Compilou:", "sim" if r.returncode == 0 else "NÃO")
    if r.returncode != 0:
        print(r.stderr[:3000])
except FileNotFoundError:
    print("javac não encontrado: instale o JDK para testar a compilação.")
