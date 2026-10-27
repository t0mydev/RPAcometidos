import time
import os
from rpacometidos.robots.base import guardar_progreso
from rpacometidos.robots.resiliencia import (
    ContextoRobot,
    esperar_overlays,
    AccionError,
    CredencialesInvalidasError
)

def agregar_persona_firmador(pagina, nombre, rol, ctx):
    """
    Agrega una persona con su respectivo rol en el formulario del Firmador de forma defensiva y resiliente.
    """
    nombre_limpio = str(nombre or '').strip().upper()
    if not nombre_limpio:
        return

    ctx.registrar("Seleccionando responsable en lista", detalle=f"Seleccionando responsable en lista: {nombre_limpio}")
    esperar_overlays(pagina)

    input_resp = pagina.locator('input[placeholder="Seleccione Responsable..."]')
    try:
        input_resp.wait_for(state="visible", timeout=7000)
        input_resp.click()
        pagina.wait_for_timeout(50)
        input_resp.press_sequentially(nombre_limpio, delay=15)

        opcion = pagina.locator('.selectize-dropdown:visible .option').first
        opcion.wait_for(state="visible", timeout=6000)
        opcion.click()
    except Exception:
        raise AccionError(
            portal=ctx.portal, paso_stepper=ctx.paso_stepper,
            accion="Seleccionando responsable en lista",
            mensaje=f"No se encontró o no se pudo seleccionar a '{nombre_limpio}' en la lista de responsables.",
            selector='input[placeholder="Seleccione Responsable..."]'
        )

    ctx.seleccionar(pagina.locator('#ddl_Rol'), rol, "Seleccionando rol de responsable")
    ctx.hacer_clic(pagina.locator('#btnAgregarPersona'), "Agregando responsable al flujo")
    esperar_overlays(pagina)
    time.sleep(0.3)

def login_firmador(pagina, usuario, clave):
    """
    Inicia sesión en el Sistema Firmador de forma resiliente.
    """
    url_login_firmador = "https://firmador.mop.gob.cl/"
    ctx = ContextoRobot(pagina, "firmador", 2, fila=0, total=0, rut="Inicio de sesión")
    guardar_progreso(
        0, 0, "Inicio de sesión Firmador", "iniciando",
        detalle="Iniciando sesión en Sistema Firmador",
        portal="firmador", paso_stepper=2, accion_actual="Iniciando sesión en Firmador"
    )
    pagina.goto(url_login_firmador)
    ctx.escribir(pagina.locator('#inp_usr'), usuario, "Ingresando usuario Firmador", sensible=False)
    ctx.escribir(pagina.locator('#inp_pass'), clave, "Ingresando contraseña Firmador", sensible=True)
    ctx.hacer_clic(pagina.locator('#btnLogin'), "Enviando credenciales Firmador")
    try:
        pagina.wait_for_url(lambda u: u.strip("/") != url_login_firmador.strip("/"), timeout=10000)
    except Exception:
        raise CredencialesInvalidasError(
            portal="firmador",
            mensaje="Usuario o contraseña incorrectos al iniciar sesión en el Portal Firmador."
        )
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)

def procesar_un_firmador(pagina, registro, fila=1, total_registros=1):
    """
    Ejecuta el flujo para un único cometido en el Sistema Firmador con trazabilidad y resiliencia.
    """
    url_flujo_firmador = "https://firmador.mop.gob.cl/Flujo/Creacion_Flujo"
    portal = "firmador"
    paso_stepper = 4

    rut_raw = str(registro.get('rut', '')).strip()
    numero_ssd = str(registro.get('numero_ssd', '')).strip()
    nombre_aprobador = str(registro.get('nombre_aprobador', '')).strip()
    nombre_firmantes = str(registro.get('nombre_firmantes', '')).strip()

    ctx = ContextoRobot(pagina, portal, paso_stepper, fila=fila, total=total_registros, rut=rut_raw)

    guardar_progreso(
        fila, total_registros, rut_raw, "ejecutando",
        detalle="Abriendo formulario de creación de flujo en Firmador",
        portal=portal, paso_stepper=paso_stepper, accion_actual="Abriendo Creacion_Flujo"
    )
    pagina.goto(url_flujo_firmador)
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)

    # 1. Tipo de Documento
    ctx.seleccionar(
        pagina.locator('#ddl_TipoDocumento'), 'RESOLUCIÓN DE COMETIDO (OPV)',
        "Seleccionando tipo de documento en Firmador"
    )

    # 2. Número de Proceso
    ctx.escribir(pagina.locator('#inp_nroproceso'), numero_ssd, "Ingresando N° de proceso en Firmador")
    #ctx.escribir(pagina.locator('#inp_nroproceso'), "20572460", "Ingresando N° de proceso de prueba en Firmador")  # Para pruebas directas sin pasar por SSD

    # 3. Buscar proceso
    ctx.hacer_clic(pagina.locator('#btnBussd'), "Buscando N° de proceso en Firmador")
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)

    # 4. Espera que aparezca la materia y copia el texto en Nombre y Descripción del Flujo
    campo_materia = pagina.locator('#inp_materia')
    try:
        campo_materia.wait_for(state="visible", timeout=12000)
        pagina.wait_for_function(
            "document.getElementById('inp_materia') && document.getElementById('inp_materia').value.trim() !== ''",
            timeout=12000
        )
    except Exception:
        raise AccionError(
            portal=portal, paso_stepper=paso_stepper,
            accion="Cargando materia del proceso",
            mensaje=f"No se cargó la materia para el N° de proceso '{numero_ssd}' en Firmador.",
            selector="#inp_materia"
        )

    esperar_overlays(pagina)
    texto_materia = campo_materia.input_value().strip()

    ctx.escribir(pagina.locator('#inp_nombreflujo'), texto_materia[:80], "Ingresando nombre de flujo")
    ctx.escribir(pagina.locator('#inp_descripcionflujo'), texto_materia[:180], "Ingresando descripción de flujo")

    # 5. Agrega firmantes
    if nombre_firmantes:
        for firmante in nombre_firmantes.split(","):
            agregar_persona_firmador(pagina, firmante, 'FIRMANTE', ctx)

    # 6. Agrega aprobadores
    if nombre_aprobador:
        for aprobador in nombre_aprobador.split(","):
            agregar_persona_firmador(pagina, aprobador, 'APROBADOR', ctx)

    # 7. Carga el archivo PDF del cometido
    ruta_pdf = str(registro.get('ruta_pdf', '')).strip()
    #ruta_pdf = "/home/r0ars/Downloads/cometido.pdf"  # Para pruebas directas sin pasar por Personal
    if not ruta_pdf or not os.path.exists(ruta_pdf) or os.path.getsize(ruta_pdf) == 0:
        raise AccionError(
            portal=portal, paso_stepper=paso_stepper,
            accion="Adjuntando PDF en Firmador",
            mensaje=f"El archivo PDF del cometido no existe o está vacío: {ruta_pdf}"
        )

    ctx.registrar("Adjuntando PDF en Firmador", detalle="Cargando archivo PDF")
    pagina.locator('#fine-uploader-manual-trigger input[name="qqfile"]').set_input_files(ruta_pdf)
    time.sleep(1)
    esperar_overlays(pagina)

    # 8. Clic en Crear Flujo
    ctx.hacer_clic(pagina.locator('#btnCrearFlujo'), "Creando flujo en Firmador")

    # 9. Espera que aparezca el modal de confirmación
    modal_confirm = pagina.locator('#modConfirm')
    try:
        modal_confirm.wait_for(state="visible", timeout=12000)
    except Exception:
        raise AccionError(
            portal=portal, paso_stepper=paso_stepper,
            accion="Esperando modal de confirmación de flujo",
            mensaje="No apareció la ventana de confirmación tras hacer clic en Crear Flujo.",
            selector="#modConfirm"
        )

    # 10. Selecciona el servicio de la oficina de partes
    ctx.seleccionar(pagina.locator('#ddl_OficinaPartes_ser'), '204', "Seleccionando servicio en oficina de partes")

    # 11. Selecciona la región y dispara el evento para cargar los destinos
    ctx.seleccionar(pagina.locator('#ddl_OficinaPartes_reg'), '5', "Seleccionando región en oficina de partes")
    pagina.locator('#ddl_OficinaPartes_reg').dispatch_event('change')
    pagina.wait_for_load_state('networkidle')

    # Espera determinista a que el select de destino tenga sus opciones cargadas tras el cambio de región
    try:
        pagina.wait_for_function(
            "document.getElementById('ddl_OficinaPartes_nom') && document.getElementById('ddl_OficinaPartes_nom').options.length > 1",
            timeout=10000
        )
    except Exception:
        # Fallback a espera de overlay
        esperar_overlays(pagina)

    # 12. Selecciona el destino que coincida con Valparaíso ('456')
    ctx.seleccionar(pagina.locator('#ddl_OficinaPartes_nom'), '456', "Seleccionando destino en oficina de partes")

    # 13. Confirma la creación del flujo
    #ctx.hacer_clic(pagina.locator('#btnConfCreaFlujo'), "Confirmando creación de flujo")
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)

    guardar_progreso(
        fila, total_registros, rut_raw, "ejecutando",
        detalle="Flujo de firmas creado exitosamente en Firmador",
        portal=portal, paso_stepper=paso_stepper, accion_actual="Flujo creado exitosamente",
        estado_cometido="completado"
    )
    time.sleep(1)
