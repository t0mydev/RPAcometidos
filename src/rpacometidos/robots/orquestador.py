import time
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    cargar_credenciales,
    limpiar_pdfs_temporales
)
from rpacometidos.robots.robot_cometidos import procesar_cometidos_en_pagina
from rpacometidos.robots.robot_ssd import procesar_ssd_en_pagina
from rpacometidos.robots.robot_firmador import procesar_firmador_en_pagina

def ejecutar_orquestador(datos_excel=None, headless=False, slow_mo=600):
    """
    Orquestador principal: abre UNA SOLA ventana de navegador y ejecuta
    los robots en pestañas (páginas) separadas compartiendo el mismo contexto.
    """
    if datos_excel is None:
        datos_excel = cargar_datos_automatizacion()

    usuario_cometidos, clave_cometidos = cargar_credenciales(sistema="cometidos")
    usuario_ssd, clave_ssd = cargar_credenciales(sistema="ssd")
    usuario_firmador, clave_firmador = cargar_credenciales(sistema="firmador")
    total_registros = len(datos_excel)

    try:
        with sync_playwright() as p:
            # 1. Abre UNA SOLA instancia de navegador
            navegador = p.firefox.launch(headless=headless, slow_mo=slow_mo)
            contexto = navegador.new_context()

            # 2. Crea las pestañas necesarias
            # Pestaña para SSD
            #pagina_ssd = contexto.new_page()
            # Pestaña para Cometidos
            pagina_cometidos = contexto.new_page()
            # Pestaña para Firmador
            #pagina_firmador = contexto.new_page()
            

            # 3. Ejecuta los flujos
            # Primero SSD, necesita generar el número de proceso
            #procesar_ssd_en_pagina(pagina_ssd, datos_excel, usuario_ssd, clave_ssd)

            # Luego Cometidos
            procesar_cometidos_en_pagina(pagina_cometidos, datos_excel, usuario_cometidos, clave_cometidos)

            # Luego Firmador
            #procesar_firmador_en_pagina(pagina_firmador, datos_excel, usuario_firmador, clave_firmador)

            navegador.close()

    except Exception as e:
        guardar_progreso(0, total_registros, str(e), "error")
        raise e
    finally:
        # Se comenta temporalmente la limpieza para permitir pruebas con PDFs en temp_pdfs
        limpiar_pdfs_temporales()
        pass

if __name__ == "__main__":
    ejecutar_orquestador()
