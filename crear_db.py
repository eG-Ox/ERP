import sqlite3
from pathlib import Path

DB_PATH = "data/db.sqlite3"
Path("data").mkdir(exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")  # ✔ activa FK enforcement
cursor = conn.cursor()

cursor.executescript("""
-- Productos
CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    stock INTEGER DEFAULT 0,
    precio REAL DEFAULT 0
);
                     
-- Usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario  TEXT UNIQUE NOT NULL,
    clave    TEXT NOT NULL,           -- contraseña hasheada
    rol      TEXT NOT NULL            -- 'admin' o 'vendedor'
);

INSERT OR IGNORE INTO usuarios (usuario, clave, rol)
VALUES ('admin', '$pbkdf2-sha256$29000$5hRG8...', 'admin'); -- contraseña: admin123


-- Compras
CREATE TABLE IF NOT EXISTS compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER REFERENCES productos(id),
    proveedor TEXT,
    cantidad INTEGER,
    costo_unitario REAL,
    fecha TEXT DEFAULT CURRENT_DATE
);

-- Clientes
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    ruc TEXT,
    direccion TEXT,
    telefono TEXT,
    correo TEXT
);

-- Ventas
CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER REFERENCES productos(id),
    cantidad INTEGER,
    precio_unitario REAL,
    fecha TEXT DEFAULT CURRENT_DATE,
    cliente_id INTEGER REFERENCES clientes(id),
    cliente TEXT
);
                     
""")



# Asegurar columnas nuevas solo si hiciera falta en BD antiguas
cursor.execute("PRAGMA table_info(ventas)")
cols = {row[1] for row in cursor.fetchall()}

missing = []
if "cliente_id" not in cols:
    cursor.execute("ALTER TABLE ventas ADD COLUMN cliente_id INTEGER;")
    missing.append("cliente_id")
if "cliente" not in cols:
    cursor.execute("ALTER TABLE ventas ADD COLUMN cliente TEXT;")
    missing.append("cliente")

conn.commit()
conn.close()

print("✔ Base de datos actualizada en", DB_PATH)
if missing:
    print("✔ Columnas añadidas:", ", ".join(missing))
