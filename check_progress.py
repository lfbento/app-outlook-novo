import sqlite3
import urllib.request
import json
import os

db_path = r'c:\bento\prg\app-outlook-novo\pipeline\data\db\progress.sqlite'
try:
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT SUBSTR(status, 1, 7) as cod_status, count(*) FROM processed_emails GROUP BY cod_status")
        rows = cur.fetchall()
        print("=== Status do Banco (progress.sqlite) ===")
        for r in rows:
            print(f"{r[0]}: {r[1]}")
        
        cur.execute("SELECT count(*) FROM processed_emails")
        total = cur.fetchone()[0]
        print(f"TOTAL PROCESSADOS (INCLUINDO FALHAS): {total}\n")
        conn.close()
    else:
        print(f"Banco não encontrado em {db_path}\n")
except Exception as e:
    print(f"Erro SQLite: {e}\n")

try:
    req = urllib.request.Request('http://127.0.0.1:15672/api/queues/%2f/outlook_ingestion')
    req.add_header('Authorization', 'Basic Z3Vlc3Q6Z3Vlc3Q=')
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        print(f"=== Status da Fila do RabbitMQ ===")
        print(f"Mensagens na Fila: {data.get('messages_ready', 0)}")
        print(f"Sendo Processadas: {data.get('messages_unacknowledged', 0)}")
        print(f"Total (Fila + Processando): {data.get('messages', 0)}")
except Exception as e:
    print(f"Erro RabbitMQ: {e}")
