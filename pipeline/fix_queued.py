import sqlite3
import sys

# Forçar UTF-8 no stdout
sys.stdout.reconfigure(encoding='utf-8')

db = r'c:\bento\prg\app-outlook-novo\pipeline\data\db\progress.sqlite'
with sqlite3.connect(db) as conn:
    rows = conn.execute("SELECT id, subject, date, status FROM processed_emails WHERE status = 'QUEUED'").fetchall()
    print(f"=== {len(rows)} emails travados em QUEUED ===")
    for r in rows:
        print(f"  ID: {r[0]}")
        print(f"  Assunto: {r[1]}")
        print(f"  Data: {r[2]}")
        print()
    
    if rows:
        conn.execute("DELETE FROM processed_emails WHERE status = 'QUEUED'")
        conn.commit()
        print(f"OK: {len(rows)} registros deletados do banco.")
        print("Eles serao reprocessados na proxima rodada do producer.")
    else:
        print("Nenhum email travado encontrado.")
