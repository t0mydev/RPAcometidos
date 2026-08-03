import pandas as pd
import re
from rapidfuzz import process, fuzz

from pathlib import Path

# Cargar la base de datos de conocidos (ruta absoluta respecto a la raíz del proyecto)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
path_conocidos = BASE_DIR / 'datos_conocidos.csv'
df_conocidos = pd.read_csv(path_conocidos)
# Normalizamos los datos de la base para evitar fallas por espacios o mayúsculas
df_conocidos['rut'] = df_conocidos['rut'].astype(str).str.strip()
df_conocidos['nombre'] = df_conocidos['nombre'].astype(str).str.strip()
df_conocidos['patente'] = df_conocidos['patente'].astype(str).str.strip().str.upper()

# Extraemos los datos conocidos a listas para agilizar la búsqueda
nombres_conocidos = df_conocidos['nombre'].tolist()
ruts_conocidos = df_conocidos['rut'].tolist()
patentes_conocidas = df_conocidos['patente'].tolist()

def validar_registro(datos_entrantes):
    resultados_validacion = {
        "rut_valido": False,
        "patente_valida": False,
        "nombre_valido": False,
        "sugerencia_correccion_nombre": None,
        "sugerencia_correccion_rut": None,
        "sugerencia_correccion_patente": None,
        "errores": []
    }

    rut_entrante = datos_entrantes.get('rut')
    patente_entrante = datos_entrantes.get('patente')
    nombre_entrante = datos_entrantes.get('nombre')

    rut_str = str(rut_entrante).strip() if rut_entrante and not pd.isna(rut_entrante) else ""
    nombre_str = str(nombre_entrante).strip() if nombre_entrante and not pd.isna(nombre_entrante) else ""
    patente_str = str(patente_entrante).strip().upper() if patente_entrante and not pd.isna(patente_entrante) else ""

    # 1. Identificar el perfil del conductor
    driver_row = None

    # Intento 1: Coincidencia exacta por RUT
    if rut_str:
        match = df_conocidos[df_conocidos['rut'] == rut_str]
        if not match.empty:
            driver_row = match.iloc[0]

    # Intento 2: Si no hay coincidencia exacta por RUT, coincidencia exacta por Nombre
    if driver_row is None and nombre_str:
        match = df_conocidos[df_conocidos['nombre'] == nombre_str]
        if not match.empty:
            driver_row = match.iloc[0]

    # Intento 3: Si no, buscar por Nombre usando RapidFuzz (coincidencia alta)
    if driver_row is None and nombre_str:
        mejor_coincidencia = process.extractOne(
            nombre_str,
            nombres_conocidos,
            scorer=fuzz.ratio
        )
        if mejor_coincidencia and mejor_coincidencia[1] >= 85:
            nombre_coincidente = mejor_coincidencia[0]
            driver_row = df_conocidos[df_conocidos['nombre'] == nombre_coincidente].iloc[0]

    # Intento 4: Si no, buscar por RUT usando RapidFuzz (coincidencia aceptable)
    if driver_row is None and rut_str:
        mejor_coincidencia = process.extractOne(
            rut_str,
            ruts_conocidos,
            scorer=fuzz.ratio
        )
        if mejor_coincidencia and mejor_coincidencia[1] >= 70:
            rut_coincidente = mejor_coincidencia[0]
            driver_row = df_conocidos[df_conocidos['rut'] == rut_coincidente].iloc[0]

    # 2. Realizar las validaciones
    if driver_row is not None:
        # Se identificó un conductor registrado
        known_rut = driver_row['rut']
        known_nombre = driver_row['nombre']
        known_patente = driver_row['patente']

        # Validación RUT
        if not rut_str:
            resultados_validacion['errores'].append("Falta el dato del RUT en la planilla cargada.")
            resultados_validacion['sugerencia_correccion_rut'] = known_rut
        elif rut_str == known_rut:
            resultados_validacion['rut_valido'] = True
        else:
            resultados_validacion['errores'].append(f"El RUT '{rut_str}' no coincide con el registrado para {known_nombre} (se esperaba '{known_rut}').")
            resultados_validacion['sugerencia_correccion_rut'] = known_rut

        # Validación Nombre
        if not nombre_str:
            resultados_validacion['errores'].append("Falta el dato del nombre en la planilla cargada.")
            resultados_validacion['sugerencia_correccion_nombre'] = known_nombre
        elif nombre_str == known_nombre:
            resultados_validacion['nombre_valido'] = True
        else:
            resultados_validacion['errores'].append(f"El nombre '{nombre_str}' no coincide con el registrado para el RUT {known_rut} (se esperaba '{known_nombre}').")
            resultados_validacion['sugerencia_correccion_nombre'] = known_nombre

        # Validación Patente
        patron_patente = r'^([A-Z]{4}\d{2}|[A-Z]{2}\d{4})$'
        formato_correcto = bool(re.match(patron_patente, patente_str)) if patente_str else False
        existe_patente = patente_str in patentes_conocidas

        if not patente_str:
            resultados_validacion['errores'].append("Falta el dato de la patente en la planilla cargada.")
            resultados_validacion['sugerencia_correccion_patente'] = known_patente
        elif patente_str == known_patente:
            resultados_validacion['patente_valida'] = True
        else:
            resultados_validacion['errores'].append(f"La patente '{patente_str}' no coincide con la registrada para el conductor {known_nombre} (se esperaba '{known_patente}').")
            if not formato_correcto and not existe_patente:
                resultados_validacion['errores'].append(f"Patente con formato incorrecto: {patente_str}")
            resultados_validacion['sugerencia_correccion_patente'] = known_patente

    else:
        # No se encontró ningún conductor registrado en la base
        # Fallback a validación individual antigua
        
        # Validación RUT individual
        if not rut_str:
            resultados_validacion['errores'].append("Falta el dato del RUT en la planilla cargada.")
        else:
            resultados_validacion['errores'].append(f"RUT no encontrado en registros conocidos: {rut_str}")
            mejor_coincidencia = process.extractOne(
                rut_str, 
                ruts_conocidos, 
                scorer=fuzz.ratio
            )
            if mejor_coincidencia and mejor_coincidencia[1] >= 70:
                resultados_validacion['sugerencia_correccion_rut'] = mejor_coincidencia[0]

        # Validación Patente individual
        patron_patente = r'^([A-Z]{4}\d{2}|[A-Z]{2}\d{4})$'
        formato_correcto = bool(re.match(patron_patente, patente_str)) if patente_str else False

        if not patente_str:
            resultados_validacion['errores'].append("Falta el dato de la patente en la planilla cargada.")
        else:
            if not formato_correcto:
                resultados_validacion['errores'].append(f"Patente con formato incorrecto: {patente_str}")
            resultados_validacion['errores'].append(f"La patente no fue encontrada en los registros conocidos: {patente_str}")
            
            mejor_coincidencia = process.extractOne(
                patente_str, 
                patentes_conocidas, 
                scorer=fuzz.ratio
            )
            if mejor_coincidencia and mejor_coincidencia[1] >= 60:
                resultados_validacion['sugerencia_correccion_patente'] = mejor_coincidencia[0]

        # Validación Nombre individual
        if not nombre_str:
            resultados_validacion['errores'].append("Falta el dato del nombre en la planilla cargada.")
        else:
            resultados_validacion['errores'].append(f"El nombre '{nombre_str}' no existe en los registros conocidos.")
            mejor_coincidencia = process.extractOne(
                nombre_str, 
                nombres_conocidos, 
                scorer=fuzz.ratio
            )
            if mejor_coincidencia and mejor_coincidencia[1] >= 85:
                resultados_validacion['sugerencia_correccion_nombre'] = mejor_coincidencia[0]
    return resultados_validacion
