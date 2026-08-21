"""Formatador Markdown limpo para e-mails convertidos (substitui obsidian_formatter)."""
import os
import re
from typing import Any, Dict, List

from markdownify import markdownify as md


class EmailFormatter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    @staticmethod
    def _sanitize(text: str) -> str:
        safe = re.sub(r'[<>:"/\\|?*]', "", str(text))
        safe = re.sub(r"[\x00-\x1f]", "", safe)
        return safe.strip()[:120] or "sem-assunto"

    def format_email(self, email: Dict[str, Any], attachment_texts: List[str]) -> str:
        account = self._sanitize(email.get("account", "conta"))
        folder = self._sanitize(email.get("folder", "pasta"))
        out_dir = os.path.join(self.output_dir, account, folder)
        os.makedirs(out_dir, exist_ok=True)

        subject = self._sanitize(email.get("subject", "Sem Assunto"))
        filename = f"{email.get('id', 'x')[:6]}_{subject}.md"
        filepath = os.path.join(out_dir, filename)

        # corpo: preferir HTML -> markdown (preserva tabelas/negrito/links)
        body_html = email.get("body_html", "")
        if body_html and body_html.strip():
            body = md(body_html, heading_style="ATX")
        else:
            body = email.get("body_text", "")

        lines = [
            "---",
            f"id: {email.get('id', '')}",
            f"account: \"{email.get('account', '')}\"",
            f"folder: \"{email.get('folder', '')}\"",
            f"direction: {email.get('direction', '')}",
            f"date: \"{email.get('date', '')}\"",
            f"sender: \"{email.get('sender', '')}\"",
            f"sender_email: \"{email.get('sender_email', '')}\"",
            f"to: \"{email.get('to', '')}\"",
            f"cc: \"{email.get('cc', '')}\"",
            "---",
            "",
            f"# {email.get('subject', 'Sem Assunto')}",
            "",
            "## 📧 Corpo",
            "",
            body.strip(),
            "",
        ]

        if attachment_texts:
            lines.append("## 📎 Anexos")
            lines.append("")
            for att_text in attachment_texts:
                lines.append(att_text.strip())
                lines.append("")

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        return filepath
