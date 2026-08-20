from pydantic import BaseModel, Field
from typing import List, Optional

class ContractEntity(BaseModel):
    name: str = Field(description="O nome da pessoa ou entidade.")
    role: Optional[str] = Field(None, description="O cargo ou a relação da pessoa com o contrato/projeto (ex: Remetente, Engenheiro, etc.).")

class CompanyEntity(BaseModel):
    name: str = Field(description="Nome da empresa (ex: Nacional Indústria Mecânica).")
    type_of_relation: Optional[str] = Field(None, description="Relação com o projeto (Cliente, Fornecedor, Parceira).")

class ProjectEntity(BaseModel):
    name: str = Field(description="O nome ou código do Projeto / Contrato.")
    location: Optional[str] = Field(None, description="Local da obra ou instalação (ex: Arauco, REPLAN, refinarias).")

class EquipmentEntity(BaseModel):
    name: str = Field(description="Nome do equipamento ou documento de engenharia (ex: trocadores de calor, cronogramas, pleitos).")
    details: Optional[str] = Field(None, description="Especificações adicionais sobre o equipamento ou status.")

class EmailExtractionModel(BaseModel):
    """
    O modelo principal que a API do LLM deve respeitar e instanciar como retorno.
    """
    executive_summary: str = Field(
        description="Um resumo executivo muito sucinto sobre qual é o principal tema do e-mail e seus anexos no contexto de engenharia de contratos."
    )
    people: List[ContractEntity] = Field(
        description="Lista de pessoas e remetentes mencionados.",
        default_factory=list
    )
    companies: List[CompanyEntity] = Field(
        description="Lista de empresas envolvidas.",
        default_factory=list
    )
    projects_and_locations: List[ProjectEntity] = Field(
        description="Projetos, contratos e locais físicos envolvidos na comunicação.",
        default_factory=list
    )
    equipments_and_documents: List[EquipmentEntity] = Field(
        description="Equipamentos, escravos de engenharia (vasos de pressão), contratos anexos e pleitos.",
        default_factory=list
    )
