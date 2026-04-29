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
            nombre_completo='Jefe de Pañol',
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
