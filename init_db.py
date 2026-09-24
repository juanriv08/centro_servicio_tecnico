"""Prepare the database before starting the production web server."""
import os

from app import app, crear_datos_semilla
from models import db, Usuario


with app.app_context():
    db.create_all()
    # For a demo deployment, set SEED_DEMO_DATA=true in the hosting service.
    if os.environ.get("SEED_DEMO_DATA", "false").lower() == "true":
        if not Usuario.query.first():
            crear_datos_semilla()
