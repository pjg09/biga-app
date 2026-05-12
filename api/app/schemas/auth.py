from uuid import UUID

from pydantic import BaseModel

from app.models.enums import UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: UserRole
    institution_id: UUID

    model_config = {"from_attributes": True}
