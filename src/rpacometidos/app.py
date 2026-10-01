from flask import Flask, render_template, request, jsonify, send_file
from rpacometidos.lector_excel import procesar_planilla_completa
from rpacometidos.procesador_datos import (
    obtener_datos_conocidos,
    agregar_dato_conocido,
    editar_dato_conocido,
    eliminar_dato_conocido,
)
import json
import io
import openpyxl
import os
import subprocess
import sys
from pathlib import Path

# Raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Unifica ambas rutas hacia la carpeta static, ahora mismo inutil ya que flask actúa como api y no como servidor web, pero lo dejamos porque a futuro si servirá los archivos estáticos de Vue
app = Flask(__name__, template_folder="vue", static_folder="vue")

@app.route('/api/procesar-excel', methods=['POST'])
def procesar_excel():
    if 'documento_excel' not in request.files:
        return jsonify({"status": "error", "mensaje": "No se recibió ningún archivo"}), 400

    archivo = request.files['documento_excel']

    if archivo.filename == '':
        return jsonify({"status": "error", "mensaje": "El archivo seleccionado está vacío"}), 400

    
    reporte_validacion = procesar_planilla_completa(archivo)

    return jsonify({
        "status": "completado",
        "resultados": reporte_validacion
    }), 200

@app.route('/api/descargar-excel-corregido', methods=['POST'])
def descargar_excel_corregido():
    if 'documento_excel' not in request.files:
        return jsonify({"status": "error", "mensaje": "No se recibió el archivo original"}), 400
        
    archivo = request.files['documento_excel']
    datos_corregidos_str = request.form.get('reporte_corregido', '[]')
    
    try:
        datos_corregidos = json.loads(datos_corregidos_str)
    except Exception:
        return jsonify({"status": "error", "mensaje": "Formato de datos corregidos inválido"}), 400

    try:
        # Carga el archivo original preservando su estructura
        wb = openpyxl.load_workbook(archivo)
        hoja = wb.active
        
        # Mapea los encabezados para saber las columnas a modificar
        from rpacometidos.lector_excel import (
            buscar_columna,
            HEADER_RUT, HEADER_SIGLA, HEADER_TIPO_MOVILIZACION,
            HEADER_LUGAR_COMETIDO, HEADER_REGION_PRINCIPAL, HEADER_REGIONES,
            HEADER_PERSONAL_TRASLADADO, HEADER_NOMBRE_APROBADOR, HEADER_NOMBRE_FIRMANTES,
            HEADER_TIPO_IMPUTACION_PRESUPUESTARIA, HEADER_FALLBACK_CONSIDERANDO,
            HEADER_ATRIBUCION_ACTUAL, HEADER_DIAS_SALIDA, HEADER_DIAS_100,
            HEADER_DIAS_70, HEADER_DIAS_60, HEADER_DIAS_50, HEADER_DIAS_40, HEADER_DIAS_35
        )
        encabezados = {celda.value: celda.column for celda in hoja[2] if celda.value} or {celda.value: celda.column for celda in hoja[1] if celda.value}

        COLUMNAS = [
            ("rut",                          HEADER_RUT),
            ("sigla",                        HEADER_SIGLA),
            ("tipo_movilizacion",            HEADER_TIPO_MOVILIZACION),
            ("lugar_cometido",               HEADER_LUGAR_COMETIDO),
            ("region_principal",             HEADER_REGION_PRINCIPAL),
            ("regiones",                     HEADER_REGIONES),
            ("personal_trasladado",          HEADER_PERSONAL_TRASLADADO),
            ("nombre_aprobador",             HEADER_NOMBRE_APROBADOR),
            ("nombre_firmantes",             HEADER_NOMBRE_FIRMANTES),
            ("tipo_imputacion_presupuestaria", HEADER_TIPO_IMPUTACION_PRESUPUESTARIA),
            ("fallback_considerando",        HEADER_FALLBACK_CONSIDERANDO),
            ("atribucion",                   HEADER_ATRIBUCION_ACTUAL),
            ("dias_salida",                  HEADER_DIAS_SALIDA),
            ("dias_100",                     HEADER_DIAS_100),
            ("dias_70",                      HEADER_DIAS_70),
            ("dias_60",                      HEADER_DIAS_60),
            ("dias_50",                      HEADER_DIAS_50),
            ("dias_40",                      HEADER_DIAS_40),
            ("dias_35",                      HEADER_DIAS_35),
        ]
        col_map = {campo: buscar_columna(encabezados, header) for campo, header in COLUMNAS}

        # Modifica los valores
        for registro in datos_corregidos:
            fila_indice = registro.get("numero_fila_excel")
            if not fila_indice:
                continue
            for campo, col in col_map.items():
                if col and campo in registro:
                    hoja.cell(row=fila_indice, column=col).value = registro[campo]

        # Guarda el archivo corregido en un buffer en memoria
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        nombre_original = archivo.filename or "planilla.xlsx"
        nombre_corregido = nombre_original.rsplit('.', 1)[0] + "_corregido.xlsx"
        
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=nombre_corregido
        )
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al generar el archivo: {str(e)}"}), 500
    
@app.route('/api/empezar-automatizacion', methods=['POST'])
def empezar_automatizacion():
    try:
        path_progreso = BASE_DIR / "progreso_automatizacion.json"
        path_datos = BASE_DIR / "datos_automatizacion.json"

        # Borra el progreso anterior si existe
        if path_progreso.exists():
            try:
                path_progreso.unlink()
            except Exception:
                pass

        # Recupera los registros corregidos desde la vista
        datos = request.json or []
        
        # Le damos formato a los datos para el robot de Playwright
        CAMPOS_SIMPLES = [
            "rut", "sigla", "fechainicio", "fechatermino", "tipo_movilizacion",
            "personal_trasladado", "fallback_considerando", "lugar_cometido",
            "regiones", "atribucion", "dias_salida",
            "tipo_imputacion_presupuestaria", "nombre_aprobador", "nombre_firmantes"
        ]
        CAMPOS_NUMERICOS = ["dias_100", "dias_70", "dias_60", "dias_50", "dias_40", "dias_35"]

        datos_robot = []
        for registro in datos:
            dato = {campo: registro.get(campo) or "" for campo in CAMPOS_SIMPLES}
            # Los campos numéricos no pueden usar `or ""` porque 0 es un valor válido
            dato.update({campo: registro.get(campo) if registro.get(campo) is not None else "" for campo in CAMPOS_NUMERICOS})
            dato["accion"] = "aprobado" if dato["rut"] and dato["sigla"] else "pendiente"
            datos_robot.append(dato)
            
        # Guarda los registros en datos_automatizacion.json
        with open(path_datos, "w", encoding="utf-8") as f:
            json.dump(datos_robot, f, ensure_ascii=False, indent=4)
            
        # Ejecuta el orquestador de robots en segundo plano
        subprocess.Popen([sys.executable, "-m", "rpacometidos.robots.orquestador"], cwd=str(BASE_DIR))
        
        return jsonify({"status": "iniciado", "mensaje": "La automatización se ha iniciado correctamente."}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al iniciar el robot: {str(e)}"}), 500

@app.route('/api/progreso-automatizacion', methods=['GET'])
def progreso_automatizacion():
    path_progreso = BASE_DIR / "progreso_automatizacion.json"
    if path_progreso.exists():
        try:
            with open(path_progreso, "r", encoding="utf-8") as f:
                datos = json.load(f)
            return jsonify(datos), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"estado": "no_iniciado"}), 200

# ==============================================================
# Endpoints de Credenciales
# ==============================================================

# Funcion para crear el archivo .json de credenciales
@app.route('/api/guardar-credenciales', methods=['POST'])
def guardar_credenciales():
    try:
        # 1. Obtenemos los datos que nos envió Vue
        datos = request.get_json() or {}
        
        # 2. Definimos la ruta del archivo en la raíz del proyecto
        path_credenciales = BASE_DIR / "credenciales.json"
        
        # 3. Guardamos el archivo JSON en el disco
        with open(path_credenciales, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
            
        # 4. Respondemos a Vue que todo salió bien (Código 200 = Éxito)
        return jsonify({"status": "completado", "mensaje": "Credenciales guardadas correctamente"}), 200
        
    except Exception as e:
        # Si algo falla (ej. permisos de disco), avisamos del error (Código 500 = Error del servidor)
        return jsonify({"status": "error", "mensaje": f"Error al guardar: {str(e)}"}), 500

# Funcion para obtener el archivo .json de credenciales
@app.route('/api/obtener-credenciales', methods=['GET'])
def obtener_credenciales():
    try:
        path_credenciales = BASE_DIR / "credenciales.json"
        if path_credenciales.exists():
            with open(path_credenciales, "r", encoding="utf-8") as f:
                datos = json.load(f)
            return jsonify({"status": "completado", "credenciales": datos}), 200
        else:
            return jsonify({"status": "completado", "credenciales": {}}), 200
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al leer credenciales: {str(e)}"}), 500

# ==============================================================
# Endpoints de Datos Conocidos (Conductores / Vehículos)
# ==============================================================

@app.route('/api/datos-conocidos', methods=['GET'])
def listar_datos_conocidos():
    try:
        datos = obtener_datos_conocidos()
        return jsonify({"status": "completado", "datos": datos}), 200
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al leer datos conocidos: {str(e)}"}), 500

@app.route('/api/datos-conocidos', methods=['POST'])
def crear_dato_conocido():
    try:
        payload = request.get_json() or {}
        rut = payload.get("rut")
        nombre = payload.get("nombre")
        sigla = payload.get("sigla")

        agregar_dato_conocido(rut, nombre, sigla)
        return jsonify({"status": "completado", "mensaje": "Registro agregado correctamente."}), 201
    except ValueError as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 400
    except KeyError as e:
        return jsonify({"status": "error", "mensaje": str(e).strip("'")}), 409
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al guardar conductor: {str(e)}"}), 500

@app.route('/api/datos-conocidos/<rut_original>', methods=['PUT'])
def modificar_dato_conocido(rut_original):
    try:
        payload = request.get_json() or {}
        rut = payload.get("rut")
        nombre = payload.get("nombre")
        sigla = payload.get("sigla")

        editar_dato_conocido(rut_original, rut, nombre, sigla)
        return jsonify({"status": "completado", "mensaje": "Registro actualizado correctamente."}), 200
    except ValueError as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 400
    except KeyError as e:
        return jsonify({"status": "error", "mensaje": str(e).strip("'")}), 409
    except FileNotFoundError as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 404
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al modificar conductor: {str(e)}"}), 500

@app.route('/api/datos-conocidos/<rut>', methods=['DELETE'])
def borrar_dato_conocido(rut):
    try:
        eliminar_dato_conocido(rut)
        return jsonify({"status": "completado", "mensaje": "Registro eliminado correctamente."}), 200
    except FileNotFoundError as e:
        return jsonify({"status": "error", "mensaje": str(e)}), 404
    except Exception as e:
        return jsonify({"status": "error", "mensaje": f"Error al eliminar conductor: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
