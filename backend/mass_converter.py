from langchain_community.llms import Ollama

def converter_dump_para_formato(texto_bruto):
    llm = Ollama(model="ornith-1.5:9b", temperature=0)
    
    prompt = f"""
    Você é um extrator de dados de concursos. Converta o texto abaixo no formato de carga para banco de dados.
    Ignore cabeçalhos, rodapés e anúncios.
    Para cada questão, use estritamente este formato:
    [ASSUNTO] Nome do assunto
    [BANCA] FGV
    [ANO] 2025
    [DIFICULDADE] Média
    [ENUNCIADO] O texto da questão
    [A] texto
    [B] texto
    [C] texto
    [D] texto
    [E] texto
    [GABARITO] Letra da alternativa correta
    ---

    Texto bruto:
    {texto_bruto}
    """
    return llm.invoke(prompt)

# Uso: Leia o arquivo bruto e salve o resultado no carga.txt
# with open('dump_questoes.txt', 'r') as f:
#     print(converter_dump_para_formato(f.read()))