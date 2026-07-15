"""Resolución de la foto de un estudiante a una URL servible.

`students.photo_url` guarda una **key** de object storage (foto subida a MinIO)
o, por compatibilidad, una URL externa ya pegada. Este helper devuelve una URL
que el browser puede cargar: presigna la key, o deja pasar la URL externa.
"""
from app.adapters.storage.base import StorageAdapter


def resolve_photo_url(storage: StorageAdapter, value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value  # URL externa (compat con fotos pegadas antes del upload)
    return storage.get_url(value)  # key en storage → URL presignada
