from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

PATH_BD = Path(__file__).resolve().parent.parent / "data" / "melate.db"


@asynccontextmanager
async def conectar():
    bd = await aiosqlite.connect(str(PATH_BD))
    bd.row_factory = aiosqlite.Row
    try:
        yield bd
    finally:
        await bd.close()


async def inicializar_bd():
    async with conectar() as bd:
        await bd.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                nombre TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await bd.commit()


async def guardar_usuario(google_sub, email, nombre):
    async with conectar() as bd:
        await bd.execute(
            """
            INSERT INTO usuarios (google_sub, email, nombre)
            VALUES (?, ?, ?)
            ON CONFLICT(google_sub) DO UPDATE SET
                email = excluded.email,
                nombre = excluded.nombre
            """,
            (google_sub, email, nombre),
        )
        await bd.commit()
        cursor = await bd.execute(
            "SELECT id, email, nombre FROM usuarios WHERE google_sub = ?",
            (google_sub,),
        )
        fila = await cursor.fetchone()
        return dict(fila)


async def obtener_usuario(usuario_id):
    async with conectar() as bd:
        cursor = await bd.execute(
            "SELECT id, email, nombre FROM usuarios WHERE id = ?",
            (usuario_id,),
        )
        fila = await cursor.fetchone()
        if fila is None:
            return None
        return dict(fila)
