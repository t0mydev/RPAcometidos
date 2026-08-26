import pandas as pd
import re
from rapidfuzz import process, fuzz
from pathlib import Path

# Cargar la base de datos de conocidos (ruta absoluta respecto a la raíz del proyecto)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
path_conocidos = BASE_DIR / 'datos_conocidos.csv'
df_conocidos = pd.read_csv(path_conocidos)
# Normaliza los datos de la base para evitar fallas por espacios o mayúsculas
df_conocidos['rut'] = df_conocidos['rut'].astype(str).str.strip()
df_conocidos['sigla'] = df_conocidos['sigla'].astype(str).str.strip().str.upper()

# Extrae los datos conocidos a listas para agilizar la búsqueda
ruts_conocidos = df_conocidos['rut'].tolist()
siglas_conocidas = df_conocidos['sigla'].tolist()

def validar_registro(datos_entrantes):
    resultados_validacion = {
        "rut_valido": False,
        "sigla_valida": False,
        "sugerencia_correccion_rut": None,
        "sugerencia_correccion_sigla": None,
        "errores": []
    }

    rut_entrante = datos_entrantes.get('rut')
    sigla_entrante = datos_entrantes.get('sigla')

    rut_str = str(rut_entrante).strip() if rut_entrante and not pd.isna(rut_entrante) else ""
    sigla_str = str(sigla_entrante).strip().upper() if sigla_entrante and not pd.isna(sigla_entrante) else ""

    # 1. Identificar el conductor por RUT
    driver_row = None

    # Intento 1: Coincidencia exacta por RUT
    if rut_str:
        match = df_conocidos[df_conocidos['rut'] == rut_str]
        if not match.empty:
            driver_row = match.iloc[0]

    # Intento 2: Buscar por RUT usando RapidFuzz (coincidencia aceptable)
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
        known_sigla = driver_row['sigla']

        # Validación RUT
        if not rut_str:
            resultados_validacion['errores'].append("Falta el dato del RUT en la planilla cargada.")
            resultados_validacion['sugerencia_correccion_rut'] = known_rut
        elif rut_str == known_rut:
            resultados_validacion['rut_valido'] = True
        else:
            resultados_validacion['errores'].append(f"El RUT '{rut_str}' no coincide con el registrado (se esperaba '{known_rut}').")
            resultados_validacion['sugerencia_correccion_rut'] = known_rut

        # Validación sigla
        patron_sigla = r'^[A-Z0-9\-\s]{2,10}$'
        formato_correcto = bool(re.match(patron_sigla, sigla_str)) if sigla_str else False
        existe_sigla = sigla_str in siglas_conocidas

        if not sigla_str:
            resultados_validacion['errores'].append("Falta el dato de la sigla en la planilla cargada.")
            resultados_validacion['sugerencia_correccion_sigla'] = known_sigla
        elif sigla_str == known_sigla:
            resultados_validacion['sigla_valida'] = True
        else:
            resultados_validacion['errores'].append(f"La sigla '{sigla_str}' no coincide con la registrada para el RUT {known_rut} (se esperaba '{known_sigla}').")
            if not formato_correcto and not existe_sigla:
                resultados_validacion['errores'].append(f"Sigla con formato incorrecto: {sigla_str}")
            resultados_validacion['sugerencia_correccion_sigla'] = known_sigla

    else:
        # No se encontró ningún conductor registrado en la base por RUT
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

        # Validación sigla individual
        patron_sigla = r'^[A-Z0-9\-\s]{2,10}$'
        formato_correcto = bool(re.match(patron_sigla, sigla_str)) if sigla_str else False

        if not sigla_str:
            resultados_validacion['errores'].append("Falta el dato de la sigla en la planilla cargada.")
        else:
            if not formato_correcto:
                resultados_validacion['errores'].append(f"Sigla con formato incorrecto: {sigla_str}")
            resultados_validacion['errores'].append(f"La sigla '{sigla_str}' no fue encontrada en los registros conocidos.")
            
            mejor_coincidencia = process.extractOne(
                sigla_str,
                siglas_conocidas,
                scorer=fuzz.ratio
            )
            if mejor_coincidencia and mejor_coincidencia[1] >= 60:
                resultados_validacion['sugerencia_correccion_sigla'] = mejor_coincidencia[0]

    return resultados_validacion
