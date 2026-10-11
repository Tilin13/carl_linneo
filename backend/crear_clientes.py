
import sqlite3
from app import BASE_DATOS, conectar_db

def crear_tabla_clientes():
    conexion = conectar_db()

    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conexion.commit()
    finally:
        conexion.close()

if __name__ == "__main__":
    crear_tabla_clientes()
    print("Tabla de clientes creada correctamente.")
