import os
os.environ['FLASK_ENV'] = 'production'
from app import create_app
from app.extensions import db
from app.models import Usuario, Trabajador, Herramienta

app = create_app('production')
app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing

with app.test_client() as client:
    with app.app_context():
        # Login as admin
        admin = Usuario.query.filter_by(rol='admin').first()
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True
        
        t = Trabajador.query.first()
        h = Herramienta.query.first()
        h.cantidad_disponible = 5
        db.session.commit()
        
        data = {
            'id_herramienta': [h.id],
            'id_trabajador': t.id,
            'notas': 'Prueba test'
        }
        rv = client.post('/mantenimiento/prestamo/nuevo', data=data, follow_redirects=True)
        print("POST /mantenimiento/prestamo/nuevo ->", rv.status_code)
        if b'Pr\xc3\xa9stamo registrado' in rv.data or b'Prestamo registrado' in rv.data:
            print("OK. Mensaje de éxito encontrado.")
        else:
            print("ERROR o algo diferente:", rv.text[:500])
