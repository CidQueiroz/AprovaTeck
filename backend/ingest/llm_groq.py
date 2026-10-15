import json
import re
import os
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

# Carrega as chaves do .env
CHAVES = []
for key_name in ["GROQ_API_KEY", "groq_pdf1", "groq_pdf2", "groq_pdf3", "groq_pdf4"]:
    chave = os.getenv(key_name)
    if chave:
        CHAVES.append(chave)

if not CHAVES:
    raise ValueError("Nenhuma chave Groq encontrada no .env!")

# Variável global para rastrear qual chave está sendo usada no momento
current_key_idx = 0

def get_current_llm():
    global current_key_idx
    chave = CHAVES[current_key_idx]
    # Llama 3 70B ou 8B. O 8B é absurdamente mais rápido para parsing, mas o 70B é mais assertivo. 
    # Como queremos altíssima velocidade e a tarefa é só extração, podemos usar o 70b-versatile ou 8b-instant.
    return ChatGroq(model_name="gpt-oss-120b", temperature=0, api_key=chave)

def alternar_chave():
    global current_key_idx
    current_key_idx = (current_key_idx + 1) % len(CHAVES)
    print(f"\n[!] Rate Limit atingido! Alternando para a chave Groq #{current_key_idx + 1}...")

def texto_para_json_groq(texto: str):
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

    max_tentativas = len(CHAVES) + 1
    tentativa = 0
    
    while tentativa < max_tentativas:
        try:
            llm = get_current_llm()
            resposta_obj = llm.invoke(prompt)
            resposta = resposta_obj.content
            
            # Limpeza
            texto_limpo = resposta.strip()
            if texto_limpo.startswith("```json"):
                texto_limpo = texto_limpo[7:]
            elif texto_limpo.startswith("```"):
                texto_limpo = texto_limpo[3:]
            if texto_limpo.endswith("```"):
                texto_limpo = texto_limpo[:-3]
                
            texto_limpo = texto_limpo.strip()
            
            match = re.search(r'\[.*\]|\{.*\}', texto_limpo, re.DOTALL)
            if match:
                texto_limpo = match.group(0)

            return json.loads(texto_limpo)
            
        except Exception as e:
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str:
                tentativa += 1
                alternar_chave()
                if tentativa == max_tentativas:
                    print("\n[!] Todas as chaves do Groq estouraram o limite por minuto!")
                    print("[!] Alternando para o Ornith 1.5 9B Local para processar esta página (enquanto a cota da nuvem reseta)...")
                    try:
                        from langchain_ollama import OllamaLLM
                        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0, format="json")
                        resp_text = llm_local.invoke(prompt)
                        resp = json.loads(resp_text)
                        
                        # O tempo que o Ornith demorou pra rodar localmente (3-4 min) é mais que suficiente 
                        # para as cotas do Groq (60s) resetarem sozinhas!
                        return resp
                    except Exception as e_local:
                        print(f"Erro no parsing do Ornith Local: {e_local}")
                        return []
            else:
                # Erro de parsing JSON
                try:
                    return recuperar_json_quebrado(texto_limpo)
                except:
                    print(f"Erro no parsing JSON: {e}")
                    return []
                    
    return []

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
