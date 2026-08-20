import os
import glob
import json
import logging
from neo4j import GraphDatabase
import frontmatter
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from src.extraction.deepseek_client import DeepSeekClient

# --- Cargar Configurações ---
load_dotenv()
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "caracol_admin"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

logger = logging.getLogger(__name__)

# --- Schemas de Extração ---
class GraphNode(BaseModel):
    id: str = Field(description="Identificador único da Entidade")
    label: str = Field(description="Rótulo em PascalCase (ex: Empresa, Norma, Relatorio, Navio, Projeto, Pessoa)")
    properties: Dict[str, Any] = Field(description="Dicionário com propriedades adicionais da entidade")

class GraphRelationship(BaseModel):
    source: str = Field(description="ID do nó de origem")
    target: str = Field(description="ID do nó de destino")
    type: str = Field(description="Tipo do relacionamento em UPPERCASE_WITH_UNDERSCORES (ex: TRABALHA_EM, CITA, APLICA_SE)")

class GraphOntology(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list, description="Lista de nós identificados")
    relationships: List[GraphRelationship] = Field(default_factory=list, description="Lista de relacionamentos entre nós")

class Neo4jSync:
    def __init__(self, max_budget: float = 9.90):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.deepseek = DeepSeekClient(api_key=DEEPSEEK_API_KEY, max_budget=max_budget)
        self.processed_ids = self._load_processed_ids()
        self.system_prompt = (
            "Você é um engenheiro de ontologias extraindo dados de e-mails corporativos (Markdown). "
            "Sua tarefa é Analisar o Frontmatter e o Texto e identificar Entidades e Relacionamentos para um banco de dados Neo4j. "
            "Retorne APENAS o JSON estruturado seguindo o schema informado. Não crie nós demais (limite de 10-15 nós principais). "
            "Garanta que os rótulos de nós sejam PascalCase e Tipos de Relacionamentos sejam CAIXA_ALTA.\n\n"
            "REGRAS CRITICAS DE EXTRAÇÃO DE PROPRIEDADES:\n"
            "1. DATAS: Sempre que houver uma data de entrega, prazo, deadline ou vencimento, "
            "   extraia como propriedade 'data_entrega' no formato YYYY-MM-DD. "
            "   Se houver TABELA no corpo do e-mail com colunas como Equipamento/Prazo/Data/Delivery, "
            "   extraia CADA LINHA como um nó Equipamento separado com sua data_entrega.\n"
            "2. VALORES MONETÁRIOS: Sempre que houver um valor em dinheiro, extraia como propriedade 'valor' (número) "
            "   e 'moeda' (texto: 'BRL', 'USD', 'EUR'). Ex: R$ 150.000,00 -> valor: 150000, moeda: 'BRL'.\n"
            "3. UNIDADES DE MEDIDA: Sempre que houver quantidades com unidade, extraia como propriedade "
            "   'quantidade' (número) e 'unidade' (texto: 'kg', 'm', 'un', 'pç', 'ton', 'mm', 'pol', 'kit'). "
            "   Ex: 25 toneladas -> quantidade: 25, unidade: 'ton'.\n"
            "4. NÚMEROS GERAIS: Extraia de forma agressiva qualquer NÚMERO EXATO "
            "   (Budget, Status percentual, Tamanhos, Diâmetros) nas properties do nó correspondente.\n"
        )
        
    def close(self):
        self.driver.close()

    def is_already_processed(self, doc_id: str) -> bool:
        """Verifica se o documento já está no set de processados (em memória)."""
        return doc_id in self.processed_ids

    def _load_processed_ids(self) -> set:
        """Carrega todos os IDs de documentos já existentes no Neo4j de uma só vez."""
        logger.info("Carregando IDs já processados do Neo4j para otimizar o reinício...")
        with self.driver.session() as session:
            result = session.run("MATCH (d:Documento) RETURN d.id as id")
            ids = {record["id"] for record in result}
            logger.info(f"{len(ids)} documentos encontrados no banco.")
            return ids

    def discover_ontology(self, text: str) -> dict:
        instruction = self.system_prompt + "\n\nJSON Schema Exigido:\n" + json.dumps(GraphOntology.model_json_schema(), indent=2)
        
        # Usa o DeepSeekClient que já lida com orçamento e chamadas à API
        try:
            # Adaptamos a chamada para usar o método do DeepSeekClient ou chamamos o client interno
            response = self.deepseek.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": f"Extraia o grafo do texto a seguir:\n\n{text[:15000]}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Atualiza o custo no DeepSeekClient
            usage = response.usage
            self.deepseek._update_cost(usage.prompt_tokens, usage.completion_tokens)
            
            if self.deepseek.is_budget_exceeded():
                raise Exception("Budget Exceeded")

            raw_json_str = response.choices[0].message.content
            parsed = json.loads(raw_json_str)
            # Valida via Pydantic
            validated = GraphOntology(**parsed)
            return validated.model_dump()
        except Exception as e:
            raise e

    def process_markdown(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
            
        content = post.content
        metadata = post.metadata
        
        doc_id = os.path.basename(filepath).replace(".md", "")
        
        # Proteção contra reinício: verifica se já existe
        if self.is_already_processed(doc_id):
            logger.info(f"[SKIP] Documento {doc_id} já existe no Neo4j.")
            return
        
        # Constrói um resumo para enviar ao LLM economizando tokens
        text_for_llm = f"### Metadados do Arquivo\n{json.dumps(metadata, ensure_ascii=False)}\n\n### Conteúdo\n{content}"
        
        try:
            graph_data = self.discover_ontology(text_for_llm)
        except Exception as e:
            logger.error(f"Erro ao extrair ontologia para {doc_id}: {e}")
            return
            
        with self.driver.session() as session:
            # Documento Raiz
            session.execute_write(self._create_document_node, doc_id, metadata)
            
            # Thread (Novo)
            thread_id = metadata.get("thread_id")
            if thread_id:
                session.execute_write(self._merge_thread_node, thread_id, metadata.get("conversation_topic", ""))
                session.execute_write(self._link_doc_to_thread, doc_id, thread_id)

            # Nodes
            for node in graph_data.get("nodes", []):
                session.execute_write(self._merge_dynamic_node, node)
                
            # Relationships
            for rel in graph_data.get("relationships", []):
                session.execute_write(self._create_relationship, rel)
                
            # Links (Document -> Entities)
            for node in graph_data.get("nodes", []):
                session.execute_write(self._link_doc_to_entity, doc_id, node["id"])
            
            # Adiciona ao set de memória para evitar reprocessamento na mesma sessão
            self.processed_ids.add(doc_id)
                
        logger.info(f"[+] Processado {doc_id}: {len(graph_data.get('nodes', []))} nós, {len(graph_data.get('relationships', []))} rels")

    @staticmethod
    def _create_document_node(tx, doc_id, metadata):
        assunto = metadata.get("assunto") or metadata.get("subject") or "Desconhecido"
        remetente = metadata.get("remetente") or metadata.get("sender") or ""
        data = metadata.get("data") or metadata.get("date") or ""
        thread_id = metadata.get("thread_id") or ""
        
        tx.run(
            "MERGE (d:Documento {id: $id}) "
            "SET d.assunto = $assunto, d.data = $data, d.remetente = $remetente, d.thread_id = $thread_id",
            id=doc_id, assunto=str(assunto), data=str(data), remetente=str(remetente), thread_id=str(thread_id)
        )

    @staticmethod
    def _merge_thread_node(tx, thread_id, topic):
        tx.run(
            "MERGE (t:Thread {id: $id}) "
            "SET t.topico = $topic",
            id=thread_id, topic=str(topic)
        )

    @staticmethod
    def _link_doc_to_thread(tx, doc_id, thread_id):
        tx.run(
            "MATCH (d:Documento {id: $doc_id}) "
            "MATCH (t:Thread {id: $thread_id}) "
            "MERGE (d)-[:PERTENCE_A_THREAD]->(t)",
            doc_id=doc_id, thread_id=thread_id
        )

    @staticmethod
    def _merge_dynamic_node(tx, node):
        label = str(node.get("label", "Entidade")).replace(" ", "").replace("-", "")
        label = "".join(filter(str.isalnum, label))
        if not label: label = "Entidade"
        
        node_id = str(node["id"])
        props = node.get("properties") or {}
        
        # Remove 'id' from props if it exists to prevent multiple values error
        if 'id' in props:
            del props['id']
            
        query = f"MERGE (n:{label} {{id: $id}}) "
        if props:
            set_clauses = ", ".join([f"n.{k} = ${k}" for k in props.keys() if str(k).isalnum()])
            if set_clauses:
                query += f"SET {set_clauses}"
                
        tx.run(query, id=node_id, **props)

    @staticmethod
    def _create_relationship(tx, rel):
        rel_type = str(rel.get("type", "RELATED_TO")).upper().replace(" ", "_").replace("-", "_")
        rel_type = "".join(filter(lambda x: x.isalnum() or x == "_", rel_type))
        if not rel_type: rel_type = "RELATED_TO"
        
        tx.run(
            f"MATCH (a {{id: $source}}) MATCH (b {{id: $target}}) "
            f"MERGE (a)-[r:{rel_type}]->(b)",
            source=str(rel["source"]), target=str(rel["target"])
        )

    @staticmethod
    def _link_doc_to_entity(tx, doc_id, entity_id):
        tx.run(
            "MATCH (d:Documento {id: $doc_id}) MATCH (e {id: $entity_id}) "
            "MERGE (d)-[:CITA]->(e)",
            doc_id=doc_id, entity_id=str(entity_id)
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
    sync = Neo4jSync(max_budget=9.90)
    obsidian_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "obsidian")
    
    files = glob.glob(os.path.join(obsidian_dir, "*.md"))
    logger.info(f"Iniciando sincronização de {len(files)} arquivos...")
    
    for i, f in enumerate(files):
        try:
            logger.info(f"[{i+1}/{len(files)}] Sincronizando {os.path.basename(f)}...")
            sync.process_markdown(f)
        except Exception as e:
            if "Budget Exceeded" in str(e):
                logger.warning(f"!!! ORÇAMENTO ESGOTADO !!! O saldo de segurança de $0,05 USD está preservado.")
                break
            logger.error(f"Erro ao processar {f}: {e}")
        
    sync.close()
    logger.info(f"Sincronização finalizada. Custo Total: ${sync.deepseek.total_cost:.4f}")
