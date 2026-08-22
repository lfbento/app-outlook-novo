# Graph Report - .  (2026-08-21)

## Corpus Check
- 83 files · ~52,875 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 405 nodes · 625 edges · 20 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 152 edges (avg confidence: 0.73)
- Token cost: 124,200 input · 24,800 output

## Community Hubs (Navigation)
- [[_COMMUNITY_File Format Routing|File Format Routing]]
- [[_COMMUNITY_Core Pipeline Orchestration|Core Pipeline Orchestration]]
- [[_COMMUNITY_Date Enrichment Pipeline|Date Enrichment Pipeline]]
- [[_COMMUNITY_Producer-Consumer Infrastructure|Producer-Consumer Infrastructure]]
- [[_COMMUNITY_Outlook PST Ingestion|Outlook PST Ingestion]]
- [[_COMMUNITY_Neo4j Graph Model|Neo4j Graph Model]]
- [[_COMMUNITY_Caracol RAG Agent|Caracol RAG Agent]]
- [[_COMMUNITY_Legacy Query Runners|Legacy Query Runners]]
- [[_COMMUNITY_Neo4j Sync Tools|Neo4j Sync Tools]]
- [[_COMMUNITY_Legacy Date Enrichment|Legacy Date Enrichment]]
- [[_COMMUNITY_Neo4j HTTP Loader|Neo4j HTTP Loader]]
- [[_COMMUNITY_Equipment Delivery Schedule|Equipment Delivery Schedule]]
- [[_COMMUNITY_MS Project Reader|MS Project Reader]]
- [[_COMMUNITY_Attachment Processing|Attachment Processing]]
- [[_COMMUNITY_Pip Bootstrap|Pip Bootstrap]]
- [[_COMMUNITY_Filename Debugging|Filename Debugging]]
- [[_COMMUNITY_API Diagnostics|API Diagnostics]]
- [[_COMMUNITY_Graph Verification Scripts|Graph Verification Scripts]]
- [[_COMMUNITY_Pip Bootstrap Script|Pip Bootstrap Script]]
- [[_COMMUNITY_Tank Edge Verification|Tank Edge Verification]]

## God Nodes (most connected - your core abstractions)
1. `debug()` - 20 edges
2. `DeepSeekClient` - 19 edges
3. `ConversionEngine` - 18 edges
4. `OutlookIngestor` - 16 edges
5. `Neo4jSync` - 16 edges
6. `main()` - 14 edges
7. `process()` - 14 edges
8. `consultar_caracol()` - 12 edges
9. `EmailExtractionModel` - 12 edges
10. `main()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `salvar_no_neo4j()` --semantically_similar_to--> `gerar_statements_doc()`  [INFERRED] [semantically similar]
  pipeline/neo4j_sync_v4.py → pipeline/neo4j_loader_http_v1.py
- `get_neo4j_driver()` --semantically_similar_to--> `get_driver()`  [INFERRED] [semantically similar]
  pipeline/config.py → pipeline/enriquecer_tudo.py
- `LLMClient` --semantically_similar_to--> `DeepSeekClient`  [INFERRED] [semantically similar]
  pipeline/src/agents/caracol_flow.py → pipeline/src/extraction/deepseek_client.py
- `Fábrica que roteia cada anexo para o engine mais adequado.     Fallback automáti` --uses--> `ConversionEngine`  [INFERRED]
  pipeline/src/ingestion/attachment_processor.py → pipeline/src/ingestion/format_router.py
- `OutlookIngestor` --semantically_similar_to--> `EmailIngestor`  [INFERRED] [semantically similar]
  pipeline/src/ingestion/outlook_reader.py → pipeline/src/ingestion/pst_reader.py

## Hyperedges (group relationships)
- **Equipment Delivery Tracking Table** — veja_cronograma, veja_prazo_entrega, veja_schedule_status, veja_clean_condensate_flash_tank, veja_formic_acid_tank, veja_scah_condensate_tank_1, veja_scah_condensate_tank_2, veja_pumping_tank, veja_bl_washing_bin_1, veja_bl_washing_bin_2, veja_bl_washing_bin_3 [EXTRACTED 0.90]
- **Fluxo da Fase 1 (Outlook -> RabbitMQ -> Markdown)** — pipeline_producer_py, pipeline_consumer_py, pipeline_src_ingestion_attachment_processor_py, fase1_documentacao_rabbitmq, fase1_documentacao_obsidian_v2 [EXTRACTED 0.90]
- **Time Multi-Agente do Caracol** — pipeline_src_agents_caracol_flow_py, implementation_plan_fase2_agente_orquestrador, implementation_plan_fase2_agente_planejador, implementation_plan_fase2_agente_processista, implementation_plan_fase2_agente_comprador, implementation_plan_fase2_agente_contratos, implementation_plan_fase2_agente_qualidade [EXTRACTED 0.90]
- **Motores de processamento de anexos (MarkItDown / Docling / MinerU)** — fase1_documentacao_markitdown, fase1_documentacao_docling, fase1_documentacao_mineru [EXTRACTED 0.85]
- **Producer/Consumer via RabbitMQ queue** — producer_main, consumer_run_consumer, rabbitmq_queue_outlook_ingestion [EXTRACTED 0.95]
- **Deterministic Neo4j Enrichment ($0, no LLM)** — enriquecer_tudo_main, enriquecer_datas_universal_main, enriquecer_cronogramas_main, neo4j_graph_database [INFERRED 0.85]
- **Decoupled Extraction -> Load Pipeline (Stage 1 -> Stage 2)** — neo4j_sync_v4_main, neo4j_loader_http_v1_main, extractions_json_store, neo4j_graph_database [INFERRED 0.85]
- **CARACOL Multi-Agent QA Pipeline** — caracol_flow_node_orquestrador, caracol_flow_node_especialista, caracol_flow_node_executor, caracol_flow_node_sintetizador [EXTRACTED 0.90]
- **Attachment Conversion Routing** — attachment_processor_attachmentprocessor, format_router_get_engine, archive_extractor_extract_archive, msproject_reader_process_msproject [EXTRACTED 0.85]
- **Email Extraction Schema** — schemas_emailextractionmodel, schemas_contractentity, schemas_companyentity, schemas_projectentity, schemas_equipmententity [EXTRACTED 0.95]
- **Caracol Query Harness Scripts** — benchmark_v2_benchmark, demo_final_demo_final, run_user_queries_run_queries, run_arauco_run_arauco_query, user_check_final_user_check [INFERRED 0.70]
- **Neo4j Graph Inspection Scripts** — inspect_neo4j_inspect_nodes, temp_neo4j_stats_main, verify_edges_pumping_tank_edges, check_progress_neo4j_progress [INFERRED 0.65]
- **Exercising the Caracol agent (consultar_caracol / RodaCaracol)** — benchmark_v3_benchmark, benchmark_indorama_benchmark, test_caracol_test_drive, test_agent_script [INFERRED 0.80]
- **Equipamento.data_entrega enrichment and query flow** — enriquecer_datas_extrair_dados_de_markdown, enriquecer_datas_atualizar_neo4j, answer_query_script, neo4j_loader_v1_salvar_no_neo4j [INFERRED 0.70]
- **Neo4j Documento/CITA cache lifecycle (invalidate → reload → verify)** — clear_updated_neo4j_docs_clear_neo4j, neo4j_loader_v1_main, verify_rel_script [INFERRED 0.70]

## Communities

### Community 0 - "File Format Routing"
Cohesion: 0.07
Nodes (42): _extract_7z(), extract_archive(), _extract_rar(), _extract_tar(), _extract_zip(), Archive Extractor — Descompacta ZIP, RAR, 7Z, TAR e processa recursivamente. Par, Extrai ZIP e retorna lista de (caminho_extraído, nome_original)., Extrai TAR/TAR.GZ/TAR.BZ2/TAR.XZ. (+34 more)

### Community 1 - "Core Pipeline Orchestration"
Cohesion: 0.07
Nodes (23): Check SQLite progress DB (SUCCESS/FAILED counts), ChromaManager, Controla o armazenamento de Embeddings (Vetorização) para busca semântica em tod, Adiciona lotes de blocos de texto ao Banco Vetorial com seus respectivos embeddi, Busca mensagens e anexos relevantes para a consulta do usuário., process_message(), Atualiza o sqlite de status independentemente., update_db_status() (+15 more)

### Community 2 - "Date Enrichment Pipeline"
Cohesion: 0.08
Nodes (34): get_neo4j_driver(), Configuração central do Pipeline CARACOL. Todos os caminhos são relativos à raiz, get_driver(), main(), parse_date(), Enriquecimento de Cronogramas MS Project v4.0 - $0 Extrai datas de início/fim de, atualizar_neo4j_batch(), extrair_tabelas_data() (+26 more)

### Community 3 - "Producer-Consumer Infrastructure"
Cohesion: 0.08
Nodes (24): main(), run_consumer(), Docling (motor PDF leve/OCR), Fase 2 em hardware separado (Ubuntu via Google Drive), main.py depreciado (ganho de velocidade/estabilidade), MarkItDown (motor de anexos leves), MinerU (motor PDF pesado), MinerU em venv isolado (conflito de dependências / Python 3.10–3.12) (+16 more)

### Community 4 - "Outlook PST Ingestion"
Cohesion: 0.08
Nodes (12): debug_pst(), ler_pst_aspose(), Lê o arquivo PST de forma independente, usando a biblioteca Aspose.Email.     Es, ProgressDB, Busca a maior data entre os e-mails processados., Lê e-mails nativamente do aplicativo Microsoft Outlook via COM (win32com)., EmailIngestor, ProgressDB (+4 more)

### Community 5 - "Neo4j Graph Model"
Cohesion: 0.12
Nodes (16): BaseModel, DeepSeekClient, Envia o texto bruto resultante da ingestão para o DeepSeek,         forçando a s, obsidian_v2/ (saída Markdown), Ontologia Dinâmica (labels/arestas atribuídas pelo LLM), GraphNode, GraphOntology, GraphRelationship (+8 more)

### Community 6 - "Caracol RAG Agent"
Cohesion: 0.11
Nodes (22): build_caracol_graph(), CaracolState, get_instance(), LLMClient, Neo4jRunner, node_especialista(), node_executor(), node_orquestrador() (+14 more)

### Community 7 - "Legacy Query Runners"
Cohesion: 0.1
Nodes (14): benchmark(), benchmark(), benchmark(), consultar_caracol(), Neo4jRunner, Ponto de entrada para fazer uma pergunta ao Caracol.     Retorna a resposta sint, demo_final(), run_arauco_query() (+6 more)

### Community 8 - "Neo4j Sync Tools"
Cohesion: 0.15
Nodes (11): check_db(), Check Neo4j Ingest Progress, inspect_nodes(), Neo4jSync, Verifica se o documento já está no set de processados (em memória)., Carrega todos os IDs de documentos já existentes no Neo4j de uma só vez., Reprocessamento Total v3.0 - Re-ingere todos os Markdowns com prompt enriquecido, reprocess_all() (+3 more)

### Community 9 - "Legacy Date Enrichment"
Cohesion: 0.15
Nodes (14): Query Equipamento Delivery Dates (March 2026), clear_neo4j(), atualizar_neo4j(), extrair_dados_de_markdown(), main(), normalizar_data(), Enriquecimento Direto de Datas v3.0 — Sem LLM, Sem Re-processamento Lê as tabela, Atualiza data_entrega nos nós existentes por TAG ou NOME. Retorna (atualizados, (+6 more)

### Community 10 - "Neo4j HTTP Loader"
Cohesion: 0.19
Nodes (13): Extractions JSON Store (data/extractions), neo4j_loader_http_v1.py (carregamento no Neo4j), _build_session(), gerar_statements_doc(), main(), Cria uma requests.Session com retry automático e connection pooling., Executa uma query individual (usada para checkpoints)., Executa múltiplos statements em uma única transação HTTP. (+5 more)

### Community 11 - "Equipment Delivery Schedule"
Cohesion: 0.21
Nodes (12): BL Washing Bin 1 (Item 11), BL Washing Bin 2 (Item 12), BL Washing Bin 3 (Item 13), Clean Condensate Flash Tank (Item 4), Red/Green Status Color Coding, Equipment Delivery Schedule (Cronograma 18/03/2024), Formic Acid Tank (Item 7), Delivery Deadline Column (PRAZO ENT.) (+4 more)

### Community 12 - "MS Project Reader"
Cohesion: 0.25
Nodes (10): _check_java(), _format_date(), _format_duration(), _format_percent(), process_msproject(), MS Project Reader — Lê arquivos .mpp e converte em Markdown tabular. Parte da ev, Verifica se Java está disponível no sistema., Formata data do MPXJ para string legível. (+2 more)

### Community 13 - "Attachment Processing"
Cohesion: 0.31
Nodes (10): AttachmentProcessor, Fábrica que roteia cada anexo para o engine mais adequado.     Fallback automáti, build_pending_map(), extract_attachments(), generate_id(), main(), process_folder(), process_outlook() (+2 more)

### Community 14 - "Pip Bootstrap"
Cohesion: 0.31
Nodes (9): bootstrap(), determine_pip_install_arguments(), include_setuptools(), include_wheel(), main(), monkeypatch_for_cert(), Install setuptools only if absent, not excluded and when using Python <3.12., Install wheel only if absent, not excluded and when using Python <3.12. (+1 more)

### Community 15 - "Filename Debugging"
Cohesion: 0.5
Nodes (4): generate_id(), Debug 3: Imprimir filenames gerados e comparar com os que existem no disco., sanitize_filename(), Obsidian vs Outlook Filename Mismatch Diagnostic

### Community 16 - "API Diagnostics"
Cohesion: 1.0
Nodes (2): Inspect ChromaDB Embedding Function Signature, Gemini API Ping Test

### Community 17 - "Graph Verification Scripts"
Cohesion: 1.0
Nodes (2): Dump All Graph Edges from Neo4j, Dump Extracted Document->Entity Data (v3.2)

### Community 42 - "Pip Bootstrap Script"
Cohesion: 1.0
Nodes (1): Pip Bootstrap Installer (get-pip)

### Community 43 - "Tank Edge Verification"
Cohesion: 1.0
Nodes (1): Verify Pumping Tank Edges

## Knowledge Gaps
- **102 isolated node(s):** `Lê o arquivo PST de forma independente, usando a biblioteca Aspose.Email.     Es`, `Enriquecimento Universal de Datas v4.0 - $0 / < 5 minutos Busca datas em múltipl`, `Extrai e converte data para YYYY-MM-DD.`, `Busca em texto corrido pareamentos de Identificador - Data (ex: Equipamento X -`, `Atualiza nós no Neo4j usando UNWIND para batching (muito mais rápido).` (+97 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `API Diagnostics`** (2 nodes): `Inspect ChromaDB Embedding Function Signature`, `Gemini API Ping Test`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Graph Verification Scripts`** (2 nodes): `Dump All Graph Edges from Neo4j`, `Dump Extracted Document->Entity Data (v3.2)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Pip Bootstrap Script`** (1 nodes): `Pip Bootstrap Installer (get-pip)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tank Edge Verification`** (1 nodes): `Verify Pumping Tank Edges`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `process()` connect `File Format Routing` to `Neo4j Sync Tools`, `Core Pipeline Orchestration`, `Attachment Processing`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Why does `DeepSeekClient` connect `Neo4j Graph Model` to `Neo4j Sync Tools`, `Core Pipeline Orchestration`, `Caracol RAG Agent`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `debug()` connect `Core Pipeline Orchestration` to `File Format Routing`, `Outlook PST Ingestion`, `Neo4j Graph Model`, `Legacy Date Enrichment`, `MS Project Reader`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `debug()` (e.g. with `._process_folder()` and `._extract_attachments()`) actually correct?**
  _`debug()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `DeepSeekClient` (e.g. with `GraphNode` and `GraphRelationship`) actually correct?**
  _`DeepSeekClient` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `ConversionEngine` (e.g. with `Teste rápido do format_router e imports.` and `AttachmentProcessor`) actually correct?**
  _`ConversionEngine` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 9 inferred relationships involving `OutlookIngestor` (e.g. with `Teste integrado com Outlook — processa 5 emails com a nova pipeline.` and `main()`) actually correct?**
  _`OutlookIngestor` has 9 INFERRED edges - model-reasoned connections that need verification._