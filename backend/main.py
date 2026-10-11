from pathlib import Path
import sqlite3
from flask import Flask, render_template, send_from_directory, request, jsonify

from dotenv import load_dotenv
from openai import OpenAI
import os
import random

load_dotenv()

# ============================================================
# RUTAS DEL PROYECTO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

GUAYABA_POS_DIR = BASE_DIR.parent / "guayabapos"

BASE_DATOS = GUAYABA_POS_DIR / "pos.db"

FRONTEND_DIR = BASE_DIR / "frontend"

# Carpeta donde están las imágenes
IMAGENES_DIR = BASE_DIR / "imagenes"


print("========================================")
print("CONFIGURACIÓN")
print("========================================")
print("BASE_DIR:       ", BASE_DIR)
print("GUAYABA_POS_DIR:", GUAYABA_POS_DIR)
print("BASE_DATOS:     ", BASE_DATOS)
print("FRONTEND_DIR:   ", FRONTEND_DIR)
print("IMAGENES_DIR:   ", IMAGENES_DIR)
print("----------------------------------------")
print("BD existe:      ", BASE_DATOS.exists())
print("Directorio BD:  ", GUAYABA_POS_DIR.exists())
print("Frontend existe:", FRONTEND_DIR.exists())
print("========================================")


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR),
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)


# Límites y configuración de seguridad
app.config.update(
    MAX_CONTENT_LENGTH=16 * 1024,  # 16 KiB por petición
    MAX_FORM_MEMORY_SIZE=16 * 1024,
    MAX_FORM_PARTS=50,

    # Cookies seguras si en el futuro usas sesiones.
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


@app.after_request
def agregar_cabeceras_seguridad(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    # No almacenar respuestas personalizadas en cachés compartidas.
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"

    return response

# ============================================================
# BASE DE DATOS
# ============================================================		
def obtener_producto(nombre):

    conexion = sqlite3.connect(BASE_DATOS)
    conexion.row_factory = sqlite3.Row

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT *
            FROM productos
            WHERE nombre = ?
        """, (nombre,))

        producto = cursor.fetchone()

        if producto is None:
            return None

        return dict(producto)

    finally:
        conexion.close()
def obtener_catalogo(categoria=None):
    """Obtiene los productos del inventario.
    
    Si se proporciona una categoría, solo devuelve
    los productos pertenecientes a esa categoría.
    """

    if not BASE_DATOS.exists():
        raise FileNotFoundError(
            f"No existe la base de datos:\n{BASE_DATOS}"
        )

    conexion = sqlite3.connect(BASE_DATOS)
    conexion.row_factory = sqlite3.Row

    try:
        cursor = conexion.cursor()

        if categoria:
            cursor.execute("""
                SELECT *
                FROM productos
                WHERE categoria = ?
            """, (categoria,))
        else:
            cursor.execute("""
                SELECT *
                FROM productos
                
            """)

        productos = cursor.fetchall()

        return [dict(producto) for producto in productos]

    finally:
        conexion.close()
# ============================================================
# RUTAS
# ============================================================

def escoger_productos_azar():
    """Devuelve hasta 3 productos aleatorios de la base de datos."""

    if not BASE_DATOS.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {BASE_DATOS}"
        )

    conexion = sqlite3.connect(BASE_DATOS)
    conexion.row_factory = sqlite3.Row

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT *
            FROM productos
            ORDER BY RANDOM()
            LIMIT 3
        """)

        productos = cursor.fetchall()

        return [dict(producto) for producto in productos]

    finally:
        conexion.close()


def buscar_productos(texto):

    conexion = sqlite3.connect(BASE_DATOS)
    conexion.row_factory = sqlite3.Row

    try:

        cursor = conexion.cursor()

        cursor.execute("""
            SELECT *
            FROM productos
            
            WHERE nombre LIKE ?
            ORDER BY nombre ASC
        """, (f"%{texto}%",))

        productos = cursor.fetchall()

        return [
            dict(producto)
            for producto in productos
        ]

    finally:
        conexion.close()

@app.route("/buscar")
def buscar():

    texto = request.args.get("busqueda", "").strip()

    print("==========================")
    print("TEXTO RECIBIDO:", repr(texto))

    productos = buscar_productos(texto)

    print("PRODUCTOS:", len(productos))
    print("==========================")

    return render_template(
        "buscar.html",
        productos=productos,
        busqueda=texto
    )



@app.route("/")
def index():
    productos = escoger_productos_azar()

    return render_template(
        "index.html",
        productos=productos
    )


@app.route("/informacion")
def informacion():
    return render_template("informacion.html")
@app.route("/contacto")
def contacto():
	return render_template("contacto.html")
@app.route("/catalogo")
@app.route("/catalogo/<categoria>")
def catalogo(categoria=None):

    productos = obtener_catalogo(categoria)

    return render_template(
        "catalogo.html",
        productos=productos,
        categoria=categoria
    )




# ============================================================
# IMÁGENES
# ============================================================

@app.route("/imagenes/<path:nombre_archivo>")
def imagenes(nombre_archivo):
    return send_from_directory(
        IMAGENES_DIR,
        nombre_archivo
    )

############################################################################
#CHATBOT
###########################################################################

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "No se encontró OPENAI_API_KEY. "
        "Configúrala en el entorno o en el archivo .env"
    )

client = OpenAI(api_key=api_key)


@app.route("/chatbox")
def chatbox():
	return render_template("chatmenu.html")

@app.route("/api/chat", methods=["POST"])
def api_chat():

    try:
        data = request.get_json() or {}

        mensaje = data.get("mensaje", "").strip()

        if not mensaje:
            return jsonify({
                "error": "El mensaje está vacío"
            }), 400

        print("MENSAJE DEL USUARIO:", mensaje)

        response = client.responses.create(
            model="gpt-5.6-luna",
            instructions="""
Eres el asistente de ventas de una tienda llamada "Linneo".

Linneo vende:
- mariposas decorativas
- insectos
- minerales

Eslogan:
"La gema oculta de la ciencia"

Tu objetivo es ayudar al cliente a:
- encontrar productos
- resolver dudas
- conocer el catálogo
- facilitar la compra

Sé amable, breve y natural.

IMPORTANTE:
Nunca inventes:
- precios
- productos
- disponibilidad
- descripciones
- características

Si no tienes información suficiente sobre un producto, dilo claramente.
""",
            input=mensaje
        )

        respuesta = response.output_text

        return jsonify({
            "respuesta": respuesta
        })

    except Exception as e:

        print("ERROR CHATBOT:", e)

        return jsonify({
            "error": "Ocurrió un error al procesar el mensaje."
        }), 500
@app.route("/producto/<path:nombre>")
def producto(nombre):

    producto = obtener_producto(nombre)

    if producto is None:
        return "Producto no encontrado", 404

    return render_template(
        "producto.html",
        producto=producto
    )
#============================================================
#HERRAMIENTAS IA
#============================================================
def herramienta_ia_buscarproductos(texto):
    productos = buscar_productos(texto)
    return productos

	
# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
