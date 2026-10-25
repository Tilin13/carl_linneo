
import os
import re
import time
import hmac
import hashlib
import secrets
import smtplib
import sqlite3
from pathlib import Path
from functools import wraps
from email.message import EmailMessage
from urllib.parse import urlsplit

import click
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
    send_from_directory,
    session,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_user,
    logout_user,
    login_required,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)
from openai import OpenAI


# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = BASE_DIR / "pos.db"
FRONTEND_DIR = BASE_DIR / "frontend"
IMAGENES_DIR = BASE_DIR / "imagenes"

SECRET_KEY = os.getenv("SECRET_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()

MAIL_SERVER = os.getenv("MAIL_SERVER", "")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")

if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "Configura SECRET_KEY con una clave aleatoria "
        "de al menos 32 caracteres."
    )

if MAIL_PORT not in (465, 587):
    raise RuntimeError("MAIL_PORT debe ser 465 o 587.")

COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "true").lower() == "true"
)

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR),
    static_folder=str(FRONTEND_DIR),
    static_url_path="",
)

app.config.update(
    SECRET_KEY=SECRET_KEY,
    SQLALCHEMY_DATABASE_URI=BASE_DATOS.as_uri().replace(
        "file://", "sqlite://", 1
    ),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_SECURE=COOKIE_SECURE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,
    WTF_CSRF_TIME_LIMIT=3600,
    MAX_CONTENT_LENGTH=1 * 1024 * 1024,
)

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Inicia sesión para continuar."
login_manager.login_message_category = "error"
login_manager.session_protection = "strong"

csrf = CSRFProtect(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ============================================================
# MODELOS
# ============================================================

class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
        index=True,
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    phone = db.Column(
        db.String(20),
        unique=True,
        nullable=True,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    rol = db.Column(
        db.String(10),
        nullable=False,
        default="user",
        server_default="user",
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

        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.rol == "admin"


class CodigoAdmin(db.Model):
    __tablename__ = "codigos_admin"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True,
    )

    codigo_hash = db.Column(db.String(64), nullable=False)
    expira = db.Column(db.Float, nullable=False)
    intentos = db.Column(db.Integer, nullable=False, default=0)
    usado = db.Column(db.Boolean, nullable=False, default=False)


# Crear las tablas conocidas por SQLAlchemy.
with app.app_context():
    db.create_all()

    # Migración mínima para una tabla usuarios preexistente.
    # Haz una copia de seguridad antes de ejecutar esta aplicación.
    inspector = db.inspect(db.engine)

    if "usuarios" in inspector.get_table_names():
        columnas = {
            columna["name"]
            for columna in inspector.get_columns("usuarios")
        }

        if "rol" not in columnas:
            with db.engine.begin() as conexion:
                conexion.exec_driver_sql("""
                    ALTER TABLE usuarios
                    ADD COLUMN rol VARCHAR(10)
                    NOT NULL DEFAULT 'user'
                """)


# ============================================================
# LOGIN MANAGER
# ============================================================

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


# ============================================================
# CORREO Y SEGUNDO FACTOR
# ============================================================

def correo_configurado():
    return all((
        MAIL_SERVER,
        MAIL_USERNAME,
        MAIL_PASSWORD,
        ADMIN_EMAIL,
    ))


def hash_codigo(codigo):
    return hmac.new(
        SECRET_KEY.encode(),
        codigo.encode(),
        hashlib.sha256,
    ).hexdigest()


def enviar_codigo_admin(destinatario, codigo):
    if not correo_configurado():
        raise RuntimeError("El correo no está configurado.")

    mensaje = EmailMessage()
    mensaje["Subject"] = "Código de acceso | Linneo"
    mensaje["From"] = MAIL_USERNAME
    mensaje["To"] = destinatario

    mensaje.set_content(
        f"Tu código de acceso para Linneo es: {codigo}\n\n"
        "El código caduca en 5 minutos y solo puede utilizarse "
        "una vez. Si no has solicitado este acceso, ignora este mensaje."
    )

    if MAIL_PORT == 465:
        with smtplib.SMTP_SSL(
            MAIL_SERVER,
            MAIL_PORT,
            timeout=10,
        ) as smtp:
            smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
            smtp.send_message(mensaje)
    else:
        with smtplib.SMTP(
            MAIL_SERVER,
            MAIL_PORT,
            timeout=10,
        ) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
            smtp.send_message(mensaje)


# ============================================================
# FUNCIONES DE SEGURIDAD
# ============================================================

def destino_local_seguro(destino):
    if not destino:
        return False

    partes = urlsplit(destino)

    return (
        not partes.scheme
        and not partes.netloc
        and destino.startswith("/")
        and not destino.startswith("//")
        and "\\" not in destino
        and not any(ord(c) < 32 for c in destino)
    )


def administrador_requerido(func):
    @wraps(func)
    @login_required
    def decorada(*args, **kwargs):
        usuario_id = str(current_user.id)
        verificacion = session.get("admin_2fa_at")
        ahora = time.time()

        autorizado = (
            current_user.rol == "admin"
            and bool(ADMIN_EMAIL)
            and current_user.email.lower() == ADMIN_EMAIL
            and session.get("admin_2fa") == usuario_id
            and isinstance(verificacion, (int, float))
            and 0 <= ahora - verificacion <= 1800
        )

        if not autorizado:
            logout_user()
            session.clear()
            abort(403)

        return func(*args, **kwargs)

    return decorada


# ============================================================
# CABECERAS DE SEGURIDAD
# ============================================================

@app.after_request
def agregar_cabeceras_seguridad(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-XSS-Protection"] = "0"

    return response


# ============================================================
# REGISTRO
# ============================================================

@app.route("/registrarse", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def registrarse():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip() or None

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,80}", username):
            flash("El nombre de usuario no es válido.", "error")

        elif (
            len(email) > 255
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        ):
            flash("Introduce un correo válido.", "error")

        elif not 12 <= len(password) <= 128:
            flash(
                "La contraseña debe tener entre 12 y 128 caracteres.",
                "error",
            )

        elif password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")

        elif phone and not re.fullmatch(
            r"[0-9+(). -]{7,20}", phone
        ):
            flash("Introduce un teléfono válido.", "error")

        else:
            condiciones = [
                User.username == username,
                User.email == email,
            ]

            if phone:
                condiciones.append(User.phone == phone)

            existente = db.session.scalar(
                select(User).where(or_(*condiciones))
            )

            if existente:
                flash(
                    "El usuario, correo o teléfono ya está registrado.",
                    "error",
                )
            else:
                usuario = User(
                    username=username,
                    email=email,
                    phone=phone,
                    rol="user",
                )
                usuario.set_password(password)

                try:
                    db.session.add(usuario)
                    db.session.commit()

                    session.clear()
                    login_user(usuario, remember=False)
                    session.permanent = True

                    return redirect(url_for("index"))

                except IntegrityError:
                    db.session.rollback()
                    flash(
                        "El usuario, correo o teléfono ya está registrado.",
                        "error",
                    )

                except Exception:
                    db.session.rollback()
                    app.logger.exception("Error durante el registro.")
                    flash(
                        "No se pudo crear la cuenta. Inténtalo de nuevo.",
                        "error",
                    )

    return render_template("registrarse.html")


# ============================================================
# INICIO DE SESIÓN
# ============================================================

@app.route("/iniciar_sesion", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        if (
            current_user.rol == "admin"
            and session.get("admin_2fa") == str(current_user.id)
        ):
            return redirect(url_for("admin"))

        if current_user.rol != "admin":
            return redirect(url_for("index"))

        logout_user()
        session.clear()

    if request.method == "POST":
        identificador = request.form.get(
            "identificador", ""
        ).strip().lower()

        password = request.form.get("password", "")

        if not identificador or not password:
            flash("Introduce tus credenciales.", "error")
            return render_template("login.html"), 400

        usuario = db.session.scalar(
            select(User).where(
                or_(
                    User.email == identificador,
                    User.username == identificador,
                )
            )
        )

        if usuario is None or not usuario.check_password(password):
            flash(
                "Nombre de usuario, correo o contraseña incorrectos.",
                "error",
            )
            return render_template("login.html"), 401

        if usuario.rol == "admin":
            if (
                not ADMIN_EMAIL
                or usuario.email.lower() != ADMIN_EMAIL
            ):
                app.logger.warning(
                    "Intento de acceso administrativo no autorizado."
                )
                abort(403)

            if not correo_configurado():
                app.logger.error("Falta configurar el correo del administrador.")
                flash("El acceso administrativo no está configurado.", "error")
                return render_template("login.html"), 503

            codigo = f"{secrets.randbelow(1_000_000):06d}"

            try:
                # Consumir códigos anteriores de esta cuenta.
                db.session.execute(
                    update(CodigoAdmin)
                    .where(
                        CodigoAdmin.usuario_id == usuario.id,
                        CodigoAdmin.usado.is_(False),
                    )
                    .values(usado=True)
                )

                registro = CodigoAdmin(
                    usuario_id=usuario.id,
                    codigo_hash=hash_codigo(codigo),
                    expira=time.time() + 300,
                    intentos=0,
                    usado=False,
                )

                db.session.add(registro)
                db.session.commit()

            except Exception:
                db.session.rollback()
                app.logger.exception("Error preparando el segundo factor.")
                flash("No se pudo iniciar sesión.", "error")
                return render_template("login.html"), 503

            session.clear()
            session["admin_2fa_pendiente"] = usuario.id
            session.permanent = True

            try:
                enviar_codigo_admin(usuario.email, codigo)
            except Exception:
                app.logger.exception("Error enviando el código administrativo.")

                registro.usado = True
                db.session.commit()
                session.clear()

                flash(
                    "No se pudo enviar el código. Inténtalo de nuevo.",
                    "error",
                )
                return render_template("login.html"), 503

            return redirect(url_for("verificar_admin"))

        # Una cuenta normal nunca recibe privilegios administrativos.
        session.clear()
        login_user(usuario, remember=False)
        session.permanent = True

        destino = request.args.get("next", "")

        if destino_local_seguro(destino):
            return redirect(destino)

        return redirect(url_for("index"))

    return render_template("login.html")


# ============================================================
# VERIFICACIÓN DEL ADMINISTRADOR
# ============================================================

@app.route("/verificar_admin", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def verificar_admin():
    usuario_id = session.get("admin_2fa_pendiente")

    if not usuario_id:
        return redirect(url_for("login"))

    usuario = db.session.get(User, usuario_id)

    if (
        usuario is None
        or usuario.rol != "admin"
        or not ADMIN_EMAIL
        or usuario.email.lower() != ADMIN_EMAIL
    ):
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()

        if not re.fullmatch(r"[0-9]{6}", codigo):
            flash("Introduce un código de seis cifras.", "error")
            return render_template("verificar_admin.html"), 400

        registro = db.session.scalar(
            select(CodigoAdmin)
            .where(
                CodigoAdmin.usuario_id == usuario.id,
                CodigoAdmin.usado.is_(False),
            )
            .order_by(CodigoAdmin.id.desc())
        )

        if registro is None:
            session.clear()
            flash("Solicita un nuevo código.", "error")
            return redirect(url_for("login"))

        if (
            registro.expira <= time.time()
            or registro.intentos >= 5
        ):
            registro.usado = True
            db.session.commit()

            session.clear()
            flash(
                "El código ha caducado. Inicia sesión de nuevo.",
                "error",
            )
            return redirect(url_for("login"))

        if not hmac.compare_digest(
            registro.codigo_hash,
            hash_codigo(codigo),
        ):
            registro.intentos += 1

            if registro.intentos >= 5:
                registro.usado = True

            db.session.commit()

            flash("Código incorrecto.", "error")
            return render_template("verificar_admin.html"), 401

        # Consumir el código antes de conceder acceso.
        registro.usado = True

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Error consumiendo el código 2FA.")
            abort(503)

        session.clear()
        login_user(usuario, remember=False)
        session.permanent = True
        session["admin_2fa"] = str(usuario.id)
        session["admin_2fa_at"] = time.time()

        return redirect(url_for("admin"))

    return render_template("verificar_admin.html")


# ============================================================
# CIERRE DE SESIÓN
# ============================================================

@app.route("/cerrar_sesion", methods=["POST"])
@login_required
def cerrar_sesion():
    logout_user()
    session.clear()
    flash("Has cerrado sesión correctamente.", "success")
    return redirect(url_for("index"))


# ============================================================
# COMANDO PARA CREAR EL ADMINISTRADOR INICIAL
# Ejecutar: flask --app main crear-admin
# ============================================================

@app.cli.command("crear-admin")
def crear_admin():
    """Crea una cuenta administrativa desde la consola."""
    import getpass

    if not ADMIN_EMAIL:
        raise click.ClickException(
            "Configura ADMIN_EMAIL en el entorno."
        )

    username = click.prompt("Nombre de usuario").strip().lower()
    password = getpass.getpass("Contraseña del administrador: ")
    confirmacion = getpass.getpass("Confirma la contraseña: ")

    if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,80}", username):
        raise click.ClickException("Nombre de usuario no válido.")

    if password != confirmacion:
        raise click.ClickException("Las contraseñas no coinciden.")

    if not 12 <= len(password) <= 128:
        raise click.ClickException(
            "La contraseña debe tener entre 12 y 128 caracteres."
        )

    existente = db.session.scalar(
        select(User).where(
            or_(
                User.username == username,
                User.email == ADMIN_EMAIL,
            )
        )
    )

    if existente:
        raise click.ClickException(
            "El usuario o correo ya existe. No se cambiarán sus permisos."
        )

    usuario = User(
        username=username,
        email=ADMIN_EMAIL,
        phone=None,
        rol="admin",
    )
    usuario.set_password(password)

    try:
        db.session.add(usuario)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise click.ClickException("La cuenta no pudo crearse.")

    click.echo("Administrador inicial creado correctamente.")


# ============================================================
# BASE DE DATOS DE PRODUCTOS
# ============================================================

def conectar_productos():
    if not BASE_DATOS.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {BASE_DATOS}"
        )

    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row
    return conexion


def escoger_productos_azar():
    conexion = conectar_productos()

    try:
        filas = conexion.execute("""
            SELECT *
            FROM productos
            ORDER BY RANDOM()
            LIMIT 3
        """).fetchall()

        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


def buscar_productos(texto):
    conexion = conectar_productos()

    try:
        filas = conexion.execute("""
            SELECT *
            FROM productos
            WHERE nombre LIKE ?
            ORDER BY nombre ASC
            LIMIT 100
        """, (f"%{texto}%",)).fetchall()

        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


def obtener_catalogo(categoria=None):
    conexion = conectar_productos()

    try:
        if categoria:
            filas = conexion.execute("""
                SELECT *
                FROM productos
                WHERE categoria = ?
                ORDER BY nombre ASC
                LIMIT 500
            """, (categoria,)).fetchall()
        else:
            filas = conexion.execute("""
                SELECT *
                FROM productos
                ORDER BY nombre ASC
                LIMIT 500
            """).fetchall()

        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


def obtener_producto(nombre):
    conexion = conectar_productos()

    try:
        fila = conexion.execute("""
            SELECT *
            FROM productos
            WHERE nombre = ?
            LIMIT 1
        """, (nombre,)).fetchone()

        return dict(fila) if fila else None
    finally:
        conexion.close()


# ============================================================
# RUTAS DE LA TIENDA
# ============================================================

@app.route("/")
def index():
    productos = escoger_productos_azar()
    return render_template("index.html", productos=productos)


@app.route("/buscar")
def buscar():
    texto = request.args.get("busqueda", "").strip()[:100]
    productos = buscar_productos(texto)

    return render_template(
        "buscar.html",
        productos=productos,
        busqueda=texto,
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
        categoria=categoria,
    )


@app.route("/imagenes/<path:nombre_archivo>")
def imagenes(nombre_archivo):
    return send_from_directory(IMAGENES_DIR, nombre_archivo)


@app.route("/producto/<path:nombre>")
def producto(nombre):
    resultado = obtener_producto(nombre)

    if resultado is None:
        abort(404)

    return render_template("producto.html", producto=resultado)


@app.route("/comprar")
@login_required
def comprar():
    return render_template("comprar.html")


# ============================================================
# PANEL ADMINISTRATIVO
# ============================================================

@app.route("/admin")
@administrador_requerido
def admin():
    return render_template("admin.html")


# ============================================================
# CHATBOT
# ============================================================

@app.route("/chatbox")
def chatbox():
    return render_template("chatmenu.html")


@app.route("/api/chat", methods=["POST"])
@limiter.limit("10 per minute")
def api_chat():
    if client is None:
        return jsonify(error="El servicio de chat no está configurado."), 503

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(error="Petición no válida."), 400

    mensaje = data.get("mensaje", "")

    if not isinstance(mensaje, str):
        return jsonify(error="Mensaje no válido."), 400

    mensaje = mensaje.strip()

    if not mensaje:
        return jsonify(error="El mensaje está vacío."), 400

    if len(mensaje) > 4000:
        return jsonify(error="El mensaje es demasiado largo."), 413

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions="""
Eres el asistente de ventas de una tienda llamada Linneo.

La tienda vende mariposas decorativas, insectos y minerales.
Su eslogan es: La gema oculta de la ciencia.

Ayuda con el catálogo y las dudas de los clientes.
No inventes precios, disponibilidad ni características.
Si no tienes información suficiente, dilo claramente.
Sé amable, breve y natural.
""",
            input=mensaje,
        )

        return jsonify(respuesta=response.output_text)

    except Exception:
        app.logger.exception("Error en el servicio de chat.")
        return jsonify(
            error="Ocurrió un error al procesar el mensaje."
        ), 502


# ============================================================
# ERRORES HTTP
# ============================================================

@app.errorhandler(403)
def prohibido(error):
    return render_template(
        "error.html",
        codigo=403,
        mensaje="No tienes permiso para acceder a esta página.",
    ), 403


@app.errorhandler(404)
def no_encontrado(error):
    return render_template(
        "error.html",
        codigo=404,
        mensaje="La página solicitada no existe.",
    ), 404


# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":
    # Solo para desarrollo local.
    # En producción usa un servidor WSGI y HTTPS.
    app.run(
        debug=False,
        host="127.0.0.1",
        port=5000,
    )
