import sqlite3

db_path = 'c:/bento/prg/app-outlook-novo/pipeline/data/db/progress.sqlite'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Buscando MinerU no banco...")
cursor.execute("SELECT id, subject, status FROM processed_emails WHERE status LIKE '%MinerU%'")
rows = cursor.fetchall()
for row in rows:
    print(row)
print(f"Total MinerU no banco: {len(rows)}")

cursor.execute("SELECT id, subject, status FROM processed_emails ORDER BY processed_at DESC LIMIT 10")
print("\nÚltimos 10 e-mails processados:")
for row in cursor.fetchall():
    print(row)

conn.close()
