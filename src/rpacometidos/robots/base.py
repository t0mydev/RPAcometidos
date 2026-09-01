import json
from pathlib import Path

# Raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

#base.py es un archivo que contiene funciones comunes utilizadas por los robots de automatización y el orquestador.

def guardar_progreso(paso, total, nombre, estado, detalle="", archivo="progreso_automatizacion.json"):
    """
    Guarda el progreso de la automatización en un archivo JSON para que Flask y Vue lo consulten.
    """
    try:
        path_progreso = BASE_DIR / archivo
        with open(path_progreso, "w", encoding="utf-8") as f:
            json.dump({
                "paso": paso,
                "total": total,
                "nombre": nombre,
                "estado": estado,
                "detalle": detalle
            }, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error al guardar progreso: {e}")

def cargar_datos_automatizacion(archivo="datos_automatizacion.json"):
    """
    Carga la lista de registros preparados desde la app Flask.
    """
    path_datos = BASE_DIR / archivo
    if not path_datos.exists():
        raise FileNotFoundError(f"El archivo de datos no se encontró en: {path_datos}")
    
    with open(path_datos, "r", encoding="utf-8") as f:
        return json.load(f)

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
        except Exception as e:
            print(f"Error al leer credenciales: {e}")
    return usuario, clave
