from uuid import UUID

from pydantic import BaseModel, Field


class DocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)


class DocumentOut(BaseModel):
    id: UUID
    title: str
    source_type: str
    status: str

    model_config = {"from_attributes": True}
