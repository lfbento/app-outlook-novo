import os

from src.markdown.email_formatter import EmailFormatter


def test_formatter_writes_file():
    f = EmailFormatter(output_dir="/tmp/md-teste-test")
    email = {
        "id": "abc123", "account": "a@x.com", "folder": "Caixa de Entrada",
        "subject": "Assunto do Email", "sender": "Fulano", "sender_email": "f@x.com",
        "to": "g@x.com", "cc": "", "date": "2026-08-20T06:59:03+00:00",
        "direction": "RECEBIDO", "body_html": "<p>Olá <b>mundo</b></p>", "body_text": "Olá mundo",
        "attachments": [],
    }
    path = f.format_email(email, [])
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert "Olá" in content
    assert "mundo" in content  # HTML convertido preserva texto
