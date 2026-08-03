from flask import Flask, render_template, request, jsonify, send_file
from rpacometidos.lector_excel import procesar_planilla_completa
import json
import io
import openpyxl
import os
from pathlib import Path

# Raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Unificamos ambas rutas hacia la carpeta static, ahora mismo inutil ya que flask actúa como api y no como servidor web, pero lo dejamos porque a futuro si servirá los archivos estáticos de Vue
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
        # Cargamos el archivo original preservando su estructura
        wb = openpyxl.load_workbook(archivo)
        hoja = wb.active
        
        # Mapeamos los encabezados para saber las columnas a modificar
        encabezados = {celda.value: celda.column for celda in hoja[1] if celda.value}
        col_rut = encabezados.get("RUT Funcionario  (Chofer)")
        col_patente = encabezados.get("Sigla Vehiculo")
        col_nombre = encabezados.get("Nombre Completo Funcionario (Chofer)")

        # Modificamos los valores
        for registro in datos_corregidos:
            fila_indice = registro.get("numero_fila_excel")
            if not fila_indice:
                continue
            
            if col_rut and "rut" in registro:
                hoja.cell(row=fila_indice, column=col_rut).value = registro["rut"]
            if col_nombre and "nombre" in registro:
                hoja.cell(row=fila_indice, column=col_nombre).value = registro["nombre"]
            if col_patente and "patente" in registro:
                hoja.cell(row=fila_indice, column=col_patente).value = registro["patente"]

        # Guardamos el archivo corregido en un buffer en memoria
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
    
#Codigo que quedó de la simulación de automatización que se hizo para la presentación, puede que sirva en el futuro para la automatización real, por ahora no se usa
import subprocess
import sys

@app.route('/api/empezar-automatizacion', methods=['POST'])
def empezar_automatizacion():
    try:
        path_progreso = BASE_DIR / "progreso_automatizacion.json"
        path_datos = BASE_DIR / "datos_automatizacion.json"
        path_robot = BASE_DIR / "robot_prueba.py" #este path debe cambiar al script en específico que se quiera ejecutar para la automatización real

        # Borramos el progreso anterior si existe
        if path_progreso.exists():
            try:
                path_progreso.unlink()
            except Exception:
                pass

        # Recuperamos los registros corregidos desde la vista
        datos = request.json or []
        
        # Le damos formato a los datos para el robot de Playwright
        datos_robot = []
        for registro in datos:
            nombre = registro.get("nombre")
            rut = registro.get("rut")
            patente = registro.get("patente")
            
            # Por defecto aprobado, a menos que falten datos esenciales
            estado = "aprobado"
            if not nombre or not rut or not patente:
                estado = "pendiente"
                
            datos_robot.append({
                "rut": rut or "",
                "nombre": nombre or "",
                "patente": patente or "",
                "accion": estado
            })
            
        # Guardamos los registros en datos_automatizacion.json
        with open(path_datos, "w", encoding="utf-8") as f:
            json.dump(datos_robot, f, ensure_ascii=False, indent=4)
            
        # Ejecutamos robot_prueba.py en segundo plano, estableciendo el directorio de trabajo
        subprocess.Popen([sys.executable, str(path_robot)], cwd=str(BASE_DIR))
        
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
