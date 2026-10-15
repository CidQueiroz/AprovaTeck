"""
pdf_parser.py
Usa LLM com fallback chain (Gemini → Groq → Qwen local) para parsear questões
de concurso extraídas de PDFs.

Fallback chain:
  1. Gemini Flash (gemini-2.0-flash) — 7 chaves rotativas
  2. Groq llama-3.3-70b             — 8 chaves rotativas
  3. Qwen2.5-coder:7b (Ollama local) — sem limite, offline
"""

from __future__ import annotations
import os
import json
import re
import random
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# ── Chaves Gemini ──────────────────────────────────────────────────────────────
GEMINI_KEYS = [v.strip() for k, v in os.environ.items() if k.startswith("GEMINI_API_KEY") and v.strip()]

# ── Chaves Groq ────────────────────────────────────────────────────────────────
GROQ_KEYS = [v.strip() for k, v in os.environ.items()
             if (k == "GROQ_API_KEY" or k.startswith("groq_pdf")) and v.strip()]

# ── Ollama local ───────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5-coder:7b"


PROMPT_TEMPLATE = """Você é um especialista em concursos públicos brasileiros.
Analise o trecho de prova abaixo e extraia TODAS as questões de múltipla escolha encontradas.

CONTEXTO (já detectado):
- Banca: {banca}
- Ano: {ano}

TEXTO DA PROVA:
---
{texto}
---

Retorne um JSON válido com uma lista de questões. Para cada questão encontrada, inclua:
- "enunciado": texto completo da pergunta (sem número da questão)
- "alternativa_a": texto da alternativa A
- "alternativa_b": texto da alternativa B  
- "alternativa_c": texto da alternativa C
- "alternativa_d": texto da alternativa D
- "alternativa_e": texto da alternativa E (null se não existir)
- "gabarito": letra do gabarito se visível no texto, senão null
- "banca": "{banca}" (use o contexto fornecido)
- "ano": {ano} (use o contexto fornecido)
- "tema": tema/disciplina da questão (ex: "Direito Constitucional", "Matemática", "Português")
- "grupo": grupo maior (ex: "Direito", "Matemática", "Língua Portuguesa", "Informática")
- "subgrupo": subgrupo específico (ex: "Constitucional", "Aritmética", "Gramática", "Banco de Dados")

REGRAS:
1. Se o texto não contiver questões completas, retorne uma lista vazia: []
2. Ignore questões incompletas (sem enunciado ou sem alternativas)
3. Mantenha o texto das alternativas sem a letra inicial (ex: não inclua "A)" no início)
4. Retorne APENAS o JSON, sem texto antes ou depois
5. Infira o tema com base no conteúdo da questão

JSON:"""


def _extract_json_from_response(text: str) -> list:
    """Extrai o JSON da resposta do LLM, removendo markdown code blocks se necessário."""
    # Remove markdown code blocks
    text = re.sub(r'```(?:json)?\s*', '', text).strip()
    text = text.strip('`').strip()

    # Tenta encontrar o array JSON na resposta
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        text = match.group(0)

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        # Às vezes o LLM retorna {"questoes": [...]}
        if isinstance(data, dict):
            for key in ['questoes', 'questions', 'items', 'data']:
                if key in data and isinstance(data[key], list):
                    return data[key]
    except json.JSONDecodeError:
        pass

    return []


# ── Provider: Gemini ───────────────────────────────────────────────────────────

def _try_gemini(prompt: str):
    """Tenta parsear com Gemini Flash usando chaves rotativas."""
    if not GEMINI_KEYS:
        return None

    keys = random.sample(GEMINI_KEYS, len(GEMINI_KEYS))  # embaralha para distribuir carga

    for key in keys:
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 8192},
            )
            text = response.text
            result = _extract_json_from_response(text)
            if result is not None:
                print(f"    [Gemini Flash] OK — {len(result)} questões extraídas")
                return result
        except Exception as e:
            err_msg = str(e)
            if "quota" in err_msg.lower() or "429" in err_msg or "rate" in err_msg.lower():
                print(f"    [Gemini] Chave com rate limit, tentando próxima...")
                continue
            print(f"    [Gemini] Erro: {err_msg[:100]}")
            continue

    print("    [Gemini] Todas as chaves falharam.")
    return None


# ── Provider: Groq ─────────────────────────────────────────────────────────────

def _try_groq(prompt: str):
    """Tenta parsear com Groq llama-3.3-70b usando chaves rotativas."""
    if not GROQ_KEYS:
        return None

    keys = random.sample(GROQ_KEYS, len(GROQ_KEYS))

    for key in keys:
        try:
            from groq import Groq
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=8000,
            )
            text = response.choices[0].message.content
            result = _extract_json_from_response(text)
            if result is not None:
                print(f"    [Groq llama-3.3] OK — {len(result)} questões extraídas")
                return result
        except Exception as e:
            err_msg = str(e)
            if "rate_limit" in err_msg.lower() or "429" in err_msg:
                print(f"    [Groq] Rate limit, tentando próxima chave...")
                continue
            print(f"    [Groq] Erro: {err_msg[:100]}")
            continue

    print("    [Groq] Todas as chaves falharam.")
    return None


# ── Provider: Ollama (Qwen local) ──────────────────────────────────────────────

def _try_qwen_local(prompt: str):
    """Fallback final: Qwen2.5-coder local via Ollama."""
    try:
        import requests
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 4096},
            },
            timeout=120,
        )
        response.raise_for_status()
        text = response.json().get("response", "")
        result = _extract_json_from_response(text)
        if result is not None:
            print(f"    [Qwen local] OK — {len(result)} questões extraídas")
            return result
    except Exception as e:
        print(f"    [Qwen local] Erro: {str(e)[:100]}")

    return None


# ── Interface pública ──────────────────────────────────────────────────────────

def parse_chunk(texto_chunk: str, banca: str = "N/A", ano: int = 0) -> list:
    """
    Parseia um chunk de texto usando fallback chain: Gemini → Groq → Qwen local.

    Returns:
        Lista de dicts com as questões extraídas.
    """
    prompt = PROMPT_TEMPLATE.format(
        banca=banca or "N/A",
        ano=ano or "não identificado",
        texto=texto_chunk,
    )

    # Chain de fallback
    for provider_fn, name in [
        (_try_gemini, "Gemini Flash"),
        (_try_groq, "Groq llama-3.3-70b"),
        (_try_qwen_local, "Qwen2.5 local"),
    ]:
        print(f"  → Tentando {name}...")
        result = provider_fn(prompt)
        if result is not None:
            return result

    print("  ⚠️  Todos os providers falharam para este chunk.")
    return []


def parse_pdf_text(texto_bruto: str, banca: str = "N/A", ano: int = 0,
                   chunk_size: int = 6000) -> list:
    """
    Parseia o texto completo de um PDF, dividindo em chunks se necessário.

    Returns:
        Lista consolidada de todas as questões extraídas.
    """
    from pdf_extractor import split_into_chunks

    chunks = split_into_chunks(texto_bruto, chunk_size=chunk_size)
    print(f"  [Parser] Processando {len(chunks)} chunk(s) com banca={banca}, ano={ano}")

    todas_questoes = []
    enunciados_vistos = set()

    for i, chunk in enumerate(chunks, 1):
        print(f"\n  [Chunk {i}/{len(chunks)}]")
        questoes = parse_chunk(chunk, banca=banca, ano=ano)

        for q in questoes:
            enunciado = q.get("enunciado", "").strip()
            if not enunciado or len(enunciado) < 20:
                continue
            # Deduplicação leve dentro do mesmo PDF (primeiros 100 chars)
            key = enunciado[:100].lower()
            if key not in enunciados_vistos:
                enunciados_vistos.add(key)
                todas_questoes.append(q)

    print(f"\n  [Parser] Total extraído do PDF: {len(todas_questoes)} questões únicas")
    return todas_questoes
