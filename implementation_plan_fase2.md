# Fase 2: "O Caracol" - Motor de Consulta RAG Baseado em Grafos

## Objetivo (Escopo do Projeto)
Transformar a enorme base de arquivos Markdown de e-mails extraídos (armazenados no Obsidian/OneDrive) em uma infraestrutura viva de Inteligência Artificial chamada **"O Caracol"**. 
O sistema será composto por duas camadas:
1. **Neo4j (Banco de Dados em Grafo)**: Armazenará proativamente todas as entidades e seus relacionamentos. **(Atualização: O Schema será Dinâmico/Auto-organizável. Em vez de hardcodar apenas meia dúzia de classes, a IA que lerá o Markdown classificará o nó na classe mais apropriada existente no contexto do e-mail (Ex: Norma, Pessoa, Relatório, Reunião, Peça, Navio)).**
2. **LangGraph (Framework Multi-Agente)**: Um time de 6 agentes especialistas em setores da engenharia operados por LLM (Orquestrador, Planejador, Processista, Comprador, Contratos, Qualidade) capazes de traduzir as dúvidas do usuário em linguagem Cypher para executar raciocínio complexo sobre os dados lidos.

## Requisitos Confirmados pelo Usuário
- **Infraestrutura Docker**: Sim, o Docker está operacional e o Neo4j está rodando.
- **Variáveis Manuais x LLM**: A extração de números exatos será feita com o auxílio da IA durante o processo de ingestão/consulta.
- **Escolha do LLM**: O modelo **DeepSeek Reasoner** (`deepseek-reasoner`) será utilizado para governar os agentes.

## Proposed Changes

Os novos artefatos vão compor o cérebro da infraestrutura no Antigravity:

### 1. Ingestão e Sincronização (A ponte entre Obsidian e Neo4j)
#### [NEW] `src/ingestion/neo4j_sync.py`
Será o script de Batch-Load (Carga em Lote). 
- Fará o Parser dos arquivos do Obsidian, extraindo os metadados do `python-frontmatter` e os metadados textuais usando Regex.
- Traduzirá links `[[Entidade]]` do corpo do markdown em arestas concretas.
- **[NOVIDADE - Ontologia Dinâmica]**: Como há uma infinidade de assuntos corporativos, não usaremos Classes Fixas no código. O LLM avaliará cada Entidade e atribuirá a Label mais correta dinamicamente (Ex: Se achar o nome 'PETROBRAS', ele cria/mergeia como Label `:Empresa`. Se achar 'NR-13', ele cataloga como Label `:Norma`). As conexões (Arestas) também serão batizadas livremente pela IA (Ex: `[:APLICA_SE]`, `[:FORNECEDOR_DE]`).

### 2. Time Multi-Agente de Consulta (O Pensamento)
Construído com `LangGraph` e `Langchain`.
#### [NEW] `src/agents/caracol_flow.py`
Alojara as lógicas dos Grafos de Estados.
- Definirá os Nodes de Agente Especialista:
  - **Orquestrador**: Age como Mestre de Roteamento, entende o prompt do usuário e designa a tarefa de consulta.
  - **Planejador**: Tradutor Cypher especialista em MS Project, P6, caminhos críticos e prazos determinísticos.
  - **Processista**: Tradutor Cypher especialista em delineamento, BOM, Nesting e normas de Engenharia.
  - **Comprador**: Analista focado em valores nos Mapas de Compra, budget e fornecedores.
  - **Contratos**: Validador legal de impostos (ICMS/ISS) e faturamento de saldos abertos.
  - **Qualidade**: Guarding de normas (API/ASME) e ensaios END para barrar materiais não validados.
- O fluxo básico será: `Recebe Pergunta` -> `Delega Especialista` -> `Gera Código Cypher` -> `Executa no Neo4j Docker` -> `Gera Resposta Natural ao Usuário`.

### 3. Interface de Interação
#### [NEW] `chat_terminal.py` ou `run_chat.py`
Um CLI elegante no terminal do Antigravity onde o usuário poderá dialogar infinitamente com a equipe de agentes do Caracol mandando prompts em português.

## Verification Plan
1. **Ambiente Local**: Faremos a checagem da disponibilidade do Container Docker do Neo4j.
2. **Carga Teste Neo4j**: Executaremos o `neo4j_sync.py` para mapear os primeiros nós num banco local e visualizaremos os resultados graficamente via host do Neo4j (`http://localhost:7474`).
3. **Teste do LLM Cypher**: Realizaremos loops cegos fazendo perguntas sobre Saldo e Budget via script terminal e avaliaremos a querie Cypher pura cuspida pela cadeia do agente Comprador antes da execução em banco.
