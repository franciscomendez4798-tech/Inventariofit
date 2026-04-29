#!/bin/bash
# ================================================================
#  deploy_railway.sh — Despliega el sistema a Railway.app
#  Ejecutar desde terminal: bash deploy_railway.sh
# ================================================================

RAILWAY=~/.local/bin/railway

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Inventario FIT → Railway.app"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Login (abre navegador)
echo ""
echo "PASO 1: Iniciando sesión en Railway..."
$RAILWAY login

# 2. Crear proyecto o enlazar existente
echo ""
echo "PASO 2: Inicializando proyecto Railway..."
$RAILWAY init

# 3. Configurar variables de entorno en Railway
echo ""
echo "PASO 3: Configurando variables de entorno..."
$RAILWAY variables set \
  SECRET_KEY="inv-fing-2026-secretkey-produccion" \
  FLASK_ENV="production" \
  DATABASE_URL="postgresql://postgres:gAnveg-fujxy6-mazhid@db.ymsghappylhjhayiklpe.supabase.co:5432/postgres"

# 4. Desplegar
echo ""
echo "PASO 4: Desplegando... (puede tardar 2-3 minutos)"
$RAILWAY up --detach

echo ""
echo "✓ Despliegue iniciado. Para ver la URL pública:"
echo "  $RAILWAY status"
echo "  $RAILWAY open"
