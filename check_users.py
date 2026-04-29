import sys
from app import create_app
from app.models import db, Usuario

app = create_app()
with app.app_context():
    users = Usuario.query.all()
    for u in users:
        print(u.id, u.email, u.es_admin, getattr(u, 'es_mantenimiento', None), getattr(u, 'rol', None))
