"""
pdf_ingestor.py
Salva questões extraídas de PDF no banco SQLite do AprovaTeck.
- Cria grupo/subgrupo automaticamente se não existir
- Deduplicação por hash SHA-256 do enunciado
- Move o PDF para /processed após ingestão bem-sucedida
"""

import sqlite3
import hashlib
import os
import shutil
from pathlib import Path
from datetime import datetime

# Resolve o DB path a partir da raiz do projeto
_SCRIPT_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
DB_PATH = _PROJECT_ROOT / "data" / "bancos" / "db_novo.sqlite"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")  # melhor concorrência
    return conn


def _hash_enunciado(enunciado: str) -> str:
    """SHA-256 dos primeiros 400 chars normalizados — fingerprint de deduplicação."""
    normalized = " ".join(enunciado.strip().lower().split())[:400]
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _ensure_schema(conn: sqlite3.Connection):
    """Garante que as colunas origem e hash_enunciado existam na tabela questoes."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(questoes)")
    colunas = {row[1] for row in cursor.fetchall()}

    if "origem" not in colunas:
        cursor.execute("ALTER TABLE questoes ADD COLUMN origem TEXT DEFAULT 'PDF'")
        print("  [DB] Coluna 'origem' adicionada.")

    if "hash_enunciado" not in colunas:
        cursor.execute("ALTER TABLE questoes ADD COLUMN hash_enunciado TEXT")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash_enunciado ON questoes(hash_enunciado)")
        print("  [DB] Coluna 'hash_enunciado' adicionada com índice.")

    if "valida" not in colunas:
        cursor.execute("ALTER TABLE questoes ADD COLUMN valida INTEGER DEFAULT 1")
        print("  [DB] Coluna 'valida' adicionada.")

    conn.commit()


def _get_or_create_grupo(cursor: sqlite3.Cursor, nome: str) -> int:
    nome = (nome or "Não Classificado").strip()
    cursor.execute("SELECT id FROM grupos WHERE nome = ?", (nome,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO grupos (nome) VALUES (?)", (nome,))
    return cursor.lastrowid


def _get_or_create_subgrupo(cursor: sqlite3.Cursor, grupo_id: int, nome: str) -> int:
    nome = (nome or "Não Classificado").strip()
    cursor.execute(
        "SELECT id FROM subgrupos WHERE grupo_id = ? AND nome = ?",
        (grupo_id, nome),
    )
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        "INSERT INTO subgrupos (grupo_id, nome) VALUES (?, ?)",
        (grupo_id, nome),
    )
    return cursor.lastrowid


def ingest_questoes(questoes: list[dict], fonte_arquivo: str = "PDF") -> dict:
    """
    Insere lista de questões no banco SQLite.

    Returns:
        dict com 'inseridas', 'duplicadas', 'erros'
    """
    if not questoes:
        return {"inseridas": 0, "duplicadas": 0, "erros": 0}

    conn = get_connection()
    _ensure_schema(conn)
    cursor = conn.cursor()

    stats = {"inseridas": 0, "duplicadas": 0, "erros": 0}

    for q in questoes:
        enunciado = (q.get("enunciado") or "").strip()
        if not enunciado or len(enunciado) < 20:
            stats["erros"] += 1
            continue

        hash_q = _hash_enunciado(enunciado)

        # Deduplicação por hash
        cursor.execute("SELECT id FROM questoes WHERE hash_enunciado = ?", (hash_q,))
        if cursor.fetchone():
            stats["duplicadas"] += 1
            continue

        # Resolve grupo/subgrupo
        grupo_nome = q.get("grupo") or "Não Classificado"
        subgrupo_nome = q.get("subgrupo") or "Não Classificado"

        try:
            grupo_id = _get_or_create_grupo(cursor, grupo_nome)
            subgrupo_id = _get_or_create_subgrupo(cursor, grupo_id, subgrupo_nome)

            cursor.execute("""
                INSERT INTO questoes (
                    subgrupo_id, banca, ano, enunciado,
                    alternativa_a, alternativa_b, alternativa_c,
                    alternativa_d, alternativa_e, gabarito,
                    origem, hash_enunciado, valida
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                subgrupo_id,
                q.get("banca") or "N/A",
                int(q.get("ano") or 0) or None,
                enunciado,
                q.get("alternativa_a") or "",
                q.get("alternativa_b") or "",
                q.get("alternativa_c") or "",
                q.get("alternativa_d") or "",
                q.get("alternativa_e") or None,
                q.get("gabarito") or None,
                fonte_arquivo,
                hash_q,
            ))
            stats["inseridas"] += 1
        except Exception as e:
            print(f"  [DB] Erro ao inserir questão: {e}")
            stats["erros"] += 1

    conn.commit()
    conn.close()
    return stats


def move_pdf_to_processed(pdf_path: Path) -> Path:
    """Move o PDF para a subpasta processed/ após ingestão bem-sucedida."""
    processed_dir = pdf_path.parent / "processed"
    processed_dir.mkdir(exist_ok=True)

    # Renomeia com timestamp para evitar colisões
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"{pdf_path.stem}_{timestamp}{pdf_path.suffix}"
    dest = processed_dir / new_name

    shutil.move(str(pdf_path), str(dest))
    print(f"  [Ingestor] PDF movido para: {dest.relative_to(pdf_path.parent.parent)}")
    return dest
