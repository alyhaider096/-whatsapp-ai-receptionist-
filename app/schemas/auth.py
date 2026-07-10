from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    tenant_id: UUID
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    email: EmailStr
    business_name: str
