from flask import Flask, render_template, request, jsonify, send_file
from rpacometidos.lector_excel import procesar_planilla_completa
import json
import io
import openpyxl

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
        col_rut = encabezados.get("Rut")
        col_patente = encabezados.get("Patente")
        col_nombre = encabezados.get("Nombre")

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
