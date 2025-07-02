"""
crear_db.py
-----------
Ejecuta este archivo UNA sola vez para generar (o actualizar) la base
data/db.sqlite3 con las tablas 'productos' y 'compras'.
"""

import sqlite3
from pathlib import Path

# 1️⃣ Asegurar que la carpeta 'data' exista
Path("data").mkdir(exist_ok=True)

# 2️⃣ Conectar (si el archivo no existe, lo crea)
conn = sqlite3.connect("data/db.sqlite3")
cursor = conn.cursor()

# 3️⃣ Crear las tablas
cursor.executescript("""
CREATE TABLE IF NOT EXISTS productos (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre   TEXT    NOT NULL,
    stock    INTEGER DEFAULT 0,
    precio   REAL    DEFAULT 0
);

CREATE TABLE IF NOT EXISTS compras (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id    INTEGER,
    proveedor      TEXT,
    cantidad       INTEGER,
    costo_unitario REAL,
    fecha          TEXT DEFAULT CURRENT_DATE,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_id INTEGER,
    cantidad INTEGER,
    precio_unitario REAL,
    fecha TEXT DEFAULT CURRENT_DATE,
    FOREIGN KEY (producto_id) REFERENCES productos(id)
)
""")


# 4️⃣ Guardar cambios y cerrar
conn.commit()
conn.close()

print("✔ Base de datos y tablas 'productos' y 'compras' listas en data/db.sqlite3")
