# FASE 1 — Pipeline de Extração de E-mails do Outlook para Markdown

## Documentação Técnica Completa para Replicação em Outro Computador

> **Última atualização:** 2026-04-26
> **Versão:** 3.1 (Integração MinerU p/ PDFs Pesados)
> **Nome do Projeto:** CARACOL — Motor de Inteligência Multi-Agente
> **Plataforma:** Windows 10/11 (requer Microsoft Outlook Desktop instalado e Docker)

---

## 1. O QUE ESTA FASE FAZ

A Fase 1 passou por uma grande evolução na versão 3.0 para mitigar vazamentos de memória (OOM). O processo foi dividido em duas frentes isoladas que se comunicam via mensageria (RabbitMQ):

1. **Produtor (`producer.py`)**: Conecta ao Microsoft Outlook Desktop via COM (win32com), varre as pastas rapidamente, extrai os anexos salvando-os fisicamente como arquivos temporários para livrar a memória RAM e envia a requisição de processamento para a Fila do RabbitMQ.
2. **Consumidor (`consumer.py`)**: Fica escutando a fila. Puxa as requisições pacientemente (um por vez).
3. **Processamento de Anexos (No Consumidor)**:
   - **MarkItDown** → e-mails, Word, Excel, texto puro (rápido)
   - **Docling** → PDFs leves (≤3MB) e imagens (alta fidelidade com OCR)
   - **MinerU** → PDFs pesados (>3MB) e layouts complexos (alta fidelidade via sliding-window, em venv isolado para evitar estouro de memória)
4. **Geração**: Cria o arquivo Markdown (.md) em `pipeline/data/obsidian_v2/` contendo metadados e os textos extraídos.
5. **Limpeza**: Deleta os anexos físicos temporários para poupar disco.
6. **Rastreabilidade**: Gerencia progresso via SQLite para permitir retomada.

---

## 2. ESTRUTURA DE DIRETÓRIOS

```text
app-outlook-novo/
└── pipeline/                        # ← RAIZ DO PIPELINE
    │
    │  ── FASE 1 (Extração Outlook → Markdown via AMQP) ──
    ├── producer.py                  # Produtor veloz (Lê Outlook e Enfileira)
    ├── consumer.py                  # Consumidor pesado (Exige Docling e Gera MD)
    ├── docker-compose.yml           # Prepara o RabbitMQ na porta 5672/15672
    ├── config.py                    # Configurações centrais
    ├── requirements.txt             # Dependências Python (+ pika)
    ├── FASE1_DOCUMENTACAO.md        # ESTE ARQUIVO
    │
    │  ── FASE 2 (Removida deste Hardware) ──
    # Roda em outro PC (Ubuntu) após sincronizar a pasta obsidian_v2 via Google Drive
    │
    │  ── INFRAESTRUTURA ──
    ├── pst_venv/                    # Virtual env Python Principal (Consumidor/Produtor)
    ├── mineru_venv/                 # Virtual env Python Isolado (Motor p/ PDFs Grandes)
    ├── data/
    │   ├── obsidian_v2/             # ← SAÍDA ATUAL DA FASE 1 (.md gerados)
    │   ├── extractions/tmp_bin/     # ← ANEXOS FÍSICOS TEMPORÁRIOS (Nova Arquitetura)
    │   └── db/
    │       └── progress.sqlite      # Tracking de status cruzado (QUEUED / SUCCESS)
    │
    └── src/
        ├── ingestion/
        │   ├── outlook_reader.py    # Leitor COM atualizado para não explodir RAM
        │   ├── attachment_processor.py # Processador de anexos que consome do tmp_bin
        │   ├── format_router.py     # Roteador (MarkItDown vs Docling)
...
```

---

## 3. PRÉ-REQUISITOS DE SISTEMA

| Software | Versão Mínima | Por Quê |
|:---------|:--------------|:--------|
| **Windows** | 10 ou 11 | win32com só funciona nativamente no Windows |
| **Microsoft Outlook** | 2016+ (Desktop) | Fonte dos e-mails |
| **Docker Desktop** | Qualquer | Para hospedar o *RabbitMQ* |
| **Python** | 3.10+ | Runtime do pipeline |
| **Java JRE** | 8+ | Leitura MS Project .mpp |

---

## 4. INSTALAÇÃO PASSO A PASSO

### 4.1. Criar Virtual Environment Python e Dependências

```powershell
cd c:\bento\prg\app-outlook-novo\pipeline
python -m venv pst_venv
.\pst_venv\Scripts\Activate.ps1

pip install python-dotenv requests pyyaml pydantic pywin32 markitdown pika
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install docling py7zr rarfile mpxj jpype1
```

### 4.2. Instalar MinerU (Motor Isolado para PDFs Pesados)

O MinerU possui dependências que entram em conflito com o ambiente principal (como versões específicas do Torch). Além disso, **exige Python 3.10 a 3.12** (versões mais novas como 3.14 não são suportadas).

```powershell
cd c:\bento\prg\app-outlook-novo\pipeline
python -m venv mineru_venv
.\mineru_venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install "mineru[all]"
```
*(Na primeira vez que o consumer processar um PDF grande, o MinerU fará o download silencioso dos modelos da nuvem).*

### 4.3 Ligar o Mensageiro (RabbitMQ)

```powershell
# Subir o contêiner em segundo plano
docker-compose up -d rabbitmq
```
*(O Neo4j foi permanentemente desligado deste computador para poupar Gigabytes de RAM).*

---

## 5. COMO EXECUTAR (ARQUITETURA PÚBLICO-ALVO)

O script unificado `main.py` foi depreciado pelo ganho de velocidade e estabilidade.

1. **Abra o Microsoft Outlook**.
2. **Confirme se o RabbitMQ está rodando no Docker**.

### Terminal 1: Iniciar Extração (Producer)
```powershell
cd c:\bento\prg\app-outlook-novo\pipeline
.\pst_venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING='utf-8'

python producer.py
```
*Isto irá extrair do Outlook instantaneamente e enviar todas as coordenadas dos e-mails + anexos salvos fisicamente em `tmp_bin` para a malha da Fila AMQP.*

### Terminal 2: Iniciar Processamento IA (Consumer)
*(Pode ser iniciado, parado, e re-iniciado à vontade. Ele nunca perde trabalho).*
```powershell
cd c:\bento\prg\app-outlook-novo\pipeline
.\pst_venv\Scripts\Activate.ps1
$env:PYTHONIOENCODING='utf-8'

python consumer.py
```

### 5.3 Painel de Controle
* Entre em **http://localhost:15672**
* Usuário: `guest` | Senha: `guest`
* Aba `Queues`: Você verá a fila `outlook_ingestion` crescendo quando o Producer rodar e diminuindo quando o Consumer trabalhar.

---

## 6. A NOVA ARQUITETURA DO PIPELINE (v3.0)

O maior trunfo da v3.0 é a resiliência de memória RAM.

```text
┌────────────────┐      ┌─────────────────────────┐       ┌────────────────┐
│ Outlook COM    │ ───► │ producer.py             │ ────► │ RabbitMQ Queue │
│ (E-mails)      │      │ (Salva .pdf/.jpg físicos│       │ (JSON payload) │
└────────────────┘      │  em tmp_bin e envia ID) │       └───────┬────────┘
                        └─────────────────────────┘               │
                                                                  │
┌────────────────┐      ┌─────────────────────────┐               │
│ obsidian_v2/   │ ◄─── │ consumer.py             │ ◄─────────────┘
│ (Final .MD)    │      │ (Processa 1 msg por vez)│
└────────────────┘      └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │ attachment_processor.py │
                        │ Roteia entre Docling,   │
                        │ MinerU e MarkItDown.    │
                        │ Devolve texto e deleta. │
                        └─────────────────────────┘
```

**Como funciona a mitigação de OOM (Out Of Memory):**
O `win32com` não segura bytes na memória em variáveis Python. O `producer.py` salva-os no HD em milissegundos.
O `consumer.py` possui a trava `prefetch_count=1`. Ele adquire exatamente **1** e-mail pesadíssimo por vez, libera a memória RAM com o `gc.collect()` e apaga os resquícios físicos.
Adicionalmente, os processadores de anexo (Docling, MinerU, MarkItDown) são **sempre executados em subprocessos isolados via `multiprocessing`**. 
- Se o PDF tiver **≤ 3MB**, roda o Docling em um subprocesso.
- Se o PDF tiver **> 3MB**, o Docling é evitado (prevenção de OOM do motor C++) e o pipeline chama o CLI do **MinerU** no `mineru_venv`. MinerU utiliza *sliding-window* para fatiar o PDF infinito sem explodir a RAM.
- Se houver falha severa em qualquer um (ou timeout), o motor cai para o fallback universal e rápido (*MarkItDown*).

---

## 7. INTEGRAÇÃO FASE 2

Conforme restruturação, a **Fase 2 não será executada no mesmo Hardware**.
A pasta `app-outlook-novo/pipeline/data/obsidian_v2/` gerada deve ser sincronizada via **Google Drive** com a máquina Ubuntu de alta capacidade que processará pesadamente as chamadas com Grandes LLMs integrando essas lógicas para dentro de um Banco de Grafo Neo4j.
