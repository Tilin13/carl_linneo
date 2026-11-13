
import sqlite3
from pathlib import Path

# Ajusta esta ruta a la ubicación real de tu base de datos
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pos.db"

def mostrar_esquema():
    if not DB_PATH.exists():
        print(f"No se encontró la base de datos: {DB_PATH}")
        return

    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()

    print("\n" + "=" * 90)
    print("             ESTRUCTURA COMPLETA DE LA BASE DE DATOS LINNEO")
    print("=" * 90)

    tablas = cursor.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name;
    """).fetchall()

    if not tablas:
        print("No hay tablas en la base de datos.")
        conexion.close()
        return

    for tabla in tablas:
        nombre = tabla["name"]

        print(f"\n{'=' * 90}")
        print(f" TABLA: {nombre}")
        print("=" * 90)

        columnas = cursor.execute(
            f'PRAGMA table_info("{nombre}")'
        ).fetchall()

        print("\nCOLUMNAS:")
        for columna in columnas:
            print(
                f"  - {columna['name']:<30}"
                f" Tipo: {columna['type']:<15}"
                f" PK: {columna['pk']}"
                f" NOT NULL: {columna['notnull']}"
                f" DEFAULT: {columna['dflt_value']}"
            )

        claves = cursor.execute(
            f'PRAGMA foreign_key_list("{nombre}")'
        ).fetchall()

        print("\nCLAVES FORÁNEAS:")
        if claves:
            for clave in claves:
                print(
                    f"  - {clave['from']} -> "
                    f"{clave['table']}.{clave['to']}"
                )
        else:
            print("  No tiene claves foráneas.")

        indices = cursor.execute(
            f'PRAGMA index_list("{nombre}")'
        ).fetchall()

        print("\nÍNDICES:")
        if indices:
            for indice in indices:
                print(
                    f"  - {indice['name']} "
                    f"(único: {indice['unique']})"
                )
        else:
            print("  No tiene índices adicionales.")

        print("\nSQL DE CREACIÓN:")
        print(tabla["sql"])

    conexion.close()
    print("\n" + "=" * 90)
    print("             FIN DEL REPORTE")
    print("=" * 90)


if __name__ == "__main__":
    mostrar_esquema()
