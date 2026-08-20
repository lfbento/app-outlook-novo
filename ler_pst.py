import os
import sys

def ler_pst_aspose(caminho_pst):
    """
    Lê o arquivo PST de forma independente, usando a biblioteca Aspose.Email.
    Esta biblioteca não requer o Outlook instalado e funciona nativamente no Python.
    """
    try:
        from aspose.email.storage.pst import PersonalStorage
    except ImportError:
        print("A biblioteca 'aspose-email-for-python-via-net' não está instalada.")
        print("Certifique-se de estar usando o ambiente virtual correto (pst_venv).")
        return False

    caminho_pst = os.path.abspath(caminho_pst)
    if not os.path.exists(caminho_pst):
        print(f"Erro: O arquivo {caminho_pst} não foi encontrado.")
        return False

    def print_tree(folder, indent=""):
        nome = folder.display_name if folder.display_name else "Sem Nome"
        print(f"{indent}- Pasta: {nome} ({folder.content_count} mensagens)")
        
        # Lê até 3 mensagens desta pasta
        messages = folder.enumerate_messages()
        count = 0
        for msg_info in messages:
            if count >= 3:
                break
            
            sujeito = msg_info.subject if msg_info.subject else "(Sem Assunto)"
            remetente = msg_info.sender_representative_name if msg_info.sender_representative_name else "(Desconhecido)"
            
            print(f"{indent}    * De: {remetente} | Assunto: {sujeito}")
            count += 1
            
        for subfolder in folder.get_sub_folders():
            print_tree(subfolder, indent + "  ")

    print(f"Abrindo PST independentemente (aspose-email): {caminho_pst} ...")
    pst = None
    try:
        # Carrega o arquivo PST
        pst = PersonalStorage.from_file(caminho_pst)
        
        # Obtém a pasta raiz e lista a estrutura
        root_folder = pst.root_folder
        
        print("\n[+] Estrutura de Pastas e E-mails (Demo Aspose):")
        print("-" * 50)
        print_tree(root_folder)
        print("-" * 50)
        print("[!] Leitura concluída e arquivo fechado com segurança.")
        
    except Exception as e:
        print(f"Erro ao ler via Aspose.Email:\n{e}")
        return False
    finally:
        # Tenta invocar o coletor de lixo forçadamente ou fechar os manipuladores de arquivo no .NET/Python via Aspose
        if pst is not None:
            # Em versoes via rede (via-net), usa-se dispose ou fecha arquivo no escopo
            try:
                if hasattr(pst, 'dispose'):
                    pst.dispose()
            except AttributeError:
                pass
        
    return True

if __name__ == "__main__":
    arquivo = "archive.pst"
    
    print("=" * 50)
    print("        LEITOR DE ARQUIVO PST (.pst) INDEPENDENTE")
    print("=" * 50)
    print("Utilizando o ambiente isolado do Python 3.11\n")
    
    sucesso = ler_pst_aspose(arquivo)
    
    if not sucesso:
        print("\n[!] Falha ao ler o PST.")
        sys.exit(1)
