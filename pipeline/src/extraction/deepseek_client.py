import os
import json
import logging
from openai import OpenAI
from pydantic import ValidationError

from src.extraction.schemas import EmailExtractionModel

logger = logging.getLogger(__name__)

# Preços reais do DeepSeek V3
COST_PER_1M_INPUT_TOKENS = 0.14
COST_PER_1M_OUTPUT_TOKENS = 0.28

class DeepSeekClient:
    def __init__(self, api_key: str, max_budget: float = 9.50):
        self.api_key = api_key
        self.max_budget = max_budget
        self.total_cost = 0.0
        
        # O DeepSeek usa compatibilidade com a biblioteca da OpenAI
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )
        
        self.system_prompt = (
            "Você é um Engenheiro de Contratos Sênior especializado em analisar documentação complexa "
            "(e-mails e anexos que vão desde cronogramas, vasos de pressão, propostas até memoriais descritivos). "
            "Sua principal função é ler os e-mails e anexos fornecidos para extrair metadados e entidades "
            "compostos por Pessoas, Empresas, Projetos/Locais, Equipamentos/Pleitos e gerar um resumo executivo. "
            "Retorne APENAS o JSON estrito requerido. Nenhuma outra conversa."
        )

    def is_budget_exceeded(self) -> bool:
        return self.total_cost >= self.max_budget

    def _update_cost(self, prompt_tokens: int, completion_tokens: int):
        input_cost = (prompt_tokens / 1_000_000) * COST_PER_1M_INPUT_TOKENS
        output_cost = (completion_tokens / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS
        
        cost = input_cost + output_cost
        
        self.total_cost += cost
        logger.info(f"Custo requisição atual: ${cost:.6f} | Custo total agregado: ${self.total_cost:.4f} / ${self.max_budget:.2f}")

    def extract_entities(self, raw_text: str) -> dict:
        """
        Envia o texto bruto resultante da ingestão para o DeepSeek,
        forçando a saída a se adequar ao esquema Pydantic (JSON).
        """
        if self.is_budget_exceeded():
            logger.error(f"FATAL: Orçamento de ${self.max_budget} foi zerado. Paralisando extrações.")
            raise Exception("Budget Exceeded")

        # Em modelos que não suportam `response_format={"type": "json_schema"}` perfeitamente,
        # pode-se requisitar JSON normal e pedir o Pydantic na prompt.
        # Mas DeepSeek/OpenAI suportam structured outputs muito bem.

        system_instruction = self.system_prompt + "\n\nJSON Schema Exigido:\n" + json.dumps(EmailExtractionModel.model_json_schema(), indent=2)

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat", # ou 'deepseek-reasoner'
                messages=[
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user", 
                        "content": f"Extraia as informações relativas a engenharia de contratos a partir do seguinte texto:\n\n{raw_text[:80000]}" # Proteção de max length
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Atualiza token counters
            usage = response.usage
            self._update_cost(usage.prompt_tokens, usage.completion_tokens)

            # Extrai e valida a saída bruta
            raw_json_str = response.choices[0].message.content
            parsed_dict = json.loads(raw_json_str)
            
            # Garante que ele passe pelo crivo do Pydantic (ou aciona fallback)
            validated_model = EmailExtractionModel(**parsed_dict)
            return validated_model.model_dump()

        except ValidationError as ve:
            logger.error(f"Erro de Validação Pydantic no retorno do LLM: {ve}")
            return {"error": "JSON validation failed", "raw": raw_json_str}
        except Exception as e:
            logger.error(f"Erro na API DeepSeek: {e}")
            return {"error": str(e)}
