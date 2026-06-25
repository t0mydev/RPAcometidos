from flask import Flask, render_template, request, jsonify
from rpacometidos.lector_excel import procesar_planilla_completa

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
