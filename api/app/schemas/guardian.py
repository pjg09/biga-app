from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import GuardianRelationship


class GuardianCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    relationship: GuardianRelationship
    email: EmailStr = Field(max_length=255)  # coincide con guardians.email VARCHAR(255)
    phone: str | None = Field(default=None, max_length=20)
    is_primary: bool = False

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()
