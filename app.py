from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient, ASCENDING
from bson.objectid import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv

import os
import hmac
import re


# --------------------------------------------------
# VARIABLES DE ENTORNO
# --------------------------------------------------

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sistemaJuan")
PASSWORD = os.getenv("APP_PASSWORD")
SECRET_KEY = os.getenv("SECRET_KEY")


if not MONGO_URI:
    raise RuntimeError("Falta MONGO_URI en el archivo .env")

if not PASSWORD:
    raise RuntimeError("Falta APP_PASSWORD en el archivo .env")

if not SECRET_KEY:
    raise RuntimeError("Falta SECRET_KEY en el archivo .env")


# --------------------------------------------------
# FLASK
# --------------------------------------------------

app = Flask(__name__)
app.secret_key = SECRET_KEY


# --------------------------------------------------
# MONGODB
# --------------------------------------------------

cliente_mongo = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)

db = cliente_mongo[MONGO_DB_NAME]

registros_db = db["registros"]


# --------------------------------------------------
# FORMATO MONEDA
# --------------------------------------------------

@app.template_filter("moneda")
def moneda(valor):
    return f"{valor:,.0f}".replace(",", ".")


# --------------------------------------------------
# PREPARAR REGISTRO PARA HTML
# --------------------------------------------------

def preparar_registro(registro):

    registro = dict(registro)

    registro["id"] = str(registro["_id"])

    return registro


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("logueado"):
        return redirect(url_for("inicio"))

    error = None

    if request.method == "POST":

        password = request.form["password"]

        if hmac.compare_digest(password, PASSWORD):

            session["logueado"] = True

            return redirect(url_for("inicio"))

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

    if not session.get("logueado"):
        return redirect(url_for("login"))


    # ----------------------------------------------
    # GUARDAR NUEVO MOVIMIENTO
    # ----------------------------------------------

    if request.method == "POST":

        fecha = request.form["fecha"]

        frasco = int(request.form["frasco"])

        efectivo = int(request.form["efectivo"])

        gastos = int(request.form["gastos"])

        detalle = request.form["detalle"].strip()


        nuevo_registro = {

            "fecha": fecha,

            "frasco": frasco,

            "efectivo": efectivo,

            "gastos": gastos,

            "detalle": detalle
        }


        registros_db.insert_one(
            nuevo_registro
        )


        return redirect(
            url_for("inicio")
        )


    # ----------------------------------------------
    # FILTRO POR MES
    # ----------------------------------------------

    mes = request.args.get(
        "mes",
        ""
    )


    filtro = {}


    if mes:

        filtro["fecha"] = {
            "$regex": "^" + re.escape(mes)
        }


    registros_mongo = list(

        registros_db
        .find(filtro)
        .sort([
            ("fecha", ASCENDING),
            ("_id", ASCENDING)
        ])

    )


    registros = [

        preparar_registro(registro)

        for registro in registros_mongo

    ]


    # ----------------------------------------------
    # TOTALES
    # ----------------------------------------------

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


    total = (
        total_frasco
        +
        total_efectivo
    )


    total_neto = (
        total
        -
        total_gastos
    )


    # ----------------------------------------------
    # SOCIEDAD ACUMULADA
    # ----------------------------------------------

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

            "registro":
                registro,

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
# ELIMINAR
# --------------------------------------------------

@app.route(
    "/eliminar/<id>",
    methods=["POST"]
)
def eliminar(id):

    if not session.get("logueado"):
        return redirect(url_for("login"))


    try:

        object_id = ObjectId(id)

    except InvalidId:

        return redirect(url_for("inicio"))


    registros_db.delete_one({
        "_id": object_id
    })


    return redirect(
        url_for("inicio")
    )


# --------------------------------------------------
# EDITAR
# --------------------------------------------------

@app.route(
    "/editar/<id>",
    methods=["GET", "POST"]
)
def editar(id):

    if not session.get("logueado"):
        return redirect(url_for("login"))


    try:

        object_id = ObjectId(id)

    except InvalidId:

        return redirect(url_for("inicio"))


    # ----------------------------------------------
    # GUARDAR CAMBIOS
    # ----------------------------------------------

    if request.method == "POST":

        fecha = request.form["fecha"]

        frasco = int(
            request.form["frasco"]
        )

        efectivo = int(
            request.form["efectivo"]
        )

        gastos = int(
            request.form["gastos"]
        )

        detalle = request.form["detalle"].strip()


        registros_db.update_one(

            {
                "_id": object_id
            },

            {
                "$set": {

                    "fecha":
                        fecha,

                    "frasco":
                        frasco,

                    "efectivo":
                        efectivo,

                    "gastos":
                        gastos,

                    "detalle":
                        detalle
                }
            }

        )


        return redirect(
            url_for("inicio")
        )


    # ----------------------------------------------
    # BUSCAR REGISTRO
    # ----------------------------------------------

    registro = registros_db.find_one({
        "_id": object_id
    })


    if registro is None:

        return redirect(
            url_for("inicio")
        )


    registro = preparar_registro(
        registro
    )


    return render_template(

        "editar.html",

        registro=registro

    )


# --------------------------------------------------
# INICIAR PROGRAMA
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=True
    )