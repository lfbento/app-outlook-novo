import os
import chromadb
from chromadb.utils import embedding_functions
import logging
import time
import random

logger = logging.getLogger(__name__)

class ChromaManager:
    """
    Controla o armazenamento de Embeddings (Vetorização) para busca semântica em todo
    o conteúdo dos e-mails (corpo e anexos).
    Como não usaremos OpenAI e a DeepSeek NÃO possui uma API de embeddings,
    utilizaremos o modelo embutido gratuito do ChromaDB (all-MiniLM-L6-v2)
    que roda localmente gerando vetores aceitáveis mesmo sem placa de vídeo (usando a CPU).
    """
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        
        try:
            # Inicializa o Client persistente do Chroma localmente
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            
            # Utiliza a API do Gemini para embeddings (Cloud) - Resolve erro de memória local
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logger.error("ERRO: GEMINI_API_KEY não encontrada no .env")
                # Fallback para o padrão se não houver chave (pode dar erro de memória)
                self.embedding_ef = embedding_functions.DefaultEmbeddingFunction()
            else:
                self.embedding_ef = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
                    api_key=api_key,
                    model_name="models/gemini-embedding-001",
                    task_type="RETRIEVAL_DOCUMENT"
                )
            
            # Cria ou busca a coleção (Tabela) de vetores de emails
            self.collection = self.client.get_or_create_collection(
                name="emails_and_documents_vectors",
                embedding_function=self.embedding_ef
            )
            logger.info("ChromaDB configurado com Gemini Embeddings (Cloud).")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar VectorStore (ChromaDB Local): {e}")
            raise e

    def add_documents(self, documents: list[str], metadatas: list[dict], ids: list[str]):
        """
        Adiciona lotes de blocos de texto ao Banco Vetorial com seus respectivos embeddings gerados na nuvem.
        Implementa Retry com Exponential Backoff para lidar com limites de cota da API (Erro 429).
        """
        if not documents:
            return
            
        max_retries = 7  # Aumentado para lidar com bloqueios mais longos da cota gratuita
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"Adicionou {len(documents)} chunks ao DB Vetorial.")
                # Pequeno intervalo de segurança entre requisições
                time.sleep(0.5)
                return
            except Exception as e:
                error_msg = str(e).lower()
                # Verifica se é um erro de cota (429) ou sobrecarga
                if "429" in error_msg or "quota" in error_msg or "resource_exhausted" in error_msg:
                    delay = (base_delay ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Limite de cota Gemini atingido. Tentativa {attempt + 1}/{max_retries}. Retentando em {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Erro inesperado no armazenamento vetorial: {e}")
                    break
        
        logger.error(f"Falha ao indexar documento após {max_retries} tentativas.")

    def semantic_search(self, query: str, top_k: int = 5):
        """Busca mensagens e anexos relevantes para a consulta do usuário."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )
            return results
        except Exception as e:
            logger.error(f"Pesquisa falhou: {e}")
            return []
