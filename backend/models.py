from typing import Optional

from pydantic import BaseModel


class UsuarioResponse(BaseModel):
    id: int
    email: str
    nombre: Optional[str]
