import sys
import os
import time
import logging
import asyncio

sys.path.append(os.getcwd())
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s', handlers=[logging.StreamHandler(sys.stdout)])

from src.agents.caracol_flow import consultar_caracol

def benchmark():
    pergunta = "Verifique se temos na base o projeto Indorama. Faça um breve resumo do projeto e demonstre as datas de início e fim dele."
    
    print("="*70)
    print(f"BENCHMARK CARACOL - PROJETO INDORAMA")
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
