
import sqlite3
from pathlib import Path

# Ruta de la base de datos
BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = BASE_DIR / "pos.db"

print("=" * 55)
print("DIAGNÓSTICO DE BASE DE DATOS - LINNEO")
print("=" * 55)

print(f"\nBase de datos examinada: {BASE_DATOS.resolve()}")
print(f"Existe: {BASE_DATOS.exists()}")

# Evita crear una base de datos vacía si la ruta es incorrecta
if not BASE_DATOS.exists():
    print("\nERROR: No se encontró el archivo pos.db.")
    raise SystemExit(1)

try:
    # Abrir en modo solo lectura
    conexion = sqlite3.connect(
        BASE_DATOS.resolve().as_uri() + "?mode=ro",
        uri=True
    )
    cursor = conexion.cursor()

    # 1. Mostrar tablas
    print("\n" + "=" * 55)
    print("TABLAS")
    print("=" * 55)

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """)

    tablas = cursor.fetchall()

    if tablas:
        for tabla in tablas:
            print("-", tabla[0])
    else:
        print("No hay tablas.")

    # 2. Estructura de usuarios
    print("\n" + "=" * 55)
    print("ESTRUCTURA DE LA TABLA USUARIOS")
    print("=" * 55)

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'usuarios'
    """)

    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(usuarios)")

        for columna in cursor.fetchall():
            print(columna)

        # 3. Usuarios registrados (sin contraseñas ni hashes)
        print("\n" + "=" * 55)
        print("USUARIOS REGISTRADOS")
        print("=" * 55)

        cursor.execute("""
            SELECT id, username, email, phone, rol
            FROM usuarios
            ORDER BY id
        """)

        usuarios = cursor.fetchall()

        if usuarios:
            for usuario in usuarios:
                print(usuario)
        else:
            print("No hay usuarios registrados.")

        # 4. Índices
        print("\n" + "=" * 55)
        print("ÍNDICES DE USUARIOS")
        print("=" * 55)

        cursor.execute("PRAGMA index_list(usuarios)")
        indices = cursor.fetchall()

        if indices:
            for indice in indices:
                print(indice)
        else:
            print("No hay índices.")

        # 5. Comprobar duplicados de username
        print("\n" + "=" * 55)
        print("USERNAME DUPLICADOS")
        print("=" * 55)

        cursor.execute("""
            SELECT username, COUNT(*)
            FROM usuarios
            GROUP BY username
            HAVING COUNT(*) > 1
        """)

        duplicados = cursor.fetchall()

        if duplicados:
            for duplicado in duplicados:
                print(duplicado)
        else:
            print("No se encontraron usernames duplicados.")

        # 6. Comprobar duplicados de email
        print("\n" + "=" * 55)
        print("EMAILS DUPLICADOS")
        print("=" * 55)

        cursor.execute("""
            SELECT email, COUNT(*)
            FROM usuarios
            GROUP BY email
            HAVING COUNT(*) > 1
        """)

        duplicados = cursor.fetchall()

        if duplicados:
            for duplicado in duplicados:
                print(duplicado)
        else:
            print("No se encontraron emails duplicados.")

    else:
        print("\nERROR: La tabla usuarios no existe.")

    conexion.close()

    print("\n" + "=" * 55)
    print("DIAGNÓSTICO FINALIZADO")
    print("=" * 55)

except sqlite3.Error as error:
    print(f"\nERROR DE SQLITE: {error}")
