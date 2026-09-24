"""
app.py
Prototipo funcional mínimo — Centro de Servicio Técnico Especializado
para Equipos Médicos.

Módulos implementados (Sprints 0-2 del plan de la Fase I):
    - Autenticación y control de acceso basado en roles
    - Inventario de equipos médicos (CRUD)
    - Órdenes de servicio (creación y transición de estados)

Stack: Python 3 + Flask + SQLAlchemy + SQLite (prototipo académico).
La arquitectura de producción documentada en la Fase I (React + Django +
PostgreSQL) se mantiene como la solución objetivo a futuro; este
prototipo demuestra la misma lógica de negocio con un stack simplificado
acorde al tiempo disponible del curso.
"""
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from models import db, Usuario, Cliente, Equipo, OrdenServicio, ESTADOS_ORDEN

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "clave-desarrollo-academico-cambiar-en-produccion"
)
# En local conserva la base SQLite dentro de instance/. En Render se puede
# indicar una ruta persistente mediante DATABASE_URL (por ejemplo,
# sqlite:////var/data/centro_servicio.db).
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///centro_servicio.db"
)
db.init_app(app)


# ---------------------------------------------------------------------
# Control de acceso basado en roles (evidencia del criterio "Seguridad"
# de ISO/IEC 25010:2023: un técnico no puede administrar usuarios).
# ---------------------------------------------------------------------
def login_requerido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def rol_requerido(*roles_permitidos):
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("login"))
            if session.get("rol") not in roles_permitidos:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorador


# ---------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("dashboard") if "usuario_id" in session else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and usuario.check_password(password):
            session["usuario_id"] = usuario.id
            session["nombre"] = usuario.nombre_completo
            session["rol"] = usuario.rol
            return redirect(url_for("dashboard"))
        flash("Usuario o contraseña incorrectos.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_requerido
def dashboard():
    total_equipos = Equipo.query.count()
    ordenes_abiertas = OrdenServicio.query.filter(OrdenServicio.estado != "Cerrada").count()
    ordenes_cerradas = OrdenServicio.query.filter_by(estado="Cerrada").count()
    equipos_fuera_servicio = Equipo.query.filter_by(estado="Fuera de servicio").count()
    return render_template(
        "dashboard.html",
        total_equipos=total_equipos,
        ordenes_abiertas=ordenes_abiertas,
        ordenes_cerradas=ordenes_cerradas,
        equipos_fuera_servicio=equipos_fuera_servicio,
    )


# ---------------------------------------------------------------------
# Módulo: Usuarios (solo Administrador)
# ---------------------------------------------------------------------
@app.route("/usuarios")
@rol_requerido("Administrador")
def listar_usuarios():
    usuarios = Usuario.query.all()
    return render_template("usuarios.html", usuarios=usuarios)


# ---------------------------------------------------------------------
# Módulo: Inventario de equipos médicos
# ---------------------------------------------------------------------
@app.route("/equipos")
@login_requerido
def listar_equipos():
    equipos = Equipo.query.all()
    return render_template("equipos.html", equipos=equipos)


@app.route("/equipos/nuevo", methods=["GET", "POST"])
@rol_requerido("Administrador", "Supervisor")
def nuevo_equipo():
    clientes = Cliente.query.all()
    if request.method == "POST":
        equipo = Equipo(
            nombre=request.form["nombre"],
            modelo=request.form.get("modelo", ""),
            numero_serie=request.form["numero_serie"],
            cliente_id=request.form["cliente_id"],
            estado="Operativo",
        )
        db.session.add(equipo)
        db.session.commit()
        flash(f"Equipo '{equipo.nombre}' registrado correctamente.", "success")
        return redirect(url_for("listar_equipos"))
    return render_template("equipo_form.html", clientes=clientes)


@app.route("/equipos/<int:equipo_id>/estado", methods=["POST"])
@rol_requerido("Administrador", "Supervisor")
def cambiar_estado_equipo(equipo_id):
    equipo = Equipo.query.get_or_404(equipo_id)
    equipo.estado = "Fuera de servicio" if equipo.estado == "Operativo" else "Operativo"
    db.session.commit()
    return redirect(url_for("listar_equipos"))


# ---------------------------------------------------------------------
# Módulo: Órdenes de servicio (máquina de estados)
# ---------------------------------------------------------------------
@app.route("/ordenes")
@login_requerido
def listar_ordenes():
    ordenes = OrdenServicio.query.order_by(OrdenServicio.fecha_creacion.desc()).all()
    return render_template("ordenes.html", ordenes=ordenes)


@app.route("/ordenes/nueva", methods=["GET", "POST"])
@login_requerido
def nueva_orden():
    equipos = Equipo.query.all()
    if request.method == "POST":
        orden = OrdenServicio(
            equipo_id=request.form["equipo_id"],
            estado="Generada",
        )
        db.session.add(orden)
        db.session.commit()
        flash(f"Orden de servicio #{orden.id} generada.", "success")
        return redirect(url_for("listar_ordenes"))
    return render_template("orden_form.html", equipos=equipos)


@app.route("/ordenes/<int:orden_id>/avanzar", methods=["POST"])
@login_requerido
def avanzar_orden(orden_id):
    orden = OrdenServicio.query.get_or_404(orden_id)
    nuevo_estado = request.form["nuevo_estado"]

    # Al asignar la orden, se vincula al técnico que la atenderá.
    if nuevo_estado == "Asignada":
        orden.tecnico_id = session["usuario_id"]
        orden.diagnostico = request.form.get("diagnostico", orden.diagnostico)

    if orden.transicionar(nuevo_estado):
        db.session.commit()
        flash(f"Orden #{orden.id} actualizada a '{nuevo_estado}'.", "success")
    else:
        flash(
            f"Transición no permitida: la orden está en '{orden.estado}' "
            f"y no puede pasar directamente a '{nuevo_estado}'.",
            "danger",
        )
    return redirect(url_for("listar_ordenes"))


# ---------------------------------------------------------------------
# Manejo de errores
# ---------------------------------------------------------------------
@app.errorhandler(403)
def acceso_denegado(e):
    return render_template("403.html"), 403


def crear_datos_semilla():
    """Crea datos iniciales de demostración si la base de datos está vacía."""
    if Usuario.query.first():
        return

    admin = Usuario(nombre_completo="Pablo Herrera", username="admin", rol="Administrador")
    admin.set_password("admin123")
    supervisor = Usuario(nombre_completo="Juan Daniel Rivera", username="supervisor", rol="Supervisor")
    supervisor.set_password("super123")
    tecnico = Usuario(nombre_completo="Javier Carpio", username="tecnico", rol="Tecnico")
    tecnico.set_password("tecnico123")
    db.session.add_all([admin, supervisor, tecnico])

    hospital = Cliente(nombre="Hospital Roosevelt", tipo="Hospital")
    clinica = Cliente(nombre="Clínica Santa Fe", tipo="Clínica")
    db.session.add_all([hospital, clinica])
    db.session.commit()

    equipo1 = Equipo(nombre="Ultrasonido GE Voluson", modelo="E10", numero_serie="US-2024-001", cliente_id=hospital.id)
    equipo2 = Equipo(nombre="Monitor de signos vitales", modelo="Mindray T5", numero_serie="MV-2024-002", cliente_id=clinica.id)
    db.session.add_all([equipo1, equipo2])
    db.session.commit()

    orden1 = OrdenServicio(equipo_id=equipo1.id, estado="Generada")
    db.session.add(orden1)
    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        crear_datos_semilla()
    app.run(debug=False, host="0.0.0.0", port=5000)
