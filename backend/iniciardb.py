import sqlite3
from pathlib import Path

# Ruta de la base de datos
BASE_DIR = Path(__file__).resolve().parent
BASE_DATOS = BASE_DIR / "pos.db"


def crear_pedidos():
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)

    try:
        conexion.execute("PRAGMA foreign_keys = ON")

        conexion.executescript("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comprador TEXT NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                cantidad_productos INTEGER NOT NULL,
                descuentos REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS detalle_pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_pedido INTEGER NOT NULL,
                id_producto INTEGER NOT NULL,
                precio_unitario REAL NOT NULL,
                cantidad INTEGER NOT NULL,
                FOREIGN KEY (id_pedido)
                    REFERENCES pedidos(id)
            );

            CREATE TABLE IF NOT EXISTS cupones (
                codigo VARCHAR(32) PRIMARY KEY,
                categoria VARCHAR(1) NOT NULL,
                descuento REAL NOT NULL,
                cobrado BOOLEAN NOT NULL DEFAULT 0
            );
        """)

        conexion.commit()
        print("Tablas de pedidos creadas correctamente.")
        print(f"Base de datos: {BASE_DATOS.resolve()}")

    except sqlite3.Error as error:
        conexion.rollback()
        print(f"Error al crear las tablas: {error}")
        raise

    finally:
        conexion.close()


if __name__ == "__main__":
    crear_pedidos()
