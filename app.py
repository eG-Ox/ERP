from flask import Flask, render_template, request, redirect, url_for, make_response, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from dataclasses import dataclass
from functools import wraps
from datetime import datetime
import sqlite3
import csv
import io

app = Flask(__name__)
app.config["SECRET_KEY"] = "erp-seguro"

# ------------------ Conexion ------------------
def conectar():
    return sqlite3.connect("data/db.sqlite3")

# ------------------ Login y Roles ------------------
login_manager = LoginManager(app)
login_manager.login_view = "login"

def rol_requerido(*roles):
    def wrapper(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            if current_user.rol not in roles:
                return abort(403)
            return fn(*args, **kwargs)
        return _inner
    return wrapper

@dataclass
class User:
    id: int
    usuario: str
    rol: str
    def is_authenticated(self): return True
    def is_active(self): return True
    def is_anonymous(self): return False
    def get_id(self): return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = conectar()
    c = conn.execute("SELECT id, usuario, rol FROM usuarios WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row: return User(*row)
    return None

# ------------------ Login ------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usr = request.form["usuario"]
        pwd = request.form["clave"]

        conn = conectar()
        row = conn.execute("SELECT id, clave, rol FROM usuarios WHERE usuario = ?", (usr,)).fetchone()
        conn.close()

        if row and check_password_hash(row[1], pwd):
            user = User(row[0], usr, row[2])
            login_user(user)
            return redirect(url_for("inicio"))
        return "Credenciales incorrectas", 401

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

# ------------------ Productos ------------------
@app.route("/")
def inicio():
    return redirect("/productos")

@app.route("/productos")
@login_required
def productos():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos")
    lista = cursor.fetchall()
    conn.close()
    return render_template("productos.html", productos=lista)

@app.route("/editar_producto/<int:id>", methods=["GET", "POST"])
@login_required
@rol_requerido("admin")
def editar_producto(id):
    conn = conectar()
    cursor = conn.cursor()

    if request.method == "POST":
        nombre = request.form["nombre"]
        stock  = int(request.form["stock"])
        precio = float(request.form["precio"])
        cursor.execute("""
            UPDATE productos
            SET nombre = ?, stock = ?, precio = ?
            WHERE id = ?
        """, (nombre, stock, precio, id))
        conn.commit()
        conn.close()
        return redirect("/productos")

    cursor.execute("SELECT * FROM productos WHERE id = ?", (id,))
    producto = cursor.fetchone()
    conn.close()
    return render_template("editar_producto.html", producto=producto)

@app.route("/eliminar_producto/<int:id>")
@login_required
@rol_requerido("admin")
def eliminar_producto(id):
    conn = conectar()
    conn.execute("DELETE FROM productos WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect("/productos")

@app.route("/agregar_producto", methods=["POST"])
@login_required
@rol_requerido("admin")
def agregar_producto():
    nombre = request.form["nombre"]
    stock = request.form["stock"]
    precio = request.form["precio"]

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO productos (nombre, stock, precio) VALUES (?, ?, ?)",
                   (nombre, stock, precio))
    conn.commit()
    conn.close()
    return redirect("/productos")

# ------------------ Compras ------------------
@app.route("/compras")
@login_required
@rol_requerido("admin")
def compras():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM productos")
    productos = cursor.fetchall()
    conn.close()
    return render_template("compras.html", productos=productos)

@app.route("/registrar_compra", methods=["POST"])
@login_required
@rol_requerido("admin")
def registrar_compra():
    producto_id = request.form["producto_id"]
    proveedor = request.form["proveedor"]
    cantidad = int(request.form["cantidad"])
    costo_unitario = float(request.form["costo_unitario"])

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO compras (producto_id, proveedor, cantidad, costo_unitario, fecha)
        VALUES (?, ?, ?, ?, ?)
    """, (producto_id, proveedor, cantidad, costo_unitario, datetime.now().date()))

    cursor.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, producto_id))

    conn.commit()
    conn.close()
    return redirect("/compras")

# ------------------ Ventas ------------------
@app.route("/ventas")
@login_required
def ventas():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM productos")
    productos = cursor.fetchall()
    cursor.execute("SELECT * FROM clientes ORDER BY nombre")
    clientes = cursor.fetchall()
    conn.close()
    return render_template("ventas.html", productos=productos, clientes=clientes)

@app.route("/registrar_venta", methods=["POST"])
@login_required
def registrar_venta():
    producto_id = request.form["producto_id"]
    cantidad = int(request.form["cantidad"])
    precio_unitario = float(request.form["precio_unitario"])
    cliente_id = request.form.get("cliente_id") or None
    cliente_txt = request.form.get("cliente_txt", "").strip()

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT stock FROM productos WHERE id = ?", (producto_id,))
    stock_actual = cursor.fetchone()[0]

    if cantidad > stock_actual:
        conn.close()
        return "Error: no hay suficiente stock para esta venta."

    cursor.execute("""
        INSERT INTO ventas (producto_id, cantidad, precio_unitario, fecha, cliente_id, cliente)
        VALUES (?, ?, ?, CURRENT_DATE, ?, ?)
    """, (producto_id, cantidad, precio_unitario, cliente_id, cliente_txt))

    venta_id = cursor.lastrowid
    cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, producto_id))

    conn.commit()
    conn.close()
    return redirect(f"/factura/{venta_id}")

# ------------------ Factura ------------------
@app.route("/factura/<int:venta_id>")
@login_required
def factura(venta_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT v.id, v.fecha, p.nombre, v.cantidad, v.precio_unitario,
               COALESCE(c.nombre, v.cliente) AS cliente
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE v.id = ?
    """, (venta_id,))

    venta = cursor.fetchone()
    conn.close()

    if not venta:
        return "Factura no encontrada."

    return render_template("factura.html", venta=venta)

# ------------------ Historial ------------------
@app.route("/historial")
@login_required
def historial():
    producto = request.args.get("producto")
    proveedor = request.args.get("proveedor")
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")

    conn = conectar()
    cursor = conn.cursor()

    compras_q = """
        SELECT c.fecha, p.nombre, c.proveedor, c.cantidad, c.costo_unitario
        FROM compras c
        JOIN productos p ON c.producto_id = p.id
        WHERE 1=1
    """
    params_c = []

    if producto:
        compras_q += " AND p.nombre = ?"
        params_c.append(producto)
    if proveedor:
        compras_q += " AND c.proveedor = ?"
        params_c.append(proveedor)
    if desde:
        compras_q += " AND date(c.fecha) >= date(?)"
        params_c.append(desde)
    if hasta:
        compras_q += " AND date(c.fecha) <= date(?)"
        params_c.append(hasta)

    cursor.execute(compras_q + " ORDER BY c.fecha DESC", tuple(params_c))
    compras = cursor.fetchall()

    ventas_q = """
        SELECT v.fecha, p.nombre, v.cantidad, v.precio_unitario
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        WHERE 1=1
    """
    params_v = []

    if producto:
        ventas_q += " AND p.nombre = ?"
        params_v.append(producto)
    if desde:
        ventas_q += " AND date(v.fecha) >= date(?)"
        params_v.append(desde)
    if hasta:
        ventas_q += " AND date(v.fecha) <= date(?)"
        params_v.append(hasta)

    cursor.execute(ventas_q + " ORDER BY v.fecha DESC", tuple(params_v))
    ventas = cursor.fetchall()

    cursor.execute("SELECT DISTINCT nombre FROM productos")
    lista_prod = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT DISTINCT proveedor FROM compras WHERE proveedor != ''")
    lista_prov = [row[0] for row in cursor.fetchall()]

    conn.close()
    return render_template("historial.html", compras=compras, ventas=ventas,
                           lista_prod=lista_prod, lista_prov=lista_prov,
                           producto_sel=producto, proveedor_sel=proveedor,
                           desde_sel=desde, hasta_sel=hasta)

# ------------------ Exportar ------------------
@app.route("/exportar_historial")
@login_required
@rol_requerido("admin")
def exportar_historial():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT c.fecha, p.nombre, c.proveedor, c.cantidad, c.costo_unitario FROM compras c JOIN productos p ON c.producto_id = p.id ORDER BY c.fecha DESC")
    compras = cursor.fetchall()

    cursor.execute("SELECT v.fecha, p.nombre, v.cantidad, v.precio_unitario, v.cliente FROM ventas v JOIN productos p ON v.producto_id = p.id ORDER BY v.fecha DESC")
    ventas = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["===== HISTORIAL DE COMPRAS ====="])
    writer.writerow(["Fecha", "Producto", "Proveedor", "Cantidad", "Costo Unitario"])
    for row in compras:
        writer.writerow(row)
    writer.writerow([])
    writer.writerow(["===== HISTORIAL DE VENTAS ====="])
    writer.writerow(["Fecha", "Producto", "Cantidad", "Precio Unitario", "Cliente"])
    for row in ventas:
        writer.writerow(row)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=historial.csv"
    response.headers["Content-type"] = "text/csv"
    return response

# ------------------ Clientes ------------------
@app.route("/clientes")
@login_required
@rol_requerido("admin")
def clientes():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes ORDER BY nombre")
    lista = cursor.fetchall()
    conn.close()
    return render_template("clientes.html", clientes=lista)

@app.route("/agregar_cliente", methods=["POST"])
@login_required
@rol_requerido("admin")
def agregar_cliente():
    datos = (
        request.form["nombre"], request.form["ruc"], request.form["direccion"],
        request.form["telefono"], request.form["correo"]
    )
    conn = conectar()
    conn.execute("INSERT INTO clientes (nombre, ruc, direccion, telefono, correo) VALUES (?, ?, ?, ?, ?)", datos)
    conn.commit()
    conn.close()
    return redirect("/clientes")

@app.route("/editar_cliente/<int:id>", methods=["GET", "POST"])
@login_required
def editar_cliente(id):
    conn = conectar()
    cursor = conn.cursor()

    if request.method == "POST":
        datos = (
            request.form["nombre"],
            request.form["ruc"],
            request.form["direccion"],
            request.form["telefono"],
            request.form["correo"],
            id
        )
        cursor.execute("""
            UPDATE clientes SET nombre=?, ruc=?, direccion=?, telefono=?, correo=? WHERE id=?
        """, datos)
        conn.commit()
        conn.close()
        return redirect("/clientes")

    cliente = cursor.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template("editar_cliente.html", cliente=cliente)

@app.route("/eliminar_cliente/<int:id>")
@login_required
def eliminar_cliente(id):
    conn = conectar()
    conn.execute("DELETE FROM clientes WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/clientes")


# --- Usuarios (solo admin) ---
@app.route("/usuarios")
@login_required
@rol_requerido("admin")
def usuarios():
    lista = conectar().execute("SELECT id, usuario, rol FROM usuarios").fetchall()
    return render_template("usuarios.html", usuarios=lista)


@app.route("/agregar_usuario", methods=["POST"])
@login_required
@rol_requerido("admin")
def agregar_usuario():
    usr  = request.form["usuario"].strip()
    pwd  = request.form["clave"]
    rol  = request.form["rol"]
    if rol not in ("admin", "vendedor"):
        return "Rol no permitido", 400
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO usuarios (usuario, clave, rol) VALUES (?,?,?)",
            (usr, generate_password_hash(pwd), rol)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return "Usuario ya existe", 400
    finally:
        conn.close()
    return redirect("/usuarios")

@app.route("/editar_usuario/<int:id>", methods=["GET", "POST"])
@login_required
@rol_requerido("admin")
def editar_usuario(id):
    conn = conectar()
    cur  = conn.cursor()

    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        rol     = request.form["rol"]
        pwd     = request.form["clave"]   # puede estar vacío

        # Actualiza usuario y rol
        cur.execute("UPDATE usuarios SET usuario=?, rol=? WHERE id=?", (usuario, rol, id))

        # Si se ingresó contraseña, actualiza hash
        if pwd:
            cur.execute("UPDATE usuarios SET clave=? WHERE id=?", (generate_password_hash(pwd), id))

        conn.commit()
        conn.close()
        return redirect("/usuarios")

    # GET
    u = cur.execute("SELECT id, usuario, rol FROM usuarios WHERE id=?", (id,)).fetchone()
    conn.close()
    if not u:
        return "Usuario no encontrado", 404
    return render_template("editar_usuario.html", u=u)

@app.route("/eliminar_usuario/<int:id>")
@login_required
@rol_requerido("admin")
def eliminar_usuario(id):
    # Evitar que un admin se elimine a sí mismo
    if current_user.id == id:
        return "No puedes eliminar tu propia cuenta.", 400

    conn = conectar()
    conn.execute("DELETE FROM usuarios WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/usuarios")



if __name__ == "__main__":
    app.run(debug=True)
