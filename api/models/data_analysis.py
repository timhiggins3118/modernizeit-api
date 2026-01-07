"""
Pydantic models for Data Analysis API.
"""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class DataAnalysisRequest(BaseModel):
    """Request model for Data Analysis."""
    scout_account_id: str
    application_name: str


class DataAnalysisResponse(BaseModel):
    """Response model for Data Analysis."""
    success: bool
    job_id: str
    status: str
    source_path: str
    artifacts_path: str
    error: Optional[str] = None
    duration_ms: int = 0
    summary: Dict[str, Any] = {}
    artifacts: Dict[str, str] = {}


class DataAnalysisStatusResponse(BaseModel):
    """Response model for data analysis job status."""
    job_id: str
    flow_type: str
    status: str
    artifacts_path: str
    created_at: str
    updated_at: str


class DataAnalysisResultsResponse(BaseModel):
    """Response model for data analysis results overview."""
    job_id: str
    status: str
    artifacts_path: str
    json_artifacts: List[str] = []
    summary: Dict[str, Any] = {}


# ERD Models

class ERDAttribute(BaseModel):
    """Entity attribute in ERD."""
    name: str
    cobol_field: str
    data_type: str
    sql_type: Optional[str] = None
    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    nullable: bool = True
    source_pic: Optional[str] = None
    business_meaning: Optional[str] = None


class ERDEntity(BaseModel):
    """Entity in ERD."""
    id: str
    name: str
    source: Dict[str, Any]
    business_purpose: Optional[str] = None
    attributes: List[ERDAttribute] = []
    confidence: float = 0.85


class ERDRelationship(BaseModel):
    """Relationship between entities."""
    id: str
    from_entity: str
    to_entity: str
    relationship_type: str
    cardinality: str
    business_rule: Optional[str] = None
    join_field: Optional[str] = None
    confidence: float = 0.8
    sources: List[str] = []


class ERDSummary(BaseModel):
    """ERD summary statistics."""
    total_entities: int = 0
    total_relationships: int = 0
    total_attributes: int = 0
    entities_by_section: Dict[str, int] = {}


class ERDOutput(BaseModel):
    """Complete ERD output."""
    generated_at: str
    job_id: str
    summary: ERDSummary
    entities: List[ERDEntity] = []
    relationships: List[ERDRelationship] = []


# Data Lineage Models

class DataTransformation(BaseModel):
    """Transformation step in data flow."""
    operation: str
    program: str
    paragraph: Optional[str] = None
    description: Optional[str] = None


class DataFlow(BaseModel):
    """Data flow from source to destination."""
    flow_name: str
    source_file: str
    source_type: str
    transformations: List[DataTransformation] = []
    destination_file: str
    destination_type: str
    business_impact: Optional[str] = None


class DataLineageOutput(BaseModel):
    """Complete data lineage output."""
    generated_at: str
    job_id: str
    summary: Dict[str, int] = {}
    flows: List[DataFlow] = []


# Copybook Models

class CopybookInfo(BaseModel):
    """Copybook analysis info."""
    name: str
    used_by: List[str] = []
    data_structures: List[Dict[str, Any]] = []
    total_fields: int = 0


class CopybookAnalysisOutput(BaseModel):
    """Complete copybook analysis output."""
    generated_at: str
    job_id: str
    summary: Dict[str, int] = {}
    copybooks: List[CopybookInfo] = []


# Data Structures (Regex Output) Models

class FieldDefinition(BaseModel):
    """COBOL field definition."""
    level: str
    name: str
    pic: Optional[str] = None
    data_type: Optional[str] = None
    length: Optional[int] = None
    usage: Optional[str] = None
    storage_type: Optional[str] = None
    occurs: Optional[int] = None
    is_array: bool = False
    redefines: Optional[str] = None
    value: Optional[str] = None


class RecordDefinition(BaseModel):
    """01-level record definition."""
    level: str = "01"
    name: str
    record_name: Optional[str] = None
    fields: List[FieldDefinition] = []


class FileDataStructures(BaseModel):
    """Data structures extracted from a single file."""
    working_storage: List[RecordDefinition] = []
    file_section: List[Dict[str, Any]] = []
    linkage_section: List[RecordDefinition] = []
    copybooks: List[Dict[str, str]] = []
    summary: Dict[str, int] = {}


class DataStructuresOutput(BaseModel):
    """Complete data structures output (regex)."""
    generated_at: str
    job_id: str
    summary: Dict[str, int] = {}
    files: List[Dict[str, Any]] = []
