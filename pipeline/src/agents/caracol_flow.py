"""
O Caracol v2.0 - Motor de Consulta RAG Baseado em Grafos
Melhorias: deepseek-chat (6x mais rapido), schema curado, few-shot, retry automatico
"""
import os
import json
import logging
from typing import TypedDict, Literal, Annotated
from operator import add

from dotenv import load_dotenv
from openai import OpenAI
from neo4j import GraphDatabase

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================
# Configuracoes
# ============================================================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "caracol_admin"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# ============================================================
# Schema Curado (embutido, sem query em runtime)
# ============================================================
SCHEMA_CURADO = """
## Labels Principais (com contagem real):
  :Documento (1699) -> [id, assunto, data, remetente, destinatarios, corpo, thread_id]
  :Pessoa (717) -> [id, nome, email]
  :Thread (493) -> [id, topico]
  :Empresa (402) -> [id, nome]
  :Equipamento (385) -> [id, nome, tipo, status, tag, quantidade, unidade, material, descricao, data_entrega, valor, moeda]
  :Projeto (346) -> [id, nome, descricao, status, valor, moeda]
  :Email (132) -> [id, assunto, data, remetente]
  :Material (104) -> [id, nome, tipo, descricao]
  :Norma (70) -> [id, nome]
  :Componente (61) -> [id, nome]
  :Contrato (58) -> [id, nome, valor]
  :Local (54) -> [id, nome]
  :NotaFiscal (42) -> [id, numero, data, valor, moeda]
  :Fornecedor (21) -> [id, nome]
  :Cronograma (8) -> [id, data_inicio, data_fim]
  :Tanque (8) -> [id, nome]

## Relacoes REAIS mais usadas (auditadas):
  Projeto: CITA(563), PERTENCE_A(285), INCLUI(190), REFERENCIA(177),
    ENVOLVE(156), RELACIONADO_A(146), ASSOCIADO_A(115), PARTE_DE(84),
    FORNECE_PARA(47), CLIENTE_DE(41)
  Equipamento: CITA(483), INCLUI(163), PERTENCE_A(110),
    INCLUI_EQUIPAMENTO(36), PARTE_DE(49), COMPOE(25), INSTALADO_EM(24)
  Documento: ENVIOU(x), ENVIOU_PARA(x), MENCIONA(x), REFERE_SE_A(x)

## REGRA CRITICA DE PERFORMANCE:
  NUNCA use [*..2] ou caminhos variaveis! Use relacoes DIRETAS.
  Correto: MATCH (p:Projeto)-[:PERTENCE_A|INCLUI|PARTE_DE]-(e:Equipamento)
  ERRADO:  MATCH (p:Projeto)-[*..2]-(e:Equipamento)  <-- PROIBIDO (leva minutos!)

  Evite toLower() quando possivel. Use CONTAINS direto (ja temos indices).
  Correto: WHERE p.id CONTAINS 'Arauco'
  Evitar: WHERE toLower(p.id) CONTAINS 'arauco'  <-- mais lento
"""

# ============================================================
# Few-Shot: Exemplos de Cypher que FUNCIONAM
# ============================================================
FEW_SHOT_EXAMPLES = """
## Exemplos de queries que FUNCIONAM neste banco (TESTADOS!):

1. Equipamentos de um projeto (relacao direta, rapido):
   MATCH (p:Projeto)-[:PERTENCE_A|INCLUI|PARTE_DE]-(e:Equipamento) WHERE p.id CONTAINS 'Arauco' RETURN e.id, e.nome, e.status, e.tag, e.material

2. Documentos com data em marco 2026:
   MATCH (d:Documento) WHERE d.data CONTAINS '2026-03' RETURN d.id, d.assunto, d.data LIMIT 20

3. Pessoas envolvidas em um projeto:
   MATCH (p:Projeto)-[:ENVOLVE|PERTENCE_A|INCLUI]-(pe:Pessoa) WHERE p.id CONTAINS 'Arauco' RETURN DISTINCT pe.id, pe.nome

4. Empresas ligadas a um projeto:
   MATCH (p:Projeto)-[:FORNECE_PARA|CLIENTE_DE|ENVOLVE|PERTENCE_A]-(e:Empresa) WHERE p.id CONTAINS '311-25' RETURN DISTINCT e.id, e.nome

5. Todos os projetos:
   MATCH (p:Projeto) RETURN p.id, p.nome LIMIT 30

6. Notas fiscais de uma empresa:
   MATCH (nf:NotaFiscal)-[:PERTENCE_A|ENVOLVE|REFERE_SE_A]-(emp:Empresa) WHERE toLower(emp.id) CONTAINS 'mtsco' RETURN nf.id, nf.data, nf.valor

7. Documentos que mencionam um equipamento:
   MATCH (d:Documento)-[:MENCIONA|CITA|REFERE_SE_A]-(e:Equipamento) WHERE e.nome CONTAINS 'Tank' RETURN d.id, d.assunto, d.data

8. Equipamentos por data de entrega especifica (ex: Março de 2026):
   MATCH (e:Equipamento) WHERE e.data_entrega CONTAINS '2026-03' OR e.data_entrega CONTAINS '03/2026' OR e.data_entrega CONTAINS '03/26' RETURN e.id, e.nome, e.tag, e.data_entrega, e.status
"""

# ============================================================
# Estado Compartilhado do Grafo (LangGraph State)
# ============================================================
class CaracolState(TypedDict):
    pergunta: str
    especialista: str
    cypher_query: str
    resultado_neo4j: str
    resposta_final: str
    historico: Annotated[list[str], add]

# ============================================================
# Cliente LLM (DeepSeek-Chat = rapido)
# ============================================================
class LLMClient:
    def __init__(self):
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    
    def chat(self, system_prompt: str, user_message: str) -> str:
        response = self.client.chat.completions.create(
            model="deepseek-chat",  # v2.0: 6x mais rapido que deepseek-reasoner
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1  # Baixa para Cypher deterministico
        )
        return response.choices[0].message.content

# ============================================================
# Neo4j Query Runner (com retry)
# ============================================================
class Neo4jRunner:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    def run_cypher(self, query: str) -> str:
        try:
            with self.driver.session() as session:
                result = session.run(query, timeout=30)  # v2.0: 30s timeout
                records = [dict(record) for record in result]
                if not records:
                    return "Nenhum resultado encontrado no banco de dados."
                output = json.dumps(records, default=str, ensure_ascii=False, indent=2)
                return output[:8000]
        except Exception as e:
            return f"ERRO_CYPHER: {str(e)}"
    
    def close(self):
        self.driver.close()

# ============================================================
# Prompts dos Agentes v2.0 (com schema curado + few-shot)
# ============================================================
PROMPT_BASE_CYPHER = (
    "Voce gera queries CYPHER para Neo4j. REGRAS OBRIGATORIAS:\n"
    "1. Retorne SOMENTE a query Cypher pura, sem explicacoes, sem markdown.\n"
    "2. Use CONTAINS para buscas de texto (nunca igualdade exata).\n"
    "3. Use caminhos variaveis [*..2] para conexoes indiretas.\n"
    "4. NUNCA invente labels ou relacoes. Use SOMENTE as que estao no schema abaixo.\n"
    "5. Sempre inclua RETURN com campos uteis (id, nome, data, etc).\n"
    "6. Use toLower() para buscas case-insensitive.\n\n"
    f"{SCHEMA_CURADO}\n\n"
    f"{FEW_SHOT_EXAMPLES}"
)

PROMPTS = {
    "orquestrador": (
        "Voce e o Orquestrador do time 'O Caracol'. Analise a pergunta e decida "
        "qual especialista deve responde-la. Especialistas disponiveis:\n"
        "- planejador: cronogramas, prazos, datas, entregas, MS Project\n"
        "- processista: materiais, equipamentos, BOM, engenharia, especificacoes\n"
        "- comprador: valores, fornecedores, orcamentos, budget, precos\n"
        "- contratos: impostos, faturamento, notas fiscais, retencoes\n"
        "- qualidade: normas API/ASME, ensaios, certificados, inspecoes\n\n"
        "Responda com APENAS o nome do especialista (uma unica palavra minuscula)."
    ),
    "planejador": (
        "Voce e o Agente Planejador. Gere Cypher para buscar cronogramas e prazos.\n"
        f"{PROMPT_BASE_CYPHER}"
    ),
    "processista": (
        "Voce e o Agente Processista. Gere Cypher para buscar materiais e equipamentos.\n"
        f"{PROMPT_BASE_CYPHER}"
    ),
    "comprador": (
        "Voce e o Agente Comprador. Gere Cypher para buscar fornecedores e valores.\n"
        f"{PROMPT_BASE_CYPHER}"
    ),
    "contratos": (
        "Voce e o Agente de Contratos. Gere Cypher para buscar notas fiscais e faturamento.\n"
        f"{PROMPT_BASE_CYPHER}"
    ),
    "qualidade": (
        "Voce e o Agente de Qualidade. Gere Cypher para buscar normas e certificados.\n"
        f"{PROMPT_BASE_CYPHER}"
    ),
    "sintetizador": (
        "Voce e o Sintetizador do time 'O Caracol'. Receba os dados brutos retornados pelo "
        "Neo4j e transforme-os em uma resposta profissional, clara e em portugues para o usuario. "
        "Inclua detalhes relevantes dos dados. Se os dados estiverem vazios ou com erro, "
        "comunique gentilmente que a informacao nao foi encontrada no grafo."
    ),
    "corretor_cypher": (
        "Voce recebe uma query Cypher que deu erro e a mensagem de erro. "
        "Corrija a query e retorne SOMENTE a query corrigida, sem explicacoes.\n"
        f"{SCHEMA_CURADO}"
    )
}

# ============================================================
# Nos do Grafo de Estado (LangGraph Nodes)
# ============================================================

llm = LLMClient()

def node_orquestrador(state: CaracolState) -> dict:
    """Decide qual especialista tratar a pergunta."""
    pergunta = state["pergunta"]
    resposta = llm.chat(PROMPTS["orquestrador"], pergunta).strip().lower()
    
    validos = ["planejador", "processista", "comprador", "contratos", "qualidade"]
    if resposta not in validos:
        resposta = "processista"
    
    logger.info(f"[ORQUESTRADOR] Delegou para: {resposta}")
    return {
        "especialista": resposta,
        "historico": [f"[Orquestrador] Delegou para: {resposta}"]
    }

def node_especialista(state: CaracolState) -> dict:
    """Gera a query Cypher usando o especialista selecionado."""
    especialista = state["especialista"]
    pergunta = state["pergunta"]
    
    # v2.0: Schema ja esta embutido no prompt, sem query em runtime
    prompt = PROMPTS.get(especialista, PROMPTS["processista"])
    cypher = llm.chat(prompt, pergunta)
    
    # Limpa formatacao markdown
    cypher = cypher.strip()
    if cypher.startswith("```"):
        lines = cypher.split("\n")
        cypher = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    cypher = cypher.strip()
    
    logger.info(f"[CYPHER] [{especialista}] Cypher gerado:\n{cypher}")
    return {
        "cypher_query": cypher,
        "historico": [f"[{especialista}] Cypher: {cypher}"]
    }

def node_executor(state: CaracolState) -> dict:
    """Executa a query Cypher no Neo4j com retry automatico."""
    neo4j_runner = Neo4jRunner.get_instance()
    cypher = state["cypher_query"]
    resultado = neo4j_runner.run_cypher(cypher)
    
    # v2.0: Retry automatico se erro de sintaxe
    if resultado.startswith("ERRO_CYPHER:"):
        logger.warning(f"[RETRY] Cypher falhou, tentando corrigir: {resultado}")
        correcao_msg = f"Query com erro:\n{cypher}\n\nErro:\n{resultado}\n\nPergunta original: {state['pergunta']}"
        cypher_corrigido = llm.chat(PROMPTS["corretor_cypher"], correcao_msg)
        cypher_corrigido = cypher_corrigido.strip()
        if cypher_corrigido.startswith("```"):
            lines = cypher_corrigido.split("\n")
            cypher_corrigido = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        cypher_corrigido = cypher_corrigido.strip()
        
        logger.info(f"[RETRY] Cypher corrigido:\n{cypher_corrigido}")
        resultado = neo4j_runner.run_cypher(cypher_corrigido)
    
    logger.info(f"[NEO4J] Resultado ({len(resultado)} chars)")
    return {
        "resultado_neo4j": resultado,
        "historico": [f"[Executor] Resultado: {resultado[:200]}..."]
    }

def node_sintetizador(state: CaracolState) -> dict:
    """Traduz os dados brutos em resposta natural para o usuario."""
    pergunta = state["pergunta"]
    resultado = state["resultado_neo4j"]
    especialista = state["especialista"]
    
    contexto = (
        f"Pergunta original do usuario: {pergunta}\n"
        f"Especialista consultado: {especialista}\n"
        f"Dados retornados pelo Neo4j:\n{resultado}"
    )
    
    resposta = llm.chat(PROMPTS["sintetizador"], contexto)
    
    logger.info(f"[SINTETIZADOR] Resposta sintetizada gerada.")
    return {
        "resposta_final": resposta,
        "historico": [f"[Sintetizador] Resposta gerada com sucesso."]
    }

# ============================================================
# Montagem do Grafo LangGraph (Singleton)
# ============================================================
from langgraph.graph import StateGraph, START, END

_compiled_graph = None

def build_caracol_graph():
    """Constroi e compila o grafo de estado do Caracol (singleton)."""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph
    
    graph = StateGraph(CaracolState)
    graph.add_node("orquestrador", node_orquestrador)
    graph.add_node("especialista", node_especialista)
    graph.add_node("executor", node_executor)
    graph.add_node("sintetizador", node_sintetizador)
    
    graph.add_edge(START, "orquestrador")
    graph.add_edge("orquestrador", "especialista")
    graph.add_edge("especialista", "executor")
    graph.add_edge("executor", "sintetizador")
    graph.add_edge("sintetizador", END)
    
    _compiled_graph = graph.compile()
    return _compiled_graph

# ============================================================
# Funcao Principal de Consulta (API publica)
# ============================================================
def consultar_caracol(pergunta: str) -> str:
    """
    Ponto de entrada para fazer uma pergunta ao Caracol.
    Retorna a resposta sintetizada em portugues.
    """
    app = build_caracol_graph()
    
    estado_inicial = {
        "pergunta": pergunta,
        "especialista": "",
        "cypher_query": "",
        "resultado_neo4j": "",
        "resposta_final": "",
        "historico": []
    }
    
    resultado = app.invoke(estado_inicial)
    return resultado["resposta_final"]

# ============================================================
# Teste direto
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    
    pergunta_teste = "Quais são os equipamentos do projeto Arauco que estão para ser entregues em março de 2026"
    print(f"\n[CARACOL] Pergunta: {pergunta_teste}\n")
    
    resposta = consultar_caracol(pergunta_teste)
    print(f"\n[CARACOL] Resposta do Caracol:\n{resposta}")
