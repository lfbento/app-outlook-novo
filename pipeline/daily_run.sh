#!/bin/bash
# daily_run.sh — Executa o pipeline de ingestão diária de e-mails
# Agendado via cron para rodar todos os dias às 10h (Brasília = 13h UTC)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/data/logs"
LOG_FILE="$LOG_DIR/daily_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

echo "=== Ingestão diária iniciada: $(date) ===" | tee "$LOG_FILE"

START_TIME=$(date +%s)

# Executa o pipeline
cd "$SCRIPT_DIR"
"$VENV/bin/python" convert_to_md.py 2>&1 | tee -a "$LOG_FILE"

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "=== Pipeline finalizado em ${ELAPSED}s ===" | tee -a "$LOG_FILE"

# Envia notificação por e-mail
"$VENV/bin/python" notify.py "$ELAPSED" 2>&1 | tee -a "$LOG_FILE"

echo "=== Concluído: $(date) ===" | tee -a "$LOG_FILE"
