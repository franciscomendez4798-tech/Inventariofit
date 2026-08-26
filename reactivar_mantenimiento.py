import os
os.environ['FLASK_ENV'] = 'production'
from app import create_app
from app.extensions import db
from app.models import Departamento

app = create_app('production')

with app.app_context():
    # Buscar departamento de mantenimiento (incluso inactivo)
    depto = Departamento.query.filter(Departamento.nombre.ilike('%mantenimiento%')).first()
    if depto:
        if not depto.activo:
            depto.activo = True
            db.session.commit()
            print(f"✅ ÉXITO: El departamento '{depto.nombre}' ha sido reactivado.")
        else:
            print(f"ℹ️ El departamento '{depto.nombre}' ya estaba activo.")
    else:
        print("❌ ERROR: No se encontró un departamento con el nombre 'mantenimiento'.")
