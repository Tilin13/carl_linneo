import secrets
import qrcode
import hashlib
import hmac
import logging
import math
import os
import re
from io import BytesIO
import base64
import secrets
from sqlalchemy import inspect, text
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_user,
    logout_user,
    login_required,
)
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
from datetime import timezone

def convertir_fecha_utc(valor):

    fecha = datetime.fromisoformat(
        valor.replace("Z", "+00:00")
    )

    if fecha.tzinfo is None:
        raise ValueError(
            "La fecha debe incluir una zona horaria."
        )

    return fecha.astimezone(
        timezone.utc
    ).replace(tzinfo=None)
# ============================================================
# CONFIGURACIÓN Y RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_DATOS = BASE_DIR / "pos.db"
FRONTEND_DIR = BASE_DIR / "frontend"
IMAGENES_DIR = BASE_DIR / "imagenes"
app = Flask(
    __name__,
    template_folder=str(FRONTEND_DIR),
    static_folder=str(FRONTEND_DIR),
    static_url_path="",
)

secret_key = os.getenv("SECRET_KEY", "").strip()
api_key = os.getenv("OPENAI_API_KEY", "").strip()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "").strip()

if not ADMIN_USER_ID.isdigit() or int(ADMIN_USER_ID) <= 0:
    raise RuntimeError(
        "Debes configurar ADMIN_USER_ID con el ID "
        "de tu cuenta administrativa."
    )

ADMIN_USER_ID = int(ADMIN_USER_ID)
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


_secure_env = os.getenv("COOKIE_SECURE")


ENTORNO = os.getenv("APP_ENV", "development").strip().lower()

if ENTORNO not in ("development", "production"):
    raise RuntimeError("APP_ENV no es válido.")

if ENTORNO == "production":
    if os.getenv("COOKIE_SECURE", "").lower() not in (
        "1", "true", "yes", "on"
    ):
        raise RuntimeError(
            "En producción COOKIE_SECURE debe estar activado."
        )

cookie_secure = ENTORNO == "production"

app.config.update(
    SECRET_KEY=secret_key,

    SESSION_COOKIE_SECURE=cookie_secure,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_NAME="linneo_session",

    PERMANENT_SESSION_LIFETIME=1800,
    SESSION_REFRESH_EACH_REQUEST=False,

    WTF_CSRF_ENABLED=True,
    WTF_CSRF_TIME_LIMIT=3600,

    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
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
    storage_uri=os.getenv(
        "RATELIMIT_STORAGE_URI",
        "memory://"
    ),
    strategy="fixed-window",
    headers_enabled=True,
)

# ============================================================
# MODELOS SQLALCHEMY
# ============================================================
class Promocion(db.Model):

    __tablename__ = "promociones"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    producto_codigo = db.Column(
        db.String(80),
        nullable=False,
        index=True
    )

    descuento = db.Column(
        db.Numeric(5, 2),
        nullable=False
    )

    fecha_inicio = db.Column(
        db.DateTime,
        nullable=False
    )

    fecha_fin = db.Column(
        db.DateTime,
        nullable=False
    )

    activa = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


def obtener_promocion(codigo):

    ahora = datetime.utcnow()

    promocion = db.session.execute(
        select(Promocion).where(
            Promocion.producto_codigo == codigo,
            Promocion.activa.is_(True),
            Promocion.fecha_inicio <= ahora,
            Promocion.fecha_fin > ahora
        ).order_by(
            Promocion.fecha_creacion.desc()
        )
    ).scalars().first()

    return promocion


def calcular_precio_promocional(precio, descuento):

    precio = Decimal(str(precio))
    descuento = Decimal(str(descuento))

    rebaja = (
        precio * descuento / Decimal("100")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    return (precio - rebaja).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )
class User(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(20),
        unique=True,
        nullable=True
    )

    password = db.Column(
        "password_hash",
        db.String(255),
        nullable=False
    )

    rol = db.Column(
        db.String(10),
        nullable=False,
        default="user"
    )

    pedidos = db.relationship(
        "Pedido",
        back_populates="usuario",
        cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        if not self.password:
            return False

        return check_password_hash(
            self.password,
            password
        )
    
def comprobar_administrador():

    with app.app_context():

        administrador = db.session.scalar(
            select(User).where(
                User.id == ADMIN_USER_ID,
                User.rol == "admin"
            )
        )

        if administrador:
            print(
                "Administrador encontrado:",
                administrador.id
            )
        else:
            print(
                "ERROR: No se encontró el administrador "
                "configurado en ADMIN_USER_ID."
            )
class LoginLock(db.Model):
    __tablename__ = "login_locks"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    lock_key = db.Column(
        db.String(64),
        unique=True,
        nullable=False
    )

    intentos = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    bloqueado_hasta = db.Column(
        db.DateTime,
        nullable=True
    )
    
from datetime import datetime, timedelta, timezone
import hashlib


MAX_INTENTOS_LOGIN = 5
DURACION_BLOQUEO = timedelta(minutes=30)


def obtener_clave_bloqueo(identificador):

    identificador = " ".join(
        identificador.split()
    ).casefold()

    ip = get_remote_address() or "desconocida"

    contenido = f"{identificador}|{ip}"

    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()


def comprobar_bloqueo(clave):

    registro = db.session.scalar(
        select(LoginLock).where(
            LoginLock.lock_key == clave
        )
    )

    if registro is None:
        return False, None

    ahora = datetime.now(timezone.utc)

    if registro.bloqueado_hasta is None:
        return False, registro

    bloqueado_hasta = (
        registro.bloqueado_hasta.replace(
            tzinfo=timezone.utc
        )
    )

    if ahora < bloqueado_hasta:
        return True, registro

    registro.intentos = 0
    registro.bloqueado_hasta = None

    db.session.commit()

    return False, registro

def registrar_fallo_login(clave):

    registro = db.session.scalar(
        select(LoginLock).where(
            LoginLock.lock_key == clave
        )
    )

    if registro is None:

        registro = LoginLock(
            lock_key=clave,
            intentos=0
        )

        db.session.add(registro)

    registro.intentos += 1

    if registro.intentos >= MAX_INTENTOS_LOGIN:

        registro.bloqueado_hasta = (
            datetime.now(timezone.utc)
            + DURACION_BLOQUEO
        )

        db.session.commit()

        return True

    db.session.commit()

    return False


def reiniciar_intentos_login(clave):

    registro = db.session.scalar(
        select(LoginLock).where(
            LoginLock.lock_key == clave
        )
    )

    if registro:

        registro.intentos = 0
        registro.bloqueado_hasta = None

        db.session.commit()

class Pedido(db.Model):
    __tablename__ = "pedidos"

    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )

    fecha = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    descuento = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    total = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    metodo_pago = db.Column(
        db.String(30),
        nullable=False,
        default="efectivo"
    )

    estado = db.Column(
        db.String(30),
        nullable=False,
        default="Pendiente"
    )

    usuario = db.relationship(
        "User",
        back_populates="pedidos"
    )

    productos = db.relationship(
        "PedidoItem",
        back_populates="pedido",
        cascade="all, delete-orphan"
    )

def migrar_usuarios_password():
    """
    Comprueba y repara las columnas básicas de usuarios.
    Conserva los hashes existentes y los datos de otras tablas.
    """
    BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(BASE_DATOS, timeout=20)

    try:
        conexion.execute("PRAGMA busy_timeout = 20000")

        existe = conexion.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'usuarios'
        """).fetchone()

        if not existe:
            raise RuntimeError(
                "La tabla usuarios no existe. "
                "Debe crearse mediante SQLAlchemy."
            )

        columnas = {
            fila[1]
            for fila in conexion.execute(
                "PRAGMA table_info(usuarios)"
            ).fetchall()
        }

        # Recuperar primero los hashes antiguos.
        if "password_hash" in columnas and "password" not in columnas:
            conexion.execute("""
                ALTER TABLE usuarios
                ADD COLUMN password VARCHAR(255)
            """)

            columnas.add("password")

        elif "password" not in columnas:
            conexion.execute("""
                ALTER TABLE usuarios
                ADD COLUMN password VARCHAR(255)
            """)

            columnas.add("password")

        if "password_hash" in columnas:
            conexion.execute("""
                UPDATE usuarios
                SET password = password_hash
                WHERE (password IS NULL OR password = '')
                  AND password_hash IS NOT NULL
            """)

        # Añadir columnas opcionales que puedan faltar.
        columnas_adicionales = {
            "phone": "VARCHAR(20)",
            "rol": "VARCHAR(10) NOT NULL DEFAULT 'user'",
        }

        for nombre, definicion in columnas_adicionales.items():
            if nombre not in columnas:
                conexion.execute(
                    f"ALTER TABLE usuarios "
                    f"ADD COLUMN {nombre} {definicion}"
                )

        conexion.commit()

        print("Estructura de usuarios comprobada.")

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()


class PedidoItem(db.Model):
    __tablename__ = "pedido_items"

    id = db.Column(db.Integer, primary_key=True)

    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedidos.id"),
        nullable=False,
        index=True
    )

    producto_codigo = db.Column(
        db.String(80),
        nullable=False
    )

    nombre = db.Column(
        db.String(200),
        nullable=False
    )

    cantidad = db.Column(
        db.Integer,
        nullable=False
    )

    precio_unitario = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    # AGREGA ESTA COLUMNA
    costo_unitario = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    total = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    pedido = db.relationship(
        "Pedido",
        back_populates="productos"
    )
# ============================================================
# CAJA: VENTAS FISICAS Y DIGITALES
# ============================================================
def migrar_descuento_pedidos():
    conexion = sqlite3.connect(BASE_DATOS, timeout=20)
    try:
        columnas = {
            fila[1]
            for fila in conexion.execute(
                "PRAGMA table_info(pedidos)"
            ).fetchall()
        }

        if "descuento" not in columnas:
            conexion.execute("""
                ALTER TABLE pedidos
                ADD COLUMN descuento NUMERIC(10, 2) NOT NULL DEFAULT 0
            """)

        conexion.commit()
    finally:
        conexion.close()
def migrar_costos_historicos():

    conexion = sqlite3.connect(BASE_DATOS, timeout=20)

    try:
        for tabla in ("ventas_caja_items", "pedido_items"):

            columnas = {
                fila[1]
                for fila in conexion.execute(
                    f"PRAGMA table_info({tabla})"
                ).fetchall()
            }

            if "costo_unitario" not in columnas:
                conexion.execute(f"""
                    ALTER TABLE {tabla}
                    ADD COLUMN costo_unitario NUMERIC(10, 2)
                """)

        conexion.commit()

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()
def registrar_items_venta(venta, productos_solicitados):
    """
    Registra los artículos de una venta y guarda el costo histórico
    de cada producto para calcular correctamente las ganancias.

    venta: objeto VentaCaja ya creado.
    productos_solicitados: lista de diccionarios con:
        - producto_id
        - cantidad
        - precio (opcional)
    """

    from decimal import Decimal, ROUND_HALF_UP

    total_venta = Decimal("0.00")
    total_costo = Decimal("0.00")

    for item in productos_solicitados:
        producto_id = item.get("producto_id")
        cantidad = int(item.get("cantidad", 0))

        if not producto_id or cantidad <= 0:
            raise ValueError("Producto o cantidad inválida.")

        producto = db.session.execute(
            text("""
                SELECT
                    id,
                    nombre,
                    precio_compra,
                    precio_manofactura,
                    precio_venta,
                    stock
                FROM productos
                WHERE id = :producto_id
            """),
            {"producto_id": producto_id}
        ).mappings().first()

        if not producto:
            raise ValueError(
                f"No se encontró el producto con ID {producto_id}."
            )

        stock_actual = int(producto["stock"] or 0)

        if stock_actual < cantidad:
            raise ValueError(
                f"Stock insuficiente para {producto['nombre']}. "
                f"Disponible: {stock_actual}."
            )

        precio_unitario = Decimal(
            str(item.get("precio", producto["precio_venta"] or 0))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        costo_compra = Decimal(
            str(producto["precio_compra"] or 0)
        )

        costo_fabricacion = Decimal(
            str(producto["precio_manofactura"] or 0)
        )

        costo_unitario = (
            costo_compra + costo_fabricacion
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        subtotal = (
            precio_unitario * cantidad
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        costo_total_item = (
            costo_unitario * cantidad
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        detalle = VentaCajaItem(
            venta_id=venta.id,
            producto_id=producto["id"],
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            costo_unitario=costo_unitario
        )

        db.session.add(detalle)

        # Descontar existencias
        db.session.execute(
            text("""
                UPDATE productos
                SET stock = stock - :cantidad
                WHERE id = :producto_id
            """),
            {
                "cantidad": cantidad,
                "producto_id": producto_id
            }
        )

        total_venta += subtotal
        total_costo += costo_total_item

    return {
        "total": total_venta.quantize(Decimal("0.01")),
        "costo": total_costo.quantize(Decimal("0.01")),
        "ganancia": (total_venta - total_costo).quantize(
            Decimal("0.01")
        )
    }
    

class Cupon(db.Model):

    __tablename__ = "cupones"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    codigo_cupon = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        index=True
    )

    descuento = db.Column(
        db.Numeric(5, 2),
        nullable=False
    )

    categoria = db.Column(
        db.String(100),
        nullable=False
    )

    activo = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    utilizado = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=True
    )

    pedido_id = db.Column(
        db.Integer,
        db.ForeignKey("pedidos.id"),
        nullable=True
    )

    fecha_creacion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    fecha_uso = db.Column(
        db.DateTime,
        nullable=True
    )


class VentaCaja(db.Model):
    __tablename__ = "ventas_caja"

    id = db.Column(db.Integer, primary_key=True)

    # Comprador registrado: opcional.
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=True,
        index=True
    )
    comprador_externo_id = db.Column(
        db.Integer,
        db.ForeignKey("compradores_externos.id"),
        nullable=True,
        index=True
    )    

    # Datos del comprador conservados como historial.
    comprador_nombre = db.Column(
        db.String(150),
        nullable=False
    )

    comprador_contacto = db.Column(
        db.String(255),
        nullable=True
    )

    # Canal de venta: fisico o digital.
    canal = db.Column(
        db.String(20),
        nullable=False
    )

    fecha = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    subtotal = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    descuento = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        default=0
    )

    total = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    metodo_pago = db.Column(
        db.String(30),
        nullable=False
    )

    estado_pago = db.Column(
        db.String(20),
        nullable=False,
        default="pagado"
    )

    # Relaciones.
    usuario = db.relationship("User")

    productos = db.relationship(
        "VentaCajaItem",
        back_populates="venta",
        cascade="all, delete-orphan"
    )

class VentaCajaItem(db.Model):
    __tablename__ = "ventas_caja_items"

    id = db.Column(db.Integer, primary_key=True)

    venta_id = db.Column(
        db.Integer,
        db.ForeignKey("ventas_caja.id"),
        nullable=False
    )

    producto_codigo = db.Column(
        db.String(80),
        nullable=False
    )

    nombre = db.Column(
        db.String(200),
        nullable=False
    )

    cantidad = db.Column(
        db.Integer,
        nullable=False
    )

    precio_unitario = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    costo_unitario = db.Column(
        db.Numeric(10, 2),
        nullable=True
    )

    total = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    venta = db.relationship(
        "VentaCaja",
        back_populates="productos"
    )
class CompradorExterno(db.Model):
    __tablename__ = "compradores_externos"

    id = db.Column(db.Integer, primary_key=True)

    nombre = db.Column(
        db.String(150),
        nullable=False
    )

    contacto = db.Column(
        db.String(255),
        nullable=True
    )

    fecha_registro = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    ventas = db.relationship(
        "VentaCaja",
        backref="comprador_externo",
        lazy=True
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

def inicializar_base_datos():

    BASE_DATOS.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with app.app_context():
        db.create_all()
def comprobar_tablas():
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)

    try:
        tablas = conexion.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """).fetchall()

        print("Tablas encontradas:")
        for tabla in tablas:
            print("-", tabla[0])

        if conexion.execute("""
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'productos'
        """).fetchone() is None:
            print("ERROR: No existe la tabla productos.")
        else:
            columnas = conexion.execute(
                "PRAGMA table_info(productos)"
            ).fetchall()

            print("Columnas de productos:")
            for columna in columnas:
                print(columna[1], columna[2])

    finally:
        conexion.close()

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None

def crear_tabla_productos():
    BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(BASE_DATOS, timeout=10)

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
    """Permite el acceso únicamente al administrador autorizado."""

    @wraps(func)
    @login_required
    def decorada(*args, **kwargs):

        usuario_autorizado = (
            current_user.is_authenticated
            and current_user.id == ADMIN_USER_ID
            and current_user.rol == "admin"
        )

        if not usuario_autorizado:
            if request.path.startswith("/api/"):
                return jsonify({
                    "error": "No tienes permisos para esta operación."
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

    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

    response.headers["Cross-Origin-Resource-Policy"] = (
        "same-origin"
    )

    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

    response.headers["Cache-Control"] = (
        "no-store"
        if request.path.startswith("/api/")
        or current_user.is_authenticated
        else "no-cache"
    )

    if request.is_secure and ENTORNO == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000"
        )

    return response

# ============================================================
# ERRORES HTTP
# ============================================================
@app.route("/caja")
@administrador_requerido
def caja():
    return render_template("caja.html")

# ============================================================
# REGISTRAR VENTAS EN CAJA
# ============================================================
@app.route("/admin/finanzas")
@administrador_requerido
def admin_finanzas():
    return render_template("finanzas.html")

@app.route(
    "/api/admin/caja/compradores-externos",
    methods=["GET"]
)
@administrador_requerido
def listar_compradores_externos():

    try:
        compradores = db.session.scalars(
            select(CompradorExterno).order_by(
                CompradorExterno.nombre.asc()
            )
        ).all()

        return jsonify([
            {
                "id": comprador.id,
                "nombre": comprador.nombre,
                "contacto": comprador.contacto or ""
            }
            for comprador in compradores
        ])

    except Exception:
        db.session.rollback()
        app.logger.exception(
            "Error consultando compradores externos."
        )

        return jsonify({
            "error": "No se pudieron cargar los compradores."
        }), 500
def migrar_metodo_pago_pedidos():
    inspector = inspect(db.engine)

    columnas = {
        columna["name"]
        for columna in inspector.get_columns("pedidos")
    }

    if "metodo_pago" not in columnas:
        with db.engine.begin() as conexion:
            conexion.execute(text("""
                ALTER TABLE pedidos
                ADD COLUMN metodo_pago VARCHAR(50)
            """))

        app.logger.info(
            "Migración aplicada: pedidos.metodo_pago"
        )
  
@app.route(
    "/api/admin/promociones",
    methods=["POST"]
)
@administrador_requerido
def crear_promocion():

    try:

        datos = request.get_json(silent=True) or {}

        codigo = str(
            datos.get("codigo", "")
        ).strip()

        descuento = Decimal(
            str(datos.get("descuento", "0"))
        )

        inicio = convertir_fecha_utc(
            datos.get("inicio", "")
        )

        fin = convertir_fecha_utc(
            datos.get("fin", "")
        )

        if not codigo:

            raise ValueError(
                "Debes indicar el código del producto."
            )

        if not descuento.is_finite() or not (
            Decimal("1") <= descuento <= Decimal("90")
        ):

            raise ValueError(
                "El descuento debe estar entre 1 y 90."
            )

        if inicio >= fin:

            raise ValueError(
                "La fecha final debe ser posterior al inicio."
            )

        producto = db.session.execute(
            text("""
                SELECT codigo
                FROM productos
                WHERE codigo = :codigo
            """),
            {"codigo": codigo}
        ).first()

        if producto is None:

            raise ValueError(
                "El producto no existe."
            )

        promocion = Promocion(
            producto_codigo=codigo,
            descuento=descuento,
            fecha_inicio=inicio,
            fecha_fin=fin,
            activa=True
        )

        db.session.add(promocion)
        db.session.commit()

        return jsonify({
            "mensaje": "Promoción creada correctamente.",
            "id": promocion.id
        }), 201

    except (ValueError, TypeError, InvalidOperation) as error:

        db.session.rollback()

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Error creando promoción."
        )

        return jsonify({
            "error": "No se pudo crear la promoción."
        }), 500
        
@app.route("/promociones")
def promociones_pagina():
	return render_template("promociones.html")
@app.route(
    "/api/promociones",
    methods=["GET"]
)
def promociones_publicas():

    try:

        ahora = datetime.utcnow()

        promociones = db.session.scalars(
            select(Promocion).where(
                Promocion.activa.is_(True),
                Promocion.fecha_inicio <= ahora,
                Promocion.fecha_fin > ahora
            )
        ).all()

        resultado = []

        for promocion in promociones:

            producto = db.session.execute(
                text("""
                    SELECT
                        codigo,
                        nombre,
                        categoria,
                        precio_venta,
                        stock
                    FROM productos
                    WHERE codigo = :codigo
                """),
                {"codigo": promocion.producto_codigo}
            ).mappings().first()

            if not producto:
                continue

            if int(producto["stock"] or 0) <= 0:
                continue

            precio_original = Decimal(
                str(producto["precio_venta"])
            )

            precio_oferta = calcular_precio_promocional(
                precio_original,
                promocion.descuento
            )

            resultado.append({

                "codigo": producto["codigo"],

                "nombre": producto["nombre"],

                "categoria": producto["categoria"],

                "precio_original": str(precio_original),

                "precio_oferta": str(precio_oferta),

                "descuento": str(promocion.descuento),

                "stock": producto["stock"]

            })

        return jsonify(resultado)

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Error cargando promociones públicas."
        )

        return jsonify({
            "error": "No se pudieron cargar las ofertas."
        }), 500
@app.route(
    "/api/admin/promociones/<int:promocion_id>",
    methods=["DELETE"]
)
@administrador_requerido
def eliminar_promocion(promocion_id):

    try:

        promocion = db.session.get(
            Promocion,
            promocion_id
        )

        if promocion is None:

            return jsonify({
                "error": "La promoción no existe."
            }), 404

        db.session.delete(promocion)
        db.session.commit()

        return jsonify({
            "mensaje": "Promoción eliminada."
        })

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Error eliminando promoción."
        )

        return jsonify({
            "error": "No se pudo eliminar la promoción."
        }), 500        
@app.route(
    "/api/admin/promociones",
    methods=["GET"]
)
@administrador_requerido
def listar_promociones_admin():

    try:

        promociones = db.session.scalars(
            select(Promocion).order_by(
                Promocion.fecha_creacion.desc()
            )
        ).all()

        resultado = []

        for promo in promociones:

            producto = db.session.execute(
                text("""
                    SELECT nombre
                    FROM productos
                    WHERE codigo = :codigo
                """),
                {"codigo": promo.producto_codigo}
            ).first()

            resultado.append({
                "id": promo.id,
                "producto_codigo": promo.producto_codigo,
                "nombre": producto[0] if producto else promo.producto_codigo,
                "descuento": str(promo.descuento),
                "fecha_inicio": promo.fecha_inicio.isoformat(),
                "fecha_fin": promo.fecha_fin.isoformat()
            })

        return jsonify(resultado)

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Error listando promociones."
        )

        return jsonify({
            "error": "No se pudieron consultar las promociones."
        }), 500
@app.route(
    "/api/admin/finanzas/ventas",
    methods=["GET"]
)
@administrador_requerido
def obtener_historial_ventas():

    try:
        ventas = db.session.scalars(
            select(VentaCaja).order_by(
                VentaCaja.fecha.desc()
            )
        ).all()

        pedidos = db.session.scalars(
            select(Pedido).order_by(
                Pedido.fecha.desc()
            )
        ).all()

        resultado = []

        ingresos = Decimal("0.00")
        costos = Decimal("0.00")
        pendientes = Decimal("0.00")

        for venta in ventas:

            detalles = []
            costo_venta = Decimal("0.00")

            for item in venta.productos:

                costo = (
                    item.costo_unitario
                    if item.costo_unitario is not None
                    else None
                )

                if costo is not None:
                    costo_venta += Decimal(str(costo)) * item.cantidad

                detalles.append({
                    "codigo": item.producto_codigo,
                    "producto": item.nombre,
                    "cantidad": item.cantidad,
                    "precio": str(item.precio_unitario),
                    "costo_unitario": (
                        str(costo) if costo is not None else None
                    ),
                    "total": str(item.total)
                })

            pagada = venta.estado_pago == "pagado"

            if pagada:
                ingresos += Decimal(str(venta.total))
                costos += costo_venta
            else:
                pendientes += Decimal(str(venta.total))

            resultado.append({
                "tipo": "venta_caja",
                "id": venta.id,
                "fecha": venta.fecha.isoformat(),
                "comprador": venta.comprador_nombre,
                "contacto": venta.comprador_contacto or "",
                "canal": venta.canal,
                "subtotal": str(venta.subtotal),
                "descuento": str(venta.descuento),
                "total": str(venta.total),
                "metodo_pago": venta.metodo_pago,
                "estado_pago": venta.estado_pago,
                "costo": str(costo_venta),
                "ganancia": (
                    str(Decimal(str(venta.total)) - costo_venta)
                    if pagada and all(
                        item.costo_unitario is not None
                        for item in venta.productos
                    )
                    else None
                ),
                "detalles": detalles
            })

        for pedido in pedidos:

            detalles = []
            costo_pedido = Decimal("0.00")

            for item in pedido.productos:

                costo = item.costo_unitario

                if costo is not None:
                    costo_pedido += (
                        Decimal(str(costo)) * item.cantidad
                    )

                detalles.append({
                    "codigo": item.producto_codigo,
                    "producto": item.nombre,
                    "cantidad": item.cantidad,
                    "precio": str(item.precio_unitario),
                    "costo_unitario": (
                        str(costo) if costo is not None else None
                    ),
                    "total": str(item.total)
                })

            pagado = pedido.estado.lower() == "pagado"

            if pagado:
                ingresos += Decimal(str(pedido.total))
                costos += costo_pedido
            else:
                pendientes += Decimal(str(pedido.total))

            resultado.append({
                "tipo": "pedido",
                "id": pedido.id,
                "fecha": pedido.fecha.isoformat(),
                "comprador": (
                    pedido.usuario.username
                    if pedido.usuario else "Desconocido"
                ),
                "contacto": (
                    pedido.usuario.email
                    if pedido.usuario else ""
                ),
                "canal": "digital",
                "subtotal": str(pedido.subtotal),
                "descuento": str(pedido.descuento),
                "total": str(pedido.total),
                "metodo_pago": pedido.metodo_pago,
                "estado_pago": pedido.estado,
                "costo": str(costo_pedido),
                "ganancia": (
                    str(Decimal(str(pedido.total)) - costo_pedido)
                    if pagado and all(
                        item.costo_unitario is not None
                        for item in pedido.productos
                    )
                    else None
                ),
                "detalles": detalles
            })

        resultado.sort(
            key=lambda x: x["fecha"],
            reverse=True
        )

        ganancia = ingresos - costos

        return jsonify({
            "ventas": resultado,
            "resumen": {
                "ingresos": str(ingresos),
                "costos": str(costos),
                "ganancia_bruta": str(ganancia),
                "perdida": str(max(Decimal("0"), -ganancia)),
                "pendiente_cobro": str(pendientes),
                "operaciones": len(resultado)
            }
        })

    except Exception:
        db.session.rollback()

        app.logger.exception(
            "Error consultando el historial financiero."
        )

        return jsonify({
            "error": "No se pudo cargar el historial financiero."
        }), 500

@app.route("/api/admin/caja/venta", methods=["POST"])
@administrador_requerido
def registrar_venta_caja():

    try:
        datos = request.get_json(silent=True) or {}

        items = datos.get("productos", [])
        metodo_pago = datos.get("metodo_pago", "")
        canal = datos.get("canal", "")
        estado_pago = datos.get("estado_pago", "pagado")

        usuario_id = datos.get("usuario_id")
        comprador_nombre = str(
            datos.get("comprador_nombre") or ""
        ).strip()

        comprador_contacto = str(
            datos.get("comprador_contacto") or ""
        ).strip()

        descuento_porcentaje = Decimal(
            str(datos.get("descuento", 0))
        )

        # --------------------------------
        # VALIDACIONES
        # --------------------------------

        if not isinstance(items, list) or not items:
            raise ValueError("Agrega al menos un producto.")

        if canal not in ("fisico", "digital"):
            raise ValueError("El canal de venta no es válido.")

        if metodo_pago not in (
            "efectivo",
            "tarjeta",
            "transferencia",
            "pago_en_linea"
        ):
            raise ValueError("El método de pago no es válido.")

        if estado_pago not in ("pagado", "pendiente"):
            raise ValueError("El estado de pago no es válido.")

        if not descuento_porcentaje.is_finite():
            raise ValueError("El descuento no es válido.")

        if descuento_porcentaje < 0 or descuento_porcentaje > 100:
            raise ValueError("El descuento debe estar entre 0 y 100.")

        # --------------------------------
        # VALIDAR COMPRADOR
        # --------------------------------

        comprador_externo_id = None

        if usuario_id is not None:

            try:
                usuario_id = int(usuario_id)
            except (ValueError, TypeError):
                raise ValueError("El comprador seleccionado no es válido.")

            if usuario_id <= 0:
                raise ValueError("El comprador seleccionado no es válido.")

            comprador = db.session.get(User, usuario_id)

            if comprador is None:
                raise ValueError("El comprador no existe.")

            comprador_nombre = comprador.username
            comprador_contacto = (
                comprador.email or comprador.phone or ""
            )

        else:

            if not comprador_nombre:
                raise ValueError("Debes indicar el nombre del comprador.")

            comprador_externo = CompradorExterno(
                nombre=comprador_nombre,
                contacto=comprador_contacto or None
            )

            db.session.add(comprador_externo)
            db.session.flush()

            comprador_externo_id = comprador_externo.id

        # --------------------------------
        # CALCULAR PRODUCTOS
        # --------------------------------

        subtotal_venta = Decimal("0.00")
        costo_venta = Decimal("0.00")
        detalles_venta = []

        for item in items:

            codigo = str(item.get("codigo", "")).strip()

            try:
                cantidad = int(item.get("cantidad", 0))
            except (ValueError, TypeError):
                raise ValueError("Cantidad de producto inválida.")

            if not codigo or cantidad <= 0:
                raise ValueError("Producto o cantidad inválida.")

            producto = db.session.execute(
                text("""
                    SELECT
                        codigo,
                        nombre,
                        precio_venta,
                        precio_compra,
                        precio_manofactura,
                        stock
                    FROM productos
                    WHERE codigo = :codigo
                """),
                {"codigo": codigo}
            ).mappings().first()

            if not producto:
                raise ValueError(
                    f"No existe el producto {codigo}."
                )

            stock = int(producto["stock"] or 0)

            if stock < cantidad:
                raise ValueError(
                    f"Stock insuficiente para {producto['nombre']}. "
                    f"Disponible: {stock}."
                )

            precio = Decimal(
                str(producto["precio_venta"] or 0)
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            costo = (
                Decimal(str(producto["precio_compra"] or 0))
                + Decimal(str(producto["precio_manofactura"] or 0))
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            total_item = (precio * cantidad).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            subtotal_venta += total_item
            costo_venta += costo * cantidad

            detalles_venta.append({
                "codigo": codigo,
                "nombre": producto["nombre"],
                "cantidad": cantidad,
                "precio": precio,
                "costo": costo,
                "total": total_item
            })

        # --------------------------------
        # CALCULAR DESCUENTO Y TOTAL
        # --------------------------------

        subtotal_venta = subtotal_venta.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        descuento_importe = (
            subtotal_venta * descuento_porcentaje / Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        total_final = subtotal_venta - descuento_importe

        costo_venta = costo_venta.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # --------------------------------
        # CREAR VENTA
        # --------------------------------

        venta = VentaCaja(
            usuario_id=usuario_id,
            comprador_externo_id=comprador_externo_id,
            comprador_nombre=comprador_nombre,
            comprador_contacto=comprador_contacto or None,
            canal=canal,
            subtotal=subtotal_venta,
            descuento=descuento_importe,
            total=total_final,
            metodo_pago=metodo_pago,
            estado_pago=estado_pago
        )

        db.session.add(venta)
        db.session.flush()

        # --------------------------------
        # GUARDAR DETALLES Y DESCONTAR STOCK
        # --------------------------------

        for detalle in detalles_venta:

            item_venta = VentaCajaItem(
                venta_id=venta.id,
                producto_codigo=detalle["codigo"],
                nombre=detalle["nombre"],
                cantidad=detalle["cantidad"],
                precio_unitario=detalle["precio"],
                costo_unitario=detalle["costo"],
                total=detalle["total"]
            )

            db.session.add(item_venta)

            resultado = db.session.execute(
                text("""
                    UPDATE productos
                    SET stock = stock - :cantidad
                    WHERE codigo = :codigo
                      AND stock >= :cantidad
                """),
                {
                    "cantidad": detalle["cantidad"],
                    "codigo": detalle["codigo"]
                }
            )

            if resultado.rowcount != 1:
                raise ValueError(
                    f"No se pudo actualizar el stock de "
                    f"{detalle['nombre']}."
                )

        # --------------------------------
        # CONFIRMAR TRANSACCIÓN
        # --------------------------------

        db.session.commit()

        ganancia = total_final - costo_venta

        return jsonify({
            "mensaje": "Venta registrada correctamente.",
            "venta_id": venta.id,
            "subtotal": float(subtotal_venta),
            "descuento": float(descuento_importe),
            "total": float(total_final),
            "costo_total": float(costo_venta),
            "ganancia": float(ganancia),
            "metodo_pago": metodo_pago
        }), 201

    except (ValueError, InvalidOperation) as e:

        db.session.rollback()

        return jsonify({
            "error": str(e)
        }), 400

    except SQLAlchemyError:

        db.session.rollback()

        app.logger.exception(
            "Error SQLAlchemy al registrar venta en caja."
        )

        return jsonify({
            "error": "Error de base de datos al registrar la venta."
        }), 500

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Error inesperado al registrar venta en caja."
        )

        return jsonify({
            "error": "Error inesperado al registrar la venta."
        }), 500


@app.route("/api/admin/caja/compradores", methods=["GET"])
@administrador_requerido
def caja_compradores():

    try:
        usuarios = db.session.scalars(
            select(User).order_by(User.username.asc())
        ).all()

        return jsonify([
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "phone": u.phone or ""
            }
            for u in usuarios
        ])

    except Exception:
        db.session.rollback()

        app.logger.exception(
            "Error cargando compradores de caja."
        )

        return jsonify({
            "error": "No se pudieron cargar los compradores."
        }), 500 
 
@app.route("/api/admin/caja/productos", methods=["GET"])
@administrador_requerido
def caja_productos():

    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row

    try:
        filas = conexion.execute("""
            SELECT
                codigo,
                nombre,
                categoria,
                precio_venta,
                stock
            FROM productos
            WHERE stock > 0
            ORDER BY nombre COLLATE NOCASE ASC
        """).fetchall()

        productos = [dict(fila) for fila in filas]

        return jsonify(productos), 200

    except sqlite3.Error:
        app.logger.exception(
            "Error cargando productos disponibles en caja."
        )

        return jsonify({
            "error": "No se pudieron cargar los productos."
        }), 500

    finally:
        conexion.close()

    
@app.route("/admin/pedido/<int:pedido_id>")
@administrador_requerido
def detalle_pedido_admin(pedido_id):

    pedido = db.session.get(Pedido, pedido_id)

    if pedido is None:
        abort(404)

    return render_template(
        "pedido.html",
        pedido=pedido
    )
 
def diagnosticar_usuarios():

    conexion = sqlite3.connect(
        BASE_DATOS,
        timeout=10
    )

    try:

        tablas = conexion.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
        """).fetchall()

        print("\n===== DIAGNÓSTICO USUARIOS =====")

        print("Base de datos:", BASE_DATOS)

        print("Tabla usuarios:",
              "usuarios" in [t[0] for t in tablas])

        columnas = conexion.execute(
            "PRAGMA table_info(usuarios)"
        ).fetchall()

        print("\nColumnas:")

        for columna in columnas:
            print(columna)

        print("\nÍndices:")

        indices = conexion.execute(
            "PRAGMA index_list(usuarios)"
        ).fetchall()

        for indice in indices:
            print(indice)

        print("\nUsuarios registrados:")

        usuarios = conexion.execute("""
            SELECT id, username, email, phone, rol,
                   CASE
                       WHEN password IS NULL THEN 'SIN PASSWORD'
                       ELSE 'CON PASSWORD'
                   END
            FROM usuarios
        """).fetchall()

        for usuario in usuarios:
            print(usuario)

        print("===== FIN DIAGNÓSTICO =====\n")

    finally:
        conexion.close() 
 
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


@app.route("/mi_cuenta")
@login_required
def mi_cuenta():

    pedidos = (
        Pedido.query
        .filter_by(usuario_id=current_user.id)
        .order_by(Pedido.fecha.desc())
        .all()
    )

    return render_template(
        "usuario.html",
        usuario=current_user,
        pedidos=pedidos
    )

def registrar_pedido(usuario_id, subtotal):

    pedido = Pedido(
        usuario_id=usuario_id,
        subtotal=subtotal,
        estado="Pendiente"
    )

    db.session.add(pedido)
    db.session.commit()

    return pedido

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

def generar_codigo_cupon():

    while True:

        codigo = secrets.token_urlsafe(24)

        existente = db.session.scalar(
            select(Cupon.id).where(
                Cupon.codigo_cupon == codigo
            )
        )

        if existente is None:
            return codigo


def crear_cupon_bd(descuento, categoria):

    codigo = generar_codigo_cupon()

    cupon = Cupon(
        codigo_cupon=codigo,
        descuento=descuento,
        categoria=categoria,
        activo=True,
        utilizado=False
    )

    db.session.add(cupon)

    db.session.flush()

    return cupon

			


def generar_qr_cupon(codigo):

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4
    )

    qr.add_data(codigo)
    qr.make(fit=True)

    imagen = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    buffer = BytesIO()

    imagen.save(buffer, format="PNG")

    buffer.seek(0)

    imagen_base64 = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    return imagen_base64


@app.route(
    "/api/admin/cupones",
    methods=["POST"]
)
@administrador_requerido
def crear_cupon_admin():

    try:

        datos = request.get_json(silent=True) or {}

        descuento = Decimal(
            str(datos.get("descuento", "0"))
        )

        categoria = str(
            datos.get("categoria", "")
        ).strip()

        if not descuento.is_finite() or not (
            Decimal("1") <= descuento <= Decimal("90")
        ):
            raise ValueError(
                "El descuento debe estar entre 1 y 90."
            )

        if not categoria or len(categoria) > 100:
            raise ValueError(
                "Selecciona una categoría válida."
            )

        existe_categoria = db.session.execute(
            text("""
                SELECT 1
                FROM productos
                WHERE categoria = :categoria
                LIMIT 1
            """),
            {"categoria": categoria}
        ).first()

        if not existe_categoria:
            raise ValueError(
                "La categoría no existe en el inventario."
            )

        cupon = crear_cupon_bd(
            descuento=descuento,
            categoria=categoria
        )

        qr = generar_qr_cupon(
            cupon.codigo_cupon
        )

        db.session.commit()

        return jsonify({
            "mensaje": "Cupón creado correctamente.",
            "id": cupon.id,
            "codigo": cupon.codigo_cupon,
            "descuento": str(cupon.descuento),
            "categoria": cupon.categoria,
            "qr": qr,
            "utilizado": False,
            "activo": True
        }), 201

    except (ValueError, TypeError, InvalidOperation) as error:

        db.session.rollback()

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Error creando cupón."
        )

        return jsonify({
            "error": "No se pudo crear el cupón."
        }), 500

@app.route(
    "/api/admin/cupones",
    methods=["GET"]
)
@administrador_requerido
def listar_cupones_admin():

    try:

        cupones = db.session.scalars(
            select(Cupon).order_by(
                Cupon.fecha_creacion.desc()
            )
        ).all()

        return jsonify([
            {
                "id": c.id,
                "codigo": c.codigo_cupon,
                "descuento": str(c.descuento),
                "categoria": c.categoria,
                "activo": c.activo,
                "utilizado": c.utilizado,
                "fecha_creacion": (
                    c.fecha_creacion.isoformat()
                ),
                "fecha_uso": (
                    c.fecha_uso.isoformat()
                    if c.fecha_uso else None
                )
            }
            for c in cupones
        ])

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Error consultando cupones."
        )

        return jsonify({
            "error": "No se pudieron consultar los cupones."
        }), 500
	


	
@app.route("/cambiar_telefono", methods=["POST"])
@login_required
def cambiar_telefono():
    nuevo_telefono = request.form.get("telefono", "").strip()

    if not nuevo_telefono:
        flash("Ingresa un número de teléfono válido.", "error")
        return redirect(url_for("mi_cuenta"))

    current_user.phone = nuevo_telefono
    db.session.commit()

    flash("Tu teléfono se actualizó correctamente.", "success")
    return redirect(url_for("mi_cuenta"))

@app.route("/cambiar_contrasena", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def cambiar_contrasena():

    password_actual = request.form.get(
        "password_actual", ""
    )

    password_nueva = request.form.get(
        "password_nueva", ""
    )

    confirmar_password = request.form.get(
        "confirmar_password", ""
    )

    # Comprobar la contraseña actual
    if not current_user.check_password(password_actual):
        flash("La contraseña actual es incorrecta.", "error")
        return redirect(url_for("mi_cuenta"))

    # Comprobar longitud
    if not 12 <= len(password_nueva) <= 128:
        flash(
            "La nueva contraseña debe tener entre 12 y 128 caracteres.",
            "error"
        )
        return redirect(url_for("mi_cuenta"))

    # Comprobar coincidencia
    if password_nueva != confirmar_password:
        flash("Las contraseñas nuevas no coinciden.", "error")
        return redirect(url_for("mi_cuenta"))

    # Evitar reutilizar la contraseña actual
    if password_actual == password_nueva:
        flash(
            "La nueva contraseña debe ser diferente.",
            "error"
        )
        return redirect(url_for("mi_cuenta"))

    # Guardar nueva contraseña
    current_user.set_password(password_nueva)

    db.session.commit()

    # Cerrar la sesión para volver a autenticar
    logout_user()
    session.clear()

    flash(
        "Contraseña actualizada. Inicia sesión nuevamente.",
        "success"
    )

    return redirect(url_for("login"))

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
def compra():
	cursor.execute("""
	UPDATE inventario: 
	""")
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

# ============================================================
# CHECKOUT: REGISTRAR UNA COMPRA
# ============================================================

@app.route("/api/pedidos", methods=["POST"])
@login_required
def crear_pedido():

    datos = request.get_json(silent=True)

    if not isinstance(datos, dict):
        return jsonify({
            "error": "Los datos de compra no son válidos."
        }), 400

    productos_solicitados = datos.get("productos")

    if (
        not isinstance(productos_solicitados, list)
        or not productos_solicitados
        or len(productos_solicitados) > 100
    ):
        return jsonify({
            "error": "El carrito está vacío o no es válido."
        }), 400

    # Agrupar productos repetidos.
    cantidades = {}

    for item in productos_solicitados:

        if not isinstance(item, dict):
            return jsonify({
                "error": "Producto no válido."
            }), 400

        codigo = str(item.get("id", "")).strip()
        cantidad = item.get("cantidad")

        if not codigo or len(codigo) > 80:
            return jsonify({
                "error": "Código de producto no válido."
            }), 400

        if (
            isinstance(cantidad, bool)
            or not isinstance(cantidad, int)
            or cantidad <= 0
            or cantidad > 10000
        ):
            return jsonify({
                "error": "Cantidad no válida."
            }), 400

        cantidades[codigo] = (
            cantidades.get(codigo, 0) + cantidad
        )

    if any(cantidad > 10000 for cantidad in cantidades.values()):
        return jsonify({
            "error": "La cantidad solicitada es demasiado grande."
        }), 400

    # Importes iniciales.
    subtotal = Decimal("0.00")
    descuento_total = Decimal("0.00")

    try:

        # Crear el pedido dentro de la transacción.
        pedido = Pedido(
            usuario_id=current_user.id,
            subtotal=Decimal("0.00"),
            descuento=Decimal("0.00"),
            total=Decimal("0.00"),
            estado="Pendiente",
            metodo_pago="efectivo"
        )

        db.session.add(pedido)
        db.session.flush()

        # Consultar cada producto directamente en la base de datos.
        for codigo, cantidad in cantidades.items():

            producto = db.session.execute(
                text("""
                    SELECT
                        codigo,
                        nombre,
                        precio_venta,
                        precio_compra,
                        precio_manofactura,
                        stock
                    FROM productos
                    WHERE codigo = :codigo
                """),
                {"codigo": codigo}
            ).mappings().first()

            if producto is None:
                raise ValueError(
                    f"El producto {codigo} ya no existe."
                )

            stock = int(producto["stock"] or 0)

            if stock < cantidad:
                raise ValueError(
                    f"No hay suficientes existencias de "
                    f"{producto['nombre']}."
                )

            # Precio original antes de promociones.
            precio_original = Decimal(
                str(producto["precio_venta"])
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            if (
                not precio_original.is_finite()
                or precio_original < 0
            ):
                raise ValueError(
                    f"El precio de {producto['nombre']} no es válido."
                )

            # Consultar promoción vigente.
            promocion = obtener_promocion(codigo)

            if promocion:
                precio = calcular_precio_promocional(
                    precio_original,
                    promocion.descuento
                )
            else:
                precio = precio_original

            precio = Decimal(str(precio)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            if (
                not precio.is_finite()
                or precio < 0
                or precio > precio_original
            ):
                raise ValueError(
                    f"El precio promocional de "
                    f"{producto['nombre']} no es válido."
                )

            # Calcular importes antes y después del descuento.
            total_original = (
                precio_original * cantidad
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            total_producto = (
                precio * cantidad
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            # Acumular el subtotal original y el ahorro.
            subtotal += total_original

            descuento_total += (
                total_original - total_producto
            )

            # Calcular costo histórico del producto.
            costo_compra = Decimal(
                str(producto["precio_compra"] or 0)
            )

            costo_manofactura = Decimal(
                str(producto["precio_manofactura"] or 0)
            )

            costo_unitario = (
                costo_compra + costo_manofactura
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            if (
                not costo_unitario.is_finite()
                or costo_unitario < 0
            ):
                raise ValueError(
                    f"El costo de {producto['nombre']} no es válido."
                )

            # Descontar stock de forma condicional.
            resultado = db.session.execute(
                text("""
                    UPDATE productos
                    SET stock = stock - :cantidad
                    WHERE codigo = :codigo
                    AND stock >= :cantidad
                """),
                {
                    "cantidad": cantidad,
                    "codigo": codigo
                }
            )

            if resultado.rowcount != 1:
                raise ValueError(
                    "El stock ha cambiado. Actualiza tu carrito."
                )

            # Guardar detalle de la compra.
            detalle = PedidoItem(
                pedido_id=pedido.id,
                producto_codigo=codigo,
                nombre=producto["nombre"],
                cantidad=cantidad,
                precio_unitario=precio,
                costo_unitario=costo_unitario,
                total=total_producto
            )

            db.session.add(detalle)

        # Redondear los importes finales.
        subtotal = subtotal.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        descuento_total = descuento_total.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        total_final = (
            subtotal - descuento_total
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # Guardar los importes definitivos del pedido.
        pedido.subtotal = subtotal
        pedido.descuento = descuento_total
        pedido.total = total_final

        # Confirmar pedido, detalles y stock juntos.
        db.session.commit()

        return jsonify({
            "mensaje": "Pedido realizado correctamente.",
            "pedido_id": pedido.id,
            "subtotal": str(pedido.subtotal),
            "descuento": str(pedido.descuento),
            "total": str(pedido.total),
            "url": url_for(
                "detalle_pedido",
                pedido_id=pedido.id
            )
        }), 201

    except ValueError as error:

        db.session.rollback()

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        app.logger.exception(
            "Error al procesar el pedido."
        )

        return jsonify({
            "error": "No se pudo procesar la compra."
        }), 500

# ============================================================
# DETALLES DE UN PEDIDO
# ============================================================

@app.route("/pedido/<int:pedido_id>")
@login_required
def detalle_pedido(pedido_id):

    pedido = Pedido.query.filter_by(
        id=pedido_id,
        usuario_id=current_user.id
    ).first_or_404()

    return render_template(
        "pedido.html",
        pedido=pedido
    )
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

def especies_disponibles():
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)
    conexion.row_factory = sqlite3.Row

    try:
        filas = conexion.execute("""
            SELECT codigo, nombre, categoria, stock
            FROM productos
            WHERE categoria IN (
                'Mariposas',
                'Escarabajos',
                'Odonatos'
            )
            AND stock > 0
            ORDER BY categoria, nombre COLLATE NOCASE
        """).fetchall()

        return [dict(fila) for fila in filas]

    finally:
        conexion.close()


@app.route("/pedido_personalizado")
def pedido_personalizado():

    return render_template(
        "pedidos_personalizados.html"
    
    )
@app.route("/crear_pedido")
def crear_pedido_p():
	especies = especies_disponibles()
	return render_template(
	"crear_pedido.html",
	especies=especies
	)

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
@limiter.limit("5 per minute", methods=["POST"])
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

        password = request.form.get(
            "password", ""
        )

        if not identificador or not password:

            flash(
                "Introduce tu usuario o correo y tu contraseña.",
                "error"
            )

            return render_template("login.html"), 400

        clave = obtener_clave_bloqueo(identificador)

        bloqueado, registro = comprobar_bloqueo(clave)

        if bloqueado:

            flash(
                "Has alcanzado el límite de intentos. "
                "Inténtalo nuevamente después de 30 minutos.",
                "error"
            )

            return render_template("login.html"), 429

        identificador_normalizado = (
            " ".join(identificador.split()).casefold()
        )

        usuario = db.session.scalar(
            select(User).where(
                or_(
                    func.lower(User.email)
                    == identificador_normalizado,

                    func.lower(User.username)
                    == identificador_normalizado
                )
            )
        )

        if (
            usuario is None
            or not usuario.check_password(password)
        ):

            bloqueado = registrar_fallo_login(clave)

            if bloqueado:

                flash(
                    "Has realizado cinco intentos "
                    "incorrectos. Acceso bloqueado durante 30 minutos.",
                    "error"
                )

                return render_template("login.html"), 429

            flash(
                "Usuario/correo o contraseña incorrectos.",
                "error"
            )

            return render_template("login.html"), 401

        reiniciar_intentos_login(clave)

        # Limpiar la sesión anterior
        session.clear()

        # Iniciar sesión sin modificar el rol
        login_user(
            usuario,
            remember=False
        )

        session.permanent = True

        # Comprobar el rol y el correo del administrador
        if (
            usuario.rol == "admin"
            and (usuario.email or "").strip().lower()
            == ADMIN_EMAIL.strip().lower()
        ):
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
        username = " ".join(
            request.form.get("username", "").split()
        ).casefold()

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
                session.clear()

                login_user(usuario, remember=False)

                session.permanent = True

                return redirect(url_for("index"))

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
def migrar_columnas_pedidos():
    conexion = sqlite3.connect(BASE_DATOS, timeout=20)

    try:
        columnas = {
            fila[1]
            for fila in conexion.execute(
                "PRAGMA table_info(pedidos)"
            ).fetchall()
        }

        if "descuento" not in columnas:
            conexion.execute("""
                ALTER TABLE pedidos
                ADD COLUMN descuento NUMERIC(10, 2) NOT NULL DEFAULT 0
            """)

        if "total" not in columnas:
            conexion.execute("""
                ALTER TABLE pedidos
                ADD COLUMN total NUMERIC(10, 2) NOT NULL DEFAULT 0
            """)

        conexion.commit()

    finally:
        conexion.close()
inicializar_base_datos()
migrar_columnas_pedidos()
migrar_usuarios_password()
migrar_descuento_pedidos()
crear_tabla_productos()
migrar_costos_historicos()
with app.app_context():
    migrar_metodo_pago_pedidos()

if __name__ == "__main__":
    modo_debug = os.getenv("FLASK_DEBUG", "false").lower() in {
        "1", "true", "yes", "on"
    }
    inicializar_base_datos()
    crear_tabla_productos()

    app.run(
        debug=modo_debug,
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
    )
