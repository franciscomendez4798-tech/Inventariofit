# ══════════════════════════════════════════════════════════════════════════════
# pythonanywhere_wsgi.py
#
# INSTRUCCIONES DE USO EN PYTHONANYWHERE:
# ─────────────────────────────────────────────────────────────────────────────
# 1. En el panel web de PythonAnywhere:
#    Web → Add a new web app → Manual configuration → Python 3.10
#
# 2. Copia el CONTENIDO de este archivo al editor WSGI de PythonAnywhere:
#    Web → (tu app) → WSGI configuration file → clic en el enlace del archivo
#
# 3. IMPORTANTE: cambia TODAS las ocurrencias de 'TU_USUARIO' por
#    tu nombre de usuario real de PythonAnywhere.
#
# 4. Guarda y recarga la app desde el panel (botón "Reload").
# ══════════════════════════════════════════════════════════════════════════════

import sys
import os

# ── Ruta del proyecto ─────────────────────────────────────────────────────────
# PythonAnywhere almacena los proyectos en /home/TU_USUARIO/
PROJECT_DIR = '/home/TU_USUARIO/inventario_universitario'

# ── Añadir el proyecto al path de Python ─────────────────────────────────────
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# ── Activar el entorno virtual ────────────────────────────────────────────────
# PythonAnywhere recomienda usar virtualenv para aislar dependencias.
VENV_DIR = '/home/TU_USUARIO/.virtualenvs/inventario_venv'
activate_this = os.path.join(VENV_DIR, 'bin', 'activate_this.py')
if os.path.exists(activate_this):
    with open(activate_this) as f:
        exec(f.read(), {'__file__': activate_this})

# ── Variables de entorno ──────────────────────────────────────────────────────
# PythonAnywhere no tiene panel para env vars como Render/Heroku,
# por eso las cargamos desde el archivo .env del proyecto.
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

# Forzar entorno de producción
os.environ.setdefault('FLASK_ENV', 'production')

# ── Crear la aplicación Flask ─────────────────────────────────────────────────
from app import create_app

application = create_app('production')

# PythonAnywhere espera la variable 'application' (estándar WSGI/PEP 3333)
# gunicorn y Render usan 'app' — aquí necesitamos 'application'
app = application
