import os
import re
import logging
import sys
from dotenv import load_dotenv
from src.vector_store.chroma_manager import ChromaManager

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

_PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
OBSIDIAN_DIR = os.path.join(_PIPELINE_DIR, "data", "obsidian")
CHROMA_DIR = os.path.join(_PIPELINE_DIR, "data", "db", "chroma")

def extract_id_and_metadata(content):
    """Extrai ID e metadados básicos do YAML frontmatter usando regex."""
    try:
        yaml_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
        if not yaml_match:
            return None, None
            
        yaml_content = yaml_match.group(1)
        metadata = {}
        
        # Regex simples para campos chave
        id_match = re.search(r'^id:\s*(.*)', yaml_content, re.MULTILINE)
        subject_match = re.search(r'^subject:\s*"(.*)"', yaml_content, re.MULTILINE)
        date_match = re.search(r'^date:\s*"(.*)"', yaml_content, re.MULTILINE)
        thread_match = re.search(r'^thread_id:\s*"(.*)"', yaml_content, re.MULTILINE)
        
        msg_id = id_match.group(1).strip() if id_match else None
        
        metadata = {
            "source": "retro-feed",
            "date": date_match.group(1) if date_match else "unknown",
            "thread_id": thread_match.group(1) if thread_match else ""
        }
        
        return msg_id, metadata
    except Exception as e:
        logger.error(f"Erro ao extrair metadados: {e}")
        return None, None

def main():
    load_dotenv()
    logger.info("=== INICIANDO RETRO-VETORIZAÇÃO RESILIENTE ===")
    
    if not os.path.exists(OBSIDIAN_DIR):
        logger.error(f"Diretório não encontrado: {OBSIDIAN_DIR}")
        return

    chroma = ChromaManager(persist_dir=CHROMA_DIR)
    files = [f for f in os.listdir(OBSIDIAN_DIR) if f.endswith(".md")]
    
    logger.info(f"Encontrados {len(files)} arquivos para processar.")
    
    success_count = 0
    
    for filename in files:
        filepath = os.path.join(OBSIDIAN_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            msg_id, metadata = extract_id_and_metadata(content)
            
            if not msg_id:
                logger.warning(f"ID não encontrado no arquivo: {filename}. Pulando.")
                continue
                
            # Vetoriza o conteúdo COMPLETO (MD + Resumo + Anexos)
            # A nova lógica de add_documents já lida com o Retry (Erro 429) internamente
            chroma.add_documents(
                documents=[content],
                metadatas=[metadata],
                ids=[msg_id]
            )
            success_count += 1
            
        except Exception as e:
            logger.error(f"Erro ao processar {filename}: {e}")

    logger.info(f"=== RETRO-VETORIZAÇÃO CONCLUÍDA ===")
    logger.info(f"Sucesso: {success_count}/{len(files)}")

if __name__ == "__main__":
    main()
