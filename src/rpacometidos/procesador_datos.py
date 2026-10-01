import pandas as pd
import re
from datetime import datetime
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
# Separar RUTs conocidos por longitud de cuerpo para evitar comparaciones cruzadas (<10M vs >=10M)
ruts_8_digitos = [r for r in ruts_conocidos if len(r) == 8]
ruts_7_digitos = [r for r in ruts_conocidos if len(r) == 7]

COLUMNAS_CSV = ["rut", "nombre", "sigla"]

def recargar_datos_conocidos():
    """Recarga el archivo CSV en el DataFrame y las listas en memoria tras una edición."""
    global df_conocidos, ruts_conocidos, siglas_conocidas, ruts_8_digitos, ruts_7_digitos
    if path_conocidos.exists():
        df_conocidos = pd.read_csv(path_conocidos)
        df_conocidos['rut'] = df_conocidos['rut'].astype(str).str.strip()
        df_conocidos['sigla'] = df_conocidos['sigla'].astype(str).str.strip().str.upper()
        if 'nombre' in df_conocidos.columns:
            df_conocidos['nombre'] = df_conocidos['nombre'].astype(str).str.strip().str.upper()
    ruts_conocidos = df_conocidos['rut'].tolist()
    siglas_conocidas = df_conocidos['sigla'].tolist()
    ruts_8_digitos = [r for r in ruts_conocidos if len(r) == 8]
    ruts_7_digitos = [r for r in ruts_conocidos if len(r) == 7]

def _escribir_csv(registros):
    import csv
    with open(path_conocidos, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS_CSV)
        writer.writeheader()
        writer.writerows(registros)

def obtener_datos_conocidos():
    """Devuelve la lista de diccionarios del CSV."""
    if not path_conocidos.exists():
        return []
    import csv
    with open(path_conocidos, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def agregar_dato_conocido(rut_raw, nombre_raw, sigla_raw):
    """Agrega un nuevo registro normalizando el RUT. Lanza excepciones si es inválido o duplicado."""
    rut = normalizar_rut(rut_raw)
    nombre = str(nombre_raw or "").strip().upper()
    sigla = str(sigla_raw or "").strip().upper()

    if not rut or not nombre or not sigla:
        raise ValueError("Todos los campos son obligatorios.")

    registros = obtener_datos_conocidos()
    if any(r["rut"] == rut for r in registros):
        raise KeyError(f"El RUT {rut} ya existe.")

    registros.append({"rut": rut, "nombre": nombre, "sigla": sigla})
    _escribir_csv(registros)
    recargar_datos_conocidos()
    return rut

def editar_dato_conocido(rut_original_raw, nuevo_rut_raw, nuevo_nombre_raw, nueva_sigla_raw):
    """Edita un registro existente. Lanza excepciones si no existe o si colisiona."""
    rut_orig = normalizar_rut(rut_original_raw)
    nuevo_rut = normalizar_rut(nuevo_rut_raw)
    nuevo_nombre = str(nuevo_nombre_raw or "").strip().upper()
    nueva_sigla = str(nueva_sigla_raw or "").strip().upper()

    if not nuevo_rut or not nuevo_nombre or not nueva_sigla:
        raise ValueError("Todos los campos son obligatorios.")

    registros = obtener_datos_conocidos()
    encontrado = False
    for r in registros:
        if r["rut"] == rut_orig:
            if nuevo_rut != rut_orig and any(x["rut"] == nuevo_rut for x in registros):
                raise KeyError(f"El RUT {nuevo_rut} ya existe en otro registro.")
            r["rut"] = nuevo_rut
            r["nombre"] = nuevo_nombre
            r["sigla"] = nueva_sigla
            encontrado = True
            break

    if not encontrado:
        raise FileNotFoundError(f"No se encontró el RUT {rut_original_raw}.")

    _escribir_csv(registros)
    recargar_datos_conocidos()

def eliminar_dato_conocido(rut_raw):
    """Elimina el registro identificado por su RUT."""
    rut = normalizar_rut(rut_raw)
    registros = obtener_datos_conocidos()
    nuevos = [r for r in registros if r["rut"] != rut]

    if len(nuevos) == len(registros):
        raise FileNotFoundError(f"No se encontró el RUT {rut_raw}.")

    _escribir_csv(nuevos)
    recargar_datos_conocidos()

def normalizar_rut(valor):
    """
    Normaliza el RUT dejándolo solo como el cuerpo numérico (sin puntos, sin guión, sin DV).
    Maneja RUTs con guión ('13652729-0', '9361648-K'), con puntos ('13.652.729-0')
    o con DV pegado ('9361648K', '136527290').
    """
    if valor is None or pd.isna(valor):
        return ""
    s = str(valor).strip().replace('.', '').replace(' ', '').upper()
    if not s:
        return ""
    if '-' in s:
        s = s.split('-')[0]
    elif s.endswith('K'):
        s = s[:-1]
    elif len(s) == 9 and s.isdigit():
        s = s[:-1]
    return s

def parsear_fecha(valor):
    """Convierte el string 'DD/MM/AAAA' a fecha para comparar inicio vs término."""
    if not valor or pd.isna(valor):
        return None
    try:
        return datetime.strptime(str(valor).strip(), "%d/%m/%Y").date()
    except ValueError:
        return None

def contar_dias_salida(valor):
    """Cuenta días si vienen separados por coma (ej: 'Lunes, Martes') o como número."""
    if not valor or pd.isna(valor):
        return 0
    s = str(valor).strip()
    try:
        return int(float(s.replace(',', '.')))
    except ValueError:
        pass
    return len([d for d in s.split(',') if d.strip()])

def sumar_viaticos(datos):
    """Suma los porcentajes de viáticos de la fila."""
    campos = ['dias_100', 'dias_70', 'dias_60', 'dias_50', 'dias_40', 'dias_35']
    total = 0.0
    for c in campos:
        v = datos.get(c)
        if v is not None and not pd.isna(v):
            try:
                total += float(str(v).strip().replace(',', '.'))
            except ValueError:
                pass
    return total

def validar_registro(datos_entrantes):
    errores_por_grupo = {
        "identidad": [],
        "vehiculo": [],
        "viaticos": [],
        "admin": []
    }

    resultados_validacion = {
        "rut_valido": False,
        "sigla_valida": False,
        "viaticos_validos": True,
        "fechas_validas": True,
        "admin_valido": True,
        "sugerencia_correccion_rut": None,
        "sugerencia_correccion_sigla": None,
        "errores": [],
        "errores_por_grupo": errores_por_grupo
    }

    rut_entrante = datos_entrantes.get('rut')
    sigla_entrante = datos_entrantes.get('sigla')

    rut_str = normalizar_rut(rut_entrante)
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
        candidatos = ruts_8_digitos if len(rut_str) == 8 else (ruts_7_digitos if len(rut_str) == 7 else ruts_conocidos)
        mejor_coincidencia = process.extractOne(
            rut_str,
            candidatos,
            scorer=fuzz.ratio
        )
        if mejor_coincidencia and mejor_coincidencia[1] >= 80:
            rut_coincidente = mejor_coincidencia[0]
            driver_row = df_conocidos[df_conocidos['rut'] == rut_coincidente].iloc[0]

    # 2. Realizar las validaciones
    if driver_row is not None:
        # Se identificó un conductor registrado
        known_rut = driver_row['rut']
        known_sigla = driver_row['sigla']

        # Validación RUT
        if not rut_str:
            err = "Falta el dato del RUT en la planilla cargada."
            resultados_validacion['errores'].append(err)
            errores_por_grupo['identidad'].append(err)
            resultados_validacion['sugerencia_correccion_rut'] = known_rut
        elif rut_str == known_rut:
            resultados_validacion['rut_valido'] = True
        else:
            err = f"El RUT '{rut_str}' no coincide con el registrado (se esperaba '{known_rut}')."
            resultados_validacion['errores'].append(err)
            errores_por_grupo['identidad'].append(err)
            resultados_validacion['sugerencia_correccion_rut'] = known_rut

        # Validación sigla
        patron_sigla = r'^[A-Z0-9\-\s]{2,15}$'
        formato_correcto = bool(re.match(patron_sigla, sigla_str)) if sigla_str else False
        existe_sigla = sigla_str in siglas_conocidas

        if not sigla_str:
            err = "Falta el dato de la sigla en la planilla cargada."
            resultados_validacion['errores'].append(err)
            errores_por_grupo['vehiculo'].append(err)
            resultados_validacion['sugerencia_correccion_sigla'] = known_sigla
        elif sigla_str == known_sigla:
            resultados_validacion['sigla_valida'] = True
        else:
            err = f"La sigla '{sigla_str}' no coincide con la registrada para el RUT {known_rut} (se esperaba '{known_sigla}')."
            resultados_validacion['errores'].append(err)
            errores_por_grupo['vehiculo'].append(err)
            if not formato_correcto and not existe_sigla:
                err_fmt = f"Sigla con formato incorrecto: {sigla_str}"
                resultados_validacion['errores'].append(err_fmt)
                errores_por_grupo['vehiculo'].append(err_fmt)
            resultados_validacion['sugerencia_correccion_sigla'] = known_sigla

    else:
        # No se encontró ningún conductor registrado en la base por RUT
        # Validación RUT individual
        if not rut_str:
            err = "Falta el dato del RUT en la planilla cargada."
            resultados_validacion['errores'].append(err)
            errores_por_grupo['identidad'].append(err)
        else:
            err = f"RUT no encontrado en registros conocidos: {rut_str}"
            resultados_validacion['errores'].append(err)
            errores_por_grupo['identidad'].append(err)
            candidatos = ruts_8_digitos if len(rut_str) == 8 else (ruts_7_digitos if len(rut_str) == 7 else ruts_conocidos)
            mejor_coincidencia = process.extractOne(
                rut_str,
                candidatos,
                scorer=fuzz.ratio
            )
            if mejor_coincidencia and mejor_coincidencia[1] >= 80:
                resultados_validacion['sugerencia_correccion_rut'] = mejor_coincidencia[0]

        # Validación sigla individual
        patron_sigla = r'^[A-Z0-9\-\s]{2,15}$'
        formato_correcto = bool(re.match(patron_sigla, sigla_str)) if sigla_str else False

        if not sigla_str:
            err = "Falta el dato de la sigla en la planilla cargada."
            resultados_validacion['errores'].append(err)
            errores_por_grupo['vehiculo'].append(err)
        else:
            if not formato_correcto:
                err_fmt = f"Sigla con formato incorrecto: {sigla_str}"
                resultados_validacion['errores'].append(err_fmt)
                errores_por_grupo['vehiculo'].append(err_fmt)
            err_sig = f"La sigla '{sigla_str}' no fue encontrada en los registros conocidos."
            resultados_validacion['errores'].append(err_sig)
            errores_por_grupo['vehiculo'].append(err_sig)
            
            mejor_coincidencia = process.extractOne(
                sigla_str,
                siglas_conocidas,
                scorer=fuzz.ratio
            )
            if mejor_coincidencia and mejor_coincidencia[1] >= 60:
                resultados_validacion['sugerencia_correccion_sigla'] = mejor_coincidencia[0]

    # 3. Validación de coherencia de viáticos (Días de salida vs suma porcentajes)
    total_dias = contar_dias_salida(datos_entrantes.get('dias_salida'))
    suma_porc = sumar_viaticos(datos_entrantes)

    if total_dias > 0 and abs(total_dias - suma_porc) > 0.01:
        resultados_validacion['viaticos_validos'] = False
        msg_viatico = f"Se indicaron {total_dias} día(s) de salida pero los porcentajes suman {suma_porc:g}."
        resultados_validacion['errores'].append(msg_viatico)
        errores_por_grupo['viaticos'].append(msg_viatico)
    elif total_dias == 0 and suma_porc > 0:
        resultados_validacion['viaticos_validos'] = False
        msg_viatico = f"No se indicaron días de salida pero los porcentajes suman {suma_porc:g}."
        resultados_validacion['errores'].append(msg_viatico)
        errores_por_grupo['viaticos'].append(msg_viatico)

    # 4. Validación de datos administrativos y fechas
    campos_obligatorios = [
        ('fechainicio', 'Fecha de inicio'),
        ('fechatermino', 'Fecha de término'),
        ('dias_salida', 'Días de salida'),
        ('sigla', 'Sigla de vehículo'),
    ]
    for campo_req, label_req in campos_obligatorios:
        val = datos_entrantes.get(campo_req)
        if val is None or str(val).strip() == "" or pd.isna(val):
            resultados_validacion['admin_valido'] = False
            msg_req = f"El campo '{label_req}' es obligatorio y está vacío."
            if msg_req not in errores_por_grupo['admin']:
                resultados_validacion['errores'].append(msg_req)
                errores_por_grupo['admin'].append(msg_req)

    # Coherencia cronológica de fechas (inicio <= término)
    d_ini = parsear_fecha(datos_entrantes.get('fechainicio'))
    d_ter = parsear_fecha(datos_entrantes.get('fechatermino'))

    if datos_entrantes.get('fechainicio') and not d_ini:
        resultados_validacion['fechas_validas'] = False
        resultados_validacion['admin_valido'] = False
        msg_f = f"Formato inválido en fecha de inicio: '{datos_entrantes.get('fechainicio')}' (se esperaba DD/MM/AAAA)."
        resultados_validacion['errores'].append(msg_f)
        errores_por_grupo['admin'].append(msg_f)

    if datos_entrantes.get('fechatermino') and not d_ter:
        resultados_validacion['fechas_validas'] = False
        resultados_validacion['admin_valido'] = False
        msg_f = f"Formato inválido en fecha de término: '{datos_entrantes.get('fechatermino')}' (se esperaba DD/MM/AAAA)."
        resultados_validacion['errores'].append(msg_f)
        errores_por_grupo['admin'].append(msg_f)

    if d_ini and d_ter and d_ini > d_ter:
        resultados_validacion['fechas_validas'] = False
        resultados_validacion['admin_valido'] = False
        msg_f = f"La fecha de inicio ({datos_entrantes.get('fechainicio')}) es posterior a la fecha de término ({datos_entrantes.get('fechatermino')})."
        resultados_validacion['errores'].append(msg_f)
        errores_por_grupo['admin'].append(msg_f)

    return resultados_validacion
