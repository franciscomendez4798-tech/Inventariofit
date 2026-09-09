import os, sys
os.environ['FLASK_ENV'] = 'production'
from app import create_app
from app.extensions import db
from app.models import Departamento, Usuario
import openpyxl

app = create_app('production')

with app.app_context():
    # 1. Reactivar departamento "Mantenimiento"
    depto_mant = Departamento.query.filter(Departamento.nombre.ilike('%mantenimiento%')).first()
    if depto_mant:
        depto_mant.activo = True
        db.session.commit()
        print(f"Departamento '{depto_mant.nombre}' reactivado correctamente.")
    else:
        print("No se encontró un departamento con el nombre 'Mantenimiento'.")

    # 2. Generar Excel de Usuarios
    usuarios = Usuario.query.all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cuentas de Usuarios"
    
    # Headers
    headers = ['ID', 'Nombre Completo', 'Email', 'Rol', 'Departamento', 'Estado', 'Fecha de Creación']
    ws.append(headers)
    
    for u in usuarios:
        depto_nombre = u.departamento.nombre if u.departamento else 'Sin Departamento'
        estado = 'Activo' if u.activo else 'Inactivo'
        fecha = u.creado_en.strftime('%Y-%m-%d %H:%M:%S') if u.creado_en else ''
        ws.append([u.id, u.nombre_completo, u.email, u.rol, depto_nombre, estado, fecha])
    
    output_path = "/Users/franmen/.gemini/antigravity/brain/972c5f7a-61a9-40be-8a55-264b35e93727/cuentas_usuarios.xlsx"
    wb.save(output_path)
    print(f"Excel generado en: {output_path}")

