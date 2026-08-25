#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# setup_pythonanywhere.sh
# Script de instalación automática para PythonAnywhere
#
# USO: Corre este script desde la consola Bash de PythonAnywhere:
#   cd ~
#   bash inventario_universitario/setup_pythonanywhere.sh
# ══════════════════════════════════════════════════════════════════════════════

set -e

# ── Colores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║    Setup — Sistema de Inventarios FING               ║${NC}"
echo -e "${BLUE}║    PythonAnywhere Deployment                         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Detectar usuario de PythonAnywhere ───────────────────────────────────────
PA_USER=$(whoami)
PROJECT_DIR="/home/${PA_USER}/inventario_universitario"
VENV_DIR="/home/${PA_USER}/.virtualenvs/inventario_venv"

echo -e "${YELLOW}Usuario detectado:${NC} $PA_USER"
echo -e "${YELLOW}Proyecto en:${NC}       $PROJECT_DIR"
echo -e "${YELLOW}Virtualenv en:${NC}     $VENV_DIR"
echo ""

# ── 1. Verificar que el proyecto está clonado ─────────────────────────────────
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ No se encontró el directorio del proyecto.${NC}"
    echo "   Primero clona el repositorio:"
    echo "   git clone https://github.com/TU_USUARIO/inventario_universitario.git ~/inventario_universitario"
    exit 1
fi
echo -e "${GREEN}✅ Directorio del proyecto encontrado${NC}"

# ── 2. Crear virtualenv con Python 3.10 (compatible con PythonAnywhere Free) ──
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "▶ Creando entorno virtual con Python 3.10..."
    python3.10 -m venv "$VENV_DIR"
    echo -e "${GREEN}✅ Virtualenv creado${NC}"
else
    echo -e "${GREEN}✅ Virtualenv ya existe${NC}"
fi

# ── 3. Instalar dependencias ──────────────────────────────────────────────────
echo ""
echo "▶ Instalando dependencias (puede tomar 2-3 minutos)..."
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt" --quiet
echo -e "${GREEN}✅ Dependencias instaladas${NC}"

# ── 4. Crear directorio instance si no existe ─────────────────────────────────
mkdir -p "$PROJECT_DIR/instance"
echo -e "${GREEN}✅ Directorio instance/ listo${NC}"

# ── 5. Inicializar base de datos ──────────────────────────────────────────────
echo ""
echo "▶ Inicializando base de datos SQLite..."
cd "$PROJECT_DIR"
"$VENV_DIR/bin/python3.10" -c "
from dotenv import load_dotenv
load_dotenv('.env')
import os
os.environ['FLASK_ENV'] = 'production'
from app import create_app
from app.extensions import db
app = create_app('production')
with app.app_context():
    db.create_all()
    print('  Tablas creadas/verificadas correctamente')
"
echo -e "${GREEN}✅ Base de datos inicializada${NC}"

# ── 6. Actualizar pythonanywhere_wsgi.py con el usuario correcto ──────────────
echo ""
echo "▶ Configurando archivo WSGI con usuario '$PA_USER'..."
WSGI_FILE="$PROJECT_DIR/pythonanywhere_wsgi.py"
# Reemplazar TU_USUARIO por el usuario real
sed -i "s/TU_USUARIO/$PA_USER/g" "$WSGI_FILE"
echo -e "${GREEN}✅ WSGI configurado${NC}"

# ── 7. Verificar configuración ────────────────────────────────────────────────
echo ""
echo "▶ Verificando que la app inicia correctamente..."
cd "$PROJECT_DIR"
FLASK_ENV=production "$VENV_DIR/bin/python" -c "
import os
os.environ['FLASK_ENV'] = 'production'
from dotenv import load_dotenv
load_dotenv('.env')
from app import create_app
app = create_app('production')
print('  App name:', app.name)
print('  DB URI:', app.config['SQLALCHEMY_DATABASE_URI'][:60])
" && echo -e "${GREEN}✅ App inicia correctamente${NC}" || {
    echo -e "${RED}❌ Error al iniciar la app. Revisa los logs arriba.${NC}"
    exit 1
}

# ── 8. Resumen final ──────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 Setup completado exitosamente!${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}PASOS FINALES (en el panel web de PythonAnywhere):${NC}"
echo ""
echo "  1. Ve a: Web → Add a new web app"
echo "     → Manual configuration → Python 3.10"
echo ""
echo "  2. En 'Code' configura:"
echo "     Source code: $PROJECT_DIR"
echo "     Working dir: $PROJECT_DIR"
echo ""
echo "  3. En 'Virtualenv' escribe:"
echo "     $VENV_DIR"
echo ""
echo "  4. En 'WSGI configuration file' reemplaza TODO el contenido con:"
echo "     el contenido de: $WSGI_FILE"
echo ""
echo "  5. Haz clic en 'Reload' (botón verde grande)"
echo ""
echo "  6. Tu app estará en: https://${PA_USER}.pythonanywhere.com"
echo ""
