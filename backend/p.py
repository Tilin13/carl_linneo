
import os
import psycopg
from psycopg.rows import dict_row


def ver_usuarios():

    # Obtiene la conexión desde las variables de entorno
    DATABASE_URL = os.environ.get("DATABASE_URL")

    if not DATABASE_URL:
        print("ERROR: No se encontró DATABASE_URL.")
        print("Configura la variable de conexión de PostgreSQL.")
        return

    try:
        with psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
            connect_timeout=10
        ) as conexion:

            with conexion.cursor() as cursor:

                cursor.execute("""
                    SELECT id, username, email, rol
                    FROM "user"
                    ORDER BY id ASC;
                """)

                usuarios = cursor.fetchall()

                if not usuarios:
                    print("No hay usuarios registrados.")
                    return

                print("\n========== USUARIOS DE LINNEO ==========\n")

                for usuario in usuarios:
                    print(f"ID: {usuario['id']}")
                    print(f"Usuario: {usuario['username']}")
                    print(f"Correo: {usuario['email']}")
                    print(f"Rol: {usuario['rol']}")
                    print("----------------------------------------")

                print("\n========== ADMINISTRADORES ==========\n")

                administradores = [
                    usuario for usuario in usuarios
                    if usuario["rol"] == "admin"
                ]

                if administradores:
                    for admin in administradores:
                        print(f"ADMIN_USER_ID = {admin['id']}")
                        print(f"Usuario: {admin['username']}")
                        print(f"Correo: {admin['email']}")
                else:
                    print("No hay administradores registrados.")

    except psycopg.Error as error:
        print("Error al consultar PostgreSQL:")
        print(error)


if __name__ == "__main__":
    ver_usuarios()
