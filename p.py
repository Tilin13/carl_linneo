
import sqlite3
from pathlib import Path

# Buscar pos.db en la misma carpeta que p.py
BASE_DIR = Path(__file__).resolve().parent
DATOS = BASE_DIR / "pos.db"

print("Buscando base de datos:", DATOS)

if not DATOS.exists():
    print("ERROR: No se encontró pos.db")
    raise SystemExit

conexion = sqlite3.connect(DATOS)
cursor = conexion.cursor()

try:
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """)

    tablas = cursor.fetchall()

    print("\n====== TABLAS DE LA BASE DE DATOS ======\n")

    for tabla in tablas:
        nombre = tabla[0]
        print(f"\nTABLA: {nombre}")

        cursor.execute(f'PRAGMA table_info("{nombre}")')

        for columna in cursor.fetchall():
            print(
                f"  - {columna[1]} "
                f"({columna[2]})"
            )

finally:
    conexion.close()
