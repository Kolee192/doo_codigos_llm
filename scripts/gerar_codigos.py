"""Envia os prompts a uma API de LLM e salva as respostas.

Uso (exemplos):
    py gerar_codigos.py --provedor gemini --apenas ESP26     # testa com 1 prompt
    py gerar_codigos.py --provedor gemini --limite 10        # os 10 primeiros
    py gerar_codigos.py --provedor deepseek                  # todos os prompts da pasta 'prompts'

Para cada prompt cria, em saida/<provedor>/:
    ESPxx.txt   resposta do modelo (o codigo)
    ESPxx.json  metadados: modelo devolvido pela API, data, motivo de parada, tokens, tempo
Se rodar de novo, pula o que ja existe (e retoma de onde parou).
So usa a biblioteca padrao do Python. A chave vem de uma variavel de ambiente.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROVEDORES = {
    "deepseek": {
        "chave_env": "DEEPSEEK_API_KEY",
        "modelo_padrao": "deepseek-flash",
        "max_tokens_padrao": 100000,
        "pausa_padrao": 0,
    },
    "gemini": {
        "chave_env": "GEMINI_API_KEY",
        "modelo_padrao": "gemini-3.8-flash",
        "max_tokens_padrao": 65536,
        "pausa_padrao": 10,
    },
    "openai": {
        "chave_env": "OPENAI_API_KEY",
        "modelo_padrao": "gpt-6-luna",
        "max_tokens_padrao": 64000,
        "pausa_padrao": 0,
    },
}
CORTE = {"length", "MAX_TOKENS", "incomplete:max_output_tokens"}  # motivos de parada que indicam resposta cortada


def montar_pedido(prov, modelo, prompt, a, chave):
    """Devolve (url, cabecalhos, corpo) no formato de cada provedor."""
    if prov == "deepseek":
        corpo = {"model": modelo, "messages": [{"role": "user", "content": prompt}],
                 "max_tokens": a.max_tokens, "stream": False}
        if a.temperatura is not None:
            corpo["temperature"] = a.temperatura
        return (a.url or "https://api.deepseek.com/chat/completions",
                {"Content-Type": "application/json", "Authorization": f"Bearer {chave}"}, corpo)
    if prov == "openai":
        corpo = {"model": modelo, "input": prompt, "max_output_tokens": a.max_tokens}
        if a.temperatura is not None:
            corpo["temperature"] = a.temperatura
        return (a.url or "https://api.openai.com/v1/responses",
                {"Content-Type": "application/json", "Authorization": f"Bearer {chave}"}, corpo)
    # gemini
    cfg = {"maxOutputTokens": a.max_tokens}
    if a.temperatura is not None:
        cfg["temperature"] = a.temperatura
    corpo = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg}
    return (a.url or f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
            {"Content-Type": "application/json", "x-goog-api-key": chave}, corpo)


def ler_resposta(prov, r):
    """Normaliza a resposta: texto, motivo de parada, modelo, tokens."""
    if prov == "deepseek":
        esc = r["choices"][0]
        uso = r.get("usage", {})
        rac = uso.get("completion_tokens_details", {}).get("reasoning_tokens")
        return {"texto": esc["message"].get("content") or "", "parada": esc.get("finish_reason"),
                "modelo": r.get("model"), "uso": uso, "tokens_entrada": uso.get("prompt_tokens", 0),
                "tokens_saida": uso.get("completion_tokens", 0), "tokens_raciocinio": rac}
    if prov == "openai":
        if r.get("status") == "failed":
            raise RuntimeError(f"Resposta com status 'failed': {r.get('error')}")
        partes = []
        for item in r.get("output") or []:
            if item.get("type") == "message":
                for c in item.get("content") or []:
                    partes.append(c.get("text") or "")  # 'output_text'; recusas ficam sem texto
        uso = r.get("usage", {})
        rac = (uso.get("output_tokens_details") or {}).get("reasoning_tokens")
        if r.get("status") == "incomplete":
            parada = "incomplete:" + str((r.get("incomplete_details") or {}).get("reason"))
        else:
            parada = r.get("status")
        return {"texto": "".join(partes), "parada": parada, "modelo": r.get("model"), "uso": uso,
                "tokens_entrada": uso.get("input_tokens", 0), "tokens_saida": uso.get("output_tokens", 0),
                "tokens_raciocinio": rac}
    cand = (r.get("candidates") or [{}])[0]
    partes = (cand.get("content") or {}).get("parts") or []
    texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
    uso = r.get("usageMetadata", {})
    rac = uso.get("thoughtsTokenCount")
    parada = cand.get("finishReason")
    if not partes and not parada:
        parada = "BLOQUEADO:" + str(r.get("promptFeedback", {}).get("blockReason"))
    # no Gemini os tokens de raciocinio vem separados dos de resposta
    return {"texto": texto, "parada": parada, "modelo": r.get("modelVersion"), "uso": uso,
            "tokens_entrada": uso.get("promptTokenCount", 0),
            "tokens_saida": uso.get("candidatesTokenCount", 0) + (rac or 0), "tokens_raciocinio": rac}


def com_tentativas(url, cab, corpo, timeout, tentativas):
    dados = json.dumps(corpo).encode("utf-8")
    for n in range(1, tentativas + 1):
        req = urllib.request.Request(url, data=dados, headers=cab, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detalhe = e.read().decode("utf-8", errors="replace")[:700]
            if "insufficient_quota" in detalhe or "credit_balance" in detalhe:
                raise RuntimeError(f"Erro 402 (sem saldo ou cota esgotada): {detalhe}")
            # chave errada, sem permissao, sem saldo, modelo ou pedido invalido: repetir nao adianta
            if e.code in (400, 401, 402, 403, 404, 422):
                raise RuntimeError(f"Erro {e.code} da API: {detalhe}")
            espera = (30 if e.code == 429 else 5) * n  # 429 = limite de uso por minuto: espera mais
            print(f"    erro {e.code}, tentando de novo em {espera}s ({n}/{tentativas})")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            espera = 5 * n
            print(f"    falha de rede ({e}), tentando de novo em {espera}s ({n}/{tentativas})")
        time.sleep(espera)
    raise RuntimeError("Desisti depois de varias tentativas.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provedor", default="deepseek", choices=PROVEDORES)
    ap.add_argument("--modelo", help="nome do modelo (padrao: o do provedor)")
    ap.add_argument("--prompts", default="prompts", help="pasta com os prompts")
    ap.add_argument("--saida", default="saida", help="pasta de saida")
    ap.add_argument("--apenas", nargs="+", help="so estes, ex.: ESP26 ESP17")
    ap.add_argument("--limite", type=int, help="so os N primeiros")
    ap.add_argument("--max-tokens", type=int, help="limite de saida (padrao: o do provedor)")
    ap.add_argument("--temperatura", type=float, help="se omitido, nao envia (usa o padrao do modelo)")
    ap.add_argument("--pausa", type=float, help="segundos de espera entre pedidos (padrao: o do provedor)")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--tentativas", type=int, default=3)
    ap.add_argument("--url", help="so para testes locais")
    a = ap.parse_args()

    prov = a.provedor
    cfg = PROVEDORES[prov]
    chave = os.environ.get(cfg["chave_env"])
    if not chave:
        sys.exit(f"Variavel {cfg['chave_env']} nao encontrada. Abra um terminal NOVO depois do setx.")
    modelo = a.modelo or cfg["modelo_padrao"]
    a.max_tokens = a.max_tokens or cfg["max_tokens_padrao"]
    pausa = cfg["pausa_padrao"] if a.pausa is None else a.pausa

    arquivos = sorted(Path(a.prompts).glob("prompt_*.txt"))
    if a.apenas:
        quer = {x.upper() for x in a.apenas}
        arquivos = [p for p in arquivos if p.stem.replace("prompt_", "").upper() in quer]
    if a.limite:
        arquivos = arquivos[: a.limite]
    if not arquivos:
        sys.exit(f"Nenhum prompt encontrado em '{a.prompts}'. Rode o script na pasta que contem 'prompts'.")

    destino = Path(a.saida) / prov
    destino.mkdir(parents=True, exist_ok=True)
    print(f"Provedor: {prov} | modelo: {modelo} | limite de saida: {a.max_tokens} | prompts: {len(arquivos)}")

    cortados, falhas, vazios, total_in, total_out, seguidas = [], [], [], 0, 0, 0
    fez_algum = False
    for i, p in enumerate(arquivos, 1):
        esp = p.stem.replace("prompt_", "")
        if (destino / f"{esp}.txt").exists():
            print(f"[{i}/{len(arquivos)}] {esp}: ja existe, pulando")
            continue
        if fez_algum and pausa:
            time.sleep(pausa)
        fez_algum = True
        url, cab, corpo = montar_pedido(prov, modelo, p.read_text(encoding="utf-8"), a, chave)
        print(f"[{i}/{len(arquivos)}] {esp}: enviando...", flush=True)
        t0 = time.time()
        try:
            r = com_tentativas(url, cab, corpo, a.timeout, a.tentativas)
        except RuntimeError as e:
            print(f"    FALHOU: {e}")
            falhas.append(esp)
            seguidas += 1
            if any(c in str(e) for c in ("Erro 401", "Erro 402", "Erro 403", "Erro 404")) or seguidas >= 3:
                sys.exit("Parei: problema de chave, saldo, modelo ou limite de uso (ver mensagem acima).")
            continue
        seg = round(time.time() - t0, 1)
        try:
            x = ler_resposta(prov, r)
        except RuntimeError as e:
            print(f"    FALHOU: {e}")
            falhas.append(esp)
            seguidas += 1
            if seguidas >= 3:
                sys.exit("Parei: 3 falhas seguidas (ver mensagens acima).")
            continue
        seguidas = 0
        total_in += x["tokens_entrada"]
        total_out += x["tokens_saida"]
        (destino / f"{esp}.txt").write_text(x["texto"], encoding="utf-8")
        meta = {
            "especificacao": esp, "provedor": prov, "modelo_pedido": modelo, "modelo_devolvido": x["modelo"],
            "data_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "motivo_parada": x["parada"], "uso_tokens": x["uso"],
            "tokens_entrada": x["tokens_entrada"], "tokens_saida_total": x["tokens_saida"],
            "tokens_raciocinio": x["tokens_raciocinio"], "segundos": seg,
            "parametros": {k: v for k, v in corpo.items() if k not in ("messages", "contents", "input")},
        }
        (destino / f"{esp}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        aviso = ""
        if x["parada"] in CORTE:
            cortados.append(esp)
            aviso = "  <-- CORTADO (limite de tokens)"
        elif not x["texto"].strip():
            vazios.append(esp)
            aviso = "  <-- RESPOSTA VAZIA"
        print(f"    ok em {seg}s | parada: {x['parada']} | tokens entrada/saida: "
              f"{x['tokens_entrada']}/{x['tokens_saida']}{aviso}")

    print("\nResumo:")
    print(f"  tokens de entrada: {total_in} | de saida: {total_out}")
    if cortados:
        print(f"  respostas CORTADAS: {', '.join(cortados)}")
    if vazios:
        print(f"  respostas VAZIAS: {', '.join(vazios)}")
    if falhas:
        print(f"  falharam: {', '.join(falhas)} (rode de novo para tentar so essas)")
    print(f"  arquivos em: {destino}")


if __name__ == "__main__":
    main()
