import sys
import os
import logging

# Ajusta o path para importar do src
sys.path.append(os.getcwd())

from src.agents.caracol_flow import consultar_caracol

def final_user_check():
    # Logs mínimos para o usuário ver o progresso
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    
    perguntas = [
        "Quem são os fornecedores de Santos para o projeto 311-25?",
        "Qual a data da última invoice do MTSCO?"
    ]
    
    print("\n" + "="*70)
    print("DEMONSTRAÇÃO FINAL CARACOL - CONSULTAS DE NEGÓCIO")
    print("="*70)
    
    for i, p in enumerate(perguntas, 1):
        print(f"\n[{i}/2] PERGUNTA: {p}")
        print("-" * 70)
        try:
            resposta = consultar_caracol(p)
            print(f"RESPOSTA: {resposta}")
        except Exception as e:
            print(f"ERRO TÉCNICO: {e}")
        print("-" * 70)

if __name__ == "__main__":
    final_user_check()
