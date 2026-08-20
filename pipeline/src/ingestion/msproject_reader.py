"""
MS Project Reader — Lê arquivos .mpp e converte em Markdown tabular.
Parte da evolução Fase 1 do Pipeline CARACOL.

Requer:
- mpxj (pip install mpxj)
- jpype1 (pip install jpype1)
- Java JRE 8+ instalado no sistema
"""
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Flag global para evitar tentar repetidamente se Java não está disponível
_java_available = None


def _check_java() -> bool:
    """Verifica se Java está disponível no sistema."""
    global _java_available
    if _java_available is not None:
        return _java_available

    try:
        import jpype
        if not jpype.isJVMStarted():
            jpype.startJVM()
        _java_available = True
    except ImportError:
        logger.warning("jpype1 não instalado — arquivos MS Project não podem ser lidos (pip install jpype1)")
        _java_available = False
    except Exception as e:
        logger.warning(f"Java JRE não disponível — arquivos MS Project não podem ser lidos: {e}")
        _java_available = False

    return _java_available


def _format_date(dt) -> str:
    """Formata data do MPXJ para string legível."""
    if dt is None:
        return "—"
    try:
        # MPXJ retorna java.util.Date ou LocalDateTime via JPype
        if hasattr(dt, 'toString'):
            dt_str = str(dt.toString())
            # Tentar parsear o formato Java
            try:
                parsed = datetime.strptime(dt_str[:10], "%Y-%m-%d")
                return parsed.strftime("%d/%m/%Y")
            except ValueError:
                return dt_str[:10]
        if isinstance(dt, datetime):
            return dt.strftime("%d/%m/%Y")
        return str(dt)[:10]
    except Exception:
        return str(dt)[:10] if dt else "—"


def _format_duration(dur) -> str:
    """Formata duração do MPXJ."""
    if dur is None:
        return "—"
    try:
        return str(dur)
    except Exception:
        return "—"


def _format_percent(val) -> str:
    """Formata percentual."""
    if val is None:
        return "0%"
    try:
        if hasattr(val, 'doubleValue'):
            return f"{int(val.doubleValue())}%"
        return f"{int(float(str(val)))}%"
    except Exception:
        return str(val)


def process_msproject(temp_path: str, filename: str) -> str:
    """
    Lê um arquivo MS Project (.mpp/.mpx) e retorna Markdown tabular.

    Args:
        temp_path: caminho do arquivo no disco
        filename: nome original do arquivo

    Returns:
        Texto Markdown com tabela de tarefas do cronograma
    """
    # Verificar Java
    if not _check_java():
        return f"[📊 {filename}: Requer Java JRE para leitura de MS Project — instale de https://adoptium.net]"

    try:
        import mpxj

        reader = mpxj.UniversalProjectReader()
        project = reader.read(temp_path)

        if project is None:
            return f"[📊 {filename}: Arquivo MS Project vazio ou corrompido]"

        # ── Extrair informações do projeto ────────────────────────
        lines = [f"[📊 Cronograma MS Project: {filename}]", ""]

        # Metadata do projeto
        proj_name = ""
        try:
            proj_name = str(project.projectProperties.projectTitle or filename)
        except Exception:
            proj_name = filename

        if proj_name and proj_name != filename:
            lines.append(f"**Projeto:** {proj_name}")
            lines.append("")

        # ── Tabela de tarefas ─────────────────────────────────────
        lines.append("| WBS | Tarefa | Início | Fim | Duração | % | Recurso |")
        lines.append("|-----|--------|--------|-----|---------|---|---------|")

        task_count = 0
        completed_count = 0

        for task in project.tasks:
            if task is None:
                continue

            try:
                task_id = str(task.wbs or task.id or "")
                task_name = str(task.name or "Sem nome")
                start = _format_date(task.start)
                finish = _format_date(task.finish)
                duration = _format_duration(task.duration)
                pct = _format_percent(task.percentageComplete)

                # Extrair recursos
                resources = []
                try:
                    for assignment in task.resourceAssignments:
                        if assignment and assignment.resource:
                            res_name = str(assignment.resource.name or "")
                            if res_name:
                                resources.append(res_name)
                except Exception:
                    pass
                resource_str = ", ".join(resources) if resources else "—"

                # Indentação visual baseada no nível da WBS
                level = task_id.count('.') if task_id else 0
                indent = "│  " * max(0, level - 1) + "├─ " if level > 0 else ""
                display_name = f"{indent}{task_name}"

                lines.append(f"| {task_id} | {display_name} | {start} | {finish} | {duration} | {pct} | {resource_str} |")

                task_count += 1
                try:
                    if task.percentageComplete and float(str(task.percentageComplete)) >= 100:
                        completed_count += 1
                except Exception:
                    pass

            except Exception as e:
                logger.debug(f"Erro lendo tarefa do MS Project: {e}")
                continue

        # Resumo
        lines.append("")
        overall_pct = f"{int(completed_count / task_count * 100)}%" if task_count > 0 else "0%"
        lines.append(f"**Tarefas totais:** {task_count} | **Concluídas:** {completed_count} ({overall_pct})")

        # ── Extrair predecessoras (dependências) ──────────────────
        dependencies = []
        for task in project.tasks:
            if task is None:
                continue
            try:
                for pred in task.predecessors:
                    if pred and pred.targetTask:
                        src_name = str(pred.targetTask.name or pred.targetTask.id)
                        tgt_name = str(task.name or task.id)
                        dep_type = str(pred.type or "FS")
                        dependencies.append(f"- {src_name} → {tgt_name} ({dep_type})")
            except Exception:
                pass

        if dependencies:
            lines.append("")
            lines.append("**Dependências:**")
            lines.extend(dependencies[:30])  # Limitar a 30 dependências
            if len(dependencies) > 30:
                lines.append(f"... e mais {len(dependencies) - 30} dependências")

        return "\n".join(lines)

    except ImportError:
        return f"[📊 {filename}: mpxj não instalado — pip install mpxj jpype1]"
    except Exception as e:
        logger.error(f"Erro lendo MS Project {filename}: {e}")
        return f"[📊 {filename}: Erro ao ler cronograma MS Project - {e}]"
