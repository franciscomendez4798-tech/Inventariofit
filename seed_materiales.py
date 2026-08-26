"""
seed_materiales.py
==================
Script para importar el inventario inicial de la Secretaría Administrativa.
"""
import os, warnings
from dotenv import load_dotenv

load_dotenv('.env')
os.environ['FLASK_ENV'] = 'production'
warnings.filterwarnings('ignore')

from app import create_app
from app.extensions import db
from app.models import Material, Categoria

app = create_app('production')

DATOS = [
    ("SUJETA DOCUMENTOS", 3, "CAJA", "GRANDES"),
    ("SUJETA DOCUMENTOS", 7, "CAJA", "MEDIANOS"),
    ("SUJETA DOCUMENTOS", 4, "CAJA", "CHICO"),
    ("RESISTOL", 30, "PIEZAS", "GRANDES"),
    ("RESISTOL", 4, "PIEZAS", "PEQUEÑO"),
    ("TIJERAS", 1, "PIEZAS", "PEQUEÑO"),
    ("TINTA DE SELLO", 2, "PIEZAS", "AZUL"),
    ("TINTA DE SELLO", 1, "PIEZAS", "NEGRO"),
    ("CUENTA FACIL", 2, "PIEZAS", "CHICO"),
    ("CUENTA FACIL", 2, "PIEZAS", "GRANDES"),
    ("REGLA DE ALUMINIO", 2, "PIEZAS", "GRANDES"),
    ("CINTA MASTICK", 10, "PIEZAS", "COLOR BEISH"),
    ("CINTA TRANSPARENTE", 3, "PIEZAS", "GRUESA"),
    ("CINTA PARA CARRETE", 3, "PIEZAS", "GRANDES"),
    ("LAPIZ MIRANDA", 3, "PIEZAS", "NO. 2"),
    ("LAPIZ BICOLOR", 6, "PIEZAS", "NO. 2"),
    ("CUTTER", 5, "PIEZAS", "GRANDES"),
    ("CALCULADORA", 2, "PIEZAS", "GRANDES"),
    ("LIMPIA PIZARRON", 7, "PIEZAS", "MEDIANOS"),
    ("PLUMON MAGISTRAL", 5, "PIEZAS", "ROJO"),
    ("MARCA TEXTO", 5, "PIEZAS", "VERDE"),
    ("MARCA TEXTO", 1, "PIEZAS", "ROSA"),
    ("MARCADOR PERMANENTE", 6, "PIEZAS", "NEGRO"),
    ("PLUMON PERMANENTE", 5, "PIEZAS", "AZUL"),
    ("GOMA (BORRADOR)", 2, "PIEZAS", "BLANCO"),
    ("LAPICERO PROFESIONAL", 2, "CAJA", "NEGRO MARCA (AZOR 0.05 MM)"),
    ("BORRADOR TIPO LAPIZ", 3, "CAJA", "GRANDES"),
    ("LAPICERO BASICO", 11, "PIEZAS", "AZUL"),
    ("MARCA TEXTO", 11, "PIEZAS", "AMARILLO"),
    ("FOLDER T/CARTA", 8, "PAQUETES", "BEISH"),
    ("FOLDER T/OFICIO", 1, "PAQUETES", "VERDE"),
    ("FOLDER T/CARTA", 1, "PAQUETES", "VERDE"),
    ("FOLDER T/CARTA", 1, "PAQUETES", "AZUL"),
    ("FOLDER T/CARTA", 1, "PAQUETES", "ROSA"),
    ("FOLDER T/OFICIO", 1, "PAQUETES", "AZUL"),
    ("FOLDER T/OFICIO", 1, "PAQUETES", "ROSA"),
    ("PROTECTOR HOJA T/CARTA", 5, "PAQUETES", "TRANSPARENTE"),
    ("TABLA DE APOYO", 1, "PIEZAS", "MADERA"),
    ("BLOCK T/CARTA DIBUJO", 1, "PIEZAS", "TRANSPARENTE"),
    ("CUADERNOS", 1, "PIEZAS", "RAYA"),
    ("DESPACHADOR DE CINTA", 2, "PIEZAS", "GRANDES"),
    ("OPALINA", 12, "PAQUETES", "BLANCO"),
    ("OPALINA", 5, "PAQUETES", "BEISH"),
    ("PERFORADORA", 1, "PIEZAS", "NEGRO"),
    ("GRAPAS", 12, "PAQUETES", "ESTANDAR"),
    ("GRAPADORA", 2, "PIEZAS", "METALICO"),
    ("CLIP", 1, "PIEZAS", "NO. 1"),
    ("CLIP", 3, "PIEZAS", "JUMBO"),
    ("CLIP MARIPOSA", 6, "PIEZAS", "NO. 1"),
    ("CLIP MARIPOSA", 4, "PIEZAS", "NO. 2"),
    ("PLUMA PUNTO FINO", 19, "CAJA", "AZUL"),
    ("PLUMA TIPO GEL", 4, "CAJA", "AZUL"),
    ("PLUMA PUNTO FINO", 7, "CAJA", "NEGRO"),
    ("PLUMA TIPO GEL", 4, "CAJA", "NEGRO"),
    ("SOBRE MANILA", 4, "PAQUETES", "26 X 34 CM"),
    ("SOBRE MANILA", 4, "PAQUETES", "30.5 X 39.5 CM"),
    ("SOBRE MANILA", 2, "PAQUETES", "26 X 30.5 CM"),
    ("SOBRE COBRANZA", 1, "PAQUETES", "11.5 X 21.5 CM"),
    ("SOBRE BLANCO", 1, "PAQUETES", "MEDIA CARTA"),
    ("HOJA T/CARTA", 9, "CAJA", "-"),
    ("HOJA T/OFICIO", 5, "CAJA", "-"),
    ("HOJA T/OFICIO", 2, "PAQUETES", "PAQUETES SUELTOS")
]

with app.app_context():
    print(f"\n{'='*50}\n INICIANDO CARGA DE MATERIALES (ADMIN)\n{'='*50}")
    
    # 1. Obtener la categoría "Papelería"
    cat_papeleria = Categoria.query.filter_by(nombre="Papelería").first()
    if not cat_papeleria:
        print("❌ Error: No se encontró la categoría 'Papelería'. Asegúrate de haber corrido seed_produccion.py antes.")
        exit(1)
        
    nuevos = 0
    actualizados = 0
    
    # 2. Procesar e insertar los datos
    for articulo, cantidad, unidad, descripcion in DATOS:
        articulo = articulo.strip()
        descripcion = descripcion.strip()
        
        # Generar nombre combinado
        if descripcion and descripcion != "-":
            nombre_final = f"{articulo} ({descripcion})"
        else:
            nombre_final = articulo
            descripcion = "" # Limpiar el guión si lo había
            
        # Buscar si ya existe
        material = Material.query.filter_by(nombre=nombre_final).first()
        
        if not material:
            material = Material(
                nombre=nombre_final,
                descripcion=descripcion,
                unidad_medida=unidad.capitalize(),
                stock_actual=cantidad,
                stock_minimo=2,                 # Solicitado: 2
                id_categoria=cat_papeleria.id,
                publicado=True                  # Solicitado: Sí
            )
            db.session.add(material)
            print(f"✅ Creado: {nombre_final} (Stock: {cantidad})")
            nuevos += 1
        else:
            # Si ya existe, solo actualizamos el stock sumando o reemplazando
            # Para este caso, vamos a reemplazar el stock con el valor oficial actual
            material.stock_actual = cantidad
            material.stock_minimo = 2
            material.publicado = True
            print(f"🔄 Actualizado: {nombre_final} (Nuevo stock: {cantidad})")
            actualizados += 1
            
    db.session.commit()
    print(f"\n{'='*50}")
    print(f"  RESUMEN:")
    print(f"  Materiales nuevos creados:   {nuevos}")
    print(f"  Materiales actualizados:     {actualizados}")
    print(f"  Total procesados:            {len(DATOS)}")
    print(f"{'='*50}\n")
