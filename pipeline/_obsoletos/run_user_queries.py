import sys
import os
import logging

# Ajusta o path para importar do src
sys.path.append(os.getcwd())

from src.agents.caracol_flow import consultar_caracol

def run_queries():
    # Desativa logs excessivos para o output ficar limpo para o usuário
    logging.basicConfig(level=logging.ERROR)
    
    queries = [
        "Quem são os fornecedores de Santos para o projeto 311-25?",
        "Qual a data da última invoice do MTSCO?"
    ]
    
    for q in queries:
        print("\n" + "="*60)
        print(f"USUARIO: {q}")
        print("-" * 60)
        try:
            resposta = consultar_caracol(q)
            print(f"CARACOL: {resposta}")
        except Exception as e:
            print(f"ERRO: {e}")
        print("="*60)

if __name__ == "__main__":
    run_queries()
