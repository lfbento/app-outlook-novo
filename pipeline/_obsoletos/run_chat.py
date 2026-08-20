"""
O Caracol - Interface de Chat Terminal
Motor de Consulta RAG com Grafos Neo4j + Time Multi-Agente DeepSeek
"""
import sys
import os
import logging

# Garante que o import dos modulos internos funcione
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Forca UTF-8 no stdout para evitar problemas de encoding do Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='replace')

from src.agents.caracol_flow import consultar_caracol, neo4j_runner

# Configura logging mais silencioso para o chat
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s]: %(message)s')

BANNER = """
================================================================
                                                              
   [CARACOL]  O   C A R A C O L                               
                                                              
   Motor de Consulta RAG Baseado em Grafos                    
   Nacional Industria - Engenharia de Contratos               
                                                              
   Time de Agentes:                                           
   > Planejador  | Processista  | Comprador                   
   > Contratos   | Qualidade    | Orquestrador                
                                                              
   Comandos: 'sair' para encerrar | 'schema' para ver o DB   
================================================================
"""

def main():
    print(BANNER)
    
    while True:
        try:
            pergunta = input("\n>> Sua pergunta: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nAte logo!")
            break
        
        if not pergunta:
            continue
        
        if pergunta.lower() in ("sair", "exit", "quit", "q"):
            print("\nAte logo!")
            break
        
        if pergunta.lower() == "schema":
            print("\n[SCHEMA] Schema atual do Neo4j:")
            print(neo4j_runner.get_schema_summary())
            continue
        
        print("\n[CARACOL] Processando... (Orquestrador -> Especialista -> Neo4j -> Resposta)\n")
        
        try:
            resposta = consultar_caracol(pergunta)
            print(f"{'=' * 60}")
            print(f"[CARACOL] Resposta:\n")
            print(resposta)
            print(f"{'=' * 60}")
        except Exception as e:
            print(f"\n[ERRO] {e}")

    neo4j_runner.close()

if __name__ == "__main__":
    main()
