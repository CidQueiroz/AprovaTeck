import json
import re
import os
import sys

# Adiciona o diretório raiz ao sys.path para permitir imports absolutos (ex: backend.prompts...)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM

load_dotenv()

# ==========================================
# 1. SETUP GROQ (Camada 1 - Extrema Velocidade)
# ==========================================
CHAVES_GROQ = []
for key_name in ["GROQ_API_KEY", "groq_pdf1", "groq_pdf2", "groq_pdf3", "groq_pdf4"]:
    chave = os.getenv(key_name)
    if chave: CHAVES_GROQ.append(chave)

idx_groq = 0

def get_groq_llm():
    if not CHAVES_GROQ: return None
    return ChatGroq(
        model="gpt-oss-120b",
        temperature=0,
        api_key=CHAVES_GROQ[idx_groq],
        max_retries=0
    )

def avancar_groq():
    global idx_groq
    idx_groq += 1
    if idx_groq >= len(CHAVES_GROQ):
        idx_groq = 0
        return False
    return True

# ==========================================
# 2. SETUP OPENROUTER (Camada 2 - Alta Velocidade)
# ==========================================
CHAVES_OR = []
for i in range(1, 10):
    k = os.getenv(f"OPENROUTER_API_KEY{i}")
    if k: CHAVES_OR.append(k)

MODELOS_OR = [
    "poolside/laguna-m.1:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "qwen/qwen3-coder:free"
]

idx_or_key = 0
idx_or_model = 0

def get_openrouter_llm():
    if not CHAVES_OR: return None
    return ChatOpenAI(
        model_name=MODELOS_OR[idx_or_model],
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=CHAVES_OR[idx_or_key],
        temperature=0,
        max_retries=0
    )

def avancar_openrouter():
    global idx_or_key, idx_or_model
    idx_or_model += 1
    if idx_or_model >= len(MODELOS_OR):
        idx_or_model = 0
        idx_or_key += 1
        if idx_or_key >= len(CHAVES_OR):
            idx_or_key = 0
            return False
    return True

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def recuperar_json_quebrado(texto_limpo):
    last_brace_idx = texto_limpo.rfind('}')
    while last_brace_idx != -1:
        recuperado = texto_limpo[:last_brace_idx + 1] + "\n  ]\n}"
        try:
            return json.loads(recuperado)
        except json.JSONDecodeError:
            last_brace_idx = texto_limpo.rfind('}', 0, last_brace_idx)
    return []

def extrair_json_da_string(resposta):
    texto_limpo = resposta.strip()
    if texto_limpo.startswith("```json"): texto_limpo = texto_limpo[7:]
    elif texto_limpo.startswith("```"): texto_limpo = texto_limpo[3:]
    if texto_limpo.endswith("```"): texto_limpo = texto_limpo[:-3]
    texto_limpo = texto_limpo.strip()
    
    match = re.search(r'\[.*\]|\{.*\}', texto_limpo, re.DOTALL)
    if match:
        texto_limpo = match.group(0)
    
    try:
        return json.loads(texto_limpo)
    except Exception as e:
        return recuperar_json_quebrado(texto_limpo)

# ==========================================
# MOTOR PRINCIPAL (God Mode)
# ==========================================
def texto_para_json_master(texto: str):
    from backend.prompts.ingestao import get_prompt_pdf_extracao
    prompt = get_prompt_pdf_extracao(texto)
    # ---------------------------------------------------------
    # CAMADA 1: GROQ
    # ---------------------------------------------------------
    if CHAVES_GROQ:
        tentativas_groq = len(CHAVES_GROQ)
        for _ in range(tentativas_groq):
            try:
                llm = get_groq_llm()
                print(f"      [Camada 1: Groq] Tentando Chave #{idx_groq+1}")
                resp = llm.invoke(prompt)
                avancar_groq() # Força a rotação (Round-Robin) para distribuir carga
                return extrair_json_da_string(resp.content)
            except Exception as e:
                err = str(e).lower()
                if "rate_limit" in err or "429" in err:
                    if not avancar_groq():
                        print("      [!] Groq esgotado globalmente neste ciclo.")
                        break
                else:
                    print(f"      [!] Erro no Groq: {e}")
                    break

    # ---------------------------------------------------------
    # CAMADA 2: OPENROUTER
    # ---------------------------------------------------------
    if CHAVES_OR:
        tentativas_or = len(CHAVES_OR) * len(MODELOS_OR)
        for _ in range(tentativas_or):
            try:
                llm = get_openrouter_llm()
                print(f"      [Camada 2: OpenRouter] Chave #{idx_or_key+1} | Modelo: {MODELOS_OR[idx_or_model]}")
                resp = llm.invoke(prompt)
                avancar_openrouter() # Força a rotação (Round-Robin) para distribuir carga
                return extrair_json_da_string(resp.content)
            except Exception as e:
                err = str(e).lower()
                if "rate limit" in err or "429" in err or "403" in err or "free" in err or "provider" in err:
                    if not avancar_openrouter():
                        print("      [!] OpenRouter esgotado globalmente neste ciclo.")
                        break
                else:
                    print(f"      [!] Erro no OpenRouter: {e}")
                    break

    # ---------------------------------------------------------
    # CAMADA 3: LOCAL ORNITH 1.5 9B
    # ---------------------------------------------------------
    print("\n      [Camada 3: Local] ATIVANDO MODO OFFLINE (Ornith 1.5 9B)")
    print("      [!] A nuvem bloqueou. O processador local assumiu a extração.")
    try:
        # IMPORTANTE: format="json" removido pois causa um gargalo extremo de processamento na CPU
        # Adicionado num_ctx=8192 para garantir que o modelo consiga ler a página inteira sem truncar!
        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0, num_ctx=8192)
        resp_text = llm_local.invoke(prompt)
        return extrair_json_da_string(resp_text)
    except Exception as e_local:
        print(f"      [!] Falha Catastrófica no Local: {e_local}")
        return []
