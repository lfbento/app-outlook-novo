import win32com.client
import sys

def test_outlook():
    print("Tentando conectar ao Outlook...")
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        print("Conectado com sucesso!\n")
        
        print("=== Contas/Caixas Encontradas ===")
        for i in range(1, outlook.Folders.Count + 1):
            account_folder = outlook.Folders.Item(i)
            print(f"- {account_folder.Name}")
            
    except Exception as e:
        print(f"Erro ao conectar: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_outlook()
