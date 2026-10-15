import fitz
import shutil
import os
from datetime import datetime
from llm_master import texto_para_json_master as texto_para_json
from validator import validar
from sqlite import salvar

def criar_backup_banco():
    db_path = "data/bancos/db_novo.sqlite"
    if os.path.exists(db_path):
        backup_path = "data/bancos/db_backup.sqlite"
        shutil.copy2(db_path, backup_path)
        print(f"Backup do banco de dados atualizado em: {backup_path}")

def rodar_pipeline(pdf_path):
    criar_backup_banco()
    doc = fitz.open(pdf_path)
    print(f"Processando {len(doc)} páginas com Ingestor Master (Groq -> OpenRouter -> Ornith Local)...")

    for i, pagina in enumerate(doc):
        print(f"\n--- Processando página {i+1}/{len(doc)} ---")
        texto_pagina = pagina.get_text()
        
        if len(texto_pagina.strip()) < 50:
            print(f"Página {i+1} muito curta ({len(texto_pagina)} caracteres), pulando.")
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Extraídos {len(texto_pagina)} caracteres. Acionando Motor Principal...")
        
        try:
            dados_json = texto_para_json(texto_pagina)
            
            if dados_json:
                questoes = validar(dados_json)
                salvar(questoes)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Página {i+1} salva: ({len(questoes)} questões extraídas e salvas).")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Página {i+1} não retornou questões válidas ou retornou vazio.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro severo no fluxo principal da página {i+1}: {e}")

if __name__ == "__main__":
    import glob
    import os
    import shutil
    
    os.makedirs("data/processados", exist_ok=True)
    
    pdf_files = glob.glob("data/raw/*.pdf")
    if not pdf_files:
        print("Nenhum arquivo PDF encontrado na pasta data/raw/")
    else:
        for pdf in pdf_files:
            print(f"\n========== INICIANDO INGESTÃO GOD MODE: {os.path.basename(pdf)} ==========")
            
            try:
                rodar_pipeline(pdf)
                print(f"========== FINALIZADO: {os.path.basename(pdf)} ==========\n")
                
                destino = os.path.join("data/processados", os.path.basename(pdf))
                shutil.move(pdf, destino)
                print(f"-> Arquivo movido com sucesso para: {destino}")
                
            except KeyboardInterrupt:
                print("\n[!] Processamento interrompido pelo usuário. O arquivo não foi movido.")
                break
            except Exception as e:
                print(f"\n[!] Erro fatal ao processar o arquivo: {e}")
