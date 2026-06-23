from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student
from app.repositories.pae_repository import PAERepository


class PAEIdentificationStrategy(Protocol):
    async def identify(self, input_data: dict, institution_id: UUID, session: AsyncSession) -> Student:
        ...


class DocumentSearchStrategy:
    async def identify(self, input_data: dict, institution_id: UUID, session: AsyncSession) -> Student:
        from sqlalchemy import select

        student_id: UUID = input_data["student_id"]
        result = await session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
        )
        student = result.scalar_one_or_none()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estudiante no encontrado en esta institución",
            )
        return student


class FacialRecognitionStrategy:
    async def identify(self, input_data: dict, institution_id: UUID, session: AsyncSession) -> Student:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Reconocimiento facial no disponible en esta versión",
        )
