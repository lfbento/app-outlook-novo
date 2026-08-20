"""
Neo4j Ingestion Pipeline v4.0 (HÍBRIDO)
Combina extração determinística (Regex/Pandas) com inferência relacional (LLM).
"""

import os
import glob
import json
import logging
import time
from typing import Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv

from openai import AsyncOpenAI
import asyncio
import argparse

# Reaproveitando nossos motores robustos de extração manual
from enriquecer_tudo import extrair_tabelas
from enriquecer_datas_universal import extrair_texto_data, extrair_tabelas_data
from enriquecer_cronogramas import parse_date
import re

# Regex pré-compilada para MS Project
RE_PROJECT_LINE = re.compile(r"([A-Z0-9\-]{4,}).*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})")

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("ingestion_v4.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
# Silenciar logs verbosos de bibliotecas externas
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ==========================================
# Configurações e Clientes
# ==========================================
# (Conexão Neo4j movida para o neo4j_loader_http_v1.py)

# ==========================================
# Globals LLM (Configuração Gemini 1.5)
# ==========================================
# ==========================================
# Globals LLM (Migração para DeepSeek V3.2 / chat)
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY não configurada no .env")

# Configuração Groq (conforme solicitado pelo Gimi)
client_llm = AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
LLM_MODEL = "llama-3.1-8b-instant"

# ==========================================
# Etapa 1: Engine Determinístico (Fatos Duros)
# ==========================================
def extrair_fatos_deterministicos(filepath: str, content: str) -> dict:
    """Extrai Datas, Moedas, Unidades usando os scripts anteriores."""
    fatos = {}
    
    # 1. Moedas e Unidades
    tabelas_valores = extrair_tabelas(filepath)
    for reg in tabelas_valores:
        tag = reg["id_match"]
        if tag not in fatos: fatos[tag] = {}
        if "valor" in reg: fatos[tag]["valor"] = reg["valor"]
        if "moeda" in reg: fatos[tag]["moeda"] = reg["moeda"]
        if "quantidade" in reg: fatos[tag]["quantidade"] = reg["quantidade"]
        if "unidade" in reg: fatos[tag]["unidade"] = reg["unidade"]

    # 2. Datas Genéricas
    datas_gerais = extrair_tabelas_data(filepath) + extrair_texto_data(filepath)
    for reg in datas_gerais:
        tag = reg["id_match"]
        if tag not in fatos: fatos[tag] = {}
        fatos[tag]["data_entrega"] = reg["data_entrega"]

    # 3. Cronograma MS Project (Quebrado do MD)
    for line in content.split('\n'):
        m_broken = RE_PROJECT_LINE.search(line)
        if m_broken:
            tag = m_broken.group(1).strip()
            if tag not in fatos: fatos[tag] = {}
            fatos[tag]["data_inicio"] = parse_date(m_broken.group(2))
            fatos[tag]["data_entrega"] = parse_date(m_broken.group(3))

    return fatos

# ==========================================
# Etapa 2: LLM Relacional (Entidades)
# ==========================================
async def chamar_llm_com_resiliencia(doc_id: str, content: str, metadata: dict, fatos: dict, driver) -> dict:
    """Divide o conteúdo em chunks e extrai entidades em paralelo."""
    
    CHUNK_SIZE = 3000
    OVERLAP = 300
    
    if len(content) <= CHUNK_SIZE:
        chunks = [content]
    else:
        chunks = []
        for i in range(0, len(content), CHUNK_SIZE - OVERLAP):
            chunks.append(content[i : i + CHUNK_SIZE])
            if i + CHUNK_SIZE >= len(content): break

    merged_nodes = {}
    merged_edges = []
    
    # Concurrency control "Safe-Mode" (Garante estabilidade no WSL2/Docker Desktop)
    semaphore = asyncio.Semaphore(5) 
    
    # No Estágio 1 do Turbo Caracol, usamos o DISCO como checkpoint
    extraction_path = os.path.join("pipeline/data/extractions", f"{doc_id}.json")
    
    async def process_chunk(idx, chunk_text):
        chunk_id = f"{doc_id}_chunk_{idx}"
        
        # O checkpoint agora é feito no nível do arquivo JSON completo no main()
        # Mas mantemos a assinatura compatível para facilitar

        prompt = f"""
        Você é o MOTOR DE EXTRAÇÃO do Agente CARACOL. Sua missão é extrair conhecimento estruturado em JSON para um grafo Neo4j.
        Analise o texto abaixo sob as LENTES DOS AGENTES ESPECIALISTAS:
        
        1. 📅 PLANEJADOR: Extraia Datas, Deadlines, Prazos de entrega, Cronogramas e marcos do MS Project. Relacione-os a Projetos ou Equipamentos.
        2. 🔩 ENGENHEIRO: Identifique Equipamentos, TAGs (ex: 11-4106-TNQ-1067), Desenhos (DWG), Revisões técnicas e Folhas de Dados.
        3. 📦 SUPRIMENTOS/COMPRAS: Capture Ordens de Compra (OC), Fornecedores, Status de Fabricação, Expedição e Materiais (PMI).
        4. 🛡️ QUALIDADE (CQ): Extraia Itens de PIT, Mapas de Solda, Inspeções, Certificações e Pendências documentais de qualidade.
        5. 💰 FINANCEIRO: Identifique Valores monetários, Parcelas de pagamento, Impostos e Medições financeiras.
        6. 📜 CONTRATUAL: Capture anexos de contratos, aditivos, clausulas críticas e comunicações oficiais.

        # REGRAS DE OURO:
        - NÃO RESUMA. Se o texto lista 10 tanques, crie 10 nós de Equipamento.
        - Use IDs curtos e consistentes para os nós (ex: ID da TAG ou nome abreviado).
        - Saída OBRIGATÓRIA: {{ "nodes": [ {{ "id", "label", "properties": {{...}} }}, ... ], "edges": [ {{ "source", "target", "type", "properties": {{...}} }}, ... ] }}

        # FATOS DETERMINÍSTICOS (JA EXTRAÍDOS): {json.dumps(fatos, ensure_ascii=False)}
        # CONTEÚDO PARA ANÁLISE ({doc_id} BLK {idx+1}):
        ---
        {chunk_text}
        ---
        """

        async with semaphore:
            for attempt in range(5):
                try:
                    response = await client_llm.chat.completions.create(
                        model=LLM_MODEL,
                        messages=[
                            {"role": "system", "content": "Você é um extrator de grafos ultra-detalhista. Atua como um conjunto de 6 agentes especialistas certificados."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={'type': 'json_object'},
                        timeout=120
                    )
                    chunk_resp_text = response.choices[0].message.content
                    data = json.loads(chunk_resp_text)
                    if isinstance(data, list):
                        data = {"nodes": data, "edges": []} # Fallback se a IA retornar lista direta
                    
                    return data, idx, False
                except Exception as e:
                    logger.warning(f"Erro no Chunk {idx+1} ({doc_id}): {e}. Retentativa {attempt+1}/5")
                    await asyncio.sleep(2**attempt)
        return {"nodes": [], "edges": []}, idx, False

    tasks = [process_chunk(idx, text) for idx, text in enumerate(chunks)]
    if len(chunks) > 1:
        logger.info(f"  -> Disparando {len(chunks)} chunks em paralelo...")

    results = await asyncio.gather(*tasks)
    
    for data, idx, cached in results:
        if cached:
            # logger.info(f"  -> Reutilizando Chunk {idx+1}/{len(chunks)} (Cache)")
            pass
        else:
            logger.info(f"  [OK] Chunk {idx+1}/{len(chunks)} processado.")
            
        if not isinstance(data, dict):
            logger.warning(f"Chunk {idx+1} retornou formato inválido (não é dicionário). Pulando merge.")
            continue
            
        for node in data.get("nodes", []):
            nid = node.get("id")
            if nid: merged_nodes[nid] = node
        merged_edges.extend(data.get("edges", []))
    
    final_data = {"nodes": list(merged_nodes.values()), "edges": merged_edges}
    
    # Salvar em disco (Estágio 1 do Turbo Caracol)
    extraction_path = os.path.join("pipeline/data/extractions", f"{doc_id}.json")
    try:
        os.makedirs("pipeline/data/extractions", exist_ok=True)
        with open(extraction_path, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro ao salvar extração em disco para {doc_id}: {e}")

    return final_data

# ==========================================
# Etapa 3: Persistência Neo4j C/ Resiliência
# ==========================================
def salvar_no_neo4j(doc_id: str, data: dict, session, metadata: dict):
    for attempt in range(3):
        try:
            # 1. Criar/Garantir Documento e Thread
            thread_id = metadata.get('thread_id')
            topic = metadata.get('conversation_topic', 'Sem Assunto')
            
            if thread_id:
                session.run("""
                    MERGE (t:Thread {id: $thread_id})
                    SET t.topico = $topic
                    MERGE (d:Documento {id: $doc_id})
                    MERGE (d)-[:PERTENCE_A]->(t)
                """, thread_id=thread_id, topic=topic, doc_id=doc_id)
            else:
                session.run("""
                    MERGE (d:Documento {id: $doc_id})
                """, doc_id=doc_id)
            
            # 2. Nodes (Processar entidades extraídas) - FORA do if/else
            node_labels = {}
            for node in data.get("nodes", []):
                # Extrair label de "label" ou "labels"[0]
                label_val = node.get("label") or (node.get("labels")[0] if isinstance(node.get("labels"), list) else None) or "Entidade"
                label = "".join([c for c in label_val if c.isalnum() or c == '_'])
                if not label: label = "Entidade"
                if label[0].isdigit(): label = "N_" + label
                
                nid = node.get("id")
                if not nid or nid == doc_id: continue 
                
                node_labels[nid] = label # Mapa para as arestas

                # Flatten inner properties object se a IA aninhou
                if "properties" in node and isinstance(node["properties"], dict):
                    inner_props = node.pop("properties")
                    for pk, pv in inner_props.items():
                        if pk not in node:
                            node[pk] = pv

                props = {}
                for k, v in node.items():
                    if k in ('label', 'labels', 'id'): continue
                    if isinstance(v, (dict, list)):
                        props[k] = json.dumps(v, ensure_ascii=False)
                    else:
                        props[k] = v

                session.run(f"""
                    MERGE (n:{label} {{id: $id}})
                    SET n += $props
                """, id=nid, props=props)
                
                # Relacionar ao Documento
                session.run(f"""
                    MATCH (d:Documento {{id: $doc_id}})
                    MATCH (n:{label} {{id: $nid}})
                    MERGE (d)-[:CITA]->(n)
                """, doc_id=doc_id, nid=nid)
                
            # 3. Edges (Relacionamentos entre entidades)
            for edge in data.get("edges", []):
                src = edge.get("source")
                tgt = edge.get("target")
                rel = "".join([c for c in edge.get("type", "LIGADO_A") if c.isalnum() or c == '_']).upper()
                if not rel: rel = "LIGADO_A"
                if rel[0].isdigit(): rel = "R_" + rel
                
                if not src or not tgt: continue
                
                s_label = node_labels.get(src, "Entidade")
                t_label = node_labels.get(tgt, "Entidade")
                
                session.run(f"""
                    MATCH (s:{s_label} {{id: $src}})
                    MATCH (t:{t_label} {{id: $tgt}})
                    MERGE (s)-[:{rel}]->(t)
                """, src=src, tgt=tgt)
            return True
        except Exception as e:
            logger.error(f"Erro Neo4j no doc {doc_id}: {e}. Retrying {attempt+1}/3")
            time.sleep(2)
    return False

# ==========================================
# Loop Principal
# ==========================================
import sys

async def main():
    parser = argparse.ArgumentParser(description="CARACOL v4.0 - Pipeline de Ingestão")
    parser.add_argument("--clear-base", action="store_true", help="Zera o banco Neo4j antes de começar")
    parser.add_argument("specific_file", nargs="?", help="Caminho para um arquivo .md específico")
    args = parser.parse_args()

    obsidian_dir = "pipeline/data/obsidian"
    
    if args.specific_file:
        files = [args.specific_file]
    else:
        files = sorted(glob.glob(os.path.join(obsidian_dir, "*.md")))
        
    total = len(files)
    logger.info(f"CARACOL v4.0 (EXTRATOR) - PIPELINE DESACOPLADO INICIADO")
    logger.info(f"Encontrados {total} arquivos.")
    processed_this_run = 0
    LIMIT_TEST = 10
    
    # No Estágio 1, não limpamos nada no Neo4j. Criamos apenas a pasta de despejo.
    os.makedirs("pipeline/data/extractions", exist_ok=True)

    for i, filepath in enumerate(files):
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                
            # Parse frontmatter simples
            metadata = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].split("\n"):
                        if ":" in line:
                            k, v = line.split(":", 1)
                            metadata[k.strip()] = v.strip().strip('"')
                            
            doc_id = metadata.get("id", os.path.basename(filepath))
            
            # Checkpoint de Disco (Stage 1)
            extraction_path = os.path.join("pipeline/data/extractions", f"{doc_id}.json")
            if os.path.exists(extraction_path):
                logger.info(f"[{i+1}/{total}] SKIP: {doc_id[:15]}... (Já extraído)")
                continue

            print("\n" + "="*60)
            logger.info(f"📁 ARQUIVO [{i+1} / {total}] -> {doc_id}")
            print("="*60)
            
            # Pular arquivos vazios ou sem conteúdo real
            if len(content.strip()) < 10:
                logger.warning(f"Arquivo vazio ou muito curto: {filepath}. Pulando.")
                continue

            # 1. Pipeline Determinístico (B3: não bloqueia o event loop)
            fatos_duros = await asyncio.to_thread(extrair_fatos_deterministicos, filepath, content)

            # 2. Extração Relacional (LLM) -> Já salva em disco internamente
            await chamar_llm_com_resiliencia(doc_id, content, metadata, fatos_duros, None)
            
            logger.info(f"✅ Arquivo {doc_id} extraído e salvo em disco.")
            
            processed_this_run += 1
            if processed_this_run >= LIMIT_TEST:
                logger.info(f"🛑 ESTÁGIO 1 CONCLUÍDO: Limite de {LIMIT_TEST} arquivos atingido.")
                break
            
        except Exception as e:
            logger.error(f"Falha total processando {filepath}: {e}")

    logger.info("EXTRAÇÃO (ESTÁGIO 1) FINALIZADA.")

if __name__ == "__main__":
    asyncio.run(main())
