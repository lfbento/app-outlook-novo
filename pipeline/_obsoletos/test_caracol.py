import logging
import sys
import os

# Ajusta o path para importar do src
sys.path.append(os.getcwd())

from src.agents.caracol_flow import consultar_caracol

def test_drive():
    # Remove emojis para evitar UnicodeEncodeError no Windows
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    
    print("\n" + "="*50)
    print("START: TEST-DRIVE CARACOL: PROJETO 311-25")
    print("="*50)
    
    pergunta = "Quais são os materiais de solda e invoices associadas ao projeto 311-25 da Nacional Indústria?"
    
    print(f"\n[USUARIO]: {pergunta}\n")
    
    try:
        resposta = consultar_caracol(pergunta)
        print("\n" + "-"*50)
        print("RESPOSTA FINAL DO CARACOL:")
        print(resposta)
        print("-"*50)
    except Exception as e:
        print(f"\nERRO NO TESTE: {e}")

if __name__ == "__main__":
    test_drive()
