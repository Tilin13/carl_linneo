import os
import re
import sqlite3
from sqlalchemy import or_
from pathlib import Path
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from sqlalchemy.exc import IntegrityError
from flask import send_from_directory, jsonify
from openai import OpenAI
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, abort
)

from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    current_user, login_required
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

load_dotenv()
# ============================================================
# RUTAS DEL PROYECTO
# ============================================================
db= SQLAlchemy()
class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    phone = db.Column(
        db.String(20),
        unique=True,
        nullable=True
    )

    password_hash = db.Column(
        db.String(512),
        nullable=False
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password
        )

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None
@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None

BASE_DIR = Path(__file__).resolve().parent.parent

BASE_DATOS = "pos.db"

FRONTEND_DIR = BASE_DIR / "frontend"


# Carpeta donde están las imágenes
IMAGENES_DIR = BASE_DIR / "imagenes"

# ============================================================
# FLASK
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = BASE_DIR / "pos.db"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "frontend"),
    static_folder=str(BASE_DIR / "frontend"),
    static_url_path=""
)

secret_key = os.getenv("SECRET_KEY")

if not secret_key:
    raise RuntimeError("Falta configurar SECRET_KEY")
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)
app.config.update(
    SECRET_KEY=secret_key,
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{BASE_DATOS.as_posix()}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SESSION_COOKIE_HTTPONLY"]= True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMSITE"] = "Lax"

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
# ============================================================
# RUTAS
# ============================================================
csrf = CSRFProtect(app)
def escoger_productos_azar():
    """Devuelve hasta 3 productos aleatorios de la base de datos."""

    if not Path(BASE_DATOS).exists():
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

def obtener_catalogo(categoria=None):
    conexion = sqlite3.connect(BASE_DATOS)
    conexion.row_factory = sqlite3.Row

    try:
        cursor = conexion.cursor()

        if categoria:
            cursor.execute("""
                SELECT *
                FROM productos
                WHERE categoria = ?
                ORDER BY nombre ASC
            """, (categoria,))
        else:
            cursor.execute("""
                SELECT *
                FROM productos
                ORDER BY nombre ASC
            """)

        return [dict(fila) for fila in cursor.fetchall()]

    finally:
        conexion.close()
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
@app.route("/iniciar_sesion", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        identificador = request.form.get(
            "identificador", ""
        ).strip()

        password = request.form.get("password", "")

        usuario = User.query.filter(
            or_(
                User.email == identificador.lower(),
                User.username == identificador
            )
        ).first()

        if usuario and usuario.check_password(password):
            login_user(usuario)
            return redirect(url_for("index"))

        flash(
            "Nombre de usuario, correo o contraseña incorrectos.",
            "error"
        )

    return render_template("login.html")


@app.route("/cerrar_sesion", methods=["POST"])
@login_required
def cerrar_sesion():
    logout_user()
    return redirect(url_for("index"))
@app.route("/cerrar_sesion", methods=["POST"])
@login_required
def cerrar_sesion():
    logout_user()
    return redirect(url_for("index"))
@app.route("/registrarse", methods=["GET", "POST"])
def registrarse():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        phone = request.form.get(
            "phone", ""
        ).strip() or None

        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not re.fullmatch(
            r"[A-Za-z0-9_.-]{3,80}", username
        ):
            flash(
                "El usuario debe tener entre 3 y 80 "
                "caracteres válidos.",
                "error"
            )

        elif not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", email
        ) or len(email) > 255:
            flash("Introduce un correo válido.", "error")

        elif len(password) < 12 or len(password) > 128:
            flash(
                "La contraseña debe tener entre "
                "12 y 128 caracteres.",
                "error"
            )

        elif password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")

        elif phone and len(phone) > 20:
            flash("El teléfono es demasiado largo.", "error")

        elif User.query.filter(
            or_(
                User.username == username,
                User.email == email,
                User.phone == phone if phone else False
            )
        ).first():
            flash(
                "El usuario, correo o teléfono ya está registrado.",
                "error"
            )

        else:
            usuario = User(
                username=username,
                email=email,
                phone=phone
            )
            usuario.set_password(password)

            try:
                db.session.add(usuario)
                db.session.commit()

                login_user(usuario)
                return redirect(url_for("index"))

            except IntegrityError:
                db.session.rollback()
                flash(
                    "El usuario, correo o teléfono ya está registrado.",
                    "error"
                )

            except Exception:
                db.session.rollback()
                app.logger.exception(
                    "Error al registrar usuario"
                )
                flash(
                    "No se pudo crear la cuenta. Inténtalo de nuevo.",
                    "error"
                )

    return render_template("registrarse.html")
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

def obtener_producto(nombre):
    """Obtiene un producto por su nombre exacto."""

    conexion = sqlite3.connect(BASE_DATOS)
    conexion.row_factory = sqlite3.Row

    try:
        cursor = conexion.cursor()

        cursor.execute("""
            SELECT *
            FROM productos
            WHERE nombre = ?
            LIMIT 1
        """, (nombre,))

        producto = cursor.fetchone()

        if producto is None:
            return None

        return dict(producto)

    finally:
        conexion.close()

@app.route("/producto/<path:nombre>")
def producto(nombre):

    producto = obtener_producto(nombre)

    if producto is None:
        return "Producto no encontrado", 404

    return render_template(
        "producto.html",
        producto=producto
    )
@app.route("/comprar")    
@login.required
def comprar():
	return render_template("comprar.html")
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
