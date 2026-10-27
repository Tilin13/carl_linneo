
import sqlite3

DB = "pos.db"

try:
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """)
    tablas = cursor.fetchall()

    if not tablas:
        print("No se encontraron tablas en la base de datos.")
    else:
        for (tabla,) in tablas:
            print(f"\n{'=' * 60}")
            print(f" TABLA: {tabla}")
            print("=" * 60)

            cursor.execute(f'SELECT * FROM "{tabla}"')
            columnas = [col[0] for col in cursor.description]

            print(" | ".join(columnas))
            print("-" * 60)

            for fila in cursor.fetchall():
                print(" | ".join(str(valor) for valor in fila))

    conn.close()

except sqlite3.Error as e:
    print(f"Error con la base de datos: {e}")
