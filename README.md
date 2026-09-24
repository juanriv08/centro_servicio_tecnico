# Prototipo — Centro de Servicio Técnico Especializado para Equipos Médicos

Prototipo funcional mínimo desarrollado como evidencia de la **Fase II** del
proyecto de curso de Aseguramiento de la Calidad (Universidad Mariano Gálvez).

Implementa los tres módulos correspondientes a los Sprints 0, 1 y 2 del plan
de trabajo documentado en la Fase I:

- Autenticación y control de acceso basado en roles (Administrador, Supervisor, Técnico)
- Inventario de equipos médicos (registro, consulta, cambio de estado)
- Órdenes de servicio con máquina de estados (Generada → Asignada → Completada → Cerrada)

## Requisitos

- Python 3.10 o superior

## Instalación

```bash
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
python3 app.py
```

Abrir en el navegador: http://127.0.0.1:5000

La base de datos SQLite (`centro_servicio.db`) y los datos de demostración
se crean automáticamente en el primer arranque.

### Usuarios de demostración

| Usuario     | Contraseña   | Rol            |
|-------------|--------------|----------------|
| admin       | admin123     | Administrador  |
| supervisor  | super123     | Supervisor     |
| tecnico     | tecnico123   | Técnico        |

## Ejecutar las pruebas automatizadas

```bash
pytest -v
```

La suite incluye 13 casos de prueba organizados por nivel, conforme a
ISO/IEC/IEEE 29119: unitarias (máquina de estados), integración (rutas +
base de datos), seguridad (control de acceso por rol) y sistema (flujo
completo de una orden de servicio).

## Notas técnicas

Este prototipo utiliza Python + Flask + SQLite como stack simplificado
para la entrega académica. La arquitectura de producción documentada en
la Fase I del proyecto (React + Django + PostgreSQL sobre contenedores
Docker) se mantiene como la solución objetivo para un entorno real; la
lógica de negocio (roles, máquina de estados, trazabilidad) es equivalente
en ambos casos.

## Publicar una demo en Render (SQLite)

Render sirve para publicar una demostración. Para conservar datos usando
SQLite, el servicio necesita un disco persistente de pago; el plan gratuito
usa almacenamiento temporal y puede borrar la base al reiniciarse, suspenderse
o desplegarse de nuevo. SQLite en un disco local también limita la aplicación
a una sola instancia. Para uso operativo, considera PostgreSQL administrado.

1. Sube el contenido del proyecto a un repositorio **privado** en GitHub. No
   subas la carpeta `venv` ni la base de datos local `instance/centro_servicio.db`.
2. En Render, selecciona **New > Web Service** y conecta ese repositorio.
3. Configura:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python init_db.py && gunicorn app:app`
   - **Plan:** uno que permita discos persistentes.
4. En **Environment**, agrega estas variables:
   - `DATABASE_URL` = `sqlite:////var/data/centro_servicio.db`
   - `SECRET_KEY` = una cadena aleatoria larga y privada
   - `SEED_DEMO_DATA` = `true` solo para crear los usuarios y datos de ejemplo
5. En **Disks**, crea un disco con **Mount Path** `/var/data`. Guarda y espera
   a que termine el despliegue. Render mostrará la URL pública `https://...onrender.com`.

El script `init_db.py` crea las tablas antes de iniciar Gunicorn. El sembrado
de ejemplos solo ocurre cuando `SEED_DEMO_DATA=true` y la base no tiene usuarios.
Las cuentas incluidas son públicas y sus contraseñas son conocidas: cámbialas
antes de compartir la URL y no uses información real de pacientes o clientes.

La base que ya tienes en `instance/centro_servicio.db` **no se copia por subir
el código**. La publicación comenzará con una base nueva (y datos de ejemplo,
si activas esa variable). Para conservar tus registros actuales, haz una copia
de seguridad y migra/importa esa base al almacenamiento persistente antes de
usar el sitio.

Para modificar el sistema después, sube los cambios al mismo repositorio; Render
reconstruirá y publicará la nueva versión. El archivo SQLite solo se conserva si
la ruta de `DATABASE_URL` está dentro del disco persistente `/var/data`.
