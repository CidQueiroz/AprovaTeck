import json
import re
import os
import time
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# Carrega as chaves do OpenRouter
CHAVES = []
for i in range(1, 10):
    k = os.getenv(f"OPENROUTER_API_KEY{i}")
    if k:
        CHAVES.append(k)

if not CHAVES:
    raise ValueError("Nenhuma chave OpenRouter encontrada no .env!")

# Melhores modelos gratuitos do OpenRouter em ordem de prioridade para JSON e Lógica
MODELOS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-coder:free",
    "cohere/north-mini-code:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "poolside/laguna-xs-2.1:free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "google/gemma-4-26b-a4b-it:free"
]

current_key_idx = 0
current_model_idx = 0

def get_current_llm():
    chave = CHAVES[current_key_idx]
    modelo = MODELOS[current_model_idx]
    # O OpenRouter é compatível com a biblioteca da OpenAI
    return ChatOpenAI(
        model_name=modelo,
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=chave,
        temperature=0,
        max_retries=0 # Desativa os retries automáticos da Langchain para rodarmos nossa lógica de troca
    )

def avançar_estrategia():
    global current_key_idx, current_model_idx
    # Tenta o próximo modelo na MESMA chave
    current_model_idx += 1
    if current_model_idx >= len(MODELOS):
        # Se esgotou os modelos, zera os modelos e passa para a PRÓXIMA chave
        current_model_idx = 0
        current_key_idx += 1
        if current_key_idx >= len(CHAVES):
            # Se esgotou as chaves também, reseta tudo e continua (o loop principal cuida do limite de tentativas)
            current_key_idx = 0

def recuperar_json_quebrado(texto_limpo):
    last_brace_idx = texto_limpo.rfind('}')
    while last_brace_idx != -1:
        recuperado = texto_limpo[:last_brace_idx + 1] + "\n  ]\n}"
        try:
            parsed = json.loads(recuperado)
            return parsed
        except json.JSONDecodeError:
            last_brace_idx = texto_limpo.rfind('}', 0, last_brace_idx)
    return []

def texto_para_json_or(texto: str):
    global current_key_idx, current_model_idx
    
    prompt = f"""Você é um parser ultra-rápido de provas de concursos de TI. O texto abaixo é o extrato de uma página inteira de prova.
Seu dever é extrair TODAS as questões dessa página. É esperado que você encontre múltiplas questões.

RETORNE APENAS UM OBJETO JSON VÁLIDO. NÃO INCLUA NENHUM TEXTO ADICIONAL. NENHUMA EXPLICAÇÃO.

Regras de Ouro:
1. Extraia CADA UMA das questões presentes no texto. NÃO pare na primeira. Leia a página até o fim.
2. Para a propriedade "tema" e "banca", preencha SEMPRE com "N/A" para economizar tempo. Não tente adivinhar.
3. Se uma alternativa não existir, preencha com "N/A".
4. Se não encontrar nenhuma questão na página, retorne {{"questoes": []}}.
5. O formato esperado de saída é OBRIGATORIAMENTE o seguinte objeto JSON:
{{
  "questoes": [
    {{
      "tema": "N/A",
      "banca": "N/A",
      "ano": 2024,
      "enunciado": "Texto completo da PRIMEIRA questão encontrada...",
      "alternativas": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
      "gabarito": "..."
    }}
  ]
}}

Texto da Prova:
{texto}
"""

    max_tentativas = len(CHAVES) * len(MODELOS)
    tentativas = 0
    
    while tentativas < max_tentativas:
        tentativas += 1
        try:
            llm = get_current_llm()
            print(f"      [OpenRouter] Chave #{current_key_idx+1}/{len(CHAVES)} | Modelo: {MODELOS[current_model_idx]}")
            
            resposta_obj = llm.invoke(prompt)
            resposta = resposta_obj.content
            
            # Limpeza do JSON
            texto_limpo = resposta.strip()
            if texto_limpo.startswith("```json"): texto_limpo = texto_limpo[7:]
            elif texto_limpo.startswith("```"): texto_limpo = texto_limpo[3:]
            if texto_limpo.endswith("```"): texto_limpo = texto_limpo[:-3]
            texto_limpo = texto_limpo.strip()
            
            match = re.search(r'\[.*\]|\{.*\}', texto_limpo, re.DOTALL)
            if match:
                texto_limpo = match.group(0)

            return json.loads(texto_limpo)
            
        except Exception as e:
            err_str = str(e).lower()
            # O OpenRouter pode retornar 429, 403, Free Limit reached, provider error, etc.
            if "rate limit" in err_str or "429" in err_str or "403" in err_str or "free" in err_str or "provider" in err_str:
                print(f"      [!] Erro capturado: {str(e)[:150]}...")
                avançar_estrategia()
            else:
                try:
                    return recuperar_json_quebrado(texto_limpo)
                except:
                    print(f"      [!] Erro de parsing JSON: {e}")
                    return []
                    
    # SE CHEGOU AQUI: Todas as chaves e todos os modelos bateram o limite (ou cota diária global)
    print("\n[!] TODAS as chaves e modelos do OpenRouter atingiram o limite simultaneamente!")
    print("[!] Alternando para o Ornith 1.5 9B Local para processar esta página...")
    try:
        from langchain_ollama import OllamaLLM
        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0, format="json")
        resp_text = llm_local.invoke(prompt)
        resp = json.loads(resp_text)
        return resp
    except Exception as e_local:
        print(f"      [!] Erro no parsing do Ornith Local: {e_local}")
        return []
