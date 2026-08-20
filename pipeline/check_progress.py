import sqlite3

conn = sqlite3.connect("c:/bento/prg/app-outlook-novo/pipeline/data/db/progress.sqlite")
cursor = conn.cursor()

print("--- CONTAGEM DE E-MAILS ---")
res = cursor.execute("SELECT status, COUNT(*) FROM processed_emails GROUP BY status").fetchall()
for row in res:
    print(row)

print("\n--- E-MAILS ATUALMENTE COM STATUS 'QUEUED' ---")
res_queued = cursor.execute("SELECT id, subject, date, processed_at FROM processed_emails WHERE status = 'QUEUED'").fetchall()
print(f"Total: {len(res_queued)}")
for row in res_queued[:15]:
    clean_subj = row[1].encode('ascii', errors='replace').decode('ascii')
    print((row[0], clean_subj, row[2], row[3]))

conn.close()
