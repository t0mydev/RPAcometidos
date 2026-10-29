from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    cargar_credenciales,
    obtener_ruta_pdf_temporal,
    limpiar_pdfs_temporales,
    registrar_accion_progreso
)
from rpacometidos.robots.resiliencia import (
    AccionError,
    ContextoRobot,
    escribir,
    hacer_clic,
    seleccionar,
    marcar_checkbox,
    esperar_overlays,
    recuperar_entorno_limpio
)
from rpacometidos.robots.robot_cometidos import login_cometidos, procesar_un_cometido
from rpacometidos.robots.robot_ssd import login_ssd, procesar_un_ssd
from rpacometidos.robots.robot_firmador import login_firmador, procesar_un_firmador
from rpacometidos.robots.orquestador import ejecutar_orquestador
from rpacometidos.robots.simulador import ejecutar_simulacion

__all__ = [
    "guardar_progreso",
    "registrar_accion_progreso",
    "cargar_datos_automatizacion",
    "guardar_datos_automatizacion",
    "cargar_credenciales",
    "obtener_ruta_pdf_temporal",
    "limpiar_pdfs_temporales",
    "AccionError",
    "ContextoRobot",
    "escribir",
    "hacer_clic",
    "seleccionar",
    "marcar_checkbox",
    "esperar_overlays",
    "recuperar_entorno_limpio",
    "login_cometidos",
    "procesar_un_cometido",
    "login_ssd",
    "procesar_un_ssd",
    "login_firmador",
    "procesar_un_firmador",
    "ejecutar_orquestador",
    "ejecutar_simulacion"
]
