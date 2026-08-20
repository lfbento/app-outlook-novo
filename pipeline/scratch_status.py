import sqlite3
import json
import urllib.request
import base64

try:
    conn = sqlite3.connect('c:/bento/prg/app-outlook-novo/pipeline/data/db/progress.sqlite')
    c = conn.cursor()
    # Checking table name
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in c.fetchall()]
    
    if 'processed_emails' in tables:
        c.execute('SELECT status, COUNT(*) FROM processed_emails GROUP BY status')
    elif 'emails' in tables:
        c.execute('SELECT status, COUNT(*) FROM emails GROUP BY status')
    else:
        print("No emails table found. Tables:", tables)
        c.execute('SELECT "unknown", 0')
        
    rows = c.fetchall()
    print('=== Status do Banco de Dados SQLite ===')
    if rows:
        for r in rows:
            print(f'  {r[0]}: {r[1]}')
    else:
        print('  Nenhum registro encontrado.')
except Exception as e:
    print('DB error:', e)

try:
    req = urllib.request.Request('http://localhost:15672/api/queues/%2F/outlook_ingestion')
    auth = base64.b64encode(b'guest:guest').decode('utf-8')
    req.add_header('Authorization', 'Basic ' + auth)
    response = urllib.request.urlopen(req)
    data = json.loads(response.read())
    print('\n=== Status da Fila (RabbitMQ) ===')
    print(f"  Mensagens Aguardando: {data.get('messages_ready', 0)}")
    print(f"  Mensagens Sendo Processadas (Unacknowledged): {data.get('messages_unacknowledged', 0)}")
    print(f"  Total na Fila: {data.get('messages', 0)}")
except Exception as e:
    print('\nRabbitMQ error:', e)
