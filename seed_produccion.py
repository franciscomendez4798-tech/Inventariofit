"""
seed_produccion.py
==================
Script maestro para cargar TODOS los datos iniciales en PythonAnywhere.
Corre SOLO UNA VEZ después de init-db.

Uso en la consola Bash de PythonAnywhere:
    cd ~/inventario_universitario
    ~/.virtualenvs/inventario_venv/bin/python3.10 seed_produccion.py
"""
import os, warnings
from dotenv import load_dotenv

load_dotenv('.env')
os.environ['FLASK_ENV'] = 'production'
warnings.filterwarnings('ignore')

from app import create_app
from app.extensions import db
from app.models import Usuario, Departamento, Categoria, Area, Trabajador

app = create_app('production')

# ─────────────────────────────────────────────────────────────────────────────
def ok(msg):   print(f'  ✅ {msg}')
def skip(msg): print(f'  ⏭  {msg} (ya existe)')
def seccion(msg): print(f'\n{"─"*55}\n  {msg}\n{"─"*55}')
# ─────────────────────────────────────────────────────────────────────────────

with app.app_context():

    # ══════════════════════════════════════════════════════════════════════════
    # 1. CATEGORÍAS BASE
    # ══════════════════════════════════════════════════════════════════════════
    seccion('1. Categorías base')
    categorias_data = [
        ('Papelería',     'Hojas, folders, plumas, clips y similares'),
        ('Limpieza',      'Detergentes, escobas, trapeadores, papel higiénico'),
        ('Cómputo',       'Cables, memorias USB, cartuchos de tinta'),
        ('Mobiliario',    'Sillas, mesas, estantes de oficina'),
        ('Mantenimiento', 'Herramientas, pintura, materiales eléctricos'),
        ('Laboratorio',   'Materiales y reactivos para laboratorios'),
        ('Audiovisual',   'Equipos de sonido, proyectores y accesorios'),
    ]
    cats = {}
    for nombre, desc in categorias_data:
        obj = Categoria.query.filter_by(nombre=nombre).first()
        if not obj:
            obj = Categoria(nombre=nombre, descripcion=desc)
            db.session.add(obj)
            db.session.flush()
            ok(f'Categoría: {nombre}')
        else:
            skip(f'Categoría: {nombre}')
        cats[nombre] = obj
    db.session.commit()

    # ══════════════════════════════════════════════════════════════════════════
    # 2. DEPARTAMENTOS REALES DE LA FACULTAD
    # ══════════════════════════════════════════════════════════════════════════
    seccion('2. Departamentos reales de la Facultad')
    # (nombre, codigo, [categorias_permitidas])
    deptos_data = [
        ('Biblioteca',                   'BIBL',     ['Papelería', 'Cómputo']),
        ('Calidad',                      'CALID',    ['Papelería']),
        ('Contabilidad',                 'CONT',     ['Papelería', 'Cómputo']),
        ('Coordinación de Carrera IISCA','CORIIS',   ['Papelería', 'Cómputo', 'Mobiliario']),
        ('Desarrollo Institucional',     'DESINT',   ['Papelería', 'Cómputo']),
        ('Dirección General',            'DIR',      ['Papelería', 'Cómputo', 'Mobiliario']),
        ('Escolares',                    'ESCOL',    ['Papelería', 'Cómputo']),
        ('Intendencia y Mantenimiento',  'INTMANT',  ['Limpieza', 'Mantenimiento']),
        ('Secretaría Académica',         'SECAC',    ['Papelería', 'Cómputo']),
        ('Centro de Cómputo',            'COMPUTO',  ['Cómputo', 'Papelería']),
        ('Exámenes Estandarizados',      'EXAMENES', ['Papelería', 'Cómputo']),
        ('Laboratorio de Hidráulica',    'LAB-HID',  ['Laboratorio', 'Mantenimiento']),
        ('Laboratorio de Física',        'LAB-FIS',  ['Laboratorio', 'Mantenimiento']),
        ('Laboratorio de Ergonomía',     'LAB-ERG',  ['Laboratorio', 'Mobiliario']),
        ('Laboratorio de Manufactura',   'LAB-MAN',  ['Laboratorio', 'Mantenimiento']),
        ('Laboratorio de Electrónica',   'LAB-ELEC', ['Laboratorio', 'Cómputo']),
        ('Laboratorio de Materiales',    'LAB-MAT',  ['Laboratorio', 'Mantenimiento']),
        ('Laboratorio de Química',       'LAB-QUI',  ['Laboratorio', 'Limpieza']),
        ('Nave Experimental',            'NAVE',     ['Mantenimiento', 'Laboratorio']),
        ('Planeación',                   'PLAN',     ['Papelería', 'Cómputo']),
        ('Posgrado',                     'POSG',     ['Papelería', 'Cómputo', 'Laboratorio']),
        ('Promoción y Captación',        'PROMO',    ['Papelería', 'Cómputo', 'Audiovisual']),
        ('Psicología',                   'PSIC',     ['Papelería', 'Cómputo']),
        ('Secretaría Administrativa',    'SEC-ADM',  ['Papelería', 'Cómputo', 'Mobiliario']),
        ('Secretaría Técnica',           'SEC-TEC',  ['Papelería', 'Cómputo']),
        ('Servicio Social',              'SERVSOC',  ['Papelería']),
        ('Titulación',                   'TITUL',    ['Papelería', 'Cómputo']),
        ('Tutorías',                     'TUTOR',    ['Papelería', 'Cómputo']),
        ('Valores',                      'VALORES',  ['Papelería']),
        ('Vinculación',                  'VINCUL',   ['Papelería', 'Cómputo', 'Audiovisual']),
        # Departamentos genéricos del sistema
        ('Mantenimiento y Servicios',    'MANT',     ['Limpieza', 'Mantenimiento']),
        ('Recursos Humanos',             'RRHH',     ['Papelería']),
    ]
    deptos = {}
    for nombre, codigo, cat_names in deptos_data:
        obj = Departamento.query.filter_by(codigo=codigo).first()
        if not obj:
            obj = Departamento(nombre=nombre, codigo=codigo)
            for c_nombre in cat_names:
                if c_nombre in cats:
                    obj.categorias.append(cats[c_nombre])
            db.session.add(obj)
            ok(f'Depto: {codigo} — {nombre}')
        else:
            skip(f'Depto: {codigo}')
        deptos[codigo] = obj
    db.session.commit()

    # ══════════════════════════════════════════════════════════════════════════
    # 3. ÁREAS FÍSICAS (para asignar a trabajadores)
    # ══════════════════════════════════════════════════════════════════════════
    seccion('3. Áreas físicas del campus')
    areas_nombres = [
        'Plazoleta y Canchas de Uso Múltiples',
        'Salones 300-306, Pasillos 300, Escaleras',
        'Nave Edificio A y Edificio B',
        'Centro de Cómputo y Biblioteca',
        'Baños Mujeres 200 y 400, Baños Hombres Casa',
        'Salones 101-105, Baños Mujeres 100, Escolares',
        'Sala de Maestros, Exámenes Profesionales',
        'Posgrado',
        'Salones 200, Pasillos 200',
        'Dirección, Escaleras, Exámenes Profesionales',
        'Laboratorio de Materiales',
        'Salones 106-115, Laboratorios de Investigación',
        'Salones 400, Baños Hombres 400, Pasillo 400',
        'General — Albañilería',
        'General — Electricidad',
        'General — Jardinería',
        'General — Climas (A/C)',
        'General — Bombas',
        'Salones 207-212, Salón Nuevo, 101-105',
        'Salones 407-412, Pasillos, Auditorio, Escolares',
        'Laboratorios Nave Experimental Edificio C',
        'Laboratorios Nave Experimental Edificio A',
        'Salones 201-206, 300-303, 401-406',
        'Salones 101-105, 208-212, Pasillo',
        'Salones 307-315, Pasillo, Salón 115',
        'Biblioteca, Baños Mujeres 100 y 200',
    ]
    areas_obj = {}
    for nombre in areas_nombres:
        obj = Area.query.filter_by(nombre=nombre).first()
        if not obj:
            obj = Area(nombre=nombre)
            db.session.add(obj)
            ok(f'Área: {nombre[:55]}')
        else:
            skip(f'Área: {nombre[:55]}')
        areas_obj[nombre] = obj
    db.session.commit()

    # ══════════════════════════════════════════════════════════════════════════
    # 4. TRABAJADORES DE MANTENIMIENTO E INTENDENCIA
    # ══════════════════════════════════════════════════════════════════════════
    seccion('4. Trabajadores de Mantenimiento e Intendencia')
    # (nombre, cargo, turno, [areas])
    trabajadores_data = [
        # ── Turno Matutino — Intendencia ──────────────────────────────────────
        ('Blanco Bautista Eduardo',             'Intendente',        'matutino',   ['Plazoleta y Canchas de Uso Múltiples']),
        ('Wilfrido Chávez',                     'Intendente',        'matutino',   ['Salones 300-306, Pasillos 300, Escaleras']),
        ('Camacho Ledezma Francisco',           'Intendente',        'matutino',   ['Nave Edificio A y Edificio B']),
        ('Elia Hernández',                      'Intendente',        'matutino',   ['Centro de Cómputo y Biblioteca']),
        ('Flores Becerra Silvia',               'Intendente',        'matutino',   ['Baños Mujeres 200 y 400, Baños Hombres Casa']),
        ('Nájera Gutiérrez Rosa Isela',         'Intendente',        'matutino',   ['Salones 101-105, Baños Mujeres 100, Escolares']),
        ('Pascual Sandra',                      'Intendente',        'matutino',   ['Sala de Maestros, Exámenes Profesionales']),
        ('Rodríguez Quintero Concepción',       'Intendente',        'matutino',   ['Posgrado']),
        ('Rodríguez Quintero José Luis',        'Intendente',        'matutino',   ['Salones 200, Pasillos 200']),
        ('Tobías Niño Margarita',               'Intendente',        'matutino',   ['Dirección, Escaleras, Exámenes Profesionales']),
        ('Nora Salazar',                        'Intendente',        'matutino',   ['Laboratorio de Materiales']),
        ('Vega Espinosa Juan Pedro',            'Intendente',        'matutino',   ['Salones 106-115, Laboratorios de Investigación']),
        ('María de Jesús de León',              'Intendente',        'matutino',   ['Salones 400, Baños Hombres 400, Pasillo 400']),
        # ── Turno Matutino — Técnicos ─────────────────────────────────────────
        ('Juan Saucedo',                        'Albañil',           'matutino',   ['General — Albañilería']),
        ('Martín Corona',                       'Electricista',      'matutino',   ['General — Electricidad']),
        ('Pablo Castillo',                      'Jardinero',         'matutino',   ['General — Jardinería']),
        ('Armando Becerra',                     'Jardinero',         'matutino',   ['General — Jardinería']),
        ('Alberto Azuara',                      'Técnico en Climas', 'matutino',   ['General — Climas (A/C)']),
        ('Antonio del Ángel',                   'Técnico en Bombas', 'matutino',   ['General — Bombas']),
        # ── Turno Vespertino — Intendencia ────────────────────────────────────
        ('Aguilar Lugo Jesús Antonio',          'Intendente',        'vespertino', ['Salones 207-212, Salón Nuevo, 101-105']),
        ('Wendy Peña',                          'Intendente',        'vespertino', ['Salones 407-412, Pasillos, Auditorio, Escolares']),
        ('Del Ángel Alvarado Yazmín Elizabeth', 'Intendente',        'vespertino', ['Dirección, Escaleras, Exámenes Profesionales']),
        ('Flores Terán Karina',                 'Intendente',        'vespertino', ['Salones 106-115, Laboratorios de Investigación']),
        ('De León Georgina',                    'Intendente',        'vespertino', ['Biblioteca, Baños Mujeres 100 y 200']),
        ('Díaz Linda',                          'Intendente',        'vespertino', ['Salones 201-206, 300-303, 401-406']),
        ('Juárez Casados Celina Concepción',    'Intendente',        'vespertino', ['Salones 101-105, 208-212, Pasillo']),
        ('Reyes López Jonathan Ulises',         'Intendente',        'vespertino', ['Salones 307-315, Pasillo, Salón 115']),
        ('Victoria Elizalde',                   'Intendente',        'vespertino', ['Laboratorios Nave Experimental Edificio C']),
        ('Alberto Alvarado',                    'Intendente',        'vespertino', ['Laboratorios Nave Experimental Edificio A']),
    ]

    for nombre, cargo, turno, area_names in trabajadores_data:
        obj = Trabajador.query.filter_by(nombre=nombre).first()
        if not obj:
            obj = Trabajador(nombre=nombre, cargo=cargo, turno=turno, activo=True)
            obj.areas = [areas_obj[a] for a in area_names if a in areas_obj]
            obj.area  = ', '.join(area_names)   # legacy string
            db.session.add(obj)
            ok(f'Trabajador: {nombre}')
        else:
            skip(f'Trabajador: {nombre}')
    db.session.commit()

    # ══════════════════════════════════════════════════════════════════════════
    # 5. USUARIOS SOLICITANTES
    # ══════════════════════════════════════════════════════════════════════════
    seccion('5. Usuarios solicitantes')
    # (nombre_completo, email, password, codigo_depto)
    usuarios_data = [
        ('MARTINEZ MANZANO SERGIO JAVIER',      'bibl@inventariofit.uat.mx',    '8BSq-D2Uv-f3Rp', 'BIBL'),
        ('GONZALEZ TURRUBIATES ALEJANDRO',      'calid@inventariofit.uat.mx',   'xC4M-KvYN-g9rg', 'CALID'),
        ('VALENZUELA FERNANDEZ JOSE RAUL',      'cont@inventariofit.uat.mx',    'HUxc-p55k-nuh9', 'CONT'),
        ('LOREDO HERNANDEZ CARLOS ALFREDO',     'coriis@inventariofit.uat.mx',  'Wn9A-quNp-arzE', 'CORIIS'),
        ('BERMEA BARRIOS JUAN ENRIQUE',         'desint@inventariofit.uat.mx',  'YJWA-32yN-5MvQ', 'DESINT'),
        ('PICHARDO RAMIREZ ROBERTO',            'dirfit@inventariofit.uat.mx',  'pBwg-pjaV-UJ5K', 'DIR'),
        ('PEREZ COBOS JULISA',                  'escol@inventariofit.uat.mx',   'e3Pb-Qm3F-pPCf', 'ESCOL'),
        ('AYALA PIÑEYRO ENRIQUE',               'intmant@inventariofit.uat.mx', 'tzTw-AdJU-ugHz', 'INTMANT'),
        ('TOBIAS JARAMILLO RICARDO',            'secac@inventariofit.uat.mx',   'jSmT-932q-VnQu', 'SECAC'),
        ('HERNANDEZ MARTINEZ GERARDO',          '309178@inventariofit.uat.mx',  'xp83-yxvJ-2Ctq', 'CONT'),
        ('ALVAREZ NAVARRO EDUARDO',             '121060@inventariofit.uat.mx',  'Hmjw-rM8d-YZFq', 'CORIIS'),
        ('MARTINEZ GARCIA MARIA ELENA',         '300307@inventariofit.uat.mx',  'abqZ-TdyP-HFkx', 'CORIIS'),
        ('OLIVERA ZURA ANGEL FRANCISCO',        '300195@inventariofit.uat.mx',  'bXac-gyXc-bSZb', 'CORIIS'),
        ('ZAVALA GUERRERO LUIS ALVARO',         '121273@inventariofit.uat.mx',  '5Kgr-M8Jj-cHGx', 'CORIIS'),
        ('TREVIÑO HERNANDEZ RAUL',              '121056@inventariofit.uat.mx',  'n9XC-AbeR-FnCm', 'CORIIS'),
        ('GARCIA RUIZ ALEJANDRO HUMBERTO',      '305479@inventariofit.uat.mx',  '95yk-zJPb-zYK3', 'CORIIS'),
        ('MARTINEZ NAVARRO JOSE LUIS',          '121286@inventariofit.uat.mx',  'gCMb-qGdW-MUEz', 'SEC-ADM'),
        ('MONTOTO GONZALEZ ADRIANA',            '121724@inventariofit.uat.mx',  'KGCW-csBz-kmDN', 'COMPUTO'),
        ('FERNANDEZ IZAGUIRRE PAULINA',         '307178@inventariofit.uat.mx',  'Ax4X-vmxz-NZHt', 'EXAMENES'),
        ('GALINDO LOPEZ RUTH DEL CARMEN',       '304318@inventariofit.uat.mx',  'MfAP-GDZk-ZnrA', 'LAB-HID'),
        ('FUENTES CASTRO JUAN ANGEL',           '305470@inventariofit.uat.mx',  'JmX9-ygPs-pc8g', 'LAB-FIS'),
        ('GAMBOA SOTO FEDERICO',                '109284@inventariofit.uat.mx',  '6vGG-fnrh-kfnD', 'LAB-ERG'),
        ('GONZALEZ TURRUBIATES JOSE GABRIEL',   '109983@inventariofit.uat.mx',  'RWkq-3xaJ-hhwZ', 'LAB-MAN'),
        ('CASTAN ROCHA EMILIO',                 '120047@inventariofit.uat.mx',  'Mrek-SynJ-Sq8K', 'LAB-ELEC'),
        ('LOPEZ LEDEZMA ARMANDO',               '109774@inventariofit.uat.mx',  '76Q3-fCMJ-rfh8', 'LAB-MAT'),
        ('TOLEDO BARAJAS LEONOR',               '122281@inventariofit.uat.mx',  'BYMm-KkNP-7wKa', 'LAB-QUI'),
        ('MORENO RAMOS DAVID ANGEL',            '121274@inventariofit.uat.mx',  'mjDV-Buc5-FaXQ', 'NAVE'),
        ('ROLON AGUILAR ELVIRA',                '121213@inventariofit.uat.mx',  'Aqyc-MDHr-UrQM', 'PLAN'),
        ('CASTAN ROCHA JOSE ANTONIO',           '120331@inventariofit.uat.mx',  'tjtJ-YqFQ-fJhk', 'POSG'),
        ('VARGAS CASTILLEJA ROCIO DEL CARMEN',  '301658@inventariofit.uat.mx',  'WdYF-8qmk-vxRV', 'POSG'),
        ('HERNANDEZ BOETA ANA SOFIA',           '309418@inventariofit.uat.mx',  'qHwH-Cxyb-wNkF', 'PROMO'),
        ('JIMENEZ HERNANDEZ ESMERALDA',         '306523@inventariofit.uat.mx',  'dUQU-VsZs-jSjV', 'PSIC'),
        ('AZUARA HERNANDEZ MARCOS ALFREDO',     '121140@inventariofit.uat.mx',  'fvDQ-FdeP-3JGw', 'SEC-ADM'),
        ('BARRAGAN RAMIREZ RODOLFO',            '120972@inventariofit.uat.mx',  'bUB3-GRYP-5BGA', 'SEC-TEC'),
        ('HERNANDEZ REJON ROSA MARIA',          '121884@inventariofit.uat.mx',  'dVyX-Mmr6-U3nc', 'SERVSOC'),
        ('HURTADO MORA HYASSELINY ALEJANDRA',   '300476@inventariofit.uat.mx',  'euVr-7A88-7dtx', 'TITUL'),
        ('MONGEYIP VELA MONICA',                '121062@inventariofit.uat.mx',  '5EG8-rMd9-bMvF', 'TUTOR'),
        ('MONICA DUBHE AGUILAR RODRIGUEZ',      '122316@inventariofit.uat.mx',  'A42Y-QJhu-phsm', 'VALORES'),
        ('TREVIÑO TRUJILLO JUANA',              '120514@inventariofit.uat.mx',  'efda-cBZY-uX7Z', 'VINCUL'),
    ]

    for nombre, email, password, depto_codigo in usuarios_data:
        obj = Usuario.query.filter_by(email=email).first()
        if not obj:
            depto = deptos.get(depto_codigo)
            obj = Usuario(
                nombre_completo=nombre,
                email=email,
                rol='solicitante',
                activo=True,
                id_departamento=depto.id if depto else None
            )
            obj.set_password(password)
            db.session.add(obj)
            ok(f'Usuario: {email}')
        else:
            skip(f'Usuario: {email}')
    db.session.commit()

    # ══════════════════════════════════════════════════════════════════════════
    # RESUMEN FINAL
    # ══════════════════════════════════════════════════════════════════════════
    print(f'\n{"═"*55}')
    print('  RESUMEN FINAL')
    print(f'{"═"*55}')
    print(f'  Categorías:   {Categoria.query.count()}')
    print(f'  Departamentos:{Departamento.query.count()}')
    print(f'  Áreas:        {Area.query.count()}')
    print(f'  Trabajadores: {Trabajador.query.count()}')
    print(f'  Usuarios:     {Usuario.query.count()}')
    print(f'\n  ✅ Seed completado. El sistema está listo.\n')
