"""Gera os prompts: junta o template com cada especificação (.txt).

Uso:
    python gerar_prompts.py PASTA_DAS_ESPECIFICACOES [arquivo1.txt arquivo2.txt ...]

Sem lista de arquivos, usa todos os .txt da pasta.
Os prompts saem na pasta 'prompts/', um arquivo por especificação.
"""
import sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit(__doc__)

pasta = Path(sys.argv[1])
template = Path(__file__).with_name("prompt_template.txt").read_text(encoding="utf-8")
nomes = sys.argv[2:] or sorted(p.name for p in pasta.glob("*.txt"))

saida = Path("prompts")
saida.mkdir(exist_ok=True)

for nome in nomes:
    spec = (pasta / nome).read_text(encoding="utf-8", errors="replace").strip()
    prompt = template.replace("{SPEC}", spec)
    destino = saida / f"prompt_{Path(nome).stem}.txt"
    destino.write_text(prompt, encoding="utf-8")
    print(f"{destino}  ({len(spec.splitlines())} histórias, {len(prompt)} caracteres)")
