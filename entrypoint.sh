#!/bin/sh
set -e

echo "=== Inventario FIT ==="
echo "PORT=${PORT}"
echo "FLASK_ENV=${FLASK_ENV}"

# ── Diagnóstico de conexión Supabase (temporal) ──
if [ "${SUPABASE_DIAG}" = "1" ]; then
  echo "=== DIAGNÓSTICO SUPABASE ==="
  python3 -c "
import psycopg2, socket

project = 'ymsghappylhjhayiklpe'
password = 'gAnveg-fujxy6-mazhid'

# Test direct connection
print('--- Direct connection ---')
try:
    host = 'db.' + project + '.supabase.co'
    ips = socket.getaddrinfo(host, 5432)
    for ip in ips[:3]:
        print(f'  Resolved: {ip[4]}')
    conn = psycopg2.connect(f'postgresql://postgres:{password}@{host}:5432/postgres', connect_timeout=5)
    print('  DIRECT: OK')
    conn.close()
except Exception as e:
    print(f'  DIRECT: {str(e)[:120]}')

# Test pooler regions
print('--- Pooler connections ---')
regions = [
    'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
    'eu-west-1', 'eu-west-2', 'eu-central-1',
    'ap-southeast-1', 'ap-northeast-1',
    'sa-east-1', 'ca-central-1'
]
for region in regions:
    host = f'aws-0-{region}.pooler.supabase.com'
    url = f'postgresql://postgres.{project}:{password}@{host}:5432/postgres'
    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        print(f'  {region}: OK <<<')
        conn.close()
    except Exception as e:
        msg = str(e).strip().split(chr(10))[0][:80]
        print(f'  {region}: {msg}')

# Also test port 6543 for transaction pooler on us-east-1
print('--- Transaction pooler (port 6543) ---')
for region in regions[:4]:
    host = f'aws-0-{region}.pooler.supabase.com'
    url = f'postgresql://postgres.{project}:{password}@{host}:6543/postgres'
    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        print(f'  {region}:6543: OK <<<')
        conn.close()
    except Exception as e:
        msg = str(e).strip().split(chr(10))[0][:80]
        print(f'  {region}:6543: {msg}')
  "
  echo "=== FIN DIAGNÓSTICO ==="
fi

flask --app run init-db

echo "=== Arrancando Gunicorn en 0.0.0.0:${PORT:-8080} ==="
exec gunicorn \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers 1 \
  --timeout 120 \
  --log-level info \
  --access-logfile - \
  --error-logfile - \
  run:app
