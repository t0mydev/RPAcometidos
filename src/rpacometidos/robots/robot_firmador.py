import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    cargar_credenciales,
    BASE_DIR
)

def agregar_persona_firmador(pagina, nombre, rol):
    """
    Agrega una persona con su respectivo rol en el formulario del Firmador.
    """
    nombre_limpio = str(nombre or '').strip().upper()
    if not nombre_limpio:
        return

    input_resp = pagina.locator('input[placeholder="Seleccione Responsable..."]')
    input_resp.click()
    pagina.wait_for_timeout(50)
    input_resp.press_sequentially(nombre_limpio, delay=10)
    pagina.wait_for_timeout(300)  # Espera un momento para que aparezcan las sugerencias
    input_resp.press("Enter")

    pagina.locator('#ddl_Rol').select_option(rol)
    pagina.locator('#btnAgregarPersona').click()
    pagina.locator('.swal2-container').wait_for(state="hidden", timeout=10000)
    time.sleep(0.2)

def login_firmador(pagina, usuario, clave):
    """
    Inicia sesión en el Sistema Firmador.
    """
    url_login_firmador = "https://firmador.mop.gob.cl/"
    guardar_progreso(0, 0, "Inicio de sesión Firmador", "iniciando", detalle="Iniciando sesión en Sistema Firmador")
    pagina.goto(url_login_firmador)
    pagina.locator('#inp_usr').fill(usuario)
    pagina.locator('#inp_pass').fill(clave)
    pagina.locator('#btnLogin').click()
    pagina.wait_for_url(lambda u: u.strip("/") != url_login_firmador.strip("/"), timeout=15000)
    pagina.wait_for_load_state('networkidle')

def procesar_un_firmador(pagina, registro, fila=1, total_registros=1):
    """
    Ejecuta el flujo para un único cometido en el Sistema Firmador.
    """
    url_flujo_firmador = "https://firmador.mop.gob.cl/Flujo/Creacion_Flujo"

    rut_raw = str(registro.get('rut', '')).strip()
    numero_ssd = str(registro.get('numero_ssd', '')).strip()
    nombre_aprobador = str(registro.get('nombre_aprobador', '')).strip()
    nombre_firmantes = str(registro.get('nombre_firmantes', '')).strip()
    
    guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Abriendo formulario en Firmador")
    pagina.goto(url_flujo_firmador)
    pagina.wait_for_load_state('networkidle')
    pagina.get_by_text("Se está cargando la información", exact=False).wait_for(state="hidden")

    pagina.locator('#ddl_TipoDocumento').select_option('RESOLUCIÓN DE COMETIDO (OPV)')

    pagina.locator('#inp_nroproceso').fill(numero_ssd)

    pagina.locator('#btnBussd').click()
    pagina.wait_for_load_state('networkidle')

    # Espera que aparezca la materia y copia el texto en Nombre y Descripción del Flujo
    campo_materia = pagina.locator('#inp_materia')
    campo_materia.wait_for(state="visible")
    pagina.wait_for_function("document.getElementById('inp_materia') && document.getElementById('inp_materia').value.trim() !== ''")

    texto_materia = campo_materia.input_value().strip()
    pagina.locator('#inp_nombreflujo').fill(texto_materia[:80])
    pagina.locator('#inp_descripcionflujo').fill(texto_materia[:180])

    # Agrega firmantes
    if nombre_firmantes:
        for firmante in nombre_firmantes.split(","):
            agregar_persona_firmador(pagina, firmante, 'FIRMANTE')

    # Agrega aprobador (o aprobadores si viniera más de uno por cualquier razón)
    if nombre_aprobador:
        for aprobador in nombre_aprobador.split(","):
            agregar_persona_firmador(pagina, aprobador, 'APROBADOR')

    # Carga el archivo PDF del cometido en el Firmador
    ruta_pdf = str(registro.get('ruta_pdf', '')).strip()
    if ruta_pdf:
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Cargando PDF en Firmador")
        pagina.locator('#fine-uploader-manual-trigger input[name="qqfile"]').set_input_files(ruta_pdf)

    guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Creando flujo en Firmador")
    # Hace clic en el botón principal para crear el flujo
    pagina.locator('#btnCrearFlujo').click()

    # Espera que aparezca el modal de confirmación
    modal_confirm = pagina.locator('#modConfirm')
    modal_confirm.wait_for(state="visible")

    # Selecciona el servicio de la oficina de partes
    pagina.locator('#ddl_OficinaPartes_ser').select_option('204')

    # Selecciona la región y dispara el evento para cargar los destinos
    pagina.locator('#ddl_OficinaPartes_reg').select_option('5')
    pagina.locator('#ddl_OficinaPartes_reg').dispatch_event('change')
    pagina.wait_for_load_state('networkidle')

    # Espera a que el banner de carga desaparezca
    pagina.get_by_text("Se esta cargando Oficinas de OPV", exact=False).wait_for(state="hidden")

    # Selecciona el destino que coincida con Valparaíso
    pagina.locator('#ddl_OficinaPartes_nom').select_option('456')

    # Confirma la creación del flujo
    pagina.locator('#btnConfCreaFlujo').click()
    pagina.wait_for_load_state('networkidle')

    time.sleep(2)

def procesar_firmador_en_pagina(pagina, datos_excel, usuario, clave):
    """
    Ejecuta el flujo del Sistema Firmador dentro de una página (pestaña) de Playwright.
    """
    total_registros = len(datos_excel)
    login_firmador(pagina, usuario, clave)

    # Procesar cada registro en el Firmador
    for fila, registro in enumerate(datos_excel, start=1):
        procesar_un_firmador(pagina, registro, fila, total_registros)

    guardar_progreso(total_registros, total_registros, "Firmador", "completado", detalle="Automatización de Firmador finalizada exitosamente")

def ejecutar_firmador(datos_excel=None, pagina=None, headless=False, slow_mo=600):
    """
    Punto de entrada para ejecutar la automatización del Firmador.
    Puede ejecutarse independientemente o reutilizando una página de Playwright existente.
    """
    if datos_excel is None:
        datos_excel = cargar_datos_automatizacion()

    usuario, clave = cargar_credenciales(sistema="firmador")

    if pagina is not None:
        return procesar_firmador_en_pagina(pagina, datos_excel, usuario, clave)

    try:
        with sync_playwright() as p:
            navegador = p.firefox.launch(headless=headless, slow_mo=slow_mo)
            contexto = navegador.new_context()
            pagina = contexto.new_page()
            procesar_firmador_en_pagina(pagina, datos_excel, usuario, clave)
            navegador.close()
    except Exception as e:
        guardar_progreso(0, len(datos_excel), f"Error Firmador: {str(e)}", "error")
        raise e

if __name__ == "__main__":
    ejecutar_firmador()
