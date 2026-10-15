import os
import json
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM
from langchain_google_genai import ChatGoogleGenerativeAI

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

load_dotenv()

def _get_chunk_text(chunk):
    c = chunk.content if hasattr(chunk, "content") else chunk
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        res = ""
        for item in c:
            if isinstance(item, dict) and "text" in item:
                res += item["text"]
            elif isinstance(item, str):
                res += item
        return res
    return str(c) if c is not None else ""

def get_llm_pool(temperature=0.1, json_mode=False, prefer_gemini=False):
    groq_pool = []
    gemini_pool = []
    openrouter_pool = []
    
    user_groq_key = st.session_state.get("user_groq_key") if HAS_STREAMLIT and hasattr(st, "session_state") else None
    user_gemini_key = st.session_state.get("user_gemini_key") if HAS_STREAMLIT and hasattr(st, "session_state") else None
    
    # 1. Chave Principal do App (Groq)
    k_main = user_groq_key if user_groq_key else os.getenv("GROQ_API_KEY")
    if k_main:
        kwargs = {"model_name": "gpt-oss-120b", "temperature": temperature, "api_key": k_main}
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        groq_pool.append({
            "name": "Groq Principal (BYOK)" if user_groq_key else "Groq Principal",
            "llm": ChatGroq(**kwargs)
        })
        
    # 2. Gemini Fallbacks
    if user_gemini_key:
        gemini_pool.append({
            "name": "Gemini (BYOK)",
            "llm": ChatGoogleGenerativeAI(
                model="gemini-3.5-flash", 
                temperature=temperature, 
                google_api_key=user_gemini_key,
                max_retries=1
            )
        })
    else:
        for i in ["1", "2", "3", "4", "5", "6", "7", "8"]:
            k = os.getenv(f"GEMINI_API_KEY{i}")
            if k:
                gemini_pool.append({
                    "name": f"Gemini (Chave {i if i else 'Base'})",
                    "llm": ChatGoogleGenerativeAI(
                        model="gemini-3.5-flash", 
                        temperature=temperature, 
                        google_api_key=k,
                        max_retries=1
                    )
                })
        
    # 3. OpenRouter Fallbacks (Gemini Free e Llama Free)
    modelos_or = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "nvidia/llama-3.1-nemotron-70b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "deepseek/deepseek-r1-distill-llama-70b:free"
    ]
    for i in range(1, 10):
        k = os.getenv(f"OPENROUTER_API_KEY{i}")
        if k:
            for m in modelos_or:
                openrouter_pool.append({
                    "name": f"OpenRouter ({m})",
                    "llm": ChatOpenAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=k,
                        model=m,
                        temperature=temperature
                    )
                })
                
    if prefer_gemini:
        return gemini_pool + groq_pool + openrouter_pool
    return groq_pool + gemini_pool + openrouter_pool

def explicar_erro(enunciado, alternativa_correta, alternativa_marcada, acertou=False, historico=None, stream=False):
    banca = st.session_state.get("banca_preferida", "Geral") if HAS_STREAMLIT and hasattr(st, "session_state") else "Geral"
    if historico is None:
        historico = []
    if acertou:
        from backend.prompts.tutor import get_prompt_explicar_acerto
        sys_prompt = get_prompt_explicar_acerto(enunciado, alternativa_correta, banca)
    else:
        from backend.prompts.tutor import get_prompt_explicar_erro
        sys_prompt = get_prompt_explicar_erro(enunciado, alternativa_correta, alternativa_marcada, banca)
        
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    messages = [SystemMessage(content=sys_prompt)]
    
    if not historico:
        messages.append(HumanMessage(content="Analise a questão e explique a resposta conforme suas instruções."))
        
    for msg in historico:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
            
    pool = get_llm_pool(temperature=0.1, prefer_gemini=True)
    
    for info in pool:
        try:
            if stream:
                stream_iter = info["llm"].stream(messages)
                first_chunk = next(stream_iter)
                def generator():
                    try:
                        txt = _get_chunk_text(first_chunk)
                        if txt: yield txt
                        for chunk in stream_iter:
                            txt = _get_chunk_text(chunk)
                            if txt: yield txt
                        yield f"\n\n*(Respondido por: {info['name']})*"
                    except Exception as e:
                        yield f"\n\n*(Erro durante a resposta da API: {str(e)})*"
                return generator()
            else:
                return info["llm"].invoke(messages).content + f"\n\n*(Respondido por: {info['name']})*"
        except Exception as e:
            print(f"[!] {info['name']} falhou na explicação. Erro: {e}")
            continue
            
    print("Todas as chaves da nuvem falharam (Explicar Erro). Usando fallback Ornith Local...")
    try:
        prompt_str = "\n".join([f"{m.type.upper()}: {m.content}" for m in messages])
        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0.1)
        if stream:
            stream_iter_local = llm_local.stream(prompt_str)
            first_chunk_local = next(stream_iter_local)
            def generator_local():
                try:
                    txt = _get_chunk_text(first_chunk_local)
                    if txt: yield txt
                    for chunk in stream_iter_local:
                        txt = _get_chunk_text(chunk)
                        if txt: yield txt
                except Exception as e:
                    yield f"\n\n*(Erro local: {str(e)})*"
            return generator_local()
        return llm_local.invoke(prompt_str)
    except Exception as e2:
        msg = f"Falha geral ao gerar análise. Erro Local: {e2}"
        if stream:
            def err_gen(): yield msg
            return err_gen()
        return msg

def gerar_conteudo_estudo(grupo, subgrupo, item_nome):
    from backend.prompts.tutor import get_prompt_estudo
    prompt = get_prompt_estudo(grupo, subgrupo, item_nome)
    
    pool = get_llm_pool(temperature=0.5)
    
    for info in pool:
        try:
            return info["llm"].invoke(prompt).content
        except Exception as e:
            print(f"[!] {info['name']} falhou no resumo. Tentando fallback...")
            continue
            
    print("Todas as chaves da nuvem falharam (Resumo). Usando fallback Ornith Local...")
    try:
        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0.5)
        return llm_local.invoke(prompt)
    except Exception as e2:
        return f"Erro ao gerar conteúdo via Nuvem e Local ({e2})"

def gerar_questao_inedita(grupo, subgrupo):
    banca = st.session_state.get("banca_preferida", "FGV") if HAS_STREAMLIT and hasattr(st, "session_state") else "FGV"
    from backend.prompts.tutor import get_prompt_gerar_questao
    prompt = get_prompt_gerar_questao(grupo, subgrupo, banca)
    
    pool = get_llm_pool(temperature=0.7, json_mode=True)
    
    for info in pool:
        try:
            resposta = info["llm"].invoke(prompt).content
            import re
            texto_limpo = resposta.strip()
            if texto_limpo.startswith("```json"): texto_limpo = texto_limpo[7:]
            elif texto_limpo.startswith("```"): texto_limpo = texto_limpo[3:]
            if texto_limpo.endswith("```"): texto_limpo = texto_limpo[:-3]
            texto_limpo = texto_limpo.strip()
            match = re.search(r'\[.*\]|\{.*\}', texto_limpo, re.DOTALL)
            if match: texto_limpo = match.group(0)
            return json.loads(texto_limpo)
        except Exception as e:
            print(f"[!] {info['name']} falhou na geração de questão. Tentando fallback...")
            continue
            
    print("Todas as chaves da nuvem falharam (Questão Inédita). Usando fallback Ornith Local...")
    try:
        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0.7, format="json", num_predict=2048)
        resposta = llm_local.invoke(prompt)
        import re
        texto_limpo = resposta.strip()
        if texto_limpo.startswith("```json"): texto_limpo = texto_limpo[7:]
        elif texto_limpo.startswith("```"): texto_limpo = texto_limpo[3:]
        if texto_limpo.endswith("```"): texto_limpo = texto_limpo[:-3]
        texto_limpo = texto_limpo.strip()
        match = re.search(r'\[.*\]|\{.*\}', texto_limpo, re.DOTALL)
        if match: texto_limpo = match.group(0)
        return json.loads(texto_limpo)
    except Exception as e2:
        print(f"Erro no fallback local Ornith: {e2}")
        return None

def resolver_gabarito_ia(enunciado, alternativas):
    prompt = f"Você é um especialista em concursos de TI.\nResolva a questão abaixo e retorne APENAS A LETRA da alternativa correta (A, B, C, D ou E).\nNÃO retorne mais nada além da letra.\n\n[QUESTÃO]\n{enunciado}\n\n[ALTERNATIVAS]\n"
    for k, v in alternativas.items():
        prompt += f"{k}) {v}\n"
        
    pool = get_llm_pool(temperature=0.0)
    
    for info in pool:
        try:
            resp = info["llm"].invoke(prompt).content.strip().upper()
            import re
            match = re.search(r'\b([A-E])\b', resp)
            if match:
                return match.group(1)
        except Exception as e:
            continue
            
    try:
        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0.0)
        resp = llm_local.invoke(prompt).strip().upper()
        match = re.search(r'\b([A-E])\b', resp)
        if match:
            return match.group(1)
    except:
        pass
    return "A"  # Fallback seguro

def mentoria_ia(enunciado, alternativas, letra_escolhida=None, historico=None, stream=False):
    banca = st.session_state.get("banca_preferida", "Geral") if HAS_STREAMLIT and hasattr(st, "session_state") else "Geral"
    if historico is None:
        historico = []
    from backend.prompts.tutor import get_prompt_mentoria
    sys_prompt = get_prompt_mentoria(enunciado, alternativas, letra_escolhida, banca)
    
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    messages = [SystemMessage(content=sys_prompt)]
    
    if not historico:
        messages.append(HumanMessage(content="Por favor, me guie e explique a questão de forma socrática, não me dê a resposta final."))
        
    for msg in historico:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    
    pool = get_llm_pool(temperature=0.3, prefer_gemini=True)
    
    for info in pool:
        try:
            if stream:
                stream_iter = info["llm"].stream(messages)
                first_chunk = next(stream_iter)
                def generator():
                    try:
                        txt = _get_chunk_text(first_chunk)
                        if txt: yield txt
                        for chunk in stream_iter:
                            txt = _get_chunk_text(chunk)
                            if txt: yield txt
                        yield f"\n\n*(Respondido por: {info['name']})*"
                    except Exception as e:
                        yield f"\n\n*(Erro na Mentoria: {str(e)})*"
                return generator()
            else:
                return info["llm"].invoke(messages).content + f"\n\n*(Respondido por: {info['name']})*"
        except Exception as e:
            print(f"[!] {info['name']} falhou na mentoria. Erro: {e}")
            continue
            
    try:
        prompt_str = "\n".join([f"{m.type.upper()}: {m.content}" for m in messages])
        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0.3)
        if stream:
            stream_iter_local = llm_local.stream(prompt_str)
            first_chunk_local = next(stream_iter_local)
            def generator_local():
                try:
                    txt = _get_chunk_text(first_chunk_local)
                    if txt: yield txt
                    for chunk in stream_iter_local:
                        txt = _get_chunk_text(chunk)
                        if txt: yield txt
                except Exception as e:
                    yield f"\n\n*(Erro local na Mentoria: {str(e)})*"
            return generator_local()
        return llm_local.invoke(prompt_str)
    except Exception as e2:
        msg = f"Falha ao acionar a Mentoria. Erro Local: {e2}"
        if stream:
            def err_gen(): yield msg
            return err_gen()
        return msg

def conselho_tutor_ia(dados_estatisticos, erros_detalhados, stream=False):
    from backend.prompts.tutor import get_prompt_conselho_tutor
    prompt = get_prompt_conselho_tutor(dados_estatisticos, erros_detalhados)
    
    pool = get_llm_pool(temperature=0.3, prefer_gemini=True)
    
    for info in pool:
        try:
            if stream:
                stream_iter = info["llm"].stream(prompt)
                first_chunk = next(stream_iter)
                def generator():
                    try:
                        txt = _get_chunk_text(first_chunk)
                        if txt: yield txt
                        for chunk in stream_iter:
                            txt = _get_chunk_text(chunk)
                            if txt: yield txt
                        yield f"\n\n*(Respondido por: {info['name']})*"
                    except Exception as e:
                        yield f"\n\n*(Erro no Conselho: {str(e)})*"
                return generator()
            else:
                return info["llm"].invoke(prompt).content + f"\n\n*(Respondido por: {info['name']})*"
        except Exception as e:
            print(f"[!] {info['name']} falhou no conselho. Erro: {e}")
            continue
            
    try:
        llm_local = OllamaLLM(model="ornith-1.5:9b", temperature=0.3)
        if stream:
            stream_iter_local = llm_local.stream(prompt)
            first_chunk_local = next(stream_iter_local)
            def generator_local():
                try:
                    txt = _get_chunk_text(first_chunk_local)
                    if txt: yield txt
                    for chunk in stream_iter_local:
                        txt = _get_chunk_text(chunk)
                        if txt: yield txt
                    yield "\n\n*(Respondido por: Ornith Local)*"
                except Exception as e:
                    yield f"\n\n*(Erro no Conselho Local: {str(e)})*"
            return generator_local()
        return llm_local.invoke(prompt) + "\n\n*(Respondido por: Ornith Local)*"
    except Exception as e2:
        msg = f"Falha ao acionar o Conselho do Tutor. Erro Local: {e2}"
        if stream:
            def err_gen(): yield msg
        return msg

PROMPT_ANALISE_BANCA = """
Você é um especialista em engenharia reversa de bancas de concurso.
Analise a questão abaixo considerando o estilo específico da banca {banca}.

Enunciado: {enunciado}
Alternativas: {alternativas}
Gabarito Oficial: {gabarito}

Entregue uma análise técnica e concisa estruturada em:
1. Padrão da Banca: Identifique o vício típico da {banca} presente (ex: pegadinha por negação sutil, troca de uma única palavra, distrator de alta proximidade).
2. Anatomia do Distrator: Explique qual alternativa foi desenhada para induzir ao erro e qual palavra-chave desclassifica essa opção.
3. Regra de Ouro: Uma diretriz em 1 frase para não cair nesse padrão novamente.
"""

def analisar_banca_ia(banca, enunciado, alternativas, gabarito, stream=False):
    prompt = PROMPT_ANALISE_BANCA.format(
        banca=banca, 
        enunciado=enunciado, 
        alternativas=json.dumps(alternativas, ensure_ascii=False, indent=2), 
        gabarito=gabarito
    )
    
    pool = get_llm_pool(temperature=0.2, prefer_gemini=True)
    
    for info in pool:
        try:
            if stream:
                stream_iter = info["llm"].stream(prompt)
                first_chunk = next(stream_iter)
                def generator():
                    try:
                        txt = _get_chunk_text(first_chunk)
                        if txt: yield txt
                        for chunk in stream_iter:
                            txt = _get_chunk_text(chunk)
                            if txt: yield txt
                        yield f"\n\n*(Analisado por: {info['name']})*"
                    except Exception as e:
                        yield f"\n\n*(Erro na Análise: {str(e)})*"
                return generator()
            else:
                return info["llm"].invoke(prompt).content + f"\n\n*(Analisado por: {info['name']})*"
        except Exception as e:
            print(f"[!] {info['name']} falhou na análise de banca. Erro: {e}")
            continue
            
    return "Falha ao gerar o Raio-X da Banca."
