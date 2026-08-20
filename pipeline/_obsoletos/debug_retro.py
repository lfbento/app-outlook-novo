"""Debug 3: Imprimir filenames gerados e comparar com os que existem no disco."""
import os, re, hashlib, sys
import win32com.client, pythoncom

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

OBSIDIAN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "obsidian")

def sanitize_filename(text):
    return re.sub(r'[<>:"/\\|?*]', '', str(text)).strip()[:100]

def generate_id(subject, date_str, sender):
    raw = f"{subject}_{date_str}_{sender}".encode('utf-8', errors='ignore')
    return hashlib.md5(raw).hexdigest()

# Listar os 10 MDs mais recentes que NÃO possuem seção de anexos
import glob
mds = glob.glob(os.path.join(OBSIDIAN_DIR, "*.md"))
pending = []
for path in mds:
    with open(path, 'r', encoding='utf-8') as f:
        if "## 📎 Anexos" not in f.read():
            pending.append(os.path.basename(path))

# Ordena por data de modificação (mais recentes primeiro)
pending_with_mtime = [(p, os.path.getmtime(os.path.join(OBSIDIAN_DIR, p))) for p in pending]
pending_with_mtime.sort(key=lambda x: x[1], reverse=True)

print("=== 15 MDs pendentes mais recentes ===")
for name, _ in pending_with_mtime[:15]:
    print(f"  DISCO: {repr(name)}")

# Agora gera os filenames dos 15 primeiros e-mails com anexo do Outlook
print("\n=== 15 filenames gerados a partir do Outlook ===")
pythoncom.CoInitialize()
outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")

for i in range(1, outlook.Folders.Count + 1):
    f = outlook.Folders.Item(i)
    if "luis.bento" in f.Name:
        account = f
        break

inbox = account.Folders("Caixa de Entrada")
items = inbox.Items
items.Sort("[ReceivedTime]", True)

count = 0
for item in items:
    try:
        if getattr(item, 'Class', 0) != 43:
            continue
        subject = getattr(item, 'Subject', '') or "Sem Assunto"
        sender = getattr(item, 'SenderName', 'Desconhecido')
        date_obj = getattr(item, 'ReceivedTime', None)
        if not date_obj:
            continue
        date_str = str(date_obj).split('+')[0]
        msg_id = generate_id(subject, date_str, sender)
        filename = f"{sanitize_filename(subject)}_{msg_id[:6]}.md"
        print(f"  GERADO: {repr(filename)}")
        count += 1
        if count >= 15:
            break
    except:
        pass

pythoncom.CoUninitialize()
