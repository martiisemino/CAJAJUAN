from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os


app = Flask(__name__)

# Clave usada por Flask para manejar la sesión.
# Más adelante, cuando lo publiquemos, la vamos a cambiar.
app.secret_key = "clave-secreta-control-caja"

# Contraseña temporal para ingresar al sistema.
PASSWORD = "1234"


# --------------------------------------------------
# BASE DE DATOS
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "caja.db")


def conectar_db():
    conexion = sqlite3.connect(DB)
    conexion.row_factory = sqlite3.Row
    return conexion


def crear_tabla():
    conexion = conectar_db()

    conexion.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            frasco INTEGER NOT NULL,
            efectivo INTEGER NOT NULL,
            gastos INTEGER NOT NULL,
            detalle TEXT
        )
    """)

    conexion.commit()
    conexion.close()


# --------------------------------------------------
# FORMATO DE MONEDA
# --------------------------------------------------

@app.template_filter("moneda")
def moneda(valor):
    return f"{valor:,.0f}".replace(",", ".")


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    # Si ya inició sesión, entra directamente al sistema.
    if session.get("logueado"):
        return redirect(url_for("inicio"))

    error = None

    if request.method == "POST":

        password = request.form["password"]

        if password == PASSWORD:

            session["logueado"] = True

            return redirect(url_for("inicio"))

        else:

            error = "Contraseña incorrecta"

    return render_template(
        "login.html",
        error=error
    )


# --------------------------------------------------
# CERRAR SESIÓN
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# --------------------------------------------------
# PÁGINA PRINCIPAL
# --------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def inicio():

    # Si no inició sesión, no puede entrar.
    if not session.get("logueado"):
        return redirect(url_for("login"))

    # --------------------------------------------------
    # GUARDAR NUEVO MOVIMIENTO
    # --------------------------------------------------

    if request.method == "POST":

        fecha = request.form["fecha"]

        frasco = int(request.form["frasco"])

        efectivo = int(request.form["efectivo"])

        gastos = int(request.form["gastos"])

        detalle = request.form["detalle"]

        conexion = conectar_db()

        conexion.execute("""
            INSERT INTO registros
            (
                fecha,
                frasco,
                efectivo,
                gastos,
                detalle
            )

            VALUES (?, ?, ?, ?, ?)

        """, (
            fecha,
            frasco,
            efectivo,
            gastos,
            detalle
        ))

        conexion.commit()
        conexion.close()

        return redirect(url_for("inicio"))


    # --------------------------------------------------
    # FILTRAR POR MES
    # --------------------------------------------------

    mes = request.args.get("mes", "")

    conexion = conectar_db()

    if mes:

        registros = conexion.execute("""
            SELECT *
            FROM registros

            WHERE substr(fecha, 1, 7) = ?

            ORDER BY fecha ASC, id ASC

        """, (mes,)).fetchall()

    else:

        registros = conexion.execute("""
            SELECT *
            FROM registros

            ORDER BY fecha ASC, id ASC

        """).fetchall()

    conexion.close()


    # --------------------------------------------------
    # TOTALES GENERALES
    # --------------------------------------------------

    total_frasco = sum(
        registro["frasco"]
        for registro in registros
    )

    total_efectivo = sum(
        registro["efectivo"]
        for registro in registros
    )

    total_gastos = sum(
        registro["gastos"]
        for registro in registros
    )

    total = total_frasco + total_efectivo

    total_neto = total - total_gastos


    # --------------------------------------------------
    # SOCIEDAD ACUMULADA
    # --------------------------------------------------

    movimientos = []

    acumulado_frasco = 0

    acumulado_efectivo = 0

    acumulado_gastos = 0


    for registro in registros:

        acumulado_frasco += registro["frasco"]

        acumulado_efectivo += registro["efectivo"]

        acumulado_gastos += registro["gastos"]


        acumulado_total = (
            acumulado_frasco
            +
            acumulado_efectivo
        )


        acumulado_neto = (
            acumulado_total
            -
            acumulado_gastos
        )


        movimientos.append({

            "registro": registro,

            "sociedad_frasco":
                acumulado_frasco,

            "sociedad_efectivo":
                acumulado_efectivo,

            "sociedad_gastos":
                acumulado_gastos,

            "sociedad_total":
                acumulado_total,

            "sociedad_neto":
                acumulado_neto

        })


    return render_template(

        "index.html",

        movimientos=movimientos,

        total_frasco=total_frasco,

        total_efectivo=total_efectivo,

        total_gastos=total_gastos,

        total=total,

        total_neto=total_neto,

        mes=mes
    )


# --------------------------------------------------
# ELIMINAR MOVIMIENTO
# --------------------------------------------------

@app.route("/eliminar/<int:id>", methods=["POST"])
def eliminar(id):

    if not session.get("logueado"):
        return redirect(url_for("login"))

    conexion = conectar_db()

    conexion.execute(
        """
        DELETE FROM registros
        WHERE id = ?
        """,
        (id,)
    )

    conexion.commit()
    conexion.close()

    return redirect(url_for("inicio"))


# --------------------------------------------------
# EDITAR MOVIMIENTO
# --------------------------------------------------

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):

    if not session.get("logueado"):
        return redirect(url_for("login"))

    conexion = conectar_db()


    # ----------------------------------------------
    # GUARDAR CAMBIOS
    # ----------------------------------------------

    if request.method == "POST":

        fecha = request.form["fecha"]

        frasco = int(request.form["frasco"])

        efectivo = int(request.form["efectivo"])

        gastos = int(request.form["gastos"])

        detalle = request.form["detalle"]


        conexion.execute("""
            UPDATE registros

            SET
                fecha = ?,
                frasco = ?,
                efectivo = ?,
                gastos = ?,
                detalle = ?

            WHERE id = ?

        """, (
            fecha,
            frasco,
            efectivo,
            gastos,
            detalle,
            id
        ))

        conexion.commit()

        conexion.close()

        return redirect(url_for("inicio"))


    # ----------------------------------------------
    # MOSTRAR DATOS ACTUALES
    # ----------------------------------------------

    registro = conexion.execute(
        """
        SELECT *
        FROM registros
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    conexion.close()


    # Si por alguna razón el registro no existe.
    if registro is None:
        return redirect(url_for("inicio"))


    return render_template(
        "editar.html",
        registro=registro
    )


# --------------------------------------------------
# INICIAR PROGRAMA
# --------------------------------------------------

if __name__ == "__main__":

    crear_tabla()

    app.run(debug=True)