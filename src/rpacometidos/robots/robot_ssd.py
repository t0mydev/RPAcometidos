import time
import csv
import re
from rpacometidos.robots.base import (
    guardar_progreso,
    BASE_DIR
)
from rpacometidos.robots.resiliencia import (
    ContextoRobot,
    AccionError,
    CredencialesInvalidasError
)
from rpacometidos.procesador_datos import normalizar_rut

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

def obtener_nombre_funcionario(rut):
    """Busca el nombre del funcionario en datos_conocidos.csv por RUT normalizado."""
    path_csv = BASE_DIR / 'datos_conocidos.csv'
    rut_norm = normalizar_rut(rut)
    if not rut_norm or not path_csv.exists():
        return ""
    with open(path_csv, mode='r', encoding='utf-8') as f:
        lector = csv.DictReader(f)
        for fila in lector:
            if normalizar_rut(fila.get('rut', '')) == rut_norm:
                return str(fila.get('nombre', '')).strip()
    return ""

def generar_texto_cometido_ssd(registro):
    """
    Genera el formato:
    COMETIDO DE SERVICIO (NOMBRE FUNCIONARIO) (DIA INICIO) (DIA TERMINO) (MES) (AÑO)
    Ejemplo: COMETIDO DE SERVICIO PABLO ROJAS 17 AL 21 AGOSTO 2026
    """
    rut = registro.get('rut', '')
    nombre = obtener_nombre_funcionario(rut).upper()
    
    # Extrae día inicio y mes
    fecha_ini = str(registro.get('fechainicio', '')).strip()
    sep_ini = "/" if "/" in fecha_ini else "-"
    partes_ini = fecha_ini.split(sep_ini)
    dia_ini = partes_ini[0] if len(partes_ini) > 0 else ""
    mes_num = partes_ini[1] if len(partes_ini) > 1 else "1"
    anio = partes_ini[2] if len(partes_ini) > 2 else ""

    # Extrae día término
    fecha_ter = str(registro.get('fechatermino', '')).strip()
    sep_ter = "/" if "/" in fecha_ter else "-"
    dia_ter = fecha_ter.split(sep_ter)[0] if fecha_ter else ""

    # Busca nombre del mes
    nombre_mes = MESES.get(int(mes_num), "") if mes_num.isdigit() else mes_num

    dia_ini_num = int(dia_ini) if dia_ini.isdigit() else dia_ini
    dia_ter_num = int(dia_ter) if dia_ter.isdigit() else dia_ter

    # Arma el texto final
    return f"COMETIDO DE SERVICIO {nombre} {dia_ini_num} AL {dia_ter_num} {nombre_mes} {anio}".strip()

def _seleccionar_en_popup_ssd(pagina, input_locator, valor, nombre_campo, ctx):
    """
    Llena un campo (Remitente, Destinatario, Dirigido a), abre el popup con Enter,
    selecciona servicio 'DV', región '5' y confirma la selección en el popup.
    """
    ctx.escribir(input_locator, valor, f"Ingresando {nombre_campo} en SSD")
    ctx.registrar(f"Abriendo popup de búsqueda de {nombre_campo}")
    try:
        with pagina.expect_popup(timeout=8000) as popup_info:
            input_locator.press("Enter")
    except Exception:
        time.sleep(0.5)
        try:
            with pagina.expect_popup(timeout=8000) as popup_info:
                input_locator.press("Enter")
        except Exception:
            raise AccionError(
                portal=ctx.portal,
                paso_stepper=ctx.paso_stepper,
                accion=f"Abriendo popup de búsqueda de {nombre_campo}",
                mensaje=f"No se abrió la ventana de búsqueda para '{nombre_campo}' al presionar Enter.",
                selector=str(input_locator)
            )

    popup = popup_info.value
    popup.wait_for_load_state('domcontentloaded')
    ctx.seleccionar(popup.locator('[name="cboServicio"]'), 'DV', f"Seleccionando servicio en popup de {nombre_campo}")
    popup.wait_for_load_state('networkidle')
    ctx.seleccionar(popup.locator('[name="cboRegion"]'), '5', f"Seleccionando región en popup de {nombre_campo}")
    popup.wait_for_load_state('networkidle')
    ctx.hacer_clic(popup.get_by_title("Click para Seleccionar"), f"Confirmando selección de {nombre_campo} en popup")

def login_ssd(pagina, usuario, clave):
    """
    Inicia sesión en el Sistema SSD de forma resiliente.
    """
    url_login_ssd = "http://ssd.mop.gov.cl/"
    ctx = ContextoRobot(pagina, "ssd", 2, fila=0, total=0, rut="Inicio de sesión")
    guardar_progreso(
        0, 0, "Inicio de sesión SSD", "iniciando",
        detalle="Iniciando sesión en Sistema SSD",
        portal="ssd", paso_stepper=2, accion_actual="Iniciando sesión en SSD"
    )
    pagina.goto(url_login_ssd)
    ctx.escribir(pagina.locator('[name="txtUsuario"]'), usuario, "Ingresando usuario SSD", sensible=False)
    ctx.escribir(pagina.locator('[name="txtPass"]'), clave, "Ingresando contraseña SSD", sensible=True)

    alerta_login = {"rechazado": False}
    def _capturar_alerta_login(dialog):
        alerta_login["rechazado"] = True
        try:
            dialog.accept()
        except Exception:
            pass

    pagina.on("dialog", _capturar_alerta_login)
    ctx.hacer_clic(pagina.locator('[name="BtnEnviarRut"]'), "Enviando credenciales SSD")
    pagina.wait_for_load_state('networkidle')
    time.sleep(0.8)
    try:
        pagina.remove_listener("dialog", _capturar_alerta_login)
    except Exception:
        pass

    if alerta_login["rechazado"] or pagina.locator('[name="txtUsuario"]').is_visible():
        raise CredencialesInvalidasError(
            portal="ssd",
            mensaje="Usuario o contraseña incorrectos al iniciar sesión en el Sistema SSD."
        )

def procesar_un_ssd(pagina, registro, fila=1, total_registros=1):
    """
    Procesa un único cometido en la pestaña de SSD y retorna el número de proceso generado.
    Cada acción cuenta con reintentos defensivos y trazabilidad de micro-paso.
    """
    numero_capturado = {}

    def manejar_dialogo_ssd(dialog):
        try:
            for _ in range(3):
                texto = dialog.message or ""
                match = re.search(r'\d+', texto)
                if match:
                    numero_capturado['numero'] = match.group()
                    break
                time.sleep(0.3)
        finally:
            time.sleep(0.5)
            dialog.accept()

    rut_raw = str(registro.get('rut', '')).strip()
    ctx = ContextoRobot(pagina, "ssd", 2, fila=fila, total=total_registros, rut=rut_raw)

    frm_main = pagina.frame_locator('frame[name="frmMain"]')
    frm_menu = pagina.frame_locator('frame[name="frmMenu"]')

    # Solo abre "Despachar Documentos" si el formulario no está ya abierto en pantalla (ej: fila 1)
    if not frm_main.locator('[name="TxtOriginado_Des"]').is_visible():
        frm_menu.locator('#divoCMenu0_0').hover()
        time.sleep(0.5)
        ctx.hacer_clic(
            frm_main.get_by_alt_text("Despachar Documentos", exact=False).first,
            "Abriendo formulario de despacho documentos en SSD",
            force=True
        )
        pagina.wait_for_load_state('networkidle')

    # 1. Remitente (HUMANO)
    _seleccionar_en_popup_ssd(pagina, frm_main.locator('[name="TxtOriginado_Des"]'), "HUMANO", "remitente", ctx)

    # 2. Destinatario (PARTES DRV)
    _seleccionar_en_popup_ssd(pagina, frm_main.locator('[name="TxtDestinatario_Des"]'), "PARTES DRV", "destinatario", ctx)

    # 3. Tipo Documento (57)
    ctx.seleccionar(
        frm_main.locator('[name="Cbo_TipoDocto"]'), '57',
        "Seleccionando tipo de documento en SSD"
    )

    # 4. Materia / Descripción
    texto_materia = generar_texto_cometido_ssd(registro)
    time.sleep(0.3)
    ctx.escribir(
        frm_main.locator('[name="TxtDescripcion"]'), texto_materia,
        "Ingresando materia del documento en SSD"
    )

    # 5. Dirigido a (PARTES DRV)
    _seleccionar_en_popup_ssd(pagina, frm_main.locator('[name="TxtDirigido_Des"]'), "PARTES DRV", "dirigido a", ctx)

    # 6. Grabar documento y capturar número de proceso
    numero_capturado.clear()
    pagina.once("dialog", manejar_dialogo_ssd)

    ctx.hacer_clic(
        frm_main.locator('[name="Grabar"]'),
        "Grabando documento en SSD"
    )

    # Verifica si se capturó el número; si no, espera 2 segundos y vuelve a revisar un par de veces
    for _ in range(3):
        if numero_capturado.get('numero'):
            break
        pagina.wait_for_timeout(2000)

    pagina.wait_for_load_state('networkidle')

    numero_proceso = numero_capturado.get('numero', '')
    if not numero_proceso:
        raise AccionError(
            portal="ssd",
            paso_stepper=2,
            accion="Captura N° SSD",
            mensaje="No se capturó la alerta nativa con el número de proceso tras hacer clic en Grabar en SSD",
            selector='[name="Grabar"]'
        )

    registro['numero_ssd'] = numero_proceso
    guardar_progreso(
        paso=fila,
        total=total_registros,
        nombre=rut_raw,
        estado="ejecutando",
        detalle=f"N° SSD generado: {numero_proceso}",
        portal="ssd",
        paso_stepper=2,
        accion_actual=f"N° SSD generado: {numero_proceso}"
    )

    time.sleep(1)
    return numero_proceso
