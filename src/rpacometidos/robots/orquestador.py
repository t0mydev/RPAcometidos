import time
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    cargar_credenciales,
    limpiar_pdfs_temporales
)
from rpacometidos.robots.robot_ssd import login_ssd, procesar_un_ssd
from rpacometidos.robots.robot_cometidos import login_cometidos, procesar_un_cometido
from rpacometidos.robots.robot_firmador import login_firmador, procesar_un_firmador

def ejecutar_orquestador(datos_excel=None, headless=False, slow_mo=400):
    """
    Orquestador principal: abre UNA SOLA ventana de navegador y ejecuta
    los robots en pestañas separadas compartiendo el mismo contexto,
    procesando cometido por cometido de forma secuencial (SSD -> Cometido -> Firmador).
    """
    if datos_excel is None:
        datos_excel = cargar_datos_automatizacion()

    usuario_cometidos, clave_cometidos = cargar_credenciales(sistema="cometidos")
    usuario_ssd, clave_ssd = cargar_credenciales(sistema="ssd")
    usuario_firmador, clave_firmador = cargar_credenciales(sistema="firmador")
    total_registros = len(datos_excel)

    try:
        limpiar_pdfs_temporales()  # Limpia PDFs temporales antes de iniciar la automatización
        with sync_playwright() as p:
            # 1. Abre UNA SOLA instancia de navegador
            navegador = p.firefox.launch(headless=headless, slow_mo=slow_mo)
            contexto = navegador.new_context()

            # 2. Crea las pestañas necesarias
            pagina_ssd = contexto.new_page()
            pagina_cometidos = contexto.new_page()
            pagina_firmador = contexto.new_page()

            # 3. Iniciar sesión una sola vez en cada sistema
            login_ssd(pagina_ssd, usuario_ssd, clave_ssd)
            login_cometidos(pagina_cometidos, usuario_cometidos, clave_cometidos)
            login_firmador(pagina_firmador, usuario_firmador, clave_firmador)

            # 4. Procesa cometido por cometido de forma secuencial
            for fila, registro in enumerate(datos_excel, start=1):
                limpiar_pdfs_temporales()  # Limpia PDFs temporales antes de procesar cada registro
                # Paso A: SSD (obtiene número de proceso)
                numero_ssd = procesar_un_ssd(pagina_ssd, registro, fila, total_registros)
                registro['numero_ssd'] = numero_ssd
                guardar_datos_automatizacion(datos_excel)

                # Paso B: Cometidos (obtiene PDF descargado)
                ruta_pdf = procesar_un_cometido(pagina_cometidos, registro, fila, total_registros)
                registro['ruta_pdf'] = str(ruta_pdf)
                guardar_datos_automatizacion(datos_excel)

                # Paso C: Firmador (crea el flujo en firmador con el número SSD y PDF)
                procesar_un_firmador(pagina_firmador, registro, fila, total_registros)

            guardar_progreso(total_registros, total_registros, "Automatización", "completado", detalle="Todos los cometidos fueron procesados exitosamente")
            navegador.close()

    except Exception as e:
        guardar_progreso(0, total_registros, str(e), "error")
        raise e
    finally:
        # Se comenta temporalmente la limpieza para permitir pruebas con PDFs en temp_pdfs
        # limpiar_pdfs_temporales()
        pass

if __name__ == "__main__":
    ejecutar_orquestador()
