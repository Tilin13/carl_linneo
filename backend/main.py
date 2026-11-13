"""
Servidor Flask de Linneo.
Conserva las páginas y rutas del proyecto y añade compatibilidad básica
con esquemas antiguos de la tabla usuarios.

IMPORTANTE:
- Haz una copia de pos.db antes de sustituir el servidor.
- No borres pos.db: contiene inventario y pedidos.
- Los formularios POST deben incluir el token CSRF de Flask-WTF.
"""

import hashlib
import hmac
import logging
import math
import os
import random
import re
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

import qrcode
from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, jsonify, redirect, render_template,
    request, send_from_directory, session, url_for
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (
    LoginManager, UserMixin, current_user, login_user,
    logout_user, login_required
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from openai import OpenAI
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = BASE_DIR / "pos.db"
FRONTEND_DIR = BASE_DIR / "frontend"
IMAGENES_DIR = BASE_DIR / "imagenes"

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()

if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "Configura SECRET_KEY en .env con una clave aleatoria "
        "de al menos 32 caracteres."
    )

if not ADMIN_EMAIL or not re.fullmatch(
    r"[^@\s]+@[^@\s]+\.[^@\s]+", ADMIN_EMAIL
):
    raise RuntimeError("Configura un ADMIN_EMAIL válido en .env.")

if not FRONTEND_DIR.is_dir():
    raise RuntimeError(f"No existe la carpeta frontend: {FRONTEND_DIR}")

cookie_secure_env = os.getenv("COOKIE_SECURE")
if cookie_secure_env is None:
    COOKIE_SECURE = os.getenv("FLASK_ENV", "").lower() == "production"
else:
    COOKIE_SECURE = cookie_secure_env.lower() in {"1", "true", "yes", "on"}

BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR),
    static_folder=str(FRONTEND_DIR),
    static_url_path=""
)

app.config.update(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_SECURE=COOKIE_SECURE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,
    SQLALCHEMY_DATABASE_URI="sqlite:///" + BASE_DATOS.as_posix(),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"timeout": 20}},
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"

csrf = CSRFProtect(app)

# El sitio puede funcionar aunque la API de OpenAI no esté configurada.
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)

logging.basicConfig(level=logging.INFO)


# ============================================================
# MODELOS
# ============================================================

class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    # Nullable para poder conservar cuentas antiguas incompletas.
    password = db.Column(db.String(255), nullable=True)
    rol = db.Column(db.String(10), nullable=False, default="user")

    pedidos = db.relationship(
        "Pedido", back_populates="usuario",
        cascade="save-update, merge"
    )

    def set_password(self, password):
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise ValueError("La contraseña debe tener entre 12 y 128 caracteres.")
        self.password = generate_password_hash(password)

    def check_password(self, password):
        if not self.password or not isinstance(password, str):
            return False
        try:
            return check_password_hash(self.password, password)
        except (ValueError, TypeError):
            return False


class LoginLock(db.Model):
    __tablename__ = "login_locks"

    id = db.Column(db.Integer, primary_key=True)
    lock_key = db.Column(db.String(64), unique=True, nullable=False)
    intentos = db.Column(db.Integer, nullable=False, default=0)
    bloqueado_hasta = db.Column(db.DateTime, nullable=True)


class Pedido(db.Model):
    __tablename__ = "pedidos"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer, db.ForeignKey("usuarios.id"),
        nullable=False, index=True
    )
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    descuento = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    metodo_pago = db.Column(db.String(30), nullable=False, default="efectivo")
    estado = db.Column(db.String(30), nullable=False, default="Pendiente")

    usuario = db.relationship("User", back_populates="pedidos")
    productos = db.relationship(
        "PedidoItem", back_populates="pedido",
        cascade="all, delete-orphan"
    )


class PedidoItem(db.Model):
    __tablename__ = "pedido_items"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(
        db.Integer, db.ForeignKey("pedidos.id"),
        nullable=False, index=True
    )
    producto_codigo = db.Column(db.String(80), nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    pedido = db.relationship("Pedido", back_populates="productos")


class CodigoAdmin(db.Model):
    # Se conserva para compatibilidad con la base antigua.
    __tablename__ = "codigos_admin"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    codigo_hash = db.Column(db.String(64), nullable=False)
    expira = db.Column(db.Float, nullable=False)
    intentos = db.Column(db.Integer, nullable=False, default=0)
    usado = db.Column(db.Boolean, nullable=False, default=False)


# ============================================================
# INICIALIZACIÓN Y MIGRACIÓN SEGURA DE USUARIOS
# ============================================================

def inicializar_base_datos():
    """Crea únicamente las tablas que falten; no borra datos existentes."""
    BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db.create_all()


def migrar_usuarios_password():
    """
    Añade columnas ausentes a usuarios y copia password_hash a password
    cuando exista. No elimina ni recrea tablas ni registros.
    """
    if not BASE_DATOS.exists():
        return

    conexion = sqlite3.connect(BASE_DATOS, timeout=20)
    try:
        existe = conexion.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='usuarios'"
        ).fetchone()
        if not existe:
            return

        columnas = {
            fila[1] for fila in conexion.execute(
                "PRAGMA table_info(usuarios)"
            ).fetchall()
        }

        # Se añaden columnas de forma aditiva para no destruir datos.
        adiciones = {
            "username": "TEXT",
            "email": "TEXT",
            "phone": "TEXT",
            "password": "VARCHAR(255)",
            "rol": "TEXT NOT NULL DEFAULT 'user'",
        }
        for nombre, tipo in adiciones.items():
            if nombre not in columnas:
                conexion.execute(
                    f'ALTER TABLE usuarios ADD COLUMN "{nombre}" {tipo}'
                )

        columnas = {
            fila[1] for fila in conexion.execute(
                "PRAGMA table_info(usuarios)"
            ).fetchall()
        }

        if "password_hash" in columnas:
            conexion.execute("""
                UPDATE usuarios
                SET password = password_hash
                WHERE (password IS NULL OR password = '')
                  AND password_hash IS NOT NULL
            """)

        # Rellenar campos vacíos para que el modelo pueda cargar filas heredadas.
        filas = conexion.execute(
            "SELECT id, username, email FROM usuarios ORDER BY id"
        ).fetchall()
        for user_id, username, email in filas:
            if not username:
                username = f"usuario_antiguo_{user_id}"
            if not email:
                email = f"usuario_antiguo_{user_id}@invalid.local"
            conexion.execute(
                "UPDATE usuarios SET username=?, email=? WHERE id=?",
                (str(username).strip().lower(), str(email).strip().lower(), user_id)
            )

        # Crear índices únicos si los datos existentes lo permiten.
        duplicados_username = conexion.execute("""
            SELECT username FROM usuarios GROUP BY username
            HAVING COUNT(*) > 1 LIMIT 1
        """).fetchone()
        duplicados_email = conexion.execute("""
            SELECT email FROM usuarios GROUP BY email
            HAVING COUNT(*) > 1 LIMIT 1
        """).fetchone()

        if not duplicados_username:
            conexion.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_username "
                "ON usuarios(username)"
            )
        else:
            app.logger.warning(
                "Hay usernames duplicados en usuarios; no se creó el índice único."
            )

        if not duplicados_email:
            conexion.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_email "
                "ON usuarios(email)"
            )
        else:
            app.logger.warning(
                "Hay emails duplicados en usuarios; no se creó el índice único."
            )

        conexion.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_phone "
            "ON usuarios(phone)"
        )
        conexion.commit()
        app.logger.info("Migración compatible de usuarios completada.")
    except Exception:
        conexion.rollback()
        app.logger.exception("Falló la migración de usuarios.")
        raise
    finally:
        conexion.close()


def crear_tabla_productos():
    """Crea inventario únicamente si todavía no existe."""
    BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(BASE_DATOS, timeout=20)
    try:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                codigo TEXT PRIMARY KEY,
                nombre TEXT NOT NULL,
                categoria TEXT NOT NULL,
                precio_compra REAL NOT NULL DEFAULT 0,
                precio_manofactura REAL NOT NULL DEFAULT 0,
                precio_venta REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0
            )
        """)
        conexion.commit()
    finally:
        conexion.close()


def comprobar_tablas():
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    try:
        tablas = conexion.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' ORDER BY name
        """).fetchall()
        print("Tablas encontradas:")
        for tabla in tablas:
            print("-", tabla[0])
        if "productos" in [t[0] for t in tablas]:
            print("Columnas de productos:")
            for columna in conexion.execute("PRAGMA table_info(productos)"):
                print(columna[1], columna[2])
        else:
            print("ERROR: No existe la tabla productos.")
    finally:
        conexion.close()


def diagnosticar_usuarios():
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    try:
        print("\n===== DIAGNÓSTICO USUARIOS =====")
        print("Base de datos:", BASE_DATOS)
        columnas = conexion.execute("PRAGMA table_info(usuarios)").fetchall()
        for columna in columnas:
            print(columna)
        print("Índices:")
        for indice in conexion.execute("PRAGMA index_list(usuarios)"):
            print(indice)
        if columnas:
            nombres = {c[1] for c in columnas}
            requeridas = ["id", "username", "email", "phone", "rol", "password"]
            if all(c in nombres for c in requeridas):
                for fila in conexion.execute("""
                    SELECT id, username, email, phone, rol,
                           CASE WHEN password IS NULL OR password=''
                                THEN 'SIN PASSWORD' ELSE 'CON PASSWORD' END
                    FROM usuarios ORDER BY id
                """):
                    print(fila)
        print("===== FIN DIAGNÓSTICO =====\n")
    finally:
        conexion.close()


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


# ============================================================
# AUTENTICACIÓN Y SEGURIDAD
# ============================================================

MAX_INTENTOS_LOGIN = 5
DURACION_BLOQUEO = timedelta(minutes=30)


def obtener_clave_bloqueo(identificador):
    identificador = " ".join(str(identificador).split()).casefold()
    ip = get_remote_address() or "desconocida"
    return hashlib.sha256(
        f"{identificador}|{ip}".encode("utf-8")
    ).hexdigest()


def comprobar_bloqueo(clave):
    registro = db.session.scalar(
        select(LoginLock).where(LoginLock.lock_key == clave)
    )
    if registro is None:
        return False, None
    if registro.bloqueado_hasta is None:
        return False, registro

    bloqueado_hasta = registro.bloqueado_hasta
    if bloqueado_hasta.tzinfo is None:
        bloqueado_hasta = bloqueado_hasta.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) < bloqueado_hasta:
        return True, registro

    registro.intentos = 0
    registro.bloqueado_hasta = None
    db.session.commit()
    return False, registro


def registrar_fallo_login(clave):
    registro = db.session.scalar(
        select(LoginLock).where(LoginLock.lock_key == clave)
    )
    if registro is None:
        registro = LoginLock(lock_key=clave, intentos=0)
        db.session.add(registro)

    registro.intentos += 1
    if registro.intentos >= MAX_INTENTOS_LOGIN:
        registro.bloqueado_hasta = (
            datetime.now(timezone.utc).replace(tzinfo=None) + DURACION_BLOQUEO
        )
        db.session.commit()
        return True

    db.session.commit()
    return False


def reiniciar_intentos_login(clave):
    registro = db.session.scalar(
        select(LoginLock).where(LoginLock.lock_key == clave)
    )
    if registro:
        registro.intentos = 0
        registro.bloqueado_hasta = None
        db.session.commit()


def hash_codigo(codigo):
    return hmac.new(
        app.config["SECRET_KEY"].encode(),
        str(codigo).encode(),
        hashlib.sha256
    ).hexdigest()


def destino_local_seguro(destino):
    if not destino:
        return False
    partes = urlsplit(destino)
    return (
        not partes.scheme and not partes.netloc
        and destino.startswith("/") and not destino.startswith("//")
        and "\\" not in destino
    )


def administrador_requerido(func):
    @wraps(func)
    def decorada(*args, **kwargs):
        es_api = request.path.startswith("/api/")
        if not current_user.is_authenticated:
            if es_api:
                return jsonify({"error": "Debes iniciar sesión."}), 401
            return redirect(url_for("login", next=request.path))

        correo = (getattr(current_user, "email", "") or "").strip().lower()
        autorizado = correo == ADMIN_EMAIL and getattr(current_user, "rol", "") == "admin"
        if not autorizado:
            if es_api:
                return jsonify({"error": "No tienes permiso para esta operación."}), 403
            abort(403)
        return func(*args, **kwargs)
    return decorada


def enviar_codigo_admin(destinatario, codigo):
    """Función heredada para envío de códigos; no interviene en el login actual."""
    requeridas = ("MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME", "MAIL_PASSWORD")
    faltantes = [nombre for nombre in requeridas if not os.getenv(nombre)]
    if faltantes:
        raise RuntimeError("Faltan variables de correo: " + ", ".join(faltantes))

    mensaje = EmailMessage()
    mensaje["Subject"] = "Código de acceso | Linneo"
    mensaje["From"] = os.environ["MAIL_USERNAME"]
    mensaje["To"] = destinatario
    mensaje.set_content(
        f"Tu código de acceso para Linneo es: {codigo}\nCaduca en 5 minutos."
    )

    servidor = os.environ["MAIL_SERVER"]
    puerto = int(os.environ["MAIL_PORT"])
    if puerto == 465:
        with smtplib.SMTP_SSL(servidor, puerto, timeout=10) as smtp:
            smtp.login(os.environ["MAIL_USERNAME"], os.environ["MAIL_PASSWORD"])
            smtp.send_message(mensaje)
    else:
        with smtplib.SMTP(servidor, puerto, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(os.environ["MAIL_USERNAME"], os.environ["MAIL_PASSWORD"])
            smtp.send_message(mensaje)


@app.after_request
def agregar_cabeceras_seguridad(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ============================================================
# ERRORES HTTP Y CUENTA
# ============================================================

@app.errorhandler(403)
def prohibido(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "No tienes permiso para esta operación."}), 403
    try:
        return render_template("403.html"), 403
    except Exception:
        return "<h1>403 - Acceso denegado</h1><a href='/'>Volver al inicio</a>", 403


@app.errorhandler(404)
def no_encontrado(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "La ruta solicitada no existe."}), 404
    try:
        return render_template("404.html"), 404
    except Exception:
        return "Página no encontrada", 404


@app.errorhandler(413)
def solicitud_demasiado_grande(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "La solicitud es demasiado grande."}), 413
    return "La solicitud es demasiado grande.", 413


@app.route("/mi_cuenta")
@login_required
def mi_cuenta():
    pedidos = (
        Pedido.query.filter_by(usuario_id=current_user.id)
        .order_by(Pedido.fecha.desc()).all()
    )
    return render_template("usuario.html", usuario=current_user, pedidos=pedidos)


def registrar_pedido(usuario_id, subtotal):
    pedido = Pedido(
        usuario_id=usuario_id,
        subtotal=Decimal(str(subtotal)),
        descuento=Decimal("0.00"),
        total=Decimal(str(subtotal)),
        estado="Pendiente"
    )
    db.session.add(pedido)
    db.session.commit()
    return pedido


@app.route("/cambiar_telefono", methods=["POST"])
@login_required
def cambiar_telefono():
    nuevo_telefono = request.form.get("telefono", "").strip()
    if not nuevo_telefono or len(nuevo_telefono) > 20 or not re.fullmatch(
        r"[0-9+(). -]{7,20}", nuevo_telefono
    ):
        flash("Ingresa un número de teléfono válido.", "error")
        return redirect(url_for("mi_cuenta"))

    try:
        current_user.phone = nuevo_telefono
        db.session.commit()
        flash("Tu teléfono se actualizó correctamente.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Ese teléfono ya está asociado a otra cuenta.", "error")
    return redirect(url_for("mi_cuenta"))


@app.route("/cambiar_contrasena", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def cambiar_contrasena():
    actual = request.form.get("password_actual", "")
    nueva = request.form.get("password_nueva", "")
    confirmar = request.form.get("confirmar_password", "")

    if not current_user.check_password(actual):
        flash("La contraseña actual es incorrecta.", "error")
    elif not 12 <= len(nueva) <= 128:
        flash("La nueva contraseña debe tener entre 12 y 128 caracteres.", "error")
    elif nueva != confirmar:
        flash("Las contraseñas nuevas no coinciden.", "error")
    elif actual == nueva:
        flash("La nueva contraseña debe ser diferente.", "error")
    else:
        current_user.set_password(nueva)
        db.session.commit()
        logout_user()
        session.clear()
        flash("Contraseña actualizada. Inicia sesión nuevamente.", "success")
        return redirect(url_for("login"))
    return redirect(url_for("mi_cuenta"))


@app.route("/verificar_admin", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def verificar_admin():
    if not current_user.is_authenticated:
        for key in ("admin_2fa_pendiente", "admin_2fa_inicio", "admin_2fa"):
            session.pop(key, None)
        return redirect(url_for("login"))
    correo = (current_user.email or "").strip().lower()
    if current_user.rol == "admin" and correo == ADMIN_EMAIL:
        for key in ("admin_2fa_pendiente", "admin_2fa_inicio", "admin_2fa"):
            session.pop(key, None)
        return redirect(url_for("admin"))
    return redirect(url_for("index"))


# ============================================================
# CAJA Y PEDIDOS DE ADMINISTRACIÓN
# ============================================================

@app.route("/caja")
@administrador_requerido
def caja():
    return render_template("caja.html")


@app.route("/api/admin/caja/venta", methods=["POST"])
@administrador_requerido
def registrar_venta_caja():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "Datos no válidos."}), 400

    usuario_id = datos.get("usuario_id")
    productos = datos.get("productos")
    metodo_pago = datos.get("metodo_pago", "efectivo")
    descuento_porcentaje = datos.get("descuento", 0)

    if isinstance(usuario_id, bool) or not isinstance(usuario_id, int) or usuario_id <= 0:
        return jsonify({"error": "Selecciona un comprador válido."}), 400
    comprador = db.session.get(User, usuario_id)
    if comprador is None:
        return jsonify({"error": "El comprador no existe."}), 404
    if metodo_pago != "efectivo":
        return jsonify({"error": "Método de pago no disponible."}), 400

    try:
        if isinstance(descuento_porcentaje, bool):
            raise ValueError
        descuento_porcentaje = Decimal(str(descuento_porcentaje))
        if not descuento_porcentaje.is_finite() or not 0 <= descuento_porcentaje <= 100:
            raise ValueError
    except (ValueError, TypeError, InvalidOperation):
        return jsonify({"error": "Descuento no válido."}), 400

    if not isinstance(productos, list) or not productos or len(productos) > 100:
        return jsonify({"error": "Agrega productos a la venta."}), 400

    cantidades = {}
    for item in productos:
        if not isinstance(item, dict):
            return jsonify({"error": "Producto no válido."}), 400
        codigo = str(item.get("codigo", "")).strip()
        cantidad = item.get("cantidad")
        if not codigo or len(codigo) > 80:
            return jsonify({"error": "Código no válido."}), 400
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or not 1 <= cantidad <= 10000:
            return jsonify({"error": "Cantidad no válida."}), 400
        cantidades[codigo] = cantidades.get(codigo, 0) + cantidad

    if any(c > 10000 for c in cantidades.values()):
        return jsonify({"error": "Cantidad demasiado grande."}), 400

    subtotal = Decimal("0.00")
    try:
        pedido = Pedido(
            usuario_id=comprador.id, subtotal=0, descuento=0, total=0,
            metodo_pago=metodo_pago, estado="Pagado"
        )
        db.session.add(pedido)
        db.session.flush()

        for codigo, cantidad in cantidades.items():
            producto = db.session.execute(text("""
                SELECT codigo, nombre, precio_venta
                FROM productos WHERE codigo=:codigo
            """), {"codigo": codigo}).mappings().first()
            if producto is None:
                raise ValueError(f"No existe el producto {codigo}.")

            resultado = db.session.execute(text("""
                UPDATE productos SET stock=stock-:cantidad
                WHERE codigo=:codigo AND stock>=:cantidad
            """), {"codigo": codigo, "cantidad": cantidad})
            if resultado.rowcount != 1:
                raise ValueError(f"Stock insuficiente para {producto['nombre']}.")

            precio = Decimal(str(producto["precio_venta"])).quantize(Decimal("0.01"))
            if not precio.is_finite() or precio < 0:
                raise ValueError("Precio de producto no válido.")
            total_producto = (precio * cantidad).quantize(Decimal("0.01"))
            db.session.add(PedidoItem(
                pedido_id=pedido.id, producto_codigo=codigo,
                nombre=producto["nombre"], cantidad=cantidad,
                precio_unitario=precio, total=total_producto
            ))
            subtotal += total_producto

        subtotal = subtotal.quantize(Decimal("0.01"))
        descuento = (subtotal * descuento_porcentaje / Decimal("100")).quantize(Decimal("0.01"))
        total = (subtotal - descuento).quantize(Decimal("0.01"))
        pedido.subtotal, pedido.descuento, pedido.total = subtotal, descuento, total
        db.session.commit()
        return jsonify({
            "mensaje": "Venta registrada correctamente.",
            "pedido_id": pedido.id,
            "comprador": comprador.username,
            "subtotal": str(subtotal),
            "descuento": str(descuento),
            "total": str(total),
            "estado": pedido.estado,
            "url": url_for("detalle_pedido_admin", pedido_id=pedido.id)
        }), 201
    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400
    except Exception:
        db.session.rollback()
        app.logger.exception("Error registrando venta de caja.")
        return jsonify({"error": "No se pudo completar la venta."}), 500


@app.route("/admin/pedido/<int:pedido_id>")
@administrador_requerido
def detalle_pedido_admin(pedido_id):
    pedido = db.session.get(Pedido, pedido_id)
    if pedido is None:
        abort(404)
    return render_template("pedido.html", pedido=pedido)


# ============================================================
# ADMINISTRACIÓN E INVENTARIO
# ============================================================

@app.route("/admin")
@administrador_requerido
def admin():
    return render_template("admin.html")


def validar_datos_producto(datos):
    if not isinstance(datos, dict):
        raise ValueError("Los datos del producto no son válidos.")

    codigo = str(datos.get("codigo", "")).strip()
    codigo_original = str(datos.get("codigo_original", "")).strip()
    nombre = str(datos.get("nombre", "")).strip()
    categoria = str(datos.get("categoria", "")).strip()

    if not codigo or not nombre or not categoria:
        raise ValueError("Código, nombre y categoría son obligatorios.")
    if len(codigo) > 80 or len(nombre) > 200:
        raise ValueError("El código o el nombre son demasiado largos.")
    if len(categoria) > 100:
        raise ValueError("La categoría es demasiado larga.")

    try:
        precios = [
            float(datos["precio_compra"]),
            float(datos["precio_manofactura"]),
            float(datos["precio_venta"])
        ]
        stock_original = datos["stock"]
        if isinstance(stock_original, bool):
            raise ValueError
        stock_numero = float(stock_original)
        stock = int(stock_numero)
        if not all(math.isfinite(p) and 0 <= p <= 1_000_000_000 for p in precios):
            raise ValueError
        if not math.isfinite(stock_numero) or stock_numero != stock:
            raise ValueError
        if not 0 <= stock <= 2_000_000_000:
            raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError("Los precios y el stock deben ser valores válidos y no negativos.")

    return {
        "codigo": codigo, "codigo_original": codigo_original,
        "nombre": nombre, "categoria": categoria,
        "precio_compra": precios[0], "precio_manofactura": precios[1],
        "precio_venta": precios[2], "stock": stock
    }


def guardar_producto(datos):
    try:
        producto = validar_datos_producto(datos)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    conexion = sqlite3.connect(BASE_DATOS, timeout=20)
    try:
        cursor = conexion.cursor()
        if producto["codigo_original"]:
            cursor.execute("""
                UPDATE productos
                SET codigo=?, nombre=?, categoria=?, precio_compra=?,
                    precio_manofactura=?, precio_venta=?, stock=?
                WHERE codigo=?
            """, (
                producto["codigo"], producto["nombre"], producto["categoria"],
                producto["precio_compra"], producto["precio_manofactura"],
                producto["precio_venta"], producto["stock"],
                producto["codigo_original"]
            ))
            if cursor.rowcount == 0:
                conexion.rollback()
                return jsonify({"error": "No se encontró el producto original."}), 404
        else:
            cursor.execute("""
                INSERT INTO productos (
                    codigo, nombre, categoria, precio_compra,
                    precio_manofactura, precio_venta, stock
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                producto["codigo"], producto["nombre"], producto["categoria"],
                producto["precio_compra"], producto["precio_manofactura"],
                producto["precio_venta"], producto["stock"]
            ))
        conexion.commit()
        return jsonify({"mensaje": "Producto guardado correctamente."}), 200
    except sqlite3.IntegrityError:
        conexion.rollback()
        return jsonify({"error": "Ese código ya existe o hay un conflicto de datos."}), 409
    except sqlite3.Error:
        conexion.rollback()
        app.logger.exception("Error guardando producto")
        return jsonify({"error": "No se pudo guardar el producto."}), 500
    finally:
        conexion.close()


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
    conexion = sqlite3.connect(BASE_DATOS, timeout=20)
    conexion.row_factory = sqlite3.Row
    try:
        filas = conexion.execute("""
            SELECT codigo, nombre, categoria, precio_compra,
                   precio_manofactura, precio_venta, stock
            FROM productos ORDER BY nombre COLLATE NOCASE
        """).fetchall()
        return jsonify([dict(fila) for fila in filas])
    except sqlite3.Error:
        app.logger.exception("Error consultando productos")
        return jsonify({"error": "No se pudo cargar el inventario."}), 500
    finally:
        conexion.close()


@app.route("/api/admin/productos", methods=["POST"])
@administrador_requerido
def admin_guarda_producto():
    return guardar_producto(request.get_json(silent=True) or {})


@app.route("/api/admin/productos/<string:codigo>", methods=["DELETE"])
@administrador_requerido
def admin_eliminar_producto(codigo):
    codigo = codigo.strip()
    if not codigo:
        return jsonify({"error": "El código del producto no es válido."}), 400
    conexion = sqlite3.connect(BASE_DATOS, timeout=20)
    try:
        cursor = conexion.execute("DELETE FROM productos WHERE codigo=?", (codigo,))
        if cursor.rowcount == 0:
            conexion.rollback()
            return jsonify({"error": "No se encontró el producto."}), 404
        conexion.commit()
        return jsonify({"mensaje": "Producto eliminado correctamente."})
    except sqlite3.Error:
        conexion.rollback()
        app.logger.exception("Error eliminando producto")
        return jsonify({"error": "No se pudo eliminar el producto."}), 500
    finally:
        conexion.close()


@app.route("/api/admin/stock", methods=["POST"])
@administrador_requerido
def admin_anadir_stock():
    datos = request.get_json(silent=True) or {}
    codigo = str(datos.get("codigo", "")).strip()
    cantidad = datos.get("cantidad")
    if not codigo:
        return jsonify({"error": "Introduce el código del producto."}), 400
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or not 1 <= cantidad <= 1_000_000:
        return jsonify({"error": "La cantidad debe ser un entero positivo."}), 400

    conexion = sqlite3.connect(BASE_DATOS, timeout=20)
    try:
        cursor = conexion.execute("""
            UPDATE productos SET stock=stock+?
            WHERE codigo=? AND stock>=0 AND stock<=2000000000-?
        """, (cantidad, codigo, cantidad))
        if cursor.rowcount == 0:
            existe = conexion.execute(
                "SELECT 1 FROM productos WHERE codigo=?", (codigo,)
            ).fetchone()
            conexion.rollback()
            if existe:
                return jsonify({"error": "La cantidad supera el límite permitido."}), 400
            return jsonify({"error": "No existe un producto con ese código."}), 404
        conexion.commit()
        return jsonify({"mensaje": f"Se añadieron {cantidad} unidades."})
    except sqlite3.Error:
        conexion.rollback()
        app.logger.exception("Error actualizando stock")
        return jsonify({"error": "No se pudo actualizar el stock."}), 500
    finally:
        conexion.close()


@app.route("/api/admin/usuarios", methods=["GET"])
@administrador_requerido
def admin_listar_usuarios():
    try:
        usuarios = db.session.scalars(select(User).order_by(User.id.asc())).all()
        return jsonify([{
            "id": u.id, "username": u.username, "email": u.email,
            "phone": u.phone or "", "rol": u.rol
        } for u in usuarios])
    except Exception:
        db.session.rollback()
        app.logger.exception("Error consultando usuarios")
        return jsonify({"error": "No se pudieron cargar los usuarios."}), 500


# ============================================================
# CHECKOUT Y DETALLES DE PEDIDO
# ============================================================

@app.route("/api/pedidos", methods=["POST"])
@login_required
def crear_pedido():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "Los datos de compra no son válidos."}), 400
    solicitados = datos.get("productos")
    if not isinstance(solicitados, list) or not solicitados or len(solicitados) > 100:
        return jsonify({"error": "El carrito está vacío o no es válido."}), 400

    cantidades = {}
    for item in solicitados:
        if not isinstance(item, dict):
            return jsonify({"error": "Producto no válido."}), 400
        codigo = str(item.get("id", "")).strip()
        cantidad = item.get("cantidad")
        if not codigo or len(codigo) > 80:
            return jsonify({"error": "Código de producto no válido."}), 400
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or not 1 <= cantidad <= 10000:
            return jsonify({"error": "Cantidad no válida."}), 400
        cantidades[codigo] = cantidades.get(codigo, 0) + cantidad

    if any(c > 10000 for c in cantidades.values()):
        return jsonify({"error": "La cantidad solicitada es demasiado grande."}), 400

    subtotal = Decimal("0.00")
    try:
        pedido = Pedido(
            usuario_id=current_user.id, subtotal=0, descuento=0,
            total=0, estado="Pendiente", metodo_pago="efectivo"
        )
        db.session.add(pedido)
        db.session.flush()

        for codigo, cantidad in cantidades.items():
            producto = db.session.execute(text("""
                SELECT codigo, nombre, precio_venta
                FROM productos WHERE codigo=:codigo
            """), {"codigo": codigo}).mappings().first()
            if producto is None:
                raise ValueError(f"El producto {codigo} ya no existe.")

            resultado = db.session.execute(text("""
                UPDATE productos SET stock=stock-:cantidad
                WHERE codigo=:codigo AND stock>=:cantidad
            """), {"cantidad": cantidad, "codigo": codigo})
            if resultado.rowcount != 1:
                raise ValueError("No hay stock suficiente. Actualiza tu carrito.")

            precio = Decimal(str(producto["precio_venta"])).quantize(Decimal("0.01"))
            if not precio.is_finite() or precio < 0:
                raise ValueError("El precio de un producto no es válido.")
            total_producto = (precio * cantidad).quantize(Decimal("0.01"))
            db.session.add(PedidoItem(
                pedido_id=pedido.id, producto_codigo=codigo,
                nombre=producto["nombre"], cantidad=cantidad,
                precio_unitario=precio, total=total_producto
            ))
            subtotal += total_producto

        pedido.subtotal = subtotal
        pedido.total = subtotal
        pedido.descuento = Decimal("0.00")
        db.session.commit()
        return jsonify({
            "mensaje": "Pedido realizado correctamente.",
            "pedido_id": pedido.id,
            "url": url_for("detalle_pedido", pedido_id=pedido.id)
        }), 201
    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400
    except Exception:
        db.session.rollback()
        app.logger.exception("Error al procesar el pedido.")
        return jsonify({"error": "No se pudo procesar la compra."}), 500


@app.route("/pedido/<int:pedido_id>")
@login_required
def detalle_pedido(pedido_id):
    pedido = Pedido.query.filter_by(
        id=pedido_id, usuario_id=current_user.id
    ).first_or_404()
    return render_template("pedido.html", pedido=pedido)


# ============================================================
# CATÁLOGO, BÚSQUEDA Y PÁGINAS PÚBLICAS
# ============================================================

def escoger_productos_azar():
    if not BASE_DATOS.exists():
        return []
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
        filas = conexion.execute("""
            SELECT * FROM productos
            WHERE nombre LIKE ? OR categoria LIKE ? OR codigo LIKE ?
            ORDER BY nombre COLLATE NOCASE ASC
        """, (f"%{texto}%", f"%{texto}%", f"%{texto}%")).fetchall()
        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


@app.route("/buscar", methods=["GET"])
def buscar():
    texto = request.args.get("busqueda", "").strip()[:200]
    return render_template(
        "buscar.html", productos=buscar_productos(texto), busqueda=texto
    )


def obtener_catalogo(categoria=None):
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row
    try:
        if categoria:
            filas = conexion.execute("""
                SELECT * FROM productos WHERE categoria=?
                ORDER BY nombre COLLATE NOCASE ASC
            """, (categoria,)).fetchall()
        else:
            filas = conexion.execute("""
                SELECT * FROM productos ORDER BY nombre COLLATE NOCASE ASC
            """).fetchall()
        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


@app.route("/")
def index():
    return render_template("index.html", productos=escoger_productos_azar())


@app.route("/informacion")
def informacion():
    return render_template("informacion.html")


@app.route("/contacto")
def contacto():
    return render_template("contacto.html")


def especies_disponibles():
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row
    try:
        filas = conexion.execute("""
            SELECT codigo, nombre, categoria, stock
            FROM productos
            WHERE categoria IN ('Mariposas','Escarabajos','Odonatos')
              AND stock > 0
            ORDER BY categoria, nombre COLLATE NOCASE
        """).fetchall()
        return [dict(fila) for fila in filas]
    finally:
        conexion.close()


@app.route("/pedido_personalizado")
def pedido_personalizado():
    return render_template("pedidos_personalizados.html")


@app.route("/crear_pedido")
def crear_pedido_p():
    return render_template("crear_pedido.html", especies=especies_disponibles())


@app.route("/catalogo")
@app.route("/catalogo/<categoria>")
def catalogo(categoria=None):
    return render_template(
        "catalogo.html", productos=obtener_catalogo(categoria),
        categoria=categoria
    )


@app.route("/imagenes/<path:nombre_archivo>")
def imagenes(nombre_archivo):
    return send_from_directory(IMAGENES_DIR, nombre_archivo)


def obtener_producto(nombre):
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row
    try:
        fila = conexion.execute(
            "SELECT * FROM productos WHERE nombre=? LIMIT 1", (nombre,)
        ).fetchone()
        return dict(fila) if fila is not None else None
    finally:
        conexion.close()


@app.route("/producto/<path:nombre>")
def producto(nombre):
    encontrado = obtener_producto(nombre)
    if encontrado is None:
        return render_template("404.html"), 404
    return render_template("producto.html", producto=encontrado)


# ============================================================
# REGISTRO, LOGIN Y CIERRE DE SESIÓN
# ============================================================

@app.route("/iniciar_sesion", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        correo = (getattr(current_user, "email", "") or "").strip().lower()
        if correo == ADMIN_EMAIL and current_user.rol == "admin":
            return redirect(url_for("admin"))
        return redirect(url_for("index"))

    if request.method == "POST":
        # Admite identificador y también username/email para formularios alternativos.
        identificador = (
            request.form.get("identificador")
            or request.form.get("username")
            or request.form.get("email")
            or ""
        ).strip()
        password = request.form.get("password", "")

        if not identificador or not password:
            flash("Introduce tu usuario o correo y tu contraseña.", "error")
            return render_template("login.html"), 400

        clave = obtener_clave_bloqueo(identificador)
        bloqueado, _ = comprobar_bloqueo(clave)
        if bloqueado:
            flash(
                "Has alcanzado el límite de intentos. Inténtalo nuevamente después de 30 minutos.",
                "error"
            )
            return render_template("login.html"), 429

        normalizado = " ".join(identificador.split()).casefold()
        usuario = db.session.scalar(select(User).where(or_(
            func.lower(User.email) == normalizado,
            func.lower(User.username) == normalizado
        )))

        if usuario is None or not usuario.check_password(password):
            if registrar_fallo_login(clave):
                flash(
                    "Has realizado cinco intentos incorrectos. Acceso bloqueado durante 30 minutos.",
                    "error"
                )
                return render_template("login.html"), 429
            flash("Usuario/correo o contraseña incorrectos.", "error")
            return render_template("login.html"), 401

        reiniciar_intentos_login(clave)
        correo = (usuario.email or "").strip().lower()

        # Solo la cuenta cuyo correo coincide con ADMIN_EMAIL puede ser admin.
        if correo == ADMIN_EMAIL:
            if usuario.rol != "admin":
                usuario.rol = "admin"
                db.session.commit()
        elif usuario.rol == "admin":
            usuario.rol = "user"
            db.session.commit()

        session.clear()
        login_user(usuario, remember=False)
        session.permanent = True

        if correo == ADMIN_EMAIL:
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
        username = " ".join(request.form.get("username", "").split()).casefold()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip() or None
        password = request.form.get("password", "")
        confirm_password = (
            request.form.get("confirm_password")
            or request.form.get("confirmPassword")
            or request.form.get("password_confirm")
            or ""
        )

        if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,80}", username):
            flash("El usuario debe tener entre 3 y 80 caracteres válidos.", "error")
        elif len(email) > 255 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Introduce un correo válido.", "error")
        elif not 12 <= len(password) <= 128:
            flash("La contraseña debe tener entre 12 y 128 caracteres.", "error")
        elif password != confirm_password:
            flash("Las contraseñas no coinciden.", "error")
        elif phone and (
            len(phone) > 20 or not re.fullmatch(r"[0-9+(). -]{7,20}", phone)
        ):
            flash("Introduce un teléfono válido.", "error")
        else:
            usuario = User(
                username=username, email=email, phone=phone,
                rol="admin" if email == ADMIN_EMAIL else "user"
            )
            try:
                usuario.set_password(password)
                db.session.add(usuario)
                db.session.commit()
                session.clear()
                login_user(usuario, remember=False)
                session.permanent = True
                if usuario.rol == "admin":
                    return redirect(url_for("admin"))
                return redirect(url_for("index"))
            except IntegrityError:
                db.session.rollback()
                flash("El usuario, correo o teléfono ya está registrado.", "error")
            except Exception:
                db.session.rollback()
                app.logger.exception("Error al registrar usuario")
                flash("No se pudo crear la cuenta. Inténtalo de nuevo.", "error")

    return render_template("registrarse.html")


@app.route("/cerrar_sesion", methods=["POST"])
@login_required
def cerrar_sesion():
    logout_user()
    session.clear()
    return redirect(url_for("index"))


@app.route("/comprar")
def comprar():
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=url_for("comprar")))
    return render_template("comprar.html")


# ============================================================
# CUPONES Y FUNCIONES HEREDADAS
# ============================================================

def crrear_cupones():
    """
    Genera un cupón en memoria. La tabla/columnas de cupones no estaban
    definidas en el código recibido, por lo que no inventa un INSERT.
    """
    primer_digito = secrets.choice("123456789")
    resto = "".join(secrets.choice("0123456789") for _ in range(31))
    codigo_cupon = primer_digito + resto
    numero_categoria = random.randint(1, 7)
    descuento = random.choice([5, 10.15, 20])
    return {
        "codigo_cupon": codigo_cupon,
        "numero_categoria": numero_categoria,
        "descuento": descuento,
        "cobrado": False
    }


def conocer_categoria(numero_categoria):
    categorias = {
        1: "Mariposas", 2: "Escarabajos", 3: "Odonatos",
        4: "Cuarzos", 5: "Minerales", 6: "Fosiles"
    }
    return categorias.get(numero_categoria, "todos")


def imprimir_codigoqr(codigo_cupon):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )
    qr.add_data(codigo_cupon)
    qr.make(fit=True)
    imagen = qr.make_image(fill_color="black", back_color="white")
    imagen.save("codigo_qr.png")
    return "codigo_qr.png"


def compra(*args, **kwargs):
    """
    Punto de compatibilidad para la función antigua incompleta.
    La implementación de compras real está en crear_pedido() y
    registrar_venta_caja(), que gestionan stock y transacciones.
    """
    app.logger.warning(
        "Se llamó a compra(), función heredada sin parámetros definidos. "
        "Usa el endpoint de pedidos o caja."
    )
    return None


# ============================================================
# CHATBOT
# ============================================================

@app.route("/chatbox")
def chatbox():
    return render_template("chatmenu.html")


@app.route("/api/chat", methods=["POST"])
@limiter.limit("20 per minute")
def api_chat():
    if client is None:
        return jsonify({
            "error": "El chatbot no está configurado. Añade OPENAI_API_KEY al archivo .env."
        }), 503

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify({"error": "La petición JSON no es válida."}), 400

    mensaje = datos.get("mensaje", "")
    if not isinstance(mensaje, str):
        return jsonify({"error": "El mensaje debe ser texto."}), 400
    mensaje = mensaje.strip()
    if not mensaje:
        return jsonify({"error": "El mensaje está vacío."}), 400
    if len(mensaje) > 4000:
        return jsonify({"error": "El mensaje supera el límite de 4000 caracteres."}), 400

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
            input=mensaje
        )
        respuesta = (response.output_text or "").strip()
        if not respuesta:
            respuesta = "No pude generar una respuesta. Inténtalo de nuevo."
        return jsonify({"respuesta": respuesta})
    except Exception:
        app.logger.exception("Error del chatbot")
        return jsonify({
            "error": "Ocurrió un error al procesar el mensaje. Inténtalo de nuevo."
        }), 502


# ============================================================
# HERRAMIENTAS IA
# ============================================================

def herramienta_ia_buscarproductos(texto):
    return buscar_productos(str(texto or "").strip()[:200])


# ============================================================
# ARRANQUE
# ============================================================

def preparar_servidor():
    """Inicializa tablas y migración una sola vez, sin borrar la base."""
    inicializar_base_datos()
    migrar_usuarios_password()
    crear_tabla_productos()


if __name__ == "__main__":
    preparar_servidor()
    modo_debug = os.getenv("FLASK_DEBUG", "false").lower() in {
        "1", "true", "yes", "on"
    }
    app.run(
        debug=modo_debug,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000"))
    )
