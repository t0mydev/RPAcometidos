import openpyxl
from rpacometidos.procesador_datos import validar_registro

def procesar_planilla_completa(archivo_excel):
    
    wb = openpyxl.load_workbook(archivo_excel, data_only=True)
    hoja = wb.active
    
    reporte_final = []

    # Toma todos los datos de la primera fila y de ahí saca la posición de cada columna que tiene dato relevante
    encabezados = {celda.value: celda.column for celda in hoja[1] if celda.value}

    # Puede que estos nombres de encabezado cambien en el futuro 
    col_rut = encabezados.get("Rut")
    col_patente = encabezados.get("Patente")
    col_nombre = encabezados.get("Nombre")

    # Iteramos desde la fila 2 hasta la última fila con datos 
    for fila_indice in range(2, hoja.max_row + 1):
        # Extraemos los valores usando los índices de columna que encontramos
        rut = hoja.cell(row=fila_indice, column=col_rut).value if col_rut else None
        patente = hoja.cell(row=fila_indice, column=col_patente).value if col_patente else None
        nombre = hoja.cell(row=fila_indice, column=col_nombre).value if col_nombre else None
        
        # Ignora fila en blanco
        if rut is None and patente is None and nombre is None:
            continue
        
        # Construimos el diccionario para el proceso de validación
        datos_fila = {
            "rut": rut,
            "patente": patente,
            "nombre": nombre
        }
        
        # Enviamos los datos al flujo de revisión de RapidFuzz y expresiones regulares
        resultado_fila = validar_registro(datos_fila)
        
        # Inyectamos los datos originales y el número de fila para que la interfaz de Vue sepa exactamente dónde marcar el error
        resultado_fila["rut"] = rut
        resultado_fila["patente"] = patente
        resultado_fila["nombre"] = nombre
        resultado_fila["numero_fila_excel"] = fila_indice
        
        reporte_final.append(resultado_fila)

    return reporte_final