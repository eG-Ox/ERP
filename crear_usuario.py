# crear_usuario.py
import sqlite3
from werkzeug.security import generate_password_hash
from getpass import getpass

db = "data/db.sqlite3"
conn = sqlite3.connect(db)

usuario = input("Nuevo usuario: ").strip()
pwd1 = getpass("Contraseña: ")
pwd2 = getpass("Repite la contraseña: ")

if pwd1 != pwd2:
    raise SystemExit("❌ Las contraseñas no coinciden.")

rol = input("Rol (admin / vendedor): ").strip().lower()
if rol not in {"admin", "vendedor"}:
    raise SystemExit("❌ Rol inválido.")

try:
    conn.execute(
        "INSERT INTO usuarios (usuario, clave, rol) VALUES (?,?,?)",
        (usuario, generate_password_hash(pwd1), rol)
    )
    conn.commit()
    print(f"✅ Usuario '{usuario}' creado con rol '{rol}'.")
except sqlite3.IntegrityError:
    print("❌ Ese usuario ya existe.")
finally:
    conn.close()
