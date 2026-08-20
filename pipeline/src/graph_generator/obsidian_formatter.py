import os
import re
from typing import Dict, Any

class ObsidianFormatter:
    """
    Constrói arquivos Markdown no formato nativo do Obsidian,
    adicionando YAML Frontmatter e os famosos `[[Wikilinks]]` para gerar
    as arestas do Knowledge Graph localmente.
    """
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _sanitize_filename(self, text: str) -> str:
        """Limpa as strings para usarmos como nomes de arquivos válidos no Windows/Mac."""
        # Remove caracteres indesejados mantendo o espaço
        safe_text = re.sub(r'[<>:"/\\|?*]', '', str(text))
        # Remove caracteres de controle (ASCII 0-31) que também são inválidos
        safe_text = re.sub(r'[\x00-\x1f]', '', safe_text)
        return safe_text.strip()[:100]

    def create_markdown(self, email_data: Dict[str, Any], extracted_entities: Dict[str, Any]) -> str:
        """
        Gera um arquivo .md no diretório designado contendo as informações e os links do Obsidian.
        """
        # Trata dados do email original
        msg_id = email_data.get('id', 'unknown')
        subject = self._sanitize_filename(email_data.get('subject', 'Sem Assunto'))
        date = email_data.get('date', 'Data Desconhecida')
        sender = email_data.get('sender', 'Desconhecido')
        thread_id = email_data.get('thread_id', '')
        conversation_topic = email_data.get('conversation_topic', '')
        
        # O arquivo do email em si
        filename = f"{subject}_{msg_id[:6]}.md"
        filepath = os.path.join(self.output_dir, filename)

        # Trata dados do JSON Extraído do DeepSeek
        summary = extracted_entities.get("executive_summary", "Sem resumo gerado.")
        
        people = [p["name"] for p in extracted_entities.get("people", [])]
        companies = [c["name"] for c in extracted_entities.get("companies", [])]
        projects = [p["name"] for p in extracted_entities.get("projects_and_locations", [])]
        equipments = [e["name"] for e in extracted_entities.get("equipments_and_documents", [])]

        # Monta blocos YAML Frontmatter (padrão de metadados do Obsidian)
        yaml_blocks = [
            "---",
            f"id: {msg_id}",
            f"thread_id: \"{thread_id}\"",
            f"conversation_topic: \"{conversation_topic}\"",
            f"date: \"{date}\"",
            f"type: e-mail",
            f"sender: \"{sender}\"",
            f"tags: [contrato, engenharia]",
            "---",
            ""
        ]

        # Monta Corpo Markdown
        body_blocks = [
            f"# {subject}",
            "",
            "## 📝 Resumo Executivo",
            f"> {summary}",
            "",
            "## 🏢 Entidades Envolvidas",
            ""
        ]

        # Helper para criar Wikilinks Obsidian [[link]]
        def wikilinks_list(items, title):
            if not items:
                return []
            lines = [f"### {title}"]
            for item in items:
                clean_item = self._sanitize_filename(item)
                # Formato essencial do Obsidian Node:
                lines.append(f"- [[{clean_item}]]")
            lines.append("")
            return lines

        body_blocks.extend(wikilinks_list(projects, "Projetos e Locais"))
        body_blocks.extend(wikilinks_list(companies, "Empresas"))
        body_blocks.extend(wikilinks_list(people, "Pessoas (Contatos)"))
        body_blocks.extend(wikilinks_list(equipments, "Equipamentos, Documentos e Pleitos"))
        
        # Seção de Thread
        if conversation_topic:
            body_blocks.append("## 🔗 Thread da Conversa")
            clean_topic = self._sanitize_filename(conversation_topic)
            body_blocks.append(f"- Tópico: [[{clean_topic}]]")
            body_blocks.append("")

        body_blocks.append("## 📧 Conteúdo Bruto (Corpo do e-mail)")
        # Inclui o texto cru como bloco de citação (truncado por segurança visual)
        raw_body = email_data.get('body', '')[:1500]
        body_blocks.append("```text")
        body_blocks.append(raw_body)
        if len(email_data.get('body', '')) > 1500:
           body_blocks.append(f"\n... [Corpo truncado no Markdown. Ver PST original]")
        body_blocks.append("```")
        body_blocks.append("")
        
        # Secão de Anexos
        if email_data.get('attachments'):
            body_blocks.append("## 📎 Anexos (Textos Extraídos via MarkItDown + Docling)")
            for att in email_data['attachments']:
                att_name = att.get('name', 'Desconhecido')
                att_text = str(att.get('extracted_text', ''))
                
                # Detectar motor usado (indicador visual)
                ext = os.path.splitext(att_name)[1].lower()
                if ext in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp']:
                    motor = "Docling"
                elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.tgz']:
                    motor = "Archive"
                elif ext in ['.mpp', '.mpx']:
                    motor = "MPXJ"
                elif ext in ['.dwg', '.dxf', '.exe', '.bin', '.dll']:
                    motor = "Skip"
                else:
                    motor = "MarkItDown"
                
                body_blocks.append(f"### Arquivo: {att_name} [Motor: {motor}]")
                body_blocks.append("```text")
                if not att_text.strip():
                    body_blocks.append("[Anexo vazio ou formato não textual]")
                else:
                    body_blocks.append(att_text)
                body_blocks.append("```")
                body_blocks.append("")

        full_markdown = "\n".join(yaml_blocks + body_blocks)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_markdown)

        return filepath
