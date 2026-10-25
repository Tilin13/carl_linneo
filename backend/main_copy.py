import hashlib
import hmac
import secrets
import smtplib
import time

from email.message import EmailMessage
from functools import wraps

from flask import session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, abort, jsonify,
    send_from_directory
)
from flask_login import (
    LoginManager, UserMixin, current_user,
    login_user, logout_user, login_required
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from openai import OpenAI

load_dotenv()

# main.py está en una subcarpeta y frontend está
# en la carpeta superior.
BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = BASE_DIR / "pos.db"
FRONTEND_DIR = BASE_DIR / "frontend"
IMAGENES_DIR = BASE_DIR / "imagenes"

secret_key = os.getenv("SECRET_KEY")
api_key = os.getenv("OPENAI_API_KEY")

if not secret_key or len(secret_key) < 32:
    raise RuntimeError(
        "Configura SECRET_KEY con una clave aleatoria "
        "de al menos 32 caracteres."
    )

if not api_key:
    raise RuntimeError("Falta configurar OPENAI_API_KEY.")

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR),
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)

app.config.update(
    SECRET_KEY=secret_key,

    # Utiliza HTTPS en producción.
    SESSION_COOKIE_SECURE=(
        os.getenv("COOKIE_SECURE", "true").lower() == "true"
    ),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,

    # SQLite existente; no se crea otra base de productos.
    SQLALCHEMY_DATABASE_URI=(
        "sqlite:///" + BASE_DATOS.as_posix()
    ),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"

csrf = CSRFProtect(app)

client = OpenAI(api_key=api_key)

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
        db.String(255),
        nullable=False
    )

    # Los nuevos registros son usuarios normales.
    rol = db.Column(
        db.String(10),
        nullable=False,
        default="user",
        server_default="user"
    )

    def set_password(self, password):
        if not isinstance(password, str):
            raise ValueError("Contraseña no válida.")

        if not 12 <= len(password) <= 128:
            raise ValueError(
                "La contraseña debe tener entre 12 y 128 caracteres."
            )

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not isinstance(password, str):
            return False

        return check_password_hash(
            self.password_hash,
            password
        )

    @property
    def es_admin(self):
        return self.rol == "admin"

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None
with app.app_context():
    db.create_all()
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]
)
def enviar_codigo_admin(destinatario, codigo):
    mensaje = EmailMessage()
    mensaje["Subject"] = "Código de acceso | Linneo"
    mensaje["From"] = os.environ["MAIL_USERNAME"]
    mensaje["To"] = destinatario

    mensaje.set_content(
        f"""Tu código de acceso para el panel de Linneo es:

{codigo}

Caduca en 5 minutos.
Si no has solicitado este acceso, ignora este mensaje.
"""
    )

    servidor = os.environ["MAIL_SERVER"]
    puerto = int(os.environ["MAIL_PORT"])

    if puerto == 465:
        with smtplib.SMTP_SSL(
            servidor, puerto, timeout=10
        ) as smtp:
            smtp.login(
                os.environ["MAIL_USERNAME"],
                os.environ["MAIL_PASSWORD"]
            )
            smtp.send_message(mensaje)
    else:
        with smtplib.SMTP(
            servidor, puerto, timeout=10
        ) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(
                os.environ["MAIL_USERNAME"],
                os.environ["MAIL_PASSWORD"]
            )
            smtp.send_message(mensaje)
       
class CodigoAdmin(db.Model):
    __tablename__ = "codigos_admin"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False
    )
    codigo_hash = db.Column(db.String(64), nullable=False)
    expira = db.Column(db.Float, nullable=False)
    intentos = db.Column(db.Integer, nullable=False, default=0)
    usado = db.Column(db.Boolean, nullable=False, default=False)

def hash_codigo(codigo):
    return hmac.new(
        app.config["SECRET_KEY"].encode(),
        codigo.encode(),
        hashlib.sha256
    ).hexdigest()


def administrador_requerido(func):
    @wraps(func)
    @login_required
    def decorada(*args, **kwargs):
        if (
            getattr(current_user, "rol", None) != "admin"
            or session.get("admin_2fa") != str(current_user.id)
        ):
            abort(403)

        return func(*args, **kwargs)

    return decorada
@app.route("/verificar_admin", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def verificar_admin():
    usuario_id = session.get("admin_2fa_pendiente")

    if not usuario_id:
        return redirect(url_for("login"))

    usuario = db.session.get(User, usuario_id)

    if (
        usuario is None
        or getattr(usuario, "rol", None) != "admin"
        or usuario.email.lower()
        != os.environ["ADMIN_EMAIL"].strip().lower()
    ):
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()

        if not re.fullmatch(r"[0-9]{6}", codigo):
            flash("Introduce un código de seis cifras.", "error")
            return render_template("verificar_admin.html")

        registro = db.session.scalar(
            select(CodigoAdmin)
            .where(
                CodigoAdmin.usuario_id == usuario.id,
                CodigoAdmin.usado.is_(False)
            )
            .order_by(CodigoAdmin.id.desc())
        )

        if registro is None:
            flash("Solicita un nuevo código.", "error")
            return redirect(url_for("login"))

        if (
            registro.expira <= time.time()
            or registro.intentos >= 5
        ):
            registro.usado = True
            db.session.commit()

            session.clear()
            flash("El código ha caducado. Inicia sesión de nuevo.", "error")
            return redirect(url_for("login"))

        if not hmac.compare_digest(
            registro.codigo_hash,
            hash_codigo(codigo)
        ):
            registro.intentos += 1

            if registro.intentos >= 5:
                registro.usado = True

            db.session.commit()
            flash("Código incorrecto.", "error")
            return render_template("verificar_admin.html")

        # El código queda consumido antes de conceder acceso.
        registro.usado = True
        db.session.commit()

        session.clear()
        login_user(usuario, remember=False)
        session["admin_2fa"] = str(usuario.id)

        return redirect(url_for("admin"))

    return render_template("verificar_admin.html")
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
@app.route("/admin")
@administrador_requerido
def admin():
    # Aquí consultas los productos y las ventas.
    return render_template("admin.html")
# ============================================================
# BASE DE DATOS
# ============================================================		
# ============================================================
# RUTAS
# ============================================================

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
######################################################################
##CUENTAS
##################################################################

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



def destino_local_seguro(destino):
    """Evita redirecciones hacia sitios externos."""
    if not destino:
        return False

    partes = urlsplit(destino)

    return (
        not partes.scheme
        and not partes.netloc
        and destino.startswith("/")
        and not destino.startswith("//")
        and "\\" not in destino
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

        usuario = db.session.scalar(
            select(User).where(
                or_(
                    User.email == identificador.lower(),
                    User.username == identificador.lower()
                )
            )
        )

        if (
            usuario is not None
            and usuario.check_password(password)
        ):
            # No conservar datos de sesión anteriores.
            session.clear()
            login_user(usuario, remember=False)

            destino = request.args.get("next", "")
            if destino_local_seguro(destino):
                return redirect(destino)

            return redirect(url_for("index"))

        flash(
            "Nombre de usuario, correo o contraseña incorrectos.",
            "error"
        )

    return render_template("login.html")


@app.route("/registrarse", methods=["GET", "POST"])
def registrarse():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip().lower()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        phone = request.form.get("phone", "").strip() or None

        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,80}", username):
            flash(
                "El usuario debe tener entre 3 y 80 "
                "caracteres válidos.",
                "error"
            )

        elif (
            len(email) > 255
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        ):
            flash("Introduce un correo válido.", "error")

        elif not 12 <= len(password) <= 128:
            flash(
                "La contraseña debe tener entre "
                "12 y 128 caracteres.",
                "error"
            )

        elif password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")

        elif phone and (
            len(phone) > 20
            or not re.fullmatch(r"[0-9+(). -]{7,20}", phone)
        ):
            flash("Introduce un teléfono válido.", "error")

        else:
            condiciones = [
                User.username == username,
                User.email == email
            ]

            if phone:
                condiciones.append(User.phone == phone)

            existente = db.session.scalar(
                select(User).where(or_(*condiciones))
            )

            if existente:
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

                    session.clear()
                    login_user(usuario, remember=False)

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


@app.route("/cerrar_sesion", methods=["POST"])
@login_required
def cerrar_sesion():
    logout_user()
    session.clear()
    return redirect(url_for("index"))

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
@login_required
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
