import time
from rpacometidos.robots.base import guardar_progreso

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

    opcion = pagina.locator('.selectize-dropdown:visible .option').first
    opcion.wait_for(state="visible", timeout=4000)
    opcion.click()

    pagina.locator('#ddl_Rol').select_option(rol)
    pagina.locator('#btnAgregarPersona').click()
    if pagina.locator('.swal2-container').is_visible():
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
    #pagina.locator('#inp_nroproceso').fill("20572460")

    pagina.locator('#btnBussd').click()
    pagina.wait_for_load_state('networkidle')

    if pagina.locator('.swal2-container').is_visible():
            pagina.locator('.swal2-container').wait_for(state="hidden", timeout=10000)

    # Espera que aparezca la materia y copia el texto en Nombre y Descripción del Flujo
    campo_materia = pagina.locator('#inp_materia')
    campo_materia.wait_for(state="visible")
    pagina.wait_for_function("document.getElementById('inp_materia') && document.getElementById('inp_materia').value.trim() !== ''")

    if pagina.locator('.swal2-container').is_visible():
            pagina.locator('.swal2-container').wait_for(state="hidden", timeout=10000)

    texto_materia = campo_materia.input_value().strip()
    pagina.locator('#inp_nombreflujo').fill(texto_materia[:80])
    pagina.locator('#inp_descripcionflujo').fill(texto_materia[:180])

    if not pagina.locator('#inp_nombreflujo').input_value():
        pagina.locator('#inp_nombreflujo').fill(texto_materia[:80])

    if not pagina.locator('#inp_descripcionflujo').input_value():
        pagina.locator('#inp_descripcionflujo').fill(texto_materia[:180])

    # Agrega firmantes
    if nombre_firmantes:
        for firmante in nombre_firmantes.split(","):
            agregar_persona_firmador(pagina, firmante, 'FIRMANTE')

    # Agrega aprobador (o aprobadores si viniera más de uno por cualquier razón)
    if nombre_aprobador:
        for aprobador in nombre_aprobador.split(","):
            agregar_persona_firmador(pagina, aprobador, 'APROBADOR')
    time.sleep(5)
    # Carga el archivo PDF del cometido en el Firmador
    ruta_pdf = str(registro.get('ruta_pdf', '')).strip()
    #ruta_pdf = "/home/r0ars/Downloads/cometido.pdf"
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
