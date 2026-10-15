"""
run_pdf_crawler.py
Entry point principal do PDF crawler do AprovaTeck.

Uso:
  # Processa todos os PDFs na pasta crawler/pdfs/
  python crawler/run_pdf_crawler.py

  # Processa um arquivo específico
  python crawler/run_pdf_crawler.py caminho/para/prova.pdf

  # Dry-run: extrai e mostra questões sem salvar no banco
  python crawler/run_pdf_crawler.py --dry-run
  python crawler/run_pdf_crawler.py prova.pdf --dry-run
"""

import sys
import os
import time
from pathlib import Path

# Adiciona o diretório crawler ao path para imports relativos funcionarem
CRAWLER_DIR = Path(__file__).parent
sys.path.insert(0, str(CRAWLER_DIR))

from pdf_extractor import extract_text_from_pdf
from pdf_parser import parse_pdf_text
from pdf_ingestor import ingest_questoes, move_pdf_to_processed

PDF_DIR = CRAWLER_DIR / "pdfs"


def _banner():
    print("""
╔══════════════════════════════════════════════════════╗
║       AprovaTeck — PDF Question Crawler              ║
║  Gemini Flash → Groq llama-3.3 → Qwen local         ║
╚══════════════════════════════════════════════════════╝
""")


def process_pdf(pdf_path: Path, dry_run: bool = False) -> dict:
    """
    Pipeline completo para um único PDF.

    Returns:
        dict com stats do processamento
    """
    print(f"\n{'─'*55}")
    print(f"📄 Processando: {pdf_path.name}")
    print(f"{'─'*55}")
    t_start = time.time()

    # 1. Extração de texto
    print("\n[1/3] Extraindo texto do PDF...")
    try:
        extracted = extract_text_from_pdf(pdf_path)
    except Exception as e:
        print(f"  ❌ Erro na extração: {e}")
        return {"arquivo": pdf_path.name, "status": "erro_extracao", "questoes": 0}

    if not extracted["texto_bruto"].strip():
        print("  ❌ PDF sem texto extraível (pode ser imagem/escaneado sem OCR).")
        return {"arquivo": pdf_path.name, "status": "sem_texto", "questoes": 0}

    banca = extracted["banca_detectada"] or "N/A"
    ano = extracted["ano_detectado"] or 0

    # 2. Parsing com LLM
    print(f"\n[2/3] Parseando questões via LLM (banca={banca}, ano={ano})...")
    try:
        questoes = parse_pdf_text(
            texto_bruto=extracted["texto_bruto"],
            banca=banca,
            ano=ano,
        )
    except Exception as e:
        print(f"  ❌ Erro no parsing: {e}")
        return {"arquivo": pdf_path.name, "status": "erro_parsing", "questoes": 0}

    if not questoes:
        print("  ⚠️  Nenhuma questão encontrada no PDF.")
        return {"arquivo": pdf_path.name, "status": "sem_questoes", "questoes": 0}

    # 3. Ingestão no banco (ou dry-run)
    if dry_run:
        print(f"\n[3/3] DRY-RUN — {len(questoes)} questões encontradas (não salvas).")
        print("\n  Amostra das primeiras 2 questões:")
        for i, q in enumerate(questoes[:2], 1):
            print(f"\n  [{i}] Banca: {q.get('banca')} | Ano: {q.get('ano')} | Tema: {q.get('tema')}")
            print(f"       Enunciado: {q.get('enunciado', '')[:120]}...")
        stats = {"inseridas": 0, "duplicadas": 0, "erros": 0}
        status = "dry_run"
    else:
        print(f"\n[3/3] Salvando {len(questoes)} questões no banco...")
        try:
            stats = ingest_questoes(questoes, fonte_arquivo=f"PDF:{pdf_path.stem}")
            print(f"  ✅ Inseridas: {stats['inseridas']} | Duplicadas: {stats['duplicadas']} | Erros: {stats['erros']}")
            status = "ok"
        except Exception as e:
            print(f"  ❌ Erro na ingestão: {e}")
            return {"arquivo": pdf_path.name, "status": "erro_db", "questoes": len(questoes)}

        # Move PDF para processed/ somente se houve inserções (ou todas eram duplicatas)
        if stats["inseridas"] > 0 or stats["duplicadas"] > 0:
            try:
                move_pdf_to_processed(pdf_path)
            except Exception as e:
                print(f"  ⚠️  Não foi possível mover o PDF: {e}")

    elapsed = time.time() - t_start
    print(f"\n  ⏱️  Tempo total: {elapsed:.1f}s")

    return {
        "arquivo": pdf_path.name,
        "status": status,
        "banca": banca,
        "ano": ano,
        "questoes": len(questoes),
        "inseridas": stats.get("inseridas", 0),
        "duplicadas": stats.get("duplicadas", 0),
        "tempo_s": round(elapsed, 1),
    }


def main():
    _banner()

    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Descobre quais PDFs processar
    if args:
        # Arquivo(s) específico(s) passado(s) como argumento
        pdfs = []
        for arg in args:
            p = Path(arg)
            if not p.is_absolute():
                p = Path.cwd() / p
            if not p.exists():
                # Tenta dentro da pasta pdfs/
                p = PDF_DIR / arg
            if p.exists() and p.suffix.lower() == ".pdf":
                pdfs.append(p)
            else:
                print(f"⚠️  Arquivo não encontrado ou não é PDF: {arg}")
    else:
        # Varre a pasta pdfs/ automaticamente
        PDF_DIR.mkdir(exist_ok=True)
        pdfs = sorted(PDF_DIR.glob("*.pdf"))

    if not pdfs:
        print(f"📂 Nenhum PDF encontrado em: {PDF_DIR}")
        print(f"   Coloque arquivos .pdf em: crawler/pdfs/")
        sys.exit(0)

    if dry_run:
        print(f"🔍 MODO DRY-RUN — os dados NÃO serão salvos no banco.\n")

    print(f"📋 {len(pdfs)} PDF(s) para processar:")
    for p in pdfs:
        print(f"   • {p.name}")

    # Processa cada PDF
    resultados = []
    for pdf_path in pdfs:
        resultado = process_pdf(pdf_path, dry_run=dry_run)
        resultados.append(resultado)

    # Relatório final
    print(f"\n{'═'*55}")
    print("📊 RELATÓRIO FINAL")
    print(f"{'═'*55}")
    total_inseridas = sum(r.get("inseridas", 0) for r in resultados)
    total_duplicadas = sum(r.get("duplicadas", 0) for r in resultados)
    total_questoes = sum(r.get("questoes", 0) for r in resultados)

    for r in resultados:
        status_icon = {"ok": "✅", "dry_run": "🔍", "sem_texto": "⚠️", "sem_questoes": "⚠️"}.get(r["status"], "❌")
        print(f"  {status_icon} {r['arquivo']}: {r.get('questoes', 0)} questões | {r.get('inseridas', 0)} inseridas")

    print(f"\n  Total questões encontradas : {total_questoes}")
    if not dry_run:
        print(f"  Total inseridas no banco   : {total_inseridas}")
        print(f"  Total duplicatas ignoradas : {total_duplicadas}")
    print(f"\n✅ Pipeline concluído!")


if __name__ == "__main__":
    main()
