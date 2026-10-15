import fitz
import shutil
import os
from datetime import datetime
from llm import texto_para_json
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
    print(f"Processando {len(doc)} páginas...")

    for i, pagina in enumerate(doc):
        print(f"\n--- Processando página {i+1}/{len(doc)} ---")
        texto_pagina = pagina.get_text()
        
        # Ignorar páginas vazias ou com muito pouco texto
        if len(texto_pagina.strip()) < 50:
            print(f"Página {i+1} muito curta ({len(texto_pagina)} caracteres), pulando.")
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Extraídos {len(texto_pagina)} caracteres. Aguardando processamento do Ornith 1.5 9B...")
        
        try:
            # O modelo processa um bloco pequeno de cada vez
            dados_json = texto_para_json(texto_pagina)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ornith 1.5 9B respondeu! Realizando parsing e validação...")
            
            if dados_json:
                questoes = validar(dados_json)
                salvar(questoes)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Página {i+1} salva com sucesso ({len(questoes)} questões).")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Página {i+1} não retornou questões.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro na página {i+1}: {e}")

if __name__ == "__main__":
    import glob
    import os
    import shutil
    
    # Cria pasta para PDFs já processados, se não existir
    os.makedirs("data/processados", exist_ok=True)
    
    pdf_files = glob.glob("data/raw/*.pdf")
    if not pdf_files:
        print("Nenhum arquivo PDF encontrado na pasta data/raw/")
    else:
        for pdf in pdf_files:
            print(f"\n========== INICIANDO PROCESSAMENTO: {os.path.basename(pdf)} ==========")
            
            try:
                rodar_pipeline(pdf)
                print(f"========== FINALIZADO: {os.path.basename(pdf)} ==========\n")
                
                # Move o arquivo apenas se finalizou sem ser interrompido
                destino = os.path.join("data/processados", os.path.basename(pdf))
                shutil.move(pdf, destino)
                print(f"-> Arquivo movido com sucesso para: {destino}")
                
            except KeyboardInterrupt:
                print("\n[!] Processamento interrompido pelo usuário. O arquivo não foi movido.")
                break
            except Exception as e:
                print(f"\n[!] Erro fatal ao processar o arquivo: {e}")