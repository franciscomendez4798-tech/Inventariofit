# 📦 Sistema de Control y Registro de Inventarios
### Secretaría Administrativa Universitaria

Sistema web desarrollado en **Python + Flask** para la gestión de inventarios,
solicitudes de insumos y control de gastos por departamento.

---

## Índice

1. [Características](#características)
2. [Stack tecnológico](#stack-tecnológico)
3. [Estructura del proyecto](#estructura-del-proyecto)
4. [Instalación local](#instalación-local)
5. [Despliegue con Docker](#despliegue-con-docker)
6. [Credenciales por defecto](#credenciales-por-defecto)
7. [Módulos del sistema](#módulos-del-sistema)
8. [Modelo de base de datos](#modelo-de-base-de-datos)
9. [Tests](#tests)
10. [Variables de entorno](#variables-de-entorno)

---

## Características

| Módulo | Descripción |
|--------|-------------|
| **RBAC** | Roles `administrador` y `solicitante` con rutas totalmente separadas |
| **Catálogo filtrado** | Solicitante solo ve materiales de las categorías permitidas a su departamento |
| **Carrito de pedidos** | Interfaz tipo carrito con offcanvas, sin recargar la página |
| **Aprobación inteligente** | El admin ve alertas SQL en tiempo real: *"este departamento pidió X unidades hace N días"* |
| **Bitácora de movimientos** | Toda entrada/salida queda registrada para auditoría y dashboard |
| **Dashboard de gastos** | Endpoint `/api/dashboard` → JSON listo para Chart.js (barras, dona, ranking) |
| **CRUD completo** | Materiales, categorías, proveedores con formularios Bootstrap |
| **Docker ready** | Dockerfile multistage + docker-compose con MySQL y Nginx |

---

## Stack tecnológico

- **Backend:** Python 3.12, Flask 3, SQLAlchemy, Flask-Login, Flask-Migrate
- **Base de datos:** SQLite (desarrollo) / MySQL 8 (producción)
- **Frontend:** Bootstrap 5, Jinja2, Chart.js 4, Bootstrap Icons
- **Servidor:** Gunicorn + Nginx (producción)
- **Tests:** pytest, pytest-flask

---

## Estructura del proyecto

```
inventario_universitario/
├── app/
│   ├── __init__.py              # Application factory
│   ├── extensions.py            # db, login_manager, migrate
│   ├── models.py                # Modelos SQLAlchemy
│   ├── auth/routes.py           # Login / Logout
│   ├── admin/routes.py          # CRUD inventario, pedidos, proveedores
│   ├── solicitante/routes.py    # Catálogo filtrado, nuevo pedido, mis pedidos
│   ├── api/routes.py            # JSON endpoints para Chart.js
│   ├── static/
│   │   ├── css/custom.css       # Diseño institucional (borgoña + dorado)
│   │   └── js/dashboard.js      # Chart.js: barras, dona, ranking
│   └── templates/
│       ├── base.html            # Layout con sidebar responsivo
│       ├── auth/login.html
│       ├── admin/               # 6 templates de administración
│       └── solicitante/         # 2 templates del portal
├── tests/
│   ├── conftest.py              # Fixtures y seed de BD en memoria
│   ├── test_auth.py             # 15 tests de autenticación y RBAC
│   ├── test_inventario.py       # 12 tests de materiales y stock
│   ├── test_pedidos.py          # 13 tests del ciclo completo de pedidos
│   └── test_api.py              # 8 tests de endpoints JSON
├── config.py                    # Configuración Dev / Prod / Test
├── run.py                       # Punto de entrada + CLI init-db
├── requirements.txt
├── pytest.ini
├── Dockerfile                   # Multistage build
├── docker-compose.yml           # Flask + MySQL + Nginx
├── nginx.conf
├── inventario_schema.sql        # Script SQL puro (MySQL / SQLite)
└── .env.example
```

---

## Instalación local

### Requisitos previos
- Python 3.10+
- pip

### Pasos

```bash
# 1. Descomprimir y entrar al proyecto
unzip inventario_universitario.zip
cd inventario_universitario

# 2. Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y cambiar SECRET_KEY

# 5. Inicializar base de datos (crea tablas + seed inicial)
flask --app run init-db

# 6. Iniciar servidor de desarrollo
flask --app run run
# → http://localhost:5000
```

---

## Despliegue con Docker

### Opción A — Solo Flask + SQLite (más simple)

```bash
# Construir y levantar
docker compose up web-simple -d

# Ver logs
docker compose logs -f web-simple

# Visitar: http://localhost:5000
```

### Opción B — Stack completo (Flask + MySQL + Nginx)

```bash
# Copiar y editar variables
cp .env.example .env
# Cambiar SECRET_KEY, MYSQL_PASSWORD, etc.

# Levantar todos los servicios
docker compose --profile full up -d

# Ver estado
docker compose ps

# Visitar: http://localhost  (Nginx en puerto 80)
```

### Comandos útiles de Docker

```bash
# Reconstruir imagen tras cambios
docker compose build web-simple

# Ejecutar seed de nuevo (si necesitas reiniciar la BD)
docker compose exec web-simple flask --app run init-db

# Ver logs en tiempo real
docker compose logs -f

# Detener todo
docker compose down

# Detener y eliminar volúmenes (⚠ borra la BD)
docker compose down -v
```

---

## Credenciales por defecto

> ⚠️ **Cambiar antes de poner en producción.**

| Campo | Valor |
|-------|-------|
| Email admin | `admin@universidad.edu.mx` |
| Contraseña  | `Admin123!` |

Para crear usuarios adicionales (solicitantes), el administrador puede
agregarlos directamente en la base de datos o mediante el panel admin
(módulo de usuarios — extensión futura).

---

## Módulos del sistema

### Vista del Administrador (`/admin/*`)

| Ruta | Descripción |
|------|-------------|
| `/admin/dashboard` | Estadísticas + gráficas Chart.js |
| `/admin/inventario` | Listado + búsqueda + toggle visibilidad |
| `/admin/material/nuevo` | Alta de material |
| `/admin/material/<id>/editar` | Edición de material |
| `/admin/material/<id>/entrada-stock` | Registrar entrada (POST) |
| `/admin/pedidos` | Cola filtrable por estado |
| `/admin/pedidos/<id>/revisar` | Aprobación inteligente con historial SQL |
| `/admin/pedidos/<id>/entregar` | Confirmar entrega física |
| `/admin/proveedores` | Directorio de proveedores |

### Vista del Solicitante (`/portal/*`)

| Ruta | Descripción |
|------|-------------|
| `/portal/catalogo` | Catálogo filtrado por departamento/categoría |
| `/portal/pedido/nuevo` | Crear pedido (POST desde el carrito) |
| `/portal/mis-pedidos` | Historial con estados en tiempo real |

### API JSON (`/api/*`)

| Ruta | Descripción |
|------|-------------|
| `/api/dashboard` | Datos para Chart.js (3 datasets) |
| `/api/pedidos-pendientes` | Badge numérico del sidebar |

---

## Modelo de base de datos

```
Departamentos ──┬── Permisos_Visibilidad ──── Categorias
                │                                  │
              Usuarios                         Materiales ──── Proveedores
                │                                  │               │
              Pedidos ──── Detalle_Pedido           │           Cotizaciones
                │                                  │
                └──────── Movimientos_Inventario ──┘
```

**Tablas:**
- `Departamentos` — Secretarías y áreas de la universidad
- `Categorias` — Tipos de material (Papelería, Limpieza, Cómputo…)
- `Permisos_Visibilidad` — Tabla pivote Departamento ↔ Categoría
- `Usuarios` — Admin y Solicitantes con `password_hash`
- `Materiales` — Catálogo con stock, mínimos y visibilidad
- `Proveedores` — Directorio de proveedores
- `Cotizaciones` — Historial de precios por proveedor
- `Pedidos` — Cabecera de solicitudes con ciclo de estados
- `Detalle_Pedido` — Líneas de cada pedido
- `Movimientos_Inventario` — Bitácora de entradas/salidas/ajustes

---

## Tests

```bash
# Ejecutar toda la suite
pytest

# Con cobertura (requiere pytest-cov)
pip install pytest-cov
pytest --cov=app --cov-report=term-missing

# Solo un módulo
pytest tests/test_pedidos.py -v

# Solo una clase
pytest tests/test_auth.py::TestProteccionRutas -v
```

La suite usa **SQLite en memoria** — no afecta la BD de desarrollo.

**48 tests en 4 archivos:**
- `test_auth.py` — Login, logout, RBAC, protección de rutas, modelos
- `test_inventario.py` — Catálogo filtrado, CRUD, stock, movimientos
- `test_pedidos.py` — Ciclo completo: creación → aprobación → entrega
- `test_api.py` — Endpoints JSON, estructura Chart.js

---

## Variables de entorno

| Variable | Por defecto | Descripción |
|----------|-------------|-------------|
| `FLASK_ENV` | `development` | `development` / `production` / `testing` |
| `SECRET_KEY` | *(inseguro)* | Clave criptográfica de sesiones — **cambiar siempre** |
| `DATABASE_URL` | SQLite local | URI de la base de datos |
| `MYSQL_ROOT_PASSWORD` | `rootpass` | Solo Docker con MySQL |
| `MYSQL_USER` | `inv_user` | Usuario MySQL |
| `MYSQL_PASSWORD` | `inv_pass` | Contraseña MySQL |

### Generar un SECRET_KEY seguro

```python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Roadmap (extensiones sugeridas)

- [ ] Módulo de usuarios: CRUD de usuarios desde el panel admin
- [ ] Paginación en inventario y pedidos
- [ ] Exportación a Excel/PDF (pedidos, inventario, movimientos)
- [ ] Notificaciones por email al aprobar/rechazar pedidos
- [ ] Módulo de solicitudes de compra cuando el stock baje del mínimo
- [ ] Autenticación de doble factor (2FA)
- [ ] API REST completa con Flask-RESTful

---

*Desarrollado para la Secretaría Administrativa Universitaria.*
