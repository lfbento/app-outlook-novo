import sqlite3
import json
import urllib.request
import base64
import os

try:
    db_path = 'c:/bento/prg/app-outlook-novo/pipeline/data/db/progress.sqlite'
    if not os.path.exists(db_path):
        print("DB File not found.")
    else:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in c.fetchall()]
        
        table_name = None
        if 'processed_emails' in tables:
            table_name = 'processed_emails'
        elif 'emails' in tables:
            table_name = 'emails'
            
        if table_name:
            c.execute(f"SELECT status, COUNT(*) FROM {table_name} GROUP BY status")
            rows = c.fetchall()
            print('=== Status do Banco de Dados SQLite ===')
            for r in rows:
                print(f'  {r[0]}: {r[1]}')
        else:
            print("Nenhuma tabela de emails encontrada no banco.")
except Exception as e:
    print('DB error:', e)

try:
    req = urllib.request.Request('http://localhost:15672/api/queues/%2F/outlook_ingestion')
    auth = base64.b64encode(b'guest:guest').decode('utf-8')
    req.add_header('Authorization', 'Basic ' + auth)
    response = urllib.request.urlopen(req)
    data = json.loads(response.read())
    print('\n=== Status da Fila (RabbitMQ) ===')
    print(f"  Mensagens Aguardando (Na Fila): {data.get('messages_ready', 0)}")
    print(f"  Mensagens Em Processamento: {data.get('messages_unacknowledged', 0)}")
    print(f"  Total: {data.get('messages', 0)}")
except Exception as e:
    print('\nRabbitMQ error:', e)
