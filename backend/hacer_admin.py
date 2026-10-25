
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = BASE_DIR / "pos.db"

correo_admin = os.getenv("ADMIN_EMAIL", "").strip().lower()

if not correo_admin:
    raise RuntimeError("Falta configurar ADMIN_EMAIL en .env")

conexion = sqlite3.connect(BASE_DATOS)

try:
    cursor = conexion.execute("""
        UPDATE usuarios
        SET rol = 'admin'
        WHERE lower(email) = ?
    """, (correo_admin,))

    if cursor.rowcount != 1:
        conexion.rollback()
        raise RuntimeError(
            "No se encontró exactamente una cuenta con ese correo. "
            "Regístrala primero y comprueba que la base de datos "
            "sea la correcta."
        )

    conexion.commit()
    print("Cuenta administradora configurada correctamente.")

finally:
    conexion.close()
