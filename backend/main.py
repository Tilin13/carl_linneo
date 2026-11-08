import secrets
import qrcode
import hashlib
import hmac
import logging
import math
import os
import re
import secrets
from decimal import Decimal, InvalidOperation
from sqlalchemy import text
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
        db.String(255),
        nullable=True
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

    conexion = sqlite3.connect(
        BASE_DATOS,
        timeout=10
    )

    try:

        columnas = {
            fila[1]
            for fila in conexion.execute(
                "PRAGMA table_info(usuarios)"
            ).fetchall()
        }

        if "password" not in columnas:

            conexion.execute("""
                ALTER TABLE usuarios
                ADD COLUMN password VARCHAR(255)
            """)

            conexion.commit()

            print(
                "Migración completada: "
                "columna password agregada."
            )

        else:

            print(
                "La columna password ya existe."
            )

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

    total = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    pedido = db.relationship(
        "Pedido",
        back_populates="productos"
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

    BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)

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

    # Validar comprador
    if (
        isinstance(usuario_id, bool)
        or not isinstance(usuario_id, int)
        or usuario_id <= 0
    ):
        return jsonify({"error": "Selecciona un comprador válido."}), 400

    comprador = db.session.get(User, usuario_id)

    if comprador is None:
        return jsonify({"error": "El comprador no existe."}), 404

    # Validar método de pago
    if metodo_pago != "efectivo":
        return jsonify({"error": "Método de pago no disponible."}), 400

    # Validar descuento
    try:
        if isinstance(descuento_porcentaje, bool):
            raise ValueError

        descuento_porcentaje = Decimal(
            str(descuento_porcentaje)
        )

        if (
            not descuento_porcentaje.is_finite()
            or descuento_porcentaje < 0
            or descuento_porcentaje > 100
        ):
            raise ValueError

    except (ValueError, TypeError, InvalidOperation):
        return jsonify({"error": "Descuento no válido."}), 400

    # Validar productos
    if (
        not isinstance(productos, list)
        or not productos
        or len(productos) > 100
    ):
        return jsonify({"error": "Agrega productos a la venta."}), 400

    cantidades = {}

    for item in productos:

        if not isinstance(item, dict):
            return jsonify({"error": "Producto no válido."}), 400

        codigo = str(item.get("codigo", "")).strip()
        cantidad = item.get("cantidad")

        if not codigo or len(codigo) > 80:
            return jsonify({"error": "Código no válido."}), 400

        if (
            isinstance(cantidad, bool)
            or not isinstance(cantidad, int)
            or not 1 <= cantidad <= 10000
        ):
            return jsonify({"error": "Cantidad no válida."}), 400

        cantidades[codigo] = cantidades.get(codigo, 0) + cantidad

    if any(c > 10000 for c in cantidades.values()):
        return jsonify({"error": "Cantidad demasiado grande."}), 400

    subtotal = Decimal("0.00")

    try:
        # Crear el pedido asociado al comprador.
        pedido = Pedido(
            usuario_id=comprador.id,
            subtotal=Decimal("0.00"),
            descuento=Decimal("0.00"),
            total=Decimal("0.00"),
            metodo_pago=metodo_pago,
            estado="Pagado"
        )

        db.session.add(pedido)
        db.session.flush()

        for codigo, cantidad in cantidades.items():

            producto = db.session.execute(
                text("""
                    SELECT codigo, nombre, precio_venta, stock
                    FROM productos
                    WHERE codigo = :codigo
                """),
                {"codigo": codigo}
            ).mappings().first()

            if producto is None:
                raise ValueError(
                    f"No existe el producto {codigo}."
                )

            # Comprobar y descontar inventario.
            resultado = db.session.execute(
                text("""
                    UPDATE productos
                    SET stock = stock - :cantidad
                    WHERE codigo = :codigo
                    AND stock >= :cantidad
                """),
                {
                    "codigo": codigo,
                    "cantidad": cantidad
                }
            )

            if resultado.rowcount != 1:
                raise ValueError(
                    f"Stock insuficiente para {producto['nombre']}."
                )

            precio = Decimal(
                str(producto["precio_venta"])
            ).quantize(Decimal("0.01"))

            if not precio.is_finite() or precio < 0:
                raise ValueError("Precio de producto no válido.")

            total_producto = (
                precio * cantidad
            ).quantize(Decimal("0.01"))

            detalle = PedidoItem(
                pedido_id=pedido.id,
                producto_codigo=codigo,
                nombre=producto["nombre"],
                cantidad=cantidad,
                precio_unitario=precio,
                total=total_producto
            )

            db.session.add(detalle)

            subtotal += total_producto

        # Calcular descuento y total.
        subtotal = subtotal.quantize(Decimal("0.01"))

        descuento = (
            subtotal * descuento_porcentaje / Decimal("100")
        ).quantize(Decimal("0.01"))

        total = (subtotal - descuento).quantize(
            Decimal("0.01")
        )

        pedido.subtotal = subtotal
        pedido.descuento = descuento
        pedido.total = total

        db.session.commit()

        return jsonify({
            "mensaje": "Venta registrada correctamente.",
            "pedido_id": pedido.id,
            "comprador": comprador.username,
            "subtotal": str(subtotal),
            "descuento": str(descuento),
            "total": str(total),
            "estado": pedido.estado,
            "url": url_for(
                "detalle_pedido_admin",
                pedido_id=pedido.id
            )
        }), 201

    except ValueError as error:
        db.session.rollback()

        return jsonify({"error": str(error)}), 400

    except Exception:
        db.session.rollback()

        app.logger.exception("Error registrando venta de caja.")

        return jsonify({
            "error": "No se pudo completar la venta."
        }), 500
    
    
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
 
def migrar_pedidos_caja():
    conexion = sqlite3.connect(BASE_DATOS, timeout=10)

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
                ADD COLUMN descuento NUMERIC(10,2)
                NOT NULL DEFAULT 0
            """)

        if "total" not in columnas:
            conexion.execute("""
                ALTER TABLE pedidos
                ADD COLUMN total NUMERIC(10,2)
                NOT NULL DEFAULT 0
            """)

            conexion.execute("""
                UPDATE pedidos
                SET total = subtotal
            """)

        if "metodo_pago" not in columnas:
            conexion.execute("""
                ALTER TABLE pedidos
                ADD COLUMN metodo_pago TEXT
                NOT NULL DEFAULT 'efectivo'
            """)

        conexion.commit()

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
def crrear_cupones():
	primer_digito = secrets.choice("123456789")
	resto = "".join(secrets.choice("0123456789") for _ in range(31))
	codigo_cupon = primer_digito + resto
	numero_categoria = random.randint(1,7)
	descuento = random.choice([5,10.15,20])
	cobrado = False
	cursor.execute("""
	INSERT INTO cupones (codigo_cupon,numero_categoria, descuento, cobrado), values=(?,?,?,?)
	""")
	
	
	
def conocer_categoria(numero_categoria):
	if numero_categoria == 1:
		categoria = "Mariposas"
	elif numero_categoria == 2:
		categoria = "Escarabajos"
	elif numero_categoria == 3:
		categoria = "Odonatos"
	elif numero_categoria == 4:
		categoria = "Cuarzos"
	elif numero_categoria == 5:
		categoria = "Minerales"
	elif numero_categoria == 6:
		categoria = "Fosiles"
	else:
		categoria = "todos"
	
	
		
def imprimir_codigoqr(codigo_cupon):
	qr = qrcode.QRCode(
	version=None,
	error_correction=qrcode.constans.ERROR_CORRECT_M,
	box_size=10,
	border=4
	)
	qr.add_data(codigo_cupon)
	qr.make(fit=True)
	imagen =qr.make_image(fill_color="black", back_color="white")
	imagen.save("codigo_qr.png")
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

    subtotal = Decimal("0.00")

    try:

        # Crear el pedido dentro de la transacción.
        pedido = Pedido(
            usuario_id=current_user.id,
            subtotal=Decimal("0.00"),
            estado="Pendiente"
        )

        db.session.add(pedido)
        db.session.flush()

        # Comprobar cada producto directamente en la BD.
        for codigo, cantidad in cantidades.items():

            producto = db.session.execute(
                text("""
                    SELECT codigo, nombre, precio_venta, stock
                    FROM productos
                    WHERE codigo = :codigo
                """),
                {"codigo": codigo}
            ).mappings().first()

            if producto is None:
                raise ValueError(
                    f"El producto {codigo} ya no existe."
                )

            stock = int(producto["stock"])

            if stock < cantidad:
                raise ValueError(
                    f"No hay suficientes existencias de "
                    f"{producto['nombre']}."
                )

            precio = Decimal(
                str(producto["precio_venta"])
            ).quantize(Decimal("0.01"))

            if not precio.is_finite() or precio < 0:
                raise ValueError(
                    "El precio de un producto no es válido."
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

            total_producto = (
                precio * cantidad
            ).quantize(Decimal("0.01"))

            # Guardar los detalles de la compra.
            detalle = PedidoItem(
                pedido_id=pedido.id,
                producto_codigo=codigo,
                nombre=producto["nombre"],
                cantidad=cantidad,
                precio_unitario=precio,
                total=total_producto
            )

            db.session.add(detalle)

            subtotal += total_producto

        # Guardar subtotal definitivo.
        pedido.subtotal = subtotal
        pedido.total = subtotal
        pedido.descuento = Decimal("0.00")
        pedido.metodo_pago = "efectivo"
        # Confirmar pedido, detalles y stock juntos.
        db.session.commit()

        return jsonify({
            "mensaje": "Pedido realizado correctamente.",
            "pedido_id": pedido.id,
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

@app.route("/pedido_personalizado")
def pedido_personalizado():
	return render_template("pedidos_personalizados.html")

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
    especies = especies_disponibles()

    return render_template(
        "pedidos_personalizados.html",
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

        password = request.form.get(
            "password", ""
        )

        if not identificador or not password:

            flash(
                "Introduce tu usuario o correo y tu contraseña.",
                "error"
            )

            return render_template(
                "login.html"
            ), 400

        clave = obtener_clave_bloqueo(
            identificador
        )

        bloqueado, registro = comprobar_bloqueo(
            clave
        )

        if bloqueado:

            flash(
                "Has alcanzado el límite de intentos. "
                "Inténtalo nuevamente después de 30 minutos.",
                "error"
            )

            return render_template(
                "login.html"
            ), 429

        identificador_normalizado = (
            " ".join(
                identificador.split()
            ).casefold()
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

            bloqueado = registrar_fallo_login(
                clave
            )

            if bloqueado:

                flash(
                    "Has realizado cinco intentos "
                    "incorrectos. Acceso bloqueado durante 30 minutos.",
                    "error"
                )

                return render_template(
                    "login.html"
                ), 429

            flash(
                "Usuario/correo o contraseña incorrectos.",
                "error"
            )

            return render_template(
                "login.html"
            ), 401

        reiniciar_intentos_login(clave)

        correo_usuario = (
            usuario.email or ""
        ).strip().lower()

        if correo_usuario == ADMIN_EMAIL:

            if usuario.rol != "admin":
                usuario.rol = "admin"
                db.session.commit()

        elif usuario.rol == "admin":

            usuario.rol = "user"
            db.session.commit()

        session.clear()

        login_user(
            usuario,
            remember=False
        )

        session.permanent = True

        if correo_usuario == ADMIN_EMAIL:
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
# Inicializar las bases de datos al cargar Flask en Render
inicializar_base_datos()

# Migraciones de la estructura de usuarios
migrar_usuarios_password()

# Inicialización del inventario
crear_tabla_productos()

# Migraciones de pedidos
migrar_pedidos_caja()
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
