from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    cargar_credenciales,
    obtener_ruta_pdf_temporal,
    limpiar_pdfs_temporales
)
from rpacometidos.robots.robot_cometidos import ejecutar_cometidos, procesar_cometidos_en_pagina
from rpacometidos.robots.robot_ssd import ejecutar_ssd, procesar_ssd_en_pagina
from rpacometidos.robots.robot_firmador import ejecutar_firmador, procesar_firmador_en_pagina
from rpacometidos.robots.orquestador import ejecutar_orquestador

__all__ = [
    "guardar_progreso",
    "cargar_datos_automatizacion",
    "guardar_datos_automatizacion",
    "cargar_credenciales",
    "obtener_ruta_pdf_temporal",
    "limpiar_pdfs_temporales",
    "ejecutar_cometidos",
    "procesar_cometidos_en_pagina",
    "ejecutar_ssd",
    "procesar_ssd_en_pagina",
    "ejecutar_firmador",
    "procesar_firmador_en_pagina",
    "ejecutar_orquestador"
]
