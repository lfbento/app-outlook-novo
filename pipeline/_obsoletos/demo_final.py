import sys
import os
import logging

# Ajusta o path para importar do src
sys.path.append(os.getcwd())

from src.agents.caracol_flow import consultar_caracol

def demo_final():
    logging.basicConfig(level=logging.ERROR)
    
    pergunta = "Quais equipamentos estao associados ao projeto 311-25?"
    
    print("\n" + "="*60)
    print(f"USUARIO: {pergunta}")
    print("-" * 60)
    try:
        resposta = consultar_caracol(pergunta)
        print(f"CARACOL: {resposta}")
    except Exception as e:
        print(f"ERRO: {e}")
    print("="*60)

if __name__ == "__main__":
    demo_final()
