import json
import re
from langchain_ollama import OllamaLLM

# Usando o modelo 3B para extração mais rápida
llm = OllamaLLM(model="ornith-1.5:9b", temperature=0, format="json", num_predict=2048)

def texto_para_json(texto: str):

    prompt = f"""
Você é um parser de provas de concursos de TI. O texto abaixo é o extrato de uma página inteira de prova.
Seu dever é extrair TODAS as questões dessa página. É esperado que você encontre múltiplas questões.

RETORNE APENAS UM OBJETO JSON VÁLIDO. NÃO INCLUA NENHUM TEXTO ADICIONAL.

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
    }},
    {{
      "tema": "N/A",
      "banca": "N/A",
      "ano": 2024,
      "enunciado": "Texto completo da SEGUNDA questão encontrada...",
      "alternativas": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
      "gabarito": "..."
    }}
  ]
}}
IMPORTANTE: Adicione um novo objeto dentro do array "questoes" para CADA questão que existir no texto da prova!

Texto da Prova:
{texto}
"""
    resposta = llm.invoke(prompt)

    # Limpeza da resposta para evitar erros de parser (ex: Expecting value)
    texto_limpo = resposta.strip()
    
    # Remoção de markdown code blocks
    if texto_limpo.startswith("```json"):
        texto_limpo = texto_limpo[7:]
    elif texto_limpo.startswith("```"):
        texto_limpo = texto_limpo[3:]
    if texto_limpo.endswith("```"):
        texto_limpo = texto_limpo[:-3]
        
    texto_limpo = texto_limpo.strip()
    
    # Busca por array json [ ... ] ou object { ... }
    match = re.search(r'\[.*\]|\{.*\}', texto_limpo, re.DOTALL)
    if match:
        texto_limpo = match.group(0)

    try:
        return json.loads(texto_limpo)
    except json.JSONDecodeError as e:
        print(f"Erro ao parsear JSON original: {e}")
        print("Tentando recuperar questões intactas da resposta truncada (perda de fôlego do modelo)...")
        
        last_brace_idx = texto_limpo.rfind('}')
        while last_brace_idx != -1:
            recuperado = texto_limpo[:last_brace_idx + 1] + "\n  ]\n}"
            try:
                parsed = json.loads(recuperado)
                print(f"Sucesso na recuperação! {len(parsed.get('questoes', []))} questões resgatadas com sucesso da string quebrada.")
                return parsed
            except json.JSONDecodeError:
                last_brace_idx = texto_limpo.rfind('}', 0, last_brace_idx)
                
        print(f"Falha total ao recuperar. Resposta bruta do modelo:\n{resposta}")
        return []