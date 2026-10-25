
import hashlib
import hmac
import logging
import math
import os
import re
import secrets
import smtplib
import sqlite3
import time
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

import pyotp
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from openai import OpenAI
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

# ============================================================
# CONFIGURACIÓN Y RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = BASE_DIR / "pos.db"
FRONTEND_DIR = BASE_DIR / "frontend"
IMAGENES_DIR = BASE_DIR / "imagenes"

secret_key = os.getenv("SECRET_KEY", "").strip()
api_key = os.getenv("OPENAI_API_KEY", "").strip()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()

if len(secret_key) < 32:
    raise RuntimeError(
        "Configura SECRET_KEY en .env con una clave aleatoria "
        "de al menos 32 caracteres."
    )

if not api_key:
    raise RuntimeError("Falta configurar OPENAI_API_KEY en .env.")

if not ADMIN_EMAIL or not re.fullmatch(
    r"[^@\s]+@[^@\s]+\.[^@\s]+", ADMIN_EMAIL
):
    raise RuntimeError(
        "Configura un correo válido en ADMIN_EMAIL dentro de .env."
    )

if not FRONTEND_DIR.exists():
    raise RuntimeError(f"No existe la carpeta frontend: {FRONTEND_DIR}")

cookie_secure_env = os.getenv("COOKIE_SECURE")
if cookie_secure_env is None:
    cookie_secure = os.getenv("FLASK_ENV", "").lower() == "production"
else:
    cookie_secure = cookie_secure_env.lower() in {
        "1", "true", "yes", "on"
    }

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR),
    static_folder=str(FRONTEND_DIR),
    static_url_path="",
)

app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_SECURE=cookie_secure,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,
    SQLALCHEMY_DATABASE_URI="sqlite:///" + BASE_DATOS.as_posix(),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"

csrf = CSRFProtect(app)
client = OpenAI(api_key=api_key)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)

# ============================================================
# MODELOS SQLALCHEMY
# ============================================================


class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(80), unique=True, nullable=False, index=True
    )
    email = db.Column(
        db.String(255), unique=True, nullable=False, index=True
    )
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
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
        return (
            self.rol == "admin"
            and (self.email or "").strip().lower() == ADMIN_EMAIL
        )


class CodigoAdmin(db.Model):
    # Se conserva por compatibilidad con la base de datos existente.
    # Ya no se utiliza para iniciar sesión.
    __tablename__ = "codigos_admin"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
    )
    codigo_hash = db.Column(db.String(64), nullable=False)
    expira = db.Column(db.Float, nullable=False)
    intentos = db.Column(db.Integer, nullable=False, default=0)
    usado = db.Column(db.Boolean, nullable=False, default=False)


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


# ============================================================
# CREACIÓN DE TABLAS Y MIGRACIÓN BÁSICA
# ============================================================


# ============================================================
# SEGURIDAD Y UTILIDADES
# ============================================================

def hash_codigo(codigo):
    """Calcula un HMAC para códigos temporales heredados."""
    return hmac.new(
        app.config["SECRET_KEY"].encode(),
        str(codigo).encode(),
        hashlib.sha256,
    ).hexdigest()


def destino_local_seguro(destino):
    """Evita redirecciones a sitios externos."""
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


def administrador_requerido(func):
    """Exige una sesión autenticada, el rol admin y ADMIN_EMAIL."""

    @wraps(func)
    def decorada(*args, **kwargs):
        es_api = request.path.startswith("/api/")

        if not current_user.is_authenticated:
            if es_api:
                return jsonify({
                    "error": "Debes iniciar sesión."
                }), 401

            return redirect(
                url_for("login", next=request.path)
            )

        correo_usuario = (
            getattr(current_user, "email", "") or ""
        ).strip().lower()

        rol = getattr(current_user, "rol", None)

        autorizado = (
            bool(ADMIN_EMAIL)
            and correo_usuario == ADMIN_EMAIL
            and rol == "admin"
        )

        if not autorizado:
            if es_api:
                return jsonify({
                    "error": "No tienes permiso para esta operación."
                }), 403

            abort(403)

        return func(*args, **kwargs)

    return decorada


def enviar_codigo_admin(destinatario, codigo):
    """Se conserva para compatibilidad; el login ya no la utiliza."""
    requeridas = (
        "MAIL_SERVER",
        "MAIL_PORT",
        "MAIL_USERNAME",
        "MAIL_PASSWORD",
    )

    faltantes = [
        nombre for nombre in requeridas if not os.getenv(nombre)
    ]

    if faltantes:
        raise RuntimeError(
            "Faltan variables de correo: " + ", ".join(faltantes)
        )

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
                os.environ["MAIL_PASSWORD"],
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
                os.environ["MAIL_PASSWORD"],
            )
            smtp.send_message(mensaje)


@app.after_request
def agregar_cabeceras_seguridad(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = (
        "strict-origin-when-cross-origin"
    )
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )

    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"

    return response


# ============================================================
# ERRORES HTTP
# ============================================================

@app.errorhandler(403)
def prohibido(error):
    if request.path.startswith("/api/"):
        return jsonify({
            "error": "No tienes permiso para esta operación."
        }), 403

    try:
        return render_template("403.html"), 403
    except Exception:
        return (
            "<h1>403 - Acceso denegado</h1>"
            "<p>No tienes permisos para acceder a esta página.</p>"
            '<a href="/">Volver al inicio</a>',
            403,
        )


@app.errorhandler(404)
def no_encontrado(error):
    if request.path.startswith("/api/"):
        return jsonify({
            "error": "La ruta solicitada no existe."
        }), 404

    try:
        return render_template("404.html"), 404
    except Exception:
        return "Página no encontrada", 404


@app.errorhandler(413)
def solicitud_demasiado_grande(error):
    if request.path.startswith("/api/"):
        return jsonify({
            "error": "La solicitud es demasiado grande."
        }), 413

    return "La solicitud es demasiado grande.", 413


# ============================================================
# RUTA ANTIGUA DE VERIFICACIÓN: SIN SEGUNDO FACTOR
# ============================================================

@app.route("/verificar_admin", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def verificar_admin():
    """
    Conserva la URL antigua, pero no solicita códigos 2FA.
    El administrador autenticado accede directamente al panel.
    """
    if not current_user.is_authenticated:
        session.pop("admin_2fa_pendiente", None)
        session.pop("admin_2fa_inicio", None)
        return redirect(url_for("login"))

    if (
        current_user.rol == "admin"
        and (current_user.email or "").strip().lower() == ADMIN_EMAIL
    ):
        session.pop("admin_2fa_pendiente", None)
        session.pop("admin_2fa_inicio", None)
        session.pop("admin_2fa", None)
        return redirect(url_for("admin"))

    return redirect(url_for("index"))


# ============================================================
# ADMINISTRACIÓN
# ============================================================

@app.route("/admin")
@administrador_requerido
def admin():
    return render_template("admin.html")


def validar_datos_producto(datos):
    """Valida y normaliza los datos recibidos de un producto."""
    if not isinstance(datos, dict):
        raise ValueError("Los datos del producto no son válidos.")

    codigo = str(datos.get("codigo", "")).strip()
    codigo_original = str(
        datos.get("codigo_original", "")
    ).strip()
    nombre = str(datos.get("nombre", "")).strip()
    categoria = str(datos.get("categoria", "")).strip()

    if not codigo or not nombre or not categoria:
        raise ValueError(
            "Código, nombre y categoría son obligatorios."
        )

    if len(codigo) > 80 or len(nombre) > 200:
        raise ValueError(
            "El código o el nombre son demasiado largos."
        )

    if len(categoria) > 100:
        raise ValueError("La categoría es demasiado larga.")

    try:
        precio_compra = float(datos["precio_compra"])
        precio_manofactura = float(datos["precio_manofactura"])
        precio_venta = float(datos["precio_venta"])
        stock_original = datos["stock"]

        if isinstance(stock_original, bool):
            raise ValueError

        stock_numero = float(stock_original)
        stock = int(stock_numero)

        precios = [
            precio_compra,
            precio_manofactura,
            precio_venta,
        ]

        if not all(
            math.isfinite(p) and 0 <= p <= 1_000_000_000
            for p in precios
        ):
            raise ValueError

        if (
            not math.isfinite(stock_numero)
            or stock_numero != stock
        ):
            raise ValueError

        if not 0 <= stock <= 2_000_000_000:
            raise ValueError

    except (
        ValueError,
        TypeError,
        KeyError,
        OverflowError,
    ):
        raise ValueError(
            "Los precios y el stock deben ser valores válidos "
            "y no negativos."
        )

    return {
        "codigo": codigo,
        "codigo_original": codigo_original,
        "nombre": nombre,
        "categoria": categoria,
        "precio_compra": precio_compra,
        "precio_manofactura": precio_manofactura,
        "precio_venta": precio_venta,
        "stock": stock,
    }


def guardar_producto(datos):
    """Implementación compartida por las rutas de guardado."""
    try:
        producto = validar_datos_producto(datos)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    conexion = sqlite3.connect(BASE_DATOS, timeout=10)

    try:
        cursor = conexion.cursor()

        if producto["codigo_original"]:
            cursor.execute(
                """
                UPDATE productos
                SET codigo = ?, nombre = ?, categoria = ?,
                    precio_compra = ?, precio_manofactura = ?,
                    precio_venta = ?, stock = ?
                WHERE codigo = ?
                """,
                (
                    producto["codigo"],
                    producto["nombre"],
                    producto["categoria"],
                    producto["precio_compra"],
                    producto["precio_manofactura"],
                    producto["precio_venta"],
                    producto["stock"],
                    producto["codigo_original"],
                ),
            )

            if cursor.rowcount == 0:
                conexion.rollback()
                return jsonify({
                    "error": "No se encontró el producto original."
                }), 404

        else:
            cursor.execute(
                """
                INSERT INTO productos (
                    codigo, nombre, categoria, precio_compra,
                    precio_manofactura, precio_venta, stock
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    producto["codigo"],
                    producto["nombre"],
                    producto["categoria"],
                    producto["precio_compra"],
                    producto["precio_manofactura"],
                    producto["precio_venta"],
                    producto["stock"],
                ),
            )

        conexion.commit()

        return jsonify({
            "mensaje": "Producto guardado correctamente."
        }), 200

    except sqlite3.IntegrityError:
        conexion.rollback()
        return jsonify({
            "error": "Ese código ya existe o hay un conflicto de datos."
        }), 409

    except sqlite3.Error:
        conexion.rollback()
        app.logger.exception("Error guardando producto")
        return jsonify({
            "error": "No se pudo guardar el producto."
        }), 500

    finally:
        conexion.close()


# Se conservan las tres URL anteriores.
@app.route("/api/admin/productos_guardar", methods=["POST"])
@administrador_requerido
def admin_guardar_producto():
    return guardar_producto(request.get_json(silent=True) or {})


@app.route("/api/admin/productos_guardados", methods=["POST"])
@administrador_requerido
def admin_guardados_producto():
    return guardar_producto(request.get_json(silent=True) or {})


@app.route("/api/admin/productos", methods=["GET"])
@administrador_requerido
def admin_listar_productos():
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row

    try:
        filas = conexion.execute(
            """
            SELECT codigo, nombre, categoria, precio_compra,
                   precio_manofactura, precio_venta, stock
            FROM productos
            ORDER BY nombre COLLATE NOCASE
            """
        ).fetchall()

        return jsonify([dict(fila) for fila in filas])

    except sqlite3.Error:
        app.logger.exception("Error consultando productos")
        return jsonify({
            "error": "No se pudo cargar el inventario."
        }), 500

    finally:
        conexion.close()


@app.route("/api/admin/productos", methods=["POST"])
@administrador_requerido
def admin_guarda_producto():
    return guardar_producto(request.get_json(silent=True) or {})


@app.route(
    "/api/admin/productos/<string:codigo>",
    methods=["DELETE"],
)
@administrador_requerido
def admin_eliminar_producto(codigo):
    codigo = codigo.strip()

    if not codigo:
        return jsonify({
            "error": "El código del producto no es válido."
        }), 400

    conexion = sqlite3.connect(BASE_DATOS, timeout=10)

    try:
        cursor = conexion.execute(
            "DELETE FROM productos WHERE codigo = ?",
            (codigo,),
        )

        if cursor.rowcount == 0:
            conexion.rollback()
            return jsonify({
                "error": "No se encontró el producto."
            }), 404

        conexion.commit()

        return jsonify({
            "mensaje": "Producto eliminado correctamente."
        })

    except sqlite3.Error:
        conexion.rollback()
        app.logger.exception("Error eliminando producto")
        return jsonify({
            "error": "No se pudo eliminar el producto."
        }), 500

    finally:
        conexion.close()


@app.route("/api/admin/stock", methods=["POST"])
@administrador_requerido
def admin_anadir_stock():
    datos = request.get_json(silent=True) or {}
    codigo = str(datos.get("codigo", "")).strip()
    cantidad = datos.get("cantidad")

    if not codigo:
        return jsonify({
            "error": "Introduce el código del producto."
        }), 400

    if (
        isinstance(cantidad, bool)
        or not isinstance(cantidad, int)
        or cantidad <= 0
        or cantidad > 1_000_000
    ):
        return jsonify({
            "error": "La cantidad debe ser un entero positivo."
        }), 400

    conexion = sqlite3.connect(BASE_DATOS, timeout=10)

    try:
        cursor = conexion.execute(
            """
            UPDATE productos
            SET stock = stock + ?
            WHERE codigo = ?
              AND stock >= 0
              AND stock <= 2000000000 - ?
            """,
            (cantidad, codigo, cantidad),
        )

        if cursor.rowcount == 0:
            existe = conexion.execute(
                "SELECT 1 FROM productos WHERE codigo = ?",
                (codigo,),
            ).fetchone()

            conexion.rollback()

            if existe:
                return jsonify({
                    "error": "La cantidad supera el límite permitido."
                }), 400

            return jsonify({
                "error": "No existe un producto con ese código."
            }), 404

        conexion.commit()

        return jsonify({
            "mensaje": f"Se añadieron {cantidad} unidades."
        })

    except sqlite3.Error:
        conexion.rollback()
        app.logger.exception("Error actualizando stock")
        return jsonify({
            "error": "No se pudo actualizar el stock."
        }), 500

    finally:
        conexion.close()


@app.route("/api/admin/usuarios", methods=["GET"])
@administrador_requerido
def admin_listar_usuarios():
    """Devuelve datos públicos, nunca hashes de contraseñas."""
    try:
        usuarios = db.session.scalars(
            select(User).order_by(User.id.asc())
        ).all()

        return jsonify([
            {
                "id": usuario.id,
                "username": usuario.username,
                "email": usuario.email,
                "phone": usuario.phone or "",
                "rol": usuario.rol,
            }
            for usuario in usuarios
        ])

    except Exception:
        db.session.rollback()
        app.logger.exception("Error consultando usuarios")
        return jsonify({
            "error": "No se pudieron cargar los usuarios."
        }), 500


# ============================================================
# PRODUCTOS, BÚSQUEDA Y CATÁLOGO
# ============================================================

def escoger_productos_azar():
    """Devuelve hasta tres productos aleatorios."""
    if not BASE_DATOS.exists():
        raise FileNotFoundError(
            f"No existe la base de datos: {BASE_DATOS}"
        )

    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row

    try:
        filas = conexion.execute(
            "SELECT * FROM productos ORDER BY RANDOM() LIMIT 3"
        ).fetchall()

        return [dict(fila) for fila in filas]

    finally:
        conexion.close()


def buscar_productos(texto):
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row

    try:
        filas = conexion.execute(
            """
            SELECT * FROM productos
            WHERE nombre LIKE ? OR categoria LIKE ? OR codigo LIKE ?
            ORDER BY nombre COLLATE NOCASE ASC
            """,
            (f"%{texto}%", f"%{texto}%", f"%{texto}%"),
        ).fetchall()

        return [dict(fila) for fila in filas]

    finally:
        conexion.close()


@app.route("/buscar", methods=["GET"])
def buscar():
    texto = request.args.get("busqueda", "").strip()
    texto = texto[:200]

    productos = buscar_productos(texto)

    return render_template(
        "buscar.html",
        productos=productos,
        busqueda=texto,
    )


def obtener_catalogo(categoria=None):
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row

    try:
        if categoria:
            filas = conexion.execute(
                """
                SELECT * FROM productos
                WHERE categoria = ?
                ORDER BY nombre COLLATE NOCASE ASC
                """,
                (categoria,),
            ).fetchall()
        else:
            filas = conexion.execute(
                """
                SELECT * FROM productos
                ORDER BY nombre COLLATE NOCASE ASC
                """
            ).fetchall()

        return [dict(fila) for fila in filas]

    finally:
        conexion.close()


@app.route("/")
def index():
    productos = escoger_productos_azar()
    return render_template("index.html", productos=productos)


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


def obtener_producto(nombre):
    """Obtiene un producto por su nombre exacto."""
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row

    try:
        fila = conexion.execute(
            "SELECT * FROM productos WHERE nombre = ? LIMIT 1",
            (nombre,),
        ).fetchone()

        return dict(fila) if fila is not None else None

    finally:
        conexion.close()


@app.route("/producto/<path:nombre>")
def producto(nombre):
    producto_encontrado = obtener_producto(nombre)

    if producto_encontrado is None:
        return render_template("404.html"), 404

    return render_template(
        "producto.html",
        producto=producto_encontrado,
    )


# ============================================================
# REGISTRO, LOGIN, LOGOUT Y USUARIOS
# ============================================================

@app.route("/iniciar_sesion", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        correo_actual = (
            getattr(current_user, "email", "") or ""
        ).strip().lower()

        if (
            correo_actual == ADMIN_EMAIL
            and current_user.rol == "admin"
        ):
            return redirect(url_for("admin"))

        return redirect(url_for("index"))

    if request.method == "POST":
        identificador = request.form.get(
            "identificador", ""
        ).strip()
        password = request.form.get("password", "")

        if not identificador or not password:
            flash(
                "Introduce tu usuario o correo y tu contraseña.",
                "error",
            )
            return render_template("login.html"), 400

        identificador_normalizado = identificador.lower()

        usuario = db.session.scalar(
            select(User).where(
                or_(
                    func.lower(User.email) == identificador_normalizado,
                    func.lower(User.username) == identificador_normalizado,
                )
            )
        )

        if usuario is None or not usuario.check_password(password):
            flash(
                "Usuario/correo o contraseña incorrectos.",
                "error",
            )
            return render_template("login.html"), 401

        correo_usuario = (
            (usuario.email or "").strip().lower()
        )

        # ADMIN_EMAIL es la única identidad administradora.
        # El inicio de sesión sigue exigiendo contraseña válida.
        if correo_usuario == ADMIN_EMAIL:
            if usuario.rol != "admin":
                usuario.rol = "admin"
                db.session.commit()

        elif usuario.rol == "admin":
            # Impide que un rol antiguo o manipulado otorgue
            # privilegios a otro correo.
            usuario.rol = "user"
            db.session.commit()

        session.clear()
        login_user(usuario, remember=False)
        session.permanent = True

        if correo_usuario == ADMIN_EMAIL:
            # No hay redirección a 2FA.
            return redirect(url_for("admin"))

        destino = request.args.get("next", "")

        if destino_local_seguro(destino):
            return redirect(destino)

        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/registrarse", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
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
                "El usuario debe tener entre 3 y 80 caracteres válidos.",
                "error",
            )

        elif (
            len(email) > 255
            or not re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+", email
            )
        ):
            flash("Introduce un correo válido.", "error")

        elif not 12 <= len(password) <= 128:
            flash(
                "La contraseña debe tener entre 12 y 128 caracteres.",
                "error",
            )

        elif password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")

        elif phone and (
            len(phone) > 20
            or not re.fullmatch(r"[0-9+(). -]{7,20}", phone)
        ):
            flash("Introduce un teléfono válido.", "error")

        else:
            # Se conserva el registro público como usuario normal.
            # La asignación de ADMIN_EMAIL se efectúa en el login.
            usuario = User(
                username=username,
                email=email,
                phone=phone,
                rol="user",
            )

            try:
                usuario.set_password(password)
            except ValueError as error:
                flash(str(error), "error")
                return render_template("registrarse.html"), 400

            try:
                db.session.add(usuario)
                db.session.commit()

                session.clear()
                login_user(usuario, remember=False)
                session.permanent = True

                # Si el correo es ADMIN_EMAIL, asignar el rol y
                # entrar directamente al panel, sin segundo factor.
                if email == ADMIN_EMAIL:
                    usuario.rol = "admin"
                    db.session.commit()
                    return redirect(url_for("admin"))

                return redirect(url_for("index"))

            except IntegrityError:
                db.session.rollback()
                flash(
                    "El usuario, correo o teléfono ya está registrado.",
                    "error",
                )

            except Exception:
                db.session.rollback()
                app.logger.exception("Error al registrar usuario")
                flash(
                    "No se pudo crear la cuenta. Inténtalo de nuevo.",
                    "error",
                )

    return render_template("registrarse.html")


@app.route("/cerrar_sesion", methods=["POST"])
def cerrar_sesion():
    if current_user.is_authenticated:
        logout_user()

    session.clear()

    return redirect(url_for("index"))


@app.route("/comprar")
def comprar():
    if not current_user.is_authenticated:
        return redirect(
            url_for("login", next=url_for("comprar"))
        )

    return render_template("comprar.html")


# ============================================================
# CHATBOT
# ============================================================

@app.route("/chatbox")
def chatbox():
    return render_template("chatmenu.html")


@app.route("/api/chat", methods=["POST"])
@limiter.limit("20 per minute")
def api_chat():
    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({
            "error": "La petición JSON no es válida."
        }), 400

    mensaje = datos.get("mensaje", "")

    if not isinstance(mensaje, str):
        return jsonify({
            "error": "El mensaje debe ser texto."
        }), 400

    mensaje = mensaje.strip()

    if not mensaje:
        return jsonify({"error": "El mensaje está vacío."}), 400

    if len(mensaje) > 4000:
        return jsonify({
            "error": "El mensaje supera el límite de 4000 caracteres."
        }), 400

    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions="""
Eres el asistente de ventas de una tienda llamada Linneo.
Linneo vende mariposas decorativas, insectos, minerales, fósiles,
esqueletos y productos relacionados con ciencias naturales.
Eslogan: "La gema oculta de la ciencia".

Ayuda a encontrar productos, resolver dudas, conocer el catálogo y facilitar
la compra. Sé amable, breve y natural.

No inventes precios, productos, disponibilidad ni características.
Si te preguntan por datos concretos del inventario y no se te han facilitado,
indica que deben consultar el catálogo o contactar con la tienda.
No afirmes haber realizado compras ni cambios en pedidos.
""",
            input=mensaje,
        )

        respuesta = (response.output_text or "").strip()

        if not respuesta:
            respuesta = (
                "No pude generar una respuesta. Inténtalo de nuevo."
            )

        return jsonify({"respuesta": respuesta})

    except Exception:
        app.logger.exception("Error del chatbot")
        return jsonify({
            "error": (
                "Ocurrió un error al procesar el mensaje. "
                "Inténtalo de nuevo."
            )
        }), 502


# ============================================================
# HERRAMIENTAS IA
# ============================================================

def herramienta_ia_buscarproductos(texto):
    return buscar_productos(str(texto or "").strip()[:200])


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    modo_debug = os.getenv("FLASK_DEBUG", "false").lower() in {
        "1", "true", "yes", "on"
    }

    app.run(
        debug=modo_debug,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
    )
