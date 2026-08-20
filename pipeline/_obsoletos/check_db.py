import sqlite3

import os
_pipeline_dir = os.path.dirname(os.path.abspath(__file__))
conn = sqlite3.connect(os.path.join(_pipeline_dir, 'data', 'db', 'progress.sqlite'))
cursor = conn.cursor()

cursor.execute('SELECT count(*) FROM processed_emails WHERE status="SUCCESS"')
success = cursor.fetchone()[0]

cursor.execute('SELECT count(*) FROM processed_emails WHERE status LIKE "FAILED%"')
failed = cursor.fetchone()[0]

cursor.execute('SELECT count(*) FROM processed_emails')
total = cursor.fetchone()[0]

print(f"SUCCESS: {success}")
print(f"FAILED: {failed}")
print(f"TOTAL_DB: {total}")
