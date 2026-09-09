import os
os.environ['FLASK_ENV'] = 'production'
from app import create_app
from app.models import Departamento
app = create_app('production')
with app.app_context():
    for d in Departamento.query.all():
        print(f"ID: {d.id} | Nombre: {d.nombre} | Activo: {d.activo}")
