# 🚀 Guía de Despliegue — PythonAnywhere

## Prerequisitos
- Cuenta gratuita en [pythonanywhere.com](https://www.pythonanywhere.com)
- Repositorio del proyecto en GitHub
- 15 minutos de tiempo

---

## Paso 1 — Subir el código a GitHub

Si aún no tienes el repo en GitHub, desde tu computadora:

```bash
cd /Users/franmen/Downloads/inventario_universitario
git init                      # (si no está inicializado)
git add .
git commit -m "Deploy inicial PythonAnywhere"
git remote add origin https://github.com/TU_USUARIO/inventario_universitario.git
git push -u origin main
```

> ⚠️ El archivo `.env` **NO** se sube a GitHub (está en `.gitignore`).  
> Lo crearás directamente en el servidor de PythonAnywhere.

---

## Paso 2 — Clonar el proyecto en PythonAnywhere

1. Ve a [pythonanywhere.com](https://www.pythonanywhere.com) e inicia sesión
2. Abre una **Consola Bash**: Dashboard → New console → Bash
3. Clona el repositorio:

```bash
git clone https://github.com/TU_USUARIO/inventario_universitario.git ~/inventario_universitario
```

---

## Paso 3 — Ejecutar el script de setup automático

```bash
cd ~/inventario_universitario
bash setup_pythonanywhere.sh
```

El script hace automáticamente:
- ✅ Crea el virtualenv con Python 3.10
- ✅ Instala todas las dependencias
- ✅ Inicializa la base de datos SQLite
- ✅ Configura el archivo WSGI con tu nombre de usuario

---

## Paso 4 — Crear el archivo `.env` en el servidor

Desde la consola Bash de PythonAnywhere:

```bash
cd ~/inventario_universitario
nano .env
```

Pega este contenido (**genera tus propias claves**):

```env
FLASK_ENV=production
SECRET_KEY=TU_CLAVE_SECRETA_AQUI
FIRMA_SECRET_KEY=OTRA_CLAVE_DIFERENTE_AQUI
SESSION_INACTIVITY_TIMEOUT=10800
LOG_LEVEL=info
```

Para generar claves seguras:
```bash
python3.10 -c "import secrets; print(secrets.token_hex(32))"
```

Guarda con `Ctrl+O`, `Enter`, luego cierra con `Ctrl+X`.

---

## Paso 5 — Configurar la Web App en PythonAnywhere

1. Ve al panel: **Web** → **Add a new web app**
2. Selecciona: **Manual configuration** → **Python 3.10** → Next

### Configurar rutas:

| Campo | Valor |
|-------|-------|
| **Source code** | `/home/TU_USUARIO/inventario_universitario` |
| **Working directory** | `/home/TU_USUARIO/inventario_universitario` |
| **Virtualenv** | `/home/TU_USUARIO/.virtualenvs/inventario_venv` |

### Configurar el archivo WSGI:

1. Haz clic en el enlace del **WSGI configuration file** (algo como `/var/www/TU_USUARIO_pythonanywhere_com_wsgi.py`)
2. **Borra TODO** el contenido actual
3. Copia y pega el contenido del archivo `pythonanywhere_wsgi.py` de este proyecto
4. Guarda con el botón **Save**

---

## Paso 6 — Recargar y probar

1. Regresa al panel **Web**
2. Haz clic en el botón verde **Reload TU_USUARIO.pythonanywhere.com**
3. Visita: **https://TU_USUARIO.pythonanywhere.com**

---

## Credenciales de acceso inicial

| Rol | Email | Contraseña |
|-----|-------|------------|
| Administrador | `admin@universidad.edu.mx` | `Admin123!` |
| Mantenimiento | `mantenimiento@universidad.edu.mx` | *(ver CREDENCIALES_USUARIOS.txt)* |

> ⚠️ **Cambia las contraseñas** en tu primera sesión.

---

## Actualizar el código (deploys futuros)

Cada vez que hagas cambios en local y los subas a GitHub:

```bash
# En la consola Bash de PythonAnywhere:
cd ~/inventario_universitario
git pull origin main

# Si añadiste nuevas dependencias:
~/.virtualenvs/inventario_venv/bin/pip install -r requirements_pythonanywhere.txt

# Si modificaste los modelos de la BD:
FLASK_ENV=production ~/.virtualenvs/inventario_venv/bin/flask --app wsgi init-db
```

Luego ve al panel **Web** → **Reload**.

---

## Solución de problemas comunes

### Error: `ModuleNotFoundError`
```bash
# Verificar que el virtualenv tiene las dependencias:
~/.virtualenvs/inventario_venv/bin/pip list | grep Flask
```

### Error en la base de datos
```bash
cd ~/inventario_universitario
FLASK_ENV=production ~/.virtualenvs/inventario_venv/bin/flask --app wsgi init-db
```

### Ver logs de error
En el panel Web → **Error log** (enlace en la parte inferior)

### La app muestra "Bad Gateway" o "Internal Server Error"
1. Abre el **Error log** en el panel Web
2. El error exacto estará al final del archivo
3. Comparte el error para diagnosticar

---

## Notas importantes del Plan Gratuito

| Característica | Plan Free |
|---------------|-----------|
| SQLite persistente | ✅ Sí |
| Dominio | `usuario.pythonanywhere.com` |
| Hibernación | ❌ No (siempre activo) |
| Renovación | Cada 3 meses (clic en botón) |
| CPU/hora | 100 segundos/día |
| Almacenamiento | 512 MB |
| MySQL | ✅ Gratuito incluido |
