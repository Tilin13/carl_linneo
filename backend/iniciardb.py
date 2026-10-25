
import sqlite3
from pathlib import Path

# Ruta fija: la carpeta donde está este archivo.
BASE_DIR = Path(__file__).resolve().parent
BASE_DATOS = BASE_DIR / "pos.db"


def inicializar_base_datos():
    BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(BASE_DATOS, timeout=10)

    try:
        conexion.execute("PRAGMA foreign_keys = ON")

        # Tabla de usuarios
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                phone TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'user'
            )
        """)

        # Tabla de códigos antiguos de administrador
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS codigos_admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                codigo_hash TEXT NOT NULL,
                expira REAL NOT NULL,
                intentos INTEGER NOT NULL DEFAULT 0,
                usado BOOLEAN NOT NULL DEFAULT 0,
                FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id)
            )
        """)

        # Tabla de productos
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                categoria TEXT NOT NULL,
                precio_compra REAL NOT NULL DEFAULT 0,
                precio_manofactura REAL NOT NULL DEFAULT 0,
                precio_venta REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0
            )
        """)

        conexion.commit()

        print("Base de datos lista.")
        print(f"Ubicación: {BASE_DATOS.resolve()}")

    except sqlite3.Error:
        conexion.rollback()
        raise

    finally:
        conexion.close()


if __name__ == "__main__":
    inicializar_base_datos()
