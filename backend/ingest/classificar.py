import sqlite3
import json
import time
import os
import sys
import re
import difflib
import concurrent.futures
import threading

# Adiciona o diretório raiz ao sys.path para permitir imports absolutos (ex: backend.prompts...)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from dotenv import load_dotenv
import warnings
from langchain_core._api.deprecation import LangChainDeprecationWarning
warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)

from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM
from backend.prompts.classificacao import get_prompt_classificacao

load_dotenv()

# Locks e Variáveis Globais para controle multi-thread
llm_lock = threading.RLock()
current_llm_index = 0
cooldowns = {}
cooldowns_file = "data/cooldowns.json"
concluidas_global = 0
total_questoes = 0

def load_cooldowns():
    global cooldowns
    if os.path.exists(cooldowns_file):
        try:
            with open(cooldowns_file, "r") as f:
                cooldowns = json.load(f)
            # Remove chaves que já saíram do cooldown
            agora = time.time()
            cooldowns = {k: v for k, v in cooldowns.items() if v > agora}
        except Exception as e:
            print(f"[AVISO] Erro ao carregar cooldowns.json: {e}")
            cooldowns = {}

def save_cooldowns():
    with llm_lock:
        try:
            with open(cooldowns_file, "w") as f:
                json.dump(cooldowns, f)
        except Exception as e:
            print(f"[AVISO] Erro ao salvar cooldowns.json: {e}")

llm_pool = []
# 1. Groq models (ignorando GROQ_API_KEY que é pro app.py)
for i in range(1, 9):
    k = os.getenv(f"groq_pdf{i}")
    if k:
        key_id = f"Groq_Key_{i}"
        llm_pool.append({
            "name": f"Groq (Chave {i})",
            "key_id": key_id,
            "llm": ChatGroq(model_name="gpt-oss-120b", temperature=0, api_key=k, timeout=30, max_retries=0)
        })

# 2. OpenRouter models
modelos_or = [
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "qwen/qwen3-coder:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "poolside/laguna-m.1:free",
    "tencent/hy3:free",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
    "cohere/north-mini-code:free"
]

for i in range(1, 10):
    k = os.getenv(f"OPENROUTER_API_KEY{i}")
    if k:
        key_id = f"OpenRouter_Key_{i}"
        for m in modelos_or:
            llm_pool.append({
                "name": f"OpenRouter (Chave {i} | {m})",
                "key_id": key_id,
                "llm": ChatOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=k,
                    model=m,
                    temperature=0,
                    timeout=30,
                    max_retries=0
                )
            })

print(f"[*] Total de LLMs no pool: {len(llm_pool)}")

llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0)

def get_next_available_llm():
    global current_llm_index
    agora = time.time()
    
    with llm_lock:
        tentativas = 0
        while tentativas < len(llm_pool):
            llm_info = llm_pool[current_llm_index]
            key_id = llm_info['key_id']
            
            if cooldowns.get(key_id, 0) > agora:
                current_llm_index = (current_llm_index + 1) % len(llm_pool)
                tentativas += 1
                continue
                
            return llm_info
            
        return None # Todas as chaves em cooldown

def processar_questao(args):
    q_id, enunciado, a, b, c, d, e, lista_grupos, nomes_grupos_edital, placeholders_g = args
    agora_log = time.strftime("%H:%M:%S")
    
    alternativas = f"A) {a}\nB) {b}\nC) {c}\nD) {d}\nE) {e}"
    prompt = get_prompt_classificacao(enunciado, alternativas, lista_grupos)
    
    resp = None
    tentativas_llm = 0
    max_tentativas = 3 # Limitar tentativas para não ficar num loop infinito caso os LLMs fiquem falhando sem dar 429
    
    while tentativas_llm < max_tentativas:
        llm_info = get_next_available_llm()
        if not llm_info:
            break # Cai pro local
            
        try:
            resp_text = llm_info["llm"].invoke(prompt).content
            
            texto_limpo = resp_text.strip()
            if texto_limpo.startswith("```json"): texto_limpo = texto_limpo[7:]
            elif texto_limpo.startswith("```"): texto_limpo = texto_limpo[3:]
            if texto_limpo.endswith("```"): texto_limpo = texto_limpo[:-3]
            texto_limpo = texto_limpo.strip()
            
            match = re.search(r'\[.*\]|\{.*\}', texto_limpo, re.DOTALL)
            if match:
                texto_limpo = match.group(0)
            resp = json.loads(texto_limpo)
            
            if resp and (resp.get("grupo_escolhido") or resp.get("group_escolhido")):
                with llm_lock:
                    global current_llm_index
                    current_llm_index = (current_llm_index + 1) % len(llm_pool)
                break
        except Exception as err:
            err_msg = str(err).replace("\n", " ")[:150]
            with llm_lock:
                key_id = llm_info['key_id']
                # Precisamos checar novamente se a chave não foi banida por outra thread nos últimos milisegundos
                if cooldowns.get(key_id, 0) <= time.time():
                    if any(x in err_msg for x in ["429", "Rate limit", "temporarily rate-limited", "404", "unavailable", "exceeded"]):
                        if "temporarily rate-limited" in err_msg:
                            print(f"[{agora_log}] [!] {key_id} esgotou temporariamente. Cooldown 60s")
                            cooldowns[key_id] = time.time() + 60
                        else:
                            print(f"[{agora_log}] [!] {key_id} indisponível (404/429). Cooldown 24h")
                            cooldowns[key_id] = time.time() + 600
                        save_cooldowns()
                    else:
                        print(f"[{agora_log}] [!] {llm_info['name']} falhou ({err_msg}). Trocando...")
                current_llm_index = (current_llm_index + 1) % len(llm_pool)
            tentativas_llm += 1
            time.sleep(1)

    # Se nuvem falhou, tenta local
    if not resp or not (resp.get("grupo_escolhido") or resp.get("group_escolhido")):
        print(f"[{agora_log}] [AVISO] Todas as chaves falharam na Q{q_id}. Usando Ornith 1.5 9B Local...")
        try:
            resp_text = llm_local.invoke(prompt)
            texto_limpo = resp_text.strip()
            if texto_limpo.startswith("```json"): texto_limpo = texto_limpo[7:]
            elif texto_limpo.startswith("```"): texto_limpo = texto_limpo[3:]
            if texto_limpo.endswith("```"): texto_limpo = texto_limpo[:-3]
            texto_limpo = texto_limpo.strip()
            
            match = re.search(r'\[.*\]|\{.*\}', texto_limpo, re.DOTALL)
            if match:
                texto_limpo = match.group(0)
            resp = json.loads(texto_limpo)
        except:
            resp = {}

    grupo = resp.get("grupo_escolhido") or resp.get("group_escolhido") or resp.get("grupo") or resp.get("group")
    tema = resp.get("subgrupo_sugerido") or resp.get("subgroup_sugerido") or resp.get("subgrupo") or resp.get("tema") or resp.get("subgroup")
    banca = resp.get("banca_sugerida") or resp.get("banca") or "N/A"
    
    # Atualiza contador global de forma segura
    global concluidas_global, total_questoes
    with llm_lock:
        concluidas_global += 1
        faltam = total_questoes - concluidas_global

    # Processo de validação e salvamento no BD
    try:
        conn_thread = sqlite3.connect("data/bancos/db_novo.sqlite", timeout=15.0)
        cur_thread = conn_thread.cursor()
        
        if not grupo or str(grupo).strip().upper() in ["N/A", "NÃO CLASSIFICADO", "DESCONHECIDO", "DESCARTAR", "FORA DO EDITAL"]:
            cur_thread.execute("UPDATE questoes SET valida = -1 WHERE id = ?", (q_id,))
            conn_thread.commit()
            print(f"[{agora_log}] [AVISO] Q{q_id} -> FORA DO EDITAL ('{grupo}') | Faltam: {faltam}")
            return
            
        if not tema or str(tema).strip().upper() in ["N/A", "NÃO CLASSIFICADO", "DESCONHECIDO", "DESCARTAR", "NONE", "FORA DO EDITAL"]:
            cur_thread.execute("UPDATE questoes SET valida = -1 WHERE id = ?", (q_id,))
            conn_thread.commit()
            print(f"[{agora_log}] [AVISO] Q{q_id} -> Tema FORA DO EDITAL ('{tema}') | Faltam: {faltam}")
            return

        cur_thread.execute(f"SELECT id, nome FROM grupos WHERE nome IN ({placeholders_g})", nomes_grupos_edital)
        todas_linhas_g = cur_thread.fetchall()
        nomes_g = [t[1] for t in todas_linhas_g]
        
        match_g = next((t for t in todas_linhas_g if t[1].strip().lower() == str(grupo).strip().lower()), None)
        
        if match_g:
            g_id = match_g[0]
            grupo_final = match_g[1]
        else:
            similares_g = difflib.get_close_matches(str(grupo).lower(), [n.lower() for n in nomes_g], n=1, cutoff=0.35)
            if similares_g:
                grupo_final = next(n for n in nomes_g if n.lower() == similares_g[0])
                g_id = next(t[0] for t in todas_linhas_g if t[1] == grupo_final)
            else:
                cur_thread.execute("UPDATE questoes SET valida = -1 WHERE id = ?", (q_id,))
                conn_thread.commit()
                print(f"[{agora_log}] [AVISO] Q{q_id} -> Grupo inaceitável '{grupo}'. Marcando Fora do Edital. | Faltam: {faltam}")
                return

        # Valida o SUBGRUPO
        cur_thread.execute("SELECT id, nome FROM subgrupos WHERE grupo_id = ?", (g_id,))
        todas_linhas_s = cur_thread.fetchall()
        
        match_s = next((t for t in todas_linhas_s if t[1].strip().lower() == str(tema).strip().lower()), None)
        
        if match_s:
            novo_sub_id = match_s[0]
            tema_final = match_s[1]
        else:
            similares_s = difflib.get_close_matches(str(tema).lower(), [t[1].lower() for t in todas_linhas_s], n=1, cutoff=0.4)
            if similares_s:
                tema_final = next(t[1] for t in todas_linhas_s if t[1].lower() == similares_s[0])
                novo_sub_id = next(t[0] for t in todas_linhas_s if t[1] == tema_final)
            else:
                cur_thread.execute("UPDATE questoes SET valida = -1 WHERE id = ?", (q_id,))
                conn_thread.commit()
                print(f"[{agora_log}] [AVISO] Q{q_id} -> Subgrupo '{tema}' inaceitável para {grupo_final}. Marcando Fora do Edital. | Faltam: {faltam}")
                return
                
        cur_thread.execute("UPDATE questoes SET subgrupo_id = ?, banca = ?, valida = 1 WHERE id = ?", (novo_sub_id, banca, q_id))
        conn_thread.commit()
        print(f"[{agora_log}] [OK] Q{q_id} -> [{grupo_final}] {tema_final} | Faltam: {faltam}")
    
    except Exception as e:
        print(f"[{agora_log}] [ERRO BANCO] Q{q_id} -> {e} | Faltam: {faltam}")
    finally:
        if 'conn_thread' in locals():
            conn_thread.close()

def main():
    load_cooldowns()
    
    conn = sqlite3.connect("data/bancos/db_novo.sqlite")
    cur = conn.cursor()
    
    with open('data/resumos/mapa_mental.json', 'r', encoding='utf-8') as f:
        edital_data = json.load(f)
        
    arvore_str = "GRUPOS E SUBGRUPOS (Use EXATAMENTE estes nomes):\n"
    nomes_grupos_edital = []
    for item in edital_data['conteudo']:
        g = item['grupo'].strip()
        nomes_grupos_edital.append(g)
        arvore_str += f"- {g}\n"
        for s in item['subgrupos']:
            arvore_str += f"  * {s.strip()}\n"
            
    lista_grupos = arvore_str
            
    placeholders_g = ','.join('?' * len(nomes_grupos_edital))
    cur.execute(f"SELECT id FROM grupos WHERE nome IN ({placeholders_g})", nomes_grupos_edital)
    ids_grupos_edital = [str(row[0]) for row in cur.fetchall()]
    
    if ids_grupos_edital:
        placeholders_g2 = ','.join('?' * len(ids_grupos_edital))
        query = f"""
            SELECT q.id, q.enunciado, q.alternativa_a, q.alternativa_b, q.alternativa_c, q.alternativa_d, q.alternativa_e 
            FROM questoes q
            LEFT JOIN subgrupos s ON q.subgrupo_id = s.id
            WHERE s.grupo_id NOT IN ({placeholders_g2}) OR q.subgrupo_id IS NULL OR q.valida = 0 OR q.valida IS NULL
        """
        cur.execute(query, ids_grupos_edital)
    else:
        print("Erro: Nenhum grupo do edital encontrado no banco!")
        conn.close()
        return
        
    questoes = cur.fetchall()
    conn.close()
    
    if not questoes:
        print("✅ Todas as questões já estão perfeitamente classificadas no novo Edital!")
        return
        
    global total_questoes
    total_questoes = len(questoes)
        
    print(f"🎯 Encontradas {total_questoes} questões aguardando reclassificação.")
    print(f"🚀 Iniciando classificação paralela (15 workers) com Pool de {len(llm_pool)} modelos na Nuvem...")
    
    args_list = []
    for q_id, enunciado, a, b, c, d, e in questoes:
        args_list.append((q_id, enunciado, a, b, c, d, e, lista_grupos, nomes_grupos_edital, placeholders_g))
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(processar_questao, arg) for arg in args_list]
        concluidas = 0
        total = len(args_list)
        for future in concurrent.futures.as_completed(futures):
            concluidas += 1
            if concluidas % 20 == 0 or concluidas == total:
                print(f"📊 Progresso: {concluidas}/{total} ({(concluidas/total)*100:.1f}%)")

    print("✨ Processo de reclassificação finalizado.")

if __name__ == "__main__":
    main()
