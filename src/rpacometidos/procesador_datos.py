import pandas as pd
import re
from rapidfuzz import process, fuzz
from pathlib import Path
#Cargar la base de datos de conocidos
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
df_conocidos = pd.read_csv(_BASE_DIR / 'datos_conocidos.csv')

#Extraemos los nombres conocidos a una lista para agilizar la búsqueda
nombres_conocidos = df_conocidos['nombre'].dropna().astype(str).tolist()

def validar_registro(datos_entrantes):
    resultados_validacion = {
        "rut_valido": False,
        "patente_valida": False,
        "nombre_valido": False,
        "sugerencia_correccion_nombre": None,
        "errores": []
    }

    rut_entrante = datos_entrantes.get('rut')
    patente_entrante = datos_entrantes.get('patente')
    nombre_entrante = datos_entrantes.get('nombre')

    #Validación de RUT
    if not rut_entrante or pd.isna(rut_entrante):
        resultados_validacion['errores'].append("Falta el dato del RUT en la planilla cargada.")
    else:
        #Si el dato existe, se ejecuta la validación lógica
        existe_rut = str(rut_entrante) in df_conocidos['rut'].astype(str).values
        if existe_rut:
            resultados_validacion['rut_valido'] = True
        else:
            resultados_validacion['errores'].append(f"RUT no encontrado en registros conocidos: {rut_entrante}")

    #Validación de Patente
    if not patente_entrante or pd.isna(patente_entrante):
        resultados_validacion['errores'].append("Falta el dato de la patente en la planilla cargada.")
    else:
        #Si el dato existe, se ejecuta la validación lógica
        patron_patente = r'^[BCDFGHJKLMNPRSTVWXYZ]{4}\d{2}$'
        if re.match(patron_patente, str(patente_entrante).upper()):
            resultados_validacion['patente_valida'] = True
        else:
            resultados_validacion['errores'].append(f"Patente con formato incorrecto: {patente_entrante}")

    #Validación de Nombre
    if not nombre_entrante or pd.isna(nombre_entrante):
        resultados_validacion['errores'].append("Falta el dato del nombre en la planilla cargada.")
    else:
        #Si el dato existe, se ejecuta la validación lógica
        nombre_str = str(nombre_entrante).strip()
        
        if nombre_str in nombres_conocidos:
            resultados_validacion['nombre_valido'] = True
        else:
            resultados_validacion['errores'].append(f"El nombre '{nombre_str}' no existe en los registros conocidos.")
            
            mejor_coincidencia = process.extractOne(
                nombre_str, 
                nombres_conocidos, 
                scorer=fuzz.ratio
            )
            
            if mejor_coincidencia:
                nombre_sugerido, similitud, indice = mejor_coincidencia
                if similitud >= 85:
                    resultados_validacion['sugerencia_correccion_nombre'] = nombre_sugerido

    return resultados_validacion