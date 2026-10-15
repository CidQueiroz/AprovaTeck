"""
pdf_extractor.py
Extrai texto bruto de PDFs de concurso usando PyMuPDF (fitz).
Faz detecção prévia de banca e ano via regex para economizar tokens do LLM.
"""

from __future__ import annotations
import re
import os
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    raise ImportError("PyMuPDF não encontrado. Execute: pip install pymupdf")

# Bancas conhecidas — ordem importa (mais específico primeiro)
BANCAS_CONHECIDAS = [
    "CESPE", "CEBRASPE", "FGV", "FCC", "VUNESP", "IBFC", "CESGRANRIO",
    "ESAF", "QUADRIX", "IDECAN", "IADES", "AOCP", "NUCEPE", "FUNCAB",
    "COPEVE", "COVEST", "COMVEST", "FEPESE", "UPENET", "FADESP",
    "CONSULPLAN", "FUNDATEC", "AVANÇA SP", "FAURGS", "CETAP",
]

# Regex para detectar ano entre 2000 e 2026
RE_ANO = re.compile(r'\b(20[0-2][0-9]|19[89][0-9])\b')

# Regex para detectar banca no texto
def _build_banca_pattern():
    escaped = [re.escape(b) for b in BANCAS_CONHECIDAS]
    return re.compile(r'\b(' + '|'.join(escaped) + r')\b', re.IGNORECASE)

RE_BANCA = _build_banca_pattern()


def extract_text_from_pdf(pdf_path) -> dict:  # accepts str or Path
    """
    Extrai texto completo do PDF e faz detecção prévia de banca/ano.

    Returns:
        dict com:
            - texto_bruto (str): texto completo extraído
            - paginas (list[str]): texto por página
            - banca_detectada (str | None): banca encontrada via regex
            - ano_detectado (int | None): ano mais frequente encontrado
            - nome_arquivo (str): nome do arquivo sem extensão
            - total_paginas (int)
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    paginas = []

    for page in doc:
        paginas.append(page.get_text("text"))

    doc.close()

    texto_bruto = "\n".join(paginas)

    # Detecção de banca via regex
    banca_detectada = None
    match_banca = RE_BANCA.search(texto_bruto[:3000])  # primeiras páginas
    if match_banca:
        banca_detectada = match_banca.group(0).upper()
        # Normaliza CEBRASPE → CESPE
        if banca_detectada == "CEBRASPE":
            banca_detectada = "CESPE/CEBRASPE"

    # Tenta inferir banca pelo nome do arquivo também
    if not banca_detectada:
        nome_upper = pdf_path.stem.upper()
        for banca in BANCAS_CONHECIDAS:
            if banca.upper() in nome_upper:
                banca_detectada = banca
                break

    # Detecção de ano — pega o mais frequente no início do documento
    anos_encontrados = RE_ANO.findall(texto_bruto[:5000])
    ano_detectado = None
    if anos_encontrados:
        from collections import Counter
        contagem = Counter(anos_encontrados)
        ano_detectado = int(contagem.most_common(1)[0][0])

    # Fallback: tenta pegar o ano do nome do arquivo
    if not ano_detectado:
        anos_no_nome = RE_ANO.findall(pdf_path.stem)
        if anos_no_nome:
            ano_detectado = int(anos_no_nome[-1])

    print(f"  [PDF Extractor] Arquivo: {pdf_path.name}")
    print(f"  [PDF Extractor] Páginas: {len(paginas)} | Banca: {banca_detectada} | Ano: {ano_detectado}")
    print(f"  [PDF Extractor] Tamanho do texto: {len(texto_bruto):,} chars")

    return {
        "texto_bruto": texto_bruto,
        "paginas": paginas,
        "banca_detectada": banca_detectada,
        "ano_detectado": ano_detectado,
        "nome_arquivo": pdf_path.stem,
        "total_paginas": len(paginas),
    }


def split_into_chunks(texto: str, chunk_size: int = 6000, overlap: int = 500) -> list:
    """
    Divide o texto em chunks com overlap para não perder questões no corte.
    chunk_size em caracteres (~1500 tokens por chunk).
    """
    chunks = []
    start = 0
    while start < len(texto):
        end = start + chunk_size
        chunks.append(texto[start:end])
        start = end - overlap  # overlap para não cortar questões no meio
        if start >= len(texto):
            break
    return chunks
