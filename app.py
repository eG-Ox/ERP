from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime
from flask import make_response
import csv
import io


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
    cliente = request.form.get("cliente", "")  # Opcional

    conn = conectar()
    cursor = conn.cursor()

    # Verificar stock
    cursor.execute("SELECT stock FROM productos WHERE id = ?", (producto_id,))
    stock_actual = cursor.fetchone()[0]

    if cantidad > stock_actual:
        conn.close()
        return "Error: no hay suficiente stock para esta venta."

    # Registrar venta
    cursor.execute("""
        INSERT INTO ventas (producto_id, cantidad, precio_unitario, fecha, cliente)
        VALUES (?, ?, ?, CURRENT_DATE, ?)
    """, (producto_id, cantidad, precio_unitario, cliente))

    # Obtener ID de la venta recién insertada
    venta_id = cursor.lastrowid

    # Actualizar stock
    cursor.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cantidad, producto_id))

    conn.commit()
    conn.close()
    return redirect(f"/factura/{venta_id}")


@app.route("/historial")
def historial():
    # ⬇️ Parámetros opcionales llegados por ?producto=x&proveedor=y&desde=2025-07-01&hasta=2025-07-31
    producto  = request.args.get("producto")
    proveedor = request.args.get("proveedor")
    desde     = request.args.get("desde")
    hasta     = request.args.get("hasta")

    conn   = conectar()
    cursor = conn.cursor()

    # ---------- CONSULTA COMPRAS ----------
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

    compras_q += " ORDER BY c.fecha DESC"
    cursor.execute(compras_q, tuple(params_c))
    compras = cursor.fetchall()

    # ---------- CONSULTA VENTAS ----------
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

    ventas_q += " ORDER BY v.fecha DESC"
    cursor.execute(ventas_q, tuple(params_v))
    ventas = cursor.fetchall()

    # ---------- LISTAS PARA DESPLEGABLES ----------
    cursor.execute("SELECT DISTINCT nombre FROM productos")
    lista_prod = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT proveedor FROM compras WHERE proveedor IS NOT NULL AND proveedor != ''")
    lista_prov = [row[0] for row in cursor.fetchall()]

    conn.close()
    return render_template(
        "historial.html",
        compras=compras,
        ventas=ventas,
        lista_prod=lista_prod,
        lista_prov=lista_prov,
        producto_sel=producto,
        proveedor_sel=proveedor,
        desde_sel=desde,
        hasta_sel=hasta
    )

@app.route("/factura/<int:venta_id>")
def factura(venta_id):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT v.id, v.fecha, p.nombre, v.cantidad, v.precio_unitario, v.cliente
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        WHERE v.id = ?
    """, (venta_id,))
    venta = cursor.fetchone()
    conn.close()

    if not venta:
        return "Factura no encontrada."

    return render_template("factura.html", venta=venta)

@app.route("/exportar_historial")
def exportar_historial():
    conn = conectar()
    cursor = conn.cursor()

    # Obtener compras
    cursor.execute("""
        SELECT c.fecha, p.nombre, c.proveedor, c.cantidad, c.costo_unitario
        FROM compras c
        JOIN productos p ON c.producto_id = p.id
        ORDER BY c.fecha DESC
    """)
    compras = cursor.fetchall()

    # Obtener ventas
    cursor.execute("""
        SELECT v.fecha, p.nombre, v.cantidad, v.precio_unitario, v.cliente
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        ORDER BY v.fecha DESC
    """)
    ventas = cursor.fetchall()

    conn.close()

    # Crear CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output)

    # Encabezado y datos de compras
    writer.writerow(["===== HISTORIAL DE COMPRAS ====="])
    writer.writerow(["Fecha", "Producto", "Proveedor", "Cantidad", "Costo Unitario"])
    for c in compras:
        writer.writerow(c)
    writer.writerow([])

    # Encabezado y datos de ventas
    writer.writerow(["===== HISTORIAL DE VENTAS ====="])
    writer.writerow(["Fecha", "Producto", "Cantidad", "Precio Unitario", "Cliente"])
    for v in ventas:
        writer.writerow(v)

    # Preparar respuesta para descarga
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=historial.csv"
    response.headers["Content-type"] = "text/csv"
    return response



if __name__ == "__main__":
    app.run(debug=True)
