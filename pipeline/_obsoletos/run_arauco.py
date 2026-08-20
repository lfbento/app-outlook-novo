import sys
import os
import logging

# Ajusta o path para importar do src
sys.path.append(os.getcwd())

from src.agents.caracol_flow import consultar_caracol

def run_arauco_query():
    # Logs mínimos
    logging.basicConfig(level=logging.ERROR)
    
    pergunta = "quais equipamentos do projeto Valmet Arauco temos que entrega em marco 2026?"
    
    print("\n" + "="*70)
    print(f"USUARIO: {pergunta}")
    print("-" * 70)
    try:
        resposta = consultar_caracol(pergunta)
        print(f"CARACOL: {resposta}")
    except Exception as e:
        print(f"ERRO: {e}")
    print("="*70)

if __name__ == "__main__":
    run_arauco_query()
