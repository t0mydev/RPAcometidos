import json
from pathlib import Path

# Raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

#base.py es un archivo que contiene funciones comunes utilizadas por los robots de automatización y el orquestador.

def guardar_progreso(paso, total, nombre, estado, detalle="", archivo="progreso_automatizacion.json"):
    """
    Guarda el progreso de la automatización en un archivo JSON para que Flask y Vue lo consulten.
    Mantiene un historial acumulativo de mensajes para que la interfaz web muestre todos los pasos.
    """
    try:
        path_progreso = BASE_DIR / archivo
        historial = []

        # Preserva el historial acumulado mientras la automatización está en curso
        if estado != "iniciando" and path_progreso.exists():
            try:
                with open(path_progreso, "r", encoding="utf-8") as f:
                    prev = json.load(f)
                    historial = prev.get("historial", [])
            except Exception:
                pass

        # Agrega el encabezado del cometido al iniciar una nueva fila
        if estado == "ejecutando" and paso > 0 and nombre:
            encabezado = f"Cometido {paso} de {total}: Procesando {nombre}"
            if not historial or encabezado not in historial:
                historial.append(encabezado)

        # Agrega el detalle específico de la etapa actual
        if detalle and (not historial or historial[-1] != detalle):
            historial.append(detalle)

        with open(path_progreso, "w", encoding="utf-8") as f:
            json.dump({
                "paso": paso,
                "total": total,
                "nombre": nombre,
                "estado": estado,
                "detalle": detalle,
                "historial": historial
            }, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

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
