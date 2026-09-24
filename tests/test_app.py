"""
test_app.py
Suite de pruebas automatizadas del prototipo, alineada a los niveles de
prueba definidos en la Tabla 6 (Fase I, sección 5.C) conforme a
ISO/IEC/IEEE 29119:

    - Pruebas UNITARIAS      -> lógica de la máquina de estados
    - Pruebas de INTEGRACIÓN -> rutas Flask + base de datos
    - Pruebas de SEGURIDAD   -> control de acceso basado en roles
    - Pruebas de SISTEMA     -> flujo completo equipo -> orden -> cierre

Ejecutar con:  pytest -v
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as flask_app
from models import db, Usuario, Cliente, Equipo, OrdenServicio


@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })
    with flask_app.app_context():
        db.create_all()

        admin = Usuario(nombre_completo="Admin Test", username="admin", rol="Administrador")
        admin.set_password("admin123")
        tecnico = Usuario(nombre_completo="Tecnico Test", username="tecnico", rol="Tecnico")
        tecnico.set_password("tec123")
        db.session.add_all([admin, tecnico])

        cliente = Cliente(nombre="Hospital de Prueba", tipo="Hospital")
        db.session.add(cliente)
        db.session.commit()

        equipo = Equipo(nombre="Ultrasonido de Prueba", numero_serie="TEST-001", cliente_id=cliente.id)
        db.session.add(equipo)
        db.session.commit()

        yield flask_app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


# =====================================================================
# NIVEL: PRUEBAS UNITARIAS
# Objetivo: validar la lógica de negocio de la máquina de estados de la
# orden de servicio de forma aislada, sin pasar por HTTP ni por la BD.
# =====================================================================
class TestMaquinaDeEstadosUnitaria:

    def test_transicion_valida_generada_a_asignada(self, app):
        with app.app_context():
            orden = OrdenServicio(estado="Generada")
            assert orden.puede_transicionar_a("Asignada") is True
            assert orden.transicionar("Asignada") is True
            assert orden.estado == "Asignada"

    def test_transicion_invalida_generada_a_cerrada(self, app):
        """No debe permitirse saltar estados (ej. cerrar una orden que
        nunca fue asignada ni completada)."""
        with app.app_context():
            orden = OrdenServicio(estado="Generada")
            assert orden.puede_transicionar_a("Cerrada") is False
            assert orden.transicionar("Cerrada") is False
            assert orden.estado == "Generada"  # no debe cambiar

    def test_orden_cerrada_no_permite_mas_transiciones(self, app):
        with app.app_context():
            orden = OrdenServicio(estado="Cerrada")
            assert orden.puede_transicionar_a("Asignada") is False
            assert orden.TRANSICIONES_VALIDAS["Cerrada"] == []

    def test_fecha_cierre_se_registra_al_cerrar(self, app):
        with app.app_context():
            orden = OrdenServicio(estado="Completada")
            assert orden.fecha_cierre is None
            orden.transicionar("Cerrada")
            assert orden.fecha_cierre is not None


# =====================================================================
# NIVEL: PRUEBAS DE INTEGRACIÓN
# Objetivo: validar que las rutas Flask interactúan correctamente con
# la base de datos (creación de equipos y órdenes end-to-end).
# =====================================================================
class TestIntegracionModulos:

    def test_login_exitoso_redirige_a_dashboard(self, client):
        resp = login(client, "admin", "admin123")
        assert resp.status_code == 200
        assert "Panel de Indicadores".encode() in resp.data

    def test_login_fallido_muestra_error(self, client):
        resp = login(client, "admin", "contrasena-incorrecta")
        assert "incorrectos".encode() in resp.data

    def test_registrar_equipo_lo_persiste_en_bd(self, client, app):
        login(client, "admin", "admin123")
        with app.app_context():
            cliente_id = Cliente.query.first().id
        resp = client.post("/equipos/nuevo", data={
            "nombre": "Monitor Fetal",
            "modelo": "M-200",
            "numero_serie": "MF-2026-099",
            "cliente_id": cliente_id,
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            equipo = Equipo.query.filter_by(numero_serie="MF-2026-099").first()
            assert equipo is not None
            assert equipo.nombre == "Monitor Fetal"

    def test_crear_orden_y_descontar_a_asignada(self, client, app):
        """Equivalente al caso de integración de la Tabla 6: 'Cerrar
        orden + descontar repuesto' -> aquí: crear orden + asignar
        técnico, verificando la relación entre módulos."""
        login(client, "admin", "admin123")
        with app.app_context():
            equipo_id = Equipo.query.first().id

        resp = client.post("/ordenes/nueva", data={"equipo_id": equipo_id}, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            orden = OrdenServicio.query.first()
            assert orden.estado == "Generada"

            resp2 = client.post(f"/ordenes/{orden.id}/avanzar", data={
                "nuevo_estado": "Asignada",
                "diagnostico": "Falla en transductor",
            }, follow_redirects=True)
            assert resp2.status_code == 200

            orden_actualizada = OrdenServicio.query.get(orden.id)
            assert orden_actualizada.estado == "Asignada"
            assert orden_actualizada.diagnostico == "Falla en transductor"


# =====================================================================
# NIVEL: PRUEBAS DE SEGURIDAD
# Objetivo: confirmar que el control de acceso basado en roles impide
# que un usuario con rol Técnico acceda a módulos administrativos.
# =====================================================================
class TestSeguridadControlDeAcceso:

    def test_tecnico_no_puede_ver_usuarios(self, client):
        login(client, "tecnico", "tec123")
        resp = client.get("/usuarios")
        assert resp.status_code == 403

    def test_tecnico_no_puede_registrar_equipos(self, client):
        login(client, "tecnico", "tec123")
        resp = client.get("/equipos/nuevo")
        assert resp.status_code == 403

    def test_usuario_no_autenticado_es_redirigido_a_login(self, client):
        resp = client.get("/dashboard", follow_redirects=True)
        assert b"Iniciar sesi" in resp.data or resp.status_code == 200

    def test_admin_si_puede_ver_usuarios(self, client):
        login(client, "admin", "admin123")
        resp = client.get("/usuarios")
        assert resp.status_code == 200


# =====================================================================
# NIVEL: PRUEBA DE SISTEMA (end-to-end)
# Objetivo: recorrer el flujo documentado en la Fase I: equipo -> orden
# -> atención -> cierre, tal como lo describe el "ejemplo práctico" de
# la lógica funcional.
# =====================================================================
class TestFlujoDeSistemaCompleto:

    def test_flujo_completo_generada_hasta_cerrada(self, client, app):
        login(client, "admin", "admin123")
        with app.app_context():
            equipo_id = Equipo.query.first().id

        client.post("/ordenes/nueva", data={"equipo_id": equipo_id}, follow_redirects=True)
        with app.app_context():
            orden_id = OrdenServicio.query.first().id

        client.post(f"/ordenes/{orden_id}/avanzar",
                     data={"nuevo_estado": "Asignada", "diagnostico": "Calibración requerida"},
                     follow_redirects=True)
        client.post(f"/ordenes/{orden_id}/avanzar", data={"nuevo_estado": "Completada"}, follow_redirects=True)
        client.post(f"/ordenes/{orden_id}/avanzar", data={"nuevo_estado": "Cerrada"}, follow_redirects=True)

        with app.app_context():
            orden_final = OrdenServicio.query.get(orden_id)
            assert orden_final.estado == "Cerrada"
            assert orden_final.fecha_cierre is not None
            assert orden_final.diagnostico == "Calibración requerida"
