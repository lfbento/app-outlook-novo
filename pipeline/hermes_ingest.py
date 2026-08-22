#!/usr/bin/env python3
"""Script para Hermes: executa pipeline de ingestão e envia notificação."""
import os
import sys
import time
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.join(SCRIPT_DIR)  # mesmo diretório
VENV_PYTHON = os.path.join(PIPELINE_DIR, ".venv", "bin", "python")
CONVERT_SCRIPT = os.path.join(PIPELINE_DIR, "convert_to_md.py")
NOTIFY_SCRIPT = os.path.join(PIPELINE_DIR, "notify.py")


def main():
    print("📧 Iniciando ingestão de e-mails...")
    start = time.time()

    # Executa o pipeline
    result = subprocess.run(
        [VENV_PYTHON, CONVERT_SCRIPT],
        capture_output=True, text=True, cwd=PIPELINE_DIR
    )

    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"❌ Pipeline falhou (exit {result.returncode})")
        print(result.stderr[-500:] if result.stderr else "sem stderr")
        # mesmo assim envia notificação de falha
        subprocess.run([VENV_PYTHON, NOTIFY_SCRIPT, str(elapsed)], cwd=PIPELINE_DIR)
        sys.exit(1)

    print(f"✅ Pipeline concluído em {elapsed:.0f}s")

    # Envia notificação por e-mail
    subprocess.run([VENV_PYTHON, NOTIFY_SCRIPT, str(elapsed)], cwd=PIPELINE_DIR)

    print("✅ Notificação enviada")


if __name__ == "__main__":
    main()
