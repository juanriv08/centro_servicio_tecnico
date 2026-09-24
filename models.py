"""
models.py
Modelo de datos del prototipo del Centro de Servicio Técnico Especializado
para Equipos Médicos.

Cubre las entidades mínimas necesarias para los tres módulos evidenciados
en la Fase II del proyecto:
    1. Usuarios y roles (autenticación y control de acceso)
    2. Inventario de equipos médicos (asociado a un cliente)
    3. Órdenes de servicio (con máquina de estados finita)
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Estados válidos de una orden de servicio (máquina de estados reducida
# para el prototipo académico; el flujo completo de 6 estados está
# documentado en la Fase I, sección de Lógica Funcional).
ESTADOS_ORDEN = ["Generada", "Asignada", "Completada", "Cerrada"]

# Roles soportados por el sistema
ROLES = ["Administrador", "Supervisor", "Tecnico"]


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="Tecnico")

    ordenes_asignadas = db.relationship("OrdenServicio", back_populates="tecnico")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Usuario {self.username} ({self.rol})>"


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # Hospital, Clínica, Consultorio

    equipos = db.relationship("Equipo", back_populates="cliente")

    def __repr__(self):
        return f"<Cliente {self.nombre}>"


class Equipo(db.Model):
    __tablename__ = "equipos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    modelo = db.Column(db.String(120))
    numero_serie = db.Column(db.String(80), unique=True, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    estado = db.Column(db.String(30), default="Operativo")  # Operativo / Fuera de servicio
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    cliente = db.relationship("Cliente", back_populates="equipos")
    ordenes = db.relationship("OrdenServicio", back_populates="equipo")

    def __repr__(self):
        return f"<Equipo {self.nombre} - {self.numero_serie}>"


class OrdenServicio(db.Model):
    __tablename__ = "ordenes_servicio"

    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey("equipos.id"), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    estado = db.Column(db.String(30), default="Generada", nullable=False)
    diagnostico = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime, nullable=True)

    equipo = db.relationship("Equipo", back_populates="ordenes")
    tecnico = db.relationship("Usuario", back_populates="ordenes_asignadas")

    # --- Lógica de la máquina de estados (sección 3.2 del documento) ---
    TRANSICIONES_VALIDAS = {
        "Generada": ["Asignada"],
        "Asignada": ["Completada"],
        "Completada": ["Cerrada"],
        "Cerrada": [],
    }

    def puede_transicionar_a(self, nuevo_estado: str) -> bool:
        """Valida si una transición de estado es permitida según la
        máquina de estados definida para la orden de servicio."""
        return nuevo_estado in self.TRANSICIONES_VALIDAS.get(self.estado, [])

    def transicionar(self, nuevo_estado: str) -> bool:
        if not self.puede_transicionar_a(nuevo_estado):
            return False
        self.estado = nuevo_estado
        if nuevo_estado == "Cerrada":
            self.fecha_cierre = datetime.utcnow()
        return True

    def __repr__(self):
        return f"<Orden #{self.id} - {self.estado}>"
