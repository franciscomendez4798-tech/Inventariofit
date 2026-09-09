import os, sys
os.environ['FLASK_ENV'] = 'production'
from app import create_app
from app.extensions import db
from app.models import Usuario, Pedido, DetallePedido, Material

app = create_app('production')
with app.app_context():
    pedido = Pedido.query.first()
    try:
        from app.utils.formatos import generar_pdf_requisiciones
        buf = generar_pdf_requisiciones([pedido])
        print("Requisicion PDF OK")
    except Exception as e:
        print("ERROR Requisicion PDF:", e)
