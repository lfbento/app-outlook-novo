import sys
import os
from pprint import pprint
# Add the src folder to path if needed
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.agents.caracol_flow import RodaCaracol

if __name__ == "__main__":
    motor = RodaCaracol()
    pergunta = "Quais são os equipamentos que deverão ser entregues dentro de março de 2026 no projeto Arauco?"
    print(f"Pergunta: {pergunta}")
    res = motor.processar_pergunta(pergunta)
    print("\n=== RESPOSTA DO AGENTE ===")
    print(res["final_answer"])
