import time
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    cargar_credenciales,
    limpiar_pdfs_temporales
)
from rpacometidos.robots.resiliencia import (
    AccionError,
    CredencialesInvalidasError,
    recuperar_entorno_limpio
)
from rpacometidos.robots.robot_ssd import login_ssd, procesar_un_ssd
from rpacometidos.robots.robot_cometidos import login_cometidos, procesar_un_cometido
from rpacometidos.robots.robot_firmador import login_firmador, procesar_un_firmador

def ejecutar_orquestador(datos_excel=None, headless=False, slow_mo=400):
    """
    Orquestador principal: abre UNA SOLA ventana de navegador y ejecuta
    los robots en pestañas separadas compartiendo el mismo contexto,
    procesando cometido por cometido de forma secuencial (SSD -> Cometido -> Firmador).
    Tolerante a fallos: si un cometido falla, se registra el error exacto y se continúa con el siguiente.
    """
    if datos_excel is None:
        datos_excel = cargar_datos_automatizacion()

    usuario_ssd, clave_ssd = cargar_credenciales(sistema="ssd")
    usuario_mop, clave_mop = cargar_credenciales(sistema="mop")
    total_registros = len(datos_excel)

    try:
        guardar_progreso(
            0, total_registros, "Inicio", "iniciando",
            detalle="Iniciando entorno de automatización...",
            portal="inicio", paso_stepper=1, accion_actual="Iniciando entorno de automatización"
        )
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
            login_cometidos(pagina_cometidos, usuario_mop, clave_mop)
            login_firmador(pagina_firmador, usuario_mop, clave_mop)

            # 4. Procesa cometido por cometido de forma secuencial
            for fila, registro in enumerate(datos_excel, start=1):
                rut_raw = str(registro.get('rut', '')).strip()
                limpiar_pdfs_temporales()  # Limpia PDFs temporales antes de procesar cada registro

                try:
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

                    registro['estado_proceso'] = 'completado'
                    guardar_datos_automatizacion(datos_excel)

                except AccionError as e:
                    # Registra el fallo de este cometido específico sin detener la automatización
                    error_info = e.a_dict()
                    registro['estado_proceso'] = 'fallido'
                    registro['error'] = error_info
                    guardar_datos_automatizacion(datos_excel)

                    guardar_progreso(
                        paso=fila,
                        total=total_registros,
                        nombre=rut_raw,
                        estado="ejecutando",
                        detalle=f"Fallo en {e.portal.upper()} ({e.accion}): {e.mensaje}",
                        portal=e.portal,
                        paso_stepper=e.paso_stepper,
                        accion_actual=e.accion,
                        ultimo_error=error_info
                    )

                    # Limpia popups y estados de formularios para el siguiente cometido
                    recuperar_entorno_limpio(pagina_ssd, pagina_cometidos, pagina_firmador)
                    continue

                except Exception:
                    # Captura cualquier error imprevisto
                    error_info = {
                        "portal": "general",
                        "paso_stepper": 0,
                        "accion": "Procesando cometido",
                        "mensaje": "Ocurrió un error inesperado al procesar este cometido en el navegador.",
                        "selector": ""
                    }
                    registro['estado_proceso'] = 'fallido'
                    registro['error'] = error_info
                    guardar_datos_automatizacion(datos_excel)

                    guardar_progreso(
                        paso=fila,
                        total=total_registros,
                        nombre=rut_raw,
                        estado="ejecutando",
                        detalle=f"Error inesperado al procesar el cometido #{fila}",
                        ultimo_error=error_info
                    )

                    recuperar_entorno_limpio(pagina_ssd, pagina_cometidos, pagina_firmador)
                    continue

            guardar_progreso(
                paso=total_registros,
                total=total_registros,
                nombre="Automatización",
                estado="completado",
                detalle="Todos los cometidos fueron procesados",
                portal="fin",
                paso_stepper=5,
                accion_actual="Fin de automatización"
            )
            navegador.close()

    except CredencialesInvalidasError as e:
        guardar_progreso(
            0, total_registros, "Credenciales inválidas", "error_credenciales",
            detalle=e.mensaje,
            portal=e.portal,
            paso_stepper=2,
            accion_actual="Credenciales rechazadas"
        )
    except AccionError as e:
        guardar_progreso(
            0, total_registros, "Error de inicio", "error",
            detalle=f"No se pudo iniciar sesión en {e.portal.upper()} ({e.accion}): {e.mensaje}"
        )
        raise e
    except Exception as e:
        guardar_progreso(
            0, total_registros, "Error de conexión", "error",
            detalle="No se pudo conectar a los portales institucionales. Verifica tu conexión a la red MOP/VPN o las credenciales ingresadas."
        )
        raise e
    finally:
        # Se comenta temporalmente la limpieza para permitir pruebas con PDFs en temp_pdfs
        # limpiar_pdfs_temporales()
        pass

if __name__ == "__main__":
    ejecutar_orquestador()
