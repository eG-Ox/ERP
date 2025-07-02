from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime


app = Flask(__name__)

def conectar():
    return sqlite3.connect("data/db.sqlite3")

@app.route("/")
def inicio():
    return redirect("/productos")

@app.route("/productos")
def productos():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos")
    lista = cursor.fetchall()
    conn.close()
    print(lista)  # 🔍 AÑADE ESTO para ver si hay productos
    return render_template("productos.html", productos=lista)


@app.route("/agregar_producto", methods=["POST"])
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

@app.route("/compras")
def compras():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM productos")
    productos = cursor.fetchall()
    conn.close()
    return render_template("compras.html", productos=productos)

@app.route("/registrar_compra", methods=["POST"])
def registrar_compra():
    producto_id = request.form["producto_id"]
    proveedor = request.form["proveedor"]
    cantidad = int(request.form["cantidad"])
    costo_unitario = float(request.form["costo_unitario"])

    conn = conectar()
    cursor = conn.cursor()

    # Guardar la compra
    cursor.execute("""
        INSERT INTO compras (producto_id, proveedor, cantidad, costo_unitario, fecha)
        VALUES (?, ?, ?, ?, ?)
    """, (producto_id, proveedor, cantidad, costo_unitario, datetime.now().date()))

    # Aumentar el stock del producto
    cursor.execute("UPDATE productos SET stock = stock + ? WHERE id = ?", (cantidad, producto_id))

    conn.commit()
    conn.close()
    return redirect("/compras")

@app.route("/ventas")
def ventas():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM productos")
    productos = cursor.fetchall()
    conn.close()
    return render_template("ventas.html", productos=productos)

@app.route("/registrar_venta", methods=["POST"])
def registrar_venta():
    producto_id = request.form["producto_id"]
    cantidad = int(request.form["cantidad"])
    precio_unitario = float(request.form["precio_unitario"])

    conn = conectar()
    cursor = conn.cursor()

    # Verificar stock actual
    cursor.execute("SELECT stock FROM productos WHERE id = ?", (producto_id,))
    stock_actual = cursor.fetchone()[0]

    if cantidad > stock_actual:
        conn.close()
        return "Error: no hay suficiente stock para esta venta."

    # Registrar la venta
    cursor.execute("""
        INSERT INTO ventas (producto_id, cantidad, precio_unitario, fecha)
        VALUES (?, ?, ?, CURRENT_DATE)
    """, (producto_id, cantidad, precio_unitario))

    # Actualizar stock
    cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, producto_id))

    conn.commit()
    conn.close()
    return redirect("/ventas")

@app.route("/historial")
def historial():
    producto = request.args.get("producto")

    conn = conectar()
    cursor = conn.cursor()

    compras_q = """
        SELECT c.fecha, p.nombre, c.proveedor, c.cantidad, c.costo_unitario
        FROM compras c
        JOIN productos p ON c.producto_id = p.id
    """
    ventas_q = """
        SELECT v.fecha, p.nombre, v.cantidad, v.precio_unitario
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
    """

    params = ()
    if producto:
        compras_q += " WHERE p.nombre = ?"
        ventas_q  += " WHERE p.nombre = ?"
        params = (producto,)

    compras_q += " ORDER BY c.fecha DESC"
    ventas_q  += " ORDER BY v.fecha DESC"

    cursor.execute(compras_q, params)
    compras = cursor.fetchall()

    cursor.execute(ventas_q, params)
    ventas = cursor.fetchall()

    # lista de productos para el selector
    cursor.execute("SELECT DISTINCT nombre FROM productos")
    lista_prod = [row[0] for row in cursor.fetchall()]

    conn.close()
    return render_template(
        "historial.html",
        compras=compras,
        ventas=ventas,
        lista_prod=lista_prod,
        producto_sel=producto
    )



if __name__ == "__main__":
    app.run(debug=True)
