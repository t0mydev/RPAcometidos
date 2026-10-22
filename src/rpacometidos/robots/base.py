import json
from pathlib import Path

# Raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

#base.py es un archivo que contiene funciones comunes utilizadas por los robots de automatización y el orquestador.

def guardar_progreso(
    paso,
    total,
    nombre,
    estado,
    detalle="",
    archivo="progreso_automatizacion.json",
    portal="",
    paso_stepper=None,
    accion_actual="",
    ultimo_error=None,
    estado_cometido=None
):
    """
    Guarda el progreso de la automatización en un archivo JSON para que Flask y Vue lo consulten.
    Mantiene el estado global en curso y la lista estructurada `estados_cometidos` con la
    acción actual, detalle y error individual de cada cometido.
    """
    try:
        path_progreso = BASE_DIR / archivo
        estados_cometidos = []
        paso_stepper_guardado = 1
        total_guardado = 0

        reinicio = (estado == "no_iniciado" or portal == "inicio")

        # Preserva estados previos de cometidos salvo al reiniciar
        if not reinicio and path_progreso.exists():
            try:
                with open(path_progreso, "r", encoding="utf-8") as f:
                    prev = json.load(f)
                    estados_cometidos = prev.get("estados_cometidos", [])
                    paso_stepper_guardado = prev.get("paso_stepper", 1)
                    total_guardado = prev.get("total_cometidos", 0)
            except Exception:
                pass

        # Índice en base 0 del cometido actual
        indice = max(0, paso - 1)
        total_final = total if total > 0 else total_guardado

        # Deducción de paso del stepper si no se especificó
        if paso_stepper is None:
            if portal == "ssd":
                paso_stepper_final = 2
            elif portal == "personal":
                paso_stepper_final = 3
            elif portal == "firmador":
                paso_stepper_final = 4
            elif estado == "completado" or portal == "fin":
                paso_stepper_final = 5
            else:
                paso_stepper_final = paso_stepper_guardado
        else:
            paso_stepper_final = paso_stepper

        accion_final = accion_actual or detalle

        # Actualiza la estructura JSON individual del cometido actual
        if estado == "ejecutando" and paso > 0:
            item_cometido = next((c for c in estados_cometidos if c.get("indice") == indice), None)
            if item_cometido is None:
                item_cometido = {
                    "indice": indice,
                    "rut": nombre,
                    "estado": "ejecutando",
                    "portal": portal,
                    "accion_actual": accion_final,
                    "detalle": detalle,
                    "ultimo_error": None
                }
                estados_cometidos.append(item_cometido)

            item_cometido["rut"] = nombre or item_cometido.get("rut", "")
            if portal:
                item_cometido["portal"] = portal
            if accion_actual or not item_cometido.get("accion_actual"):
                item_cometido["accion_actual"] = accion_final
            item_cometido["detalle"] = detalle

            if ultimo_error is not None:
                item_cometido["ultimo_error"] = ultimo_error
                item_cometido["estado"] = "fallido"
            elif estado_cometido:
                item_cometido["estado"] = estado_cometido

        with open(path_progreso, "w", encoding="utf-8") as f:
            json.dump({
                "estado": estado,
                "paso_stepper": paso_stepper_final,
                "total_cometidos": total_final,
                "detalle": detalle,
                "estados_cometidos": estados_cometidos
            }, f, ensure_ascii=False, indent=4)
    except Exception:
        pass


def registrar_accion_progreso(fila, total, nombre, portal, paso_stepper, accion, detalle="", archivo="progreso_automatizacion.json"):
    """
    Atajo para registrar un micro-paso de acción dentro de un portal.
    Si fila == 0 (fase de autenticación previa al lote), mantiene estado="iniciando" para no disparar el bucle en el frontend.
    """
    estado = "iniciando" if fila == 0 else "ejecutando"
    guardar_progreso(
        paso=fila,
        total=total,
        nombre=nombre,
        estado=estado,
        detalle=detalle or accion,
        archivo=archivo,
        portal=portal,
        paso_stepper=paso_stepper,
        accion_actual=accion
    )

def cargar_datos_automatizacion(archivo="datos_automatizacion.json"):
    """
    Carga la lista de registros preparados desde la app Flask.
    """
    path_datos = BASE_DIR / archivo
    if not path_datos.exists():
        raise FileNotFoundError(f"El archivo de datos no se encontró en: {path_datos}")
    
    with open(path_datos, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_datos_automatizacion(datos, archivo="datos_automatizacion.json"):
    """
    Guarda o actualiza los datos de automatización en disco para compartir información entre robots.
    """
    try:
        path_datos = BASE_DIR / archivo
        with open(path_datos, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

def cargar_credenciales(sistema=None, archivo="credenciales.json"):
    """
    Carga usuario y contraseña del archivo de credenciales.
    Permite filtrar por sistema ('cometidos' o 'ssd').
    """
    path_credenciales = BASE_DIR / archivo
    usuario = "no lee el archivo"
    clave = "no lee el archivo"
    if path_credenciales.exists():
        try:
            with open(path_credenciales, "r", encoding="utf-8") as f:
                creds = json.load(f)
                if sistema and sistema in creds and isinstance(creds[sistema], dict):
                    seccion = creds[sistema]
                    usuario = seccion.get("usuario", usuario)
                    clave = seccion.get("clave", clave)
                else:
                    usuario = creds.get("usuario", usuario)
                    clave = creds.get("clave", clave)
        except Exception:
            pass
    return usuario, clave

def obtener_ruta_pdf_temporal(nombre_archivo):
    """
    Retorna la ruta absoluta para un PDF temporal y crea la carpeta si no existe.
    """
    carpeta_temp = BASE_DIR / "temp_pdfs"
    carpeta_temp.mkdir(parents=True, exist_ok=True)
    return carpeta_temp / nombre_archivo

def limpiar_pdfs_temporales():
    """
    Elimina todos los archivos PDF temporales generados durante la automatización.
    """
    carpeta_temp = BASE_DIR / "temp_pdfs"
    if carpeta_temp.exists():
        for archivo in carpeta_temp.glob("*.pdf"):
            try:
                archivo.unlink()
            except Exception:
                pass
