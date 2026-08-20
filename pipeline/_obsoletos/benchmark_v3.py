import sys
import os
import time
import logging

sys.path.append(os.getcwd())

from src.agents.caracol_flow import consultar_caracol

def benchmark():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    
    pergunta = "Quais são os equipamentos do projeto arauco que tem que ser entregues em março de 2026?"
    
    print("="*70)
    print(f"BENCHMARK CARACOL v3.1 (Base Totalmente Enriquecida)")
    print(f"PERGUNTA: {pergunta}")
    print("="*70)
    
    start = time.time()
    resposta = consultar_caracol(pergunta)
    elapsed = time.time() - start
    
    print(f"\nRESPOSTA:\n{resposta}")
    print(f"\n{'='*70}")
    print(f"TEMPO TOTAL: {elapsed:.1f}s")
    print(f"{'='*70}")

if __name__ == "__main__":
    benchmark()
