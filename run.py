"""
run.py — Punto de entrada del Sistema de Inventarios Universitario
Uso:
    flask --app run init-db    # Inicializa la base de datos con seed
    flask --app run run        # Inicia el servidor de desarrollo
    python run.py              # Alternativa directa
"""
import os
from app import create_app
from app.extensions import db

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.cli.command('init-db')
def init_db():
    """Crea tablas y carga datos iniciales (seed)."""
    db.create_all()

    from app.models import Usuario, Departamento, Categoria, Proveedor

    # ── Admin por defecto ──────────────────────────────────────────────────
    if not Usuario.query.filter_by(rol='administrador').first():
        admin = Usuario(
            nombre_completo='Administrador del Sistema',
            email='admin@universidad.edu.mx',
            rol='administrador',
        )
        admin.set_password('Admin123!')   # Cambiar en producción
        db.session.add(admin)

    # ── Mantenimiento por defecto ──────────────────────────────────────────
    if not Usuario.query.filter_by(rol='mantenimiento').first():
        mante = Usuario(
            nombre_completo='Encargado de Bodega',
            email='mantenimiento@universidad.edu.mx',
            rol='mantenimiento',
        )
        mante.set_password('Mante123!')   # Cambiar en producción
        db.session.add(mante)

    # ── Categorías base ────────────────────────────────────────────────────
    cats = [
        ('Papelería',       'Hojas, folders, plumas, clips y similares'),
        ('Limpieza',        'Detergentes, escobas, trapeadores, papel higiénico'),
        ('Cómputo',         'Cables, memorias USB, cartuchos de tinta'),
        ('Mobiliario',      'Sillas, mesas, estantes de oficina'),
        ('Mantenimiento',   'Herramientas, pintura, materiales eléctricos'),
    ]
    cat_objs = {}
    for nombre, desc in cats:
        if not Categoria.query.filter_by(nombre=nombre).first():
            c = Categoria(nombre=nombre, descripcion=desc)
            db.session.add(c)
            db.session.flush()
        else:
            c = Categoria.query.filter_by(nombre=nombre).first()
        cat_objs[nombre] = c

    # ── Departamentos y permisos ───────────────────────────────────────────
    deptos_config = [
        ('Secretaría Académica',      'SEC-ACA', ['Papelería', 'Cómputo']),
        ('Dirección General',         'DIR-GEN', ['Papelería', 'Cómputo', 'Mobiliario']),
        ('Mantenimiento y Servicios', 'MANT',    ['Limpieza', 'Mantenimiento']),
        ('Recursos Humanos',          'RRHH',    ['Papelería']),
    ]
    for nombre, codigo, cats_permitidas in deptos_config:
        if not Departamento.query.filter_by(codigo=codigo).first():
            d = Departamento(nombre=nombre, codigo=codigo)
            for c_nombre in cats_permitidas:
                if c_nombre in cat_objs:
                    d.categorias.append(cat_objs[c_nombre])
            db.session.add(d)
            db.session.flush()

    # ── Proveedor de ejemplo ───────────────────────────────────────────────
    if not Proveedor.query.first():
        p = Proveedor(
            nombre='Papelería Central SA de CV',
            contacto='Lic. Ramírez',
            telefono='834-000-0001',
            email='ventas@papeleriacentral.com',
            rfc='PCE010101AAA',
        )
        db.session.add(p)

    db.session.commit()
    print('✓ Base de datos inicializada con datos de prueba.')
    print('  Admin: admin@universidad.edu.mx / Admin123!')


@app.cli.command('seed-trabajadores')
def seed_trabajadores():
    """Inserta el personal de mantenimiento desde el documento ÁREAS DEL PERSONAL ACTUAL."""
    from app.models import Trabajador

    plantilla = [
        # (nombre, cargo, area, turno)
        # ── Turno Matutino ─── Intendencia ────────────────────────────────
        ("Blanco Bautista Eduardo",             "Intendente",          "Plazoleta, Canchas de Uso Múltiples",                                "Matutino"),
        ("Wilfrido Chávez",                     "Intendente",          "Salones 300-306, Pasillos 300, Escaleras",                           "Matutino"),
        ("Camacho Ledezma Francisco",           "Intendente",          "Nave Edificio A y Edificio B",                                       "Matutino"),
        ("Elia Hernández",                      "Intendente",          "Centro de Cómputo, Biblioteca",                                      "Matutino"),
        ("Flores Becerra Silvia",               "Intendente",          "Baños Mujeres 200 y 400, Baños Hombres Casa",                        "Matutino"),
        ("Nájera Gutiérrez Rosa Isela",         "Intendente",          "Salones 101-105, Baños Mujeres 100, Escolares, Salón Nuevo/Serv. Social", "Matutino"),
        ("Pascual Sandra",                      "Intendente",          "Sala de Maestros, Pasillos Exámenes Profesionales, Áreas sin uso",   "Matutino"),
        ("Rodríguez Quintero Concepción",       "Intendente",          "Posgrado",                                                           "Matutino"),
        ("Rodríguez Quintero José Luis",        "Intendente",          "Salones 200, Pasillos 200",                                          "Matutino"),
        ("Tobías Niño Margarita",               "Intendente",          "Dirección, Escaleras y Exámenes Profesionales",                      "Matutino"),
        ("Nora Salazar",                        "Intendente",          "Laboratorio de Materiales",                                          "Matutino"),
        ("Vega Espinosa Juan Pedro",            "Intendente",          "Salones 106-115, Laboratorios de Investigación",                     "Matutino"),
        ("María de Jesús de León",              "Intendente",          "Salones 400, Baños Hombres 400, Pasillo 400",                        "Matutino"),
        # ── Turno Matutino ─── Técnicos y especialistas ───────────────────
        ("Juan Saucedo",                        "Albañil",             "General",                                                            "Matutino"),
        ("Martín Corona",                       "Electricista",        "General",                                                            "Matutino"),
        ("Pablo Castillo",                      "Jardinero",           "General",                                                            "Matutino"),
        ("Armando Becerra",                     "Jardinero",           "General",                                                            "Matutino"),
        ("Alberto Azuara",                      "Técnico en Climas",   "General",                                                            "Matutino"),
        ("Antonio del Ángel",                   "Técnico en Bombas",   "General",                                                            "Matutino"),
        # ── Turno Vespertino ─── Intendencia ──────────────────────────────
        ("Aguilar Lugo Jesús Antonio",          "Intendente",          "Salones 207-212, Salón Nuevo, 101-105",                              "Vespertino"),
        ("Wendy Peña",                          "Intendente",          "Salones 407-412, Pasillos Auditorio, Escolares, 304-306",            "Vespertino"),
        ("Del Ángel Alvarado Yazmín Elizabeth", "Intendente",          "Dirección, Sala de Maestros y Exámenes Profesionales",               "Vespertino"),
        ("Flores Terán Karina",                 "Intendente",          "Salones 106-115, Tutorías, Cómputo, Psicología, Laboratorios",       "Vespertino"),
        ("De León Georgina",                    "Intendente",          "Biblioteca, Baños Mujeres 100 y 200, Baños Hombres 400",             "Vespertino"),
        ("Díaz Linda",                          "Intendente",          "Salones 201-206, 300-303, 401-406, Baños de Hombres Casa",           "Vespertino"),
        ("Juárez Casados Celina Concepción",    "Intendente",          "Salones 101-105, Salón Nuevo, Salones 208-212, Pasillo",             "Vespertino"),
        ("Reyes López Jonathan Ulises",         "Intendente",          "Salones 307-315, Pasillo, Salón 115",                                "Vespertino"),
        ("Victoria Elizalde",                   "Intendente",          "Laboratorios Nave Experimental Edif. C / Baños",                     "Vespertino"),
        ("Alberto Alvarado",                    "Intendente",          "Laboratorios Nave Experimental Edif. A",                             "Vespertino"),
    ]

    insertados = 0
    saltados   = 0
    for nombre, cargo, area, turno in plantilla:
        existe = Trabajador.query.filter_by(nombre=nombre).first()
        if existe:
            print(f"  SKIP: {nombre}")
            saltados += 1
            continue
        t = Trabajador(
            nombre  = nombre,
            cargo   = cargo,
            area    = f"{area} — Turno {turno}",
            activo  = True,
        )
        db.session.add(t)
        print(f"  + {cargo:<25} {nombre}")
        insertados += 1

    db.session.commit()
    print(f"\n✓ Insertados: {insertados}  |  Ya existían: {saltados}")
    total = Trabajador.query.count()
    print(f"✓ Total trabajadores en BD: {total}")

    from sqlalchemy import text
    db.session.execute(text(
        "SELECT setval(pg_get_serial_sequence('\"Trabajadores\"', 'id'), "
        "(SELECT MAX(id) FROM \"Trabajadores\"), true)"
    ))
    db.session.commit()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
