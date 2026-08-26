import time
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    cargar_credenciales
)
from rpacometidos.robots.robot_cometidos import procesar_cometidos_en_pagina
from rpacometidos.robots.robot_ssd import procesar_ssd_en_pagina

def ejecutar_orquestador(datos_excel=None, headless=False, slow_mo=600):
    """
    Orquestador principal: abre UNA SOLA ventana de navegador y ejecuta
    los robots en pestañas (páginas) separadas compartiendo el mismo contexto.
    """
    if datos_excel is None:
        datos_excel = cargar_datos_automatizacion()

    usuario, clave = cargar_credenciales()
    total_registros = len(datos_excel)

    try:
        with sync_playwright() as p:
            # 1. Abre UNA SOLA instancia de navegador
            navegador = p.firefox.launch(headless=headless, slow_mo=slow_mo)
            contexto = navegador.new_context()

            # 2. Crea las pestañas necesarias
            # Pestaña para Cometidos
            pagina_cometidos = contexto.new_page()

            # Pestaña para SSD (descomentar cuando se active el robot de SSD)
            # pagina_ssd = contexto.new_page()

            # 3. Ejecuta los flujos
            # Por ejemplo: primero SSD si necesitas generar el número de proceso
            # procesar_ssd_en_pagina(pagina_ssd, datos_excel, usuario, clave)

            # Luego Cometidos
            procesar_cometidos_en_pagina(pagina_cometidos, datos_excel, usuario, clave)

            navegador.close()

    except Exception as e:
        guardar_progreso(0, total_registros, str(e), "error")
        raise e

if __name__ == "__main__":
    ejecutar_orquestador()
