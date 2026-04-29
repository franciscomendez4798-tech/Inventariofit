-- ============================================================
--  SISTEMA DE CONTROL Y REGISTRO DE INVENTARIOS
--  Secretaría Administrativa Universitaria
--  Compatible con MySQL 8+ y SQLite 3.35+
-- ============================================================

-- ============================================================
-- NOTA DE COMPATIBILIDAD:
--   Para SQLite: elimina ENGINE=InnoDB y el COMMENT de cada tabla.
--   Para MySQL:  el script corre tal cual.
-- ============================================================

PRAGMA foreign_keys = ON;  -- Solo SQLite; en MySQL esto no aplica

-- ------------------------------------------------------------
-- 1. DEPARTAMENTOS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Departamentos (
    id            INTEGER      PRIMARY KEY AUTOINCREMENT,
    nombre        VARCHAR(120) NOT NULL UNIQUE,
    codigo        VARCHAR(20)  NOT NULL UNIQUE,   -- Ej. "SEC-ACA", "MANT"
    descripcion   TEXT,
    activo        BOOLEAN      NOT NULL DEFAULT 1,
    creado_en     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 2. USUARIOS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Usuarios (
    id               INTEGER      PRIMARY KEY AUTOINCREMENT,
    nombre_completo  VARCHAR(150) NOT NULL,
    email            VARCHAR(150) NOT NULL UNIQUE,
    -- Contraseña almacenada como hash (werkzeug generate_password_hash)
    password_hash    VARCHAR(256) NOT NULL,
    rol              VARCHAR(20)  NOT NULL DEFAULT 'solicitante'
                         CHECK (rol IN ('administrador', 'solicitante')),
    id_departamento  INTEGER,                     -- NULL solo para admin
    activo           BOOLEAN      NOT NULL DEFAULT 1,
    creado_en        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_departamento) REFERENCES Departamentos(id)
        ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- 3. CATEGORÍAS DE MATERIALES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Categorias (
    id          INTEGER      PRIMARY KEY AUTOINCREMENT,
    nombre      VARCHAR(100) NOT NULL UNIQUE,     -- Ej. "Papelería", "Limpieza"
    descripcion TEXT,
    activo      BOOLEAN      NOT NULL DEFAULT 1
);

-- ------------------------------------------------------------
-- 4. PERMISOS DE VISIBILIDAD  (Departamento ↔ Categoría)
--    Define qué categorías puede ver/pedir cada departamento.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Permisos_Visibilidad (
    id               INTEGER  PRIMARY KEY AUTOINCREMENT,
    id_departamento  INTEGER  NOT NULL,
    id_categoria     INTEGER  NOT NULL,
    UNIQUE (id_departamento, id_categoria),
    FOREIGN KEY (id_departamento) REFERENCES Departamentos(id)
        ON DELETE CASCADE,
    FOREIGN KEY (id_categoria)    REFERENCES Categorias(id)
        ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 5. PROVEEDORES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Proveedores (
    id          INTEGER      PRIMARY KEY AUTOINCREMENT,
    nombre      VARCHAR(150) NOT NULL,
    contacto    VARCHAR(150),                     -- Nombre del representante
    telefono    VARCHAR(30),
    email       VARCHAR(150),
    direccion   TEXT,
    rfc         VARCHAR(20),                      -- RFC o ID fiscal
    notas       TEXT,
    activo      BOOLEAN      NOT NULL DEFAULT 1,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 6. MATERIALES (Catálogo de artículos en inventario)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Materiales (
    id               INTEGER       PRIMARY KEY AUTOINCREMENT,
    nombre           VARCHAR(200)  NOT NULL,
    descripcion      TEXT,
    unidad_medida    VARCHAR(50)   NOT NULL,      -- Ej. "pieza", "caja", "litro"
    stock_actual     INTEGER       NOT NULL DEFAULT 0
                         CHECK (stock_actual >= 0),
    stock_minimo     INTEGER       NOT NULL DEFAULT 5, -- Umbral de alerta
    precio_unitario  DECIMAL(10,2) DEFAULT 0.00,
    id_categoria     INTEGER       NOT NULL,
    id_proveedor     INTEGER,                     -- Proveedor preferente
    publicado        BOOLEAN       NOT NULL DEFAULT 0, -- Visible para solicitantes
    imagen_url       VARCHAR(500),
    creado_en        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_categoria) REFERENCES Categorias(id),
    FOREIGN KEY (id_proveedor) REFERENCES Proveedores(id)
        ON DELETE SET NULL
);

-- Trigger para actualizar la columna actualizado_en en SQLite
-- (En MySQL usa ON UPDATE CURRENT_TIMESTAMP en la definición)
CREATE TRIGGER IF NOT EXISTS trg_materiales_updated
AFTER UPDATE ON Materiales
BEGIN
    UPDATE Materiales SET actualizado_en = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;

-- ------------------------------------------------------------
-- 7. COTIZACIONES (Registro de precios por proveedor)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Cotizaciones (
    id               INTEGER       PRIMARY KEY AUTOINCREMENT,
    id_material      INTEGER       NOT NULL,
    id_proveedor     INTEGER       NOT NULL,
    precio_cotizado  DECIMAL(10,2) NOT NULL,
    fecha_cotizacion DATE          NOT NULL,
    fecha_vigencia   DATE,                        -- NULL = sin vencimiento
    notas            TEXT,
    FOREIGN KEY (id_material)  REFERENCES Materiales(id)  ON DELETE CASCADE,
    FOREIGN KEY (id_proveedor) REFERENCES Proveedores(id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 8. PEDIDOS (Cabecera de cada solicitud)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Pedidos (
    id               INTEGER      PRIMARY KEY AUTOINCREMENT,
    folio            VARCHAR(20)  NOT NULL UNIQUE, -- Ej. "PED-2024-001"
    id_solicitante   INTEGER      NOT NULL,
    id_departamento  INTEGER      NOT NULL,
    -- Estados del ciclo de vida del pedido
    estado           VARCHAR(20)  NOT NULL DEFAULT 'pendiente'
                         CHECK (estado IN (
                             'pendiente',    -- Recién creado, sin revisar
                             'en_revision',  -- Admin lo está revisando
                             'modificado',   -- Admin ajustó cantidades
                             'aprobado',     -- Aprobado, stock descontado
                             'rechazado',    -- Rechazado con motivo
                             'entregado'     -- Entrega física confirmada
                         )),
    notas_solicitante TEXT,
    notas_admin       TEXT,                       -- Observaciones al aprobar/rechazar
    fecha_solicitud   DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_resolucion  DATETIME,                   -- Cuando admin aprueba/rechaza
    fecha_entrega     DATETIME,
    FOREIGN KEY (id_solicitante)  REFERENCES Usuarios(id),
    FOREIGN KEY (id_departamento) REFERENCES Departamentos(id)
);

-- ------------------------------------------------------------
-- 9. DETALLE_PEDIDO (Líneas de cada pedido)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Detalle_Pedido (
    id                  INTEGER       PRIMARY KEY AUTOINCREMENT,
    id_pedido           INTEGER       NOT NULL,
    id_material         INTEGER       NOT NULL,
    cantidad_solicitada INTEGER       NOT NULL CHECK (cantidad_solicitada > 0),
    cantidad_aprobada   INTEGER,                  -- NULL hasta que admin resuelve
    precio_unitario_ref DECIMAL(10,2) DEFAULT 0.00, -- Precio al momento del pedido
    FOREIGN KEY (id_pedido)   REFERENCES Pedidos(id)   ON DELETE CASCADE,
    FOREIGN KEY (id_material) REFERENCES Materiales(id)
);

-- ------------------------------------------------------------
-- 10. MOVIMIENTOS_INVENTARIO  (Bitácora de entradas y salidas)
--     Permite reconstruir el historial y generar el dashboard.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Movimientos_Inventario (
    id              INTEGER       PRIMARY KEY AUTOINCREMENT,
    id_material     INTEGER       NOT NULL,
    tipo_movimiento VARCHAR(15)   NOT NULL
                        CHECK (tipo_movimiento IN ('entrada', 'salida', 'ajuste')),
    cantidad        INTEGER       NOT NULL,       -- Siempre positivo
    stock_resultante INTEGER      NOT NULL,       -- Stock tras el movimiento
    id_pedido       INTEGER,                      -- FK a Pedidos (para salidas)
    id_usuario      INTEGER,                      -- Quién registró el movimiento
    motivo          TEXT,                         -- Descripción libre
    fecha           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_material) REFERENCES Materiales(id),
    FOREIGN KEY (id_pedido)   REFERENCES Pedidos(id)   ON DELETE SET NULL,
    FOREIGN KEY (id_usuario)  REFERENCES Usuarios(id)  ON DELETE SET NULL
);

-- ============================================================
-- ÍNDICES  (Mejoran las consultas de catálogo y dashboard)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_materiales_categoria ON Materiales(id_categoria);
CREATE INDEX IF NOT EXISTS idx_materiales_publicado  ON Materiales(publicado);
CREATE INDEX IF NOT EXISTS idx_pedidos_departamento  ON Pedidos(id_departamento);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado        ON Pedidos(estado);
CREATE INDEX IF NOT EXISTS idx_pedidos_fecha         ON Pedidos(fecha_solicitud);
CREATE INDEX IF NOT EXISTS idx_movimientos_material  ON Movimientos_Inventario(id_material);
CREATE INDEX IF NOT EXISTS idx_movimientos_fecha     ON Movimientos_Inventario(fecha);

-- ============================================================
-- DATOS INICIALES (seed mínimo para arrancar el sistema)
-- ============================================================

-- Administrador por defecto  (password: "admin123" — cambiar en producción)
INSERT OR IGNORE INTO Usuarios (nombre_completo, email, password_hash, rol)
VALUES (
    'Administrador del Sistema',
    'admin@universidad.edu.mx',
    'pbkdf2:sha256:600000$seed$hashedvalue',  -- Reemplazar con hash real
    'administrador'
);

-- Categorías base
INSERT OR IGNORE INTO Categorias (nombre, descripcion) VALUES
    ('Papelería',       'Hojas, folders, plumas, clips y similares'),
    ('Limpieza',        'Detergentes, escobas, trapeadores, papel higiénico'),
    ('Cómputo',         'Cables, memorias USB, cartuchos de tinta'),
    ('Mobiliario',      'Sillas, mesas, estantes de oficina'),
    ('Mantenimiento',   'Herramientas, pintura, materiales eléctricos');

-- Departamentos ejemplo
INSERT OR IGNORE INTO Departamentos (nombre, codigo) VALUES
    ('Secretaría Académica',      'SEC-ACA'),
    ('Dirección General',         'DIR-GEN'),
    ('Mantenimiento y Servicios', 'MANT'),
    ('Recursos Humanos',          'RRHH');

-- Permisos de visibilidad (quién ve qué categoría)
-- Secretaría Académica → Papelería, Cómputo
INSERT OR IGNORE INTO Permisos_Visibilidad (id_departamento, id_categoria)
SELECT d.id, c.id FROM Departamentos d, Categorias c
WHERE d.codigo = 'SEC-ACA' AND c.nombre IN ('Papelería', 'Cómputo');

-- Dirección General → Papelería, Cómputo, Mobiliario
INSERT OR IGNORE INTO Permisos_Visibilidad (id_departamento, id_categoria)
SELECT d.id, c.id FROM Departamentos d, Categorias c
WHERE d.codigo = 'DIR-GEN' AND c.nombre IN ('Papelería', 'Cómputo', 'Mobiliario');

-- Mantenimiento → Limpieza, Mantenimiento
INSERT OR IGNORE INTO Permisos_Visibilidad (id_departamento, id_categoria)
SELECT d.id, c.id FROM Departamentos d, Categorias c
WHERE d.codigo = 'MANT' AND c.nombre IN ('Limpieza', 'Mantenimiento');

-- RRHH → Papelería
INSERT OR IGNORE INTO Permisos_Visibilidad (id_departamento, id_categoria)
SELECT d.id, c.id FROM Departamentos d, Categorias c
WHERE d.codigo = 'RRHH' AND c.nombre = 'Papelería';
