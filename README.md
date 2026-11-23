# Qualidade de código Java gerado por LLMs a partir de especificações de sistemas orientados a objetos

Trabalho final da disciplina **DOO – INF03068** (Prof. Filipe Fernandes, Ph.D.).
Autor: **[SEU NOME]**

Este repositório reúne todos os artefatos do experimento: especificações, prompts, respostas dos modelos, códigos Java, scripts, métricas e resultados estatísticos. O método adapta o de Oliveira et al. (2025), *Avaliação de Qualidade de Código Java gerado por Large Language Models* (ERES 2025, DOI 10.5753/eres.2025.16845), trocando os problemas do LeetCode por especificações de sistemas orientados a objetos e incluindo métricas de orientação a objetos.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `especificacoes/` | 30 especificações (ESP01 a ESP30), em texto |
| `planilha_origens.csv` | Origem, formato, link e licença de cada especificação |
| `prompt_template.txt` | Texto do prompt (zero-shot) com o marcador `{SPEC}` |
| `prompts/` | Os 30 prompts finais, já montados |
| `respostas_llm/<modelo>/` | Resposta bruta de cada modelo a cada prompt (89 arquivos) |
| `metadados_geracao.csv` | Modelo devolvido pela API, data, motivo de parada, tokens e tempo de cada geração |
| `codigos_java.zip` | Respostas separadas em arquivos `.java`, mais o resultado da compilação |
| `scripts/` | Geração de prompts e códigos, compilação, medição e análise |
| `resultados/` | Métricas por resposta, por método e por tipo, relatórios do PMD, estatísticas e figuras |

## Dados

- **Fontes das especificações:** conjunto de histórias de usuário de Dalpiaz (*Requirements data sets (user stories)*, Mendeley Data, v2, DOI 10.17632/7zbk8zsd8y.2) para ESP01 a ESP15, e o *Software Requirements Data Set* (Zenodo, registro 7897601, que reúne documentos do PURE, Zenodo 7118517, e outros) para ESP16 a ESP30.
- **Critério de seleção:** foram excluídos os conjuntos em que a maioria das histórias descreve tarefas de projeto ou papéis técnicos, e não funcionalidades para usuários do sistema, além de sistemas embarcados ou de hardware.
- **Licenças:** os textos pertencem aos autores originais. A página do conjunto de Dalpiaz informa que o curador não conhece acordos de licença sobre os dados. Consulte `planilha_origens.csv` antes de reutilizar.

## Modelos e configuração

| Modelo (nome devolvido pela API) | Limite de saída | Período de geração (UTC) |
|---|---|---|
| `deepseek-flash` | 100.000 tokens | 21/11/2026 |
| `gemini-3.8-flash` | 65.536 tokens | 21 a 22/11/2026 |
| `gpt-6-luna` | 64.000 tokens | 22/11/2026 |

Todas as gerações usaram a API de cada provedor, com os parâmetros padrão (sem temperatura nem esforço de raciocínio definidos), uma geração por especificação. O Gemini tem 29 respostas: a ESP29 não foi obtida por indisponibilidade do servidor (erro 503 persistente).

## Como reproduzir

Requisitos: Python 3, JDK 17 e PMD 7.29.0. As chaves de API ficam em variáveis de ambiente (`DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`) e **nunca** devem ser versionadas.

1. Gerar os prompts: `python scripts/gerar_prompts.py especificacoes` (usa `prompt_template.txt`).
2. Gerar os códigos: `python scripts/gerar_codigos.py --provedor deepseek` (também `gemini` e `openai`).
3. Separar, compilar e medir: `python scripts/medir.py` (compila com `--release 17` e roda o PMD com `scripts/regras_metricas.xml`).
4. Análise: `scripts/le_pmd.py`, `scripts/Metricas.java` (NOM, NPM e LCOM), `scripts/agrega.py`, `scripts/estat.py` e `scripts/graficos.py`. Esses scripts têm caminhos do ambiente em que rodaram e precisam de ajuste.

## Resultados (resumo)

**Compilação (JDK 17)**

| Modelo | Respostas que compilam |
|---|---|
| DeepSeek | 26/30 |
| Gemini | 25/29 |
| OpenAI | 22/30 |

**Medianas por modelo e teste de Friedman (calculados sobre as 29 especificações comuns aos três modelos)**

| Métrica | DeepSeek | Gemini | OpenAI | p |
|---|---|---|---|---|
| Ciclomática média por método | 1,67 | 1,58 | 1,83 | 0,005 |
| Cognitiva média por método | 0,70 | 0,65 | 0,78 | 0,485 |
| NOM total | 232 | 205 | 137 | < 0,001 |
| NOM médio por tipo | 8,1 | 8,8 | 11,5 | 0,001 |
| LCOM-HS médio | 0,73 | 0,75 | 0,86 | 0,001 |
| Proporção de métodos públicos | 0,96 | 0,99 | 0,86 | < 0,001 |
| Linhas de código | 1537 | 1607 | 1072 | < 0,001 |

As definições das métricas, os testes dois a dois (Wilcoxon pareado, correção de Holm) e as análises de sensibilidade estão em `resultados/`.

## Limitações

- Uma única geração por especificação e modelo, sem repetições.
- Configurações padrão de cada provedor; o DeepSeek raciocina por padrão e usou bem mais tokens de raciocínio que os demais.
- Dois formatos de especificação misturados (histórias de usuário e documentos de requisitos).
- O LCOM-HS é calculado por análise sintática, sem resolução de símbolos.
- Um arquivo do Gemini (ESP24, `DHWebServer.java`) não foi lido pelo PMD por erro de sintaxe.

## Licença

Código e scripts: **[A DEFINIR PELO AUTOR]**. Os dados de entrada mantêm as licenças de origem.
