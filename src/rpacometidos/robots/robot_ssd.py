import time
import csv
import re
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    cargar_credenciales,
    BASE_DIR
)

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

def obtener_nombre_funcionario(rut):
    """Busca el nombre del funcionario en datos_conocidos.csv por RUT."""
    path_csv = BASE_DIR / 'datos_conocidos.csv'
    rut_str = str(rut).strip()
    if path_csv.exists():
        with open(path_csv, mode='r', encoding='utf-8') as f:
            lector = csv.DictReader(f)
            for fila in lector:
                if str(fila.get('rut', '')).strip() == rut_str:
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

def procesar_ssd_en_pagina(pagina, datos_excel, usuario, clave):
    """
    Ejecuta el flujo de SSD dentro de una página (pestaña) de Playwright.
    """
    total_registros = len(datos_excel)
    numero_capturado = {}

    def manejar_dialogo_ssd(dialog):
        texto = dialog.message
        match = re.search(r'\d+', texto)
        numero_capturado['numero'] = match.group() if match else ""
        time.sleep(5)

        dialog.accept()

    url_login_ssd = "http://ssd.mop.gov.cl/"
    #url_login_ssd = "file:///home/r0ars/Downloads/test_alerta_ssd.html"

    guardar_progreso(0, total_registros, "Inicio de sesión SSD", "iniciando", detalle="Iniciando sesión en Sistema SSD")

    # # 1. Login en el sistema SSD
    pagina.goto(url_login_ssd)
    pagina.locator('[name="txtUsuario"]').fill(usuario)
    pagina.locator('[name="txtPass"]').fill(clave)
    pagina.locator('[name="BtnEnviarRut"]').click()
    pagina.wait_for_load_state('networkidle')

    # 2. Procesar cada registro para generar el número de proceso SSD
    for fila, registro in enumerate(datos_excel, start=1):
        rut_raw = str(registro.get('rut', '')).strip()
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Abriendo formulario de despacho documentos en SSD")


        frm_main = pagina.frame_locator('frame[name="frmMain"]')
        frm_menu = pagina.frame_locator('frame[name="frmMenu"]')
        frm_menu.locator('#divoCMenu0_0').hover()
        time.sleep(0.5)
        frm_main.get_by_alt_text("Despachar Documentos", exact=False).first.click(force=True)
        pagina.wait_for_load_state('networkidle')

        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Configurando remitente y destinatario en SSD")
        frm_main.locator('[name="TxtOriginado_Des"]').fill("HUMANO")
        # Espera a que se abra la ventana emergente al presionar Enter
        with pagina.expect_popup() as popup_info1:
            frm_main.locator('[name="TxtOriginado_Des"]').press("Enter")
    
        popup1 = popup_info1.value
        popup1.wait_for_load_state('domcontentloaded')
        popup1.locator('[name="cboServicio"]').select_option('DV')
        popup1.wait_for_load_state('networkidle')
        popup1.locator('[name="cboRegion"]').select_option('5')
        popup1.wait_for_load_state('networkidle')
        popup1.get_by_title("Click para Seleccionar").click()


        frm_main.locator('[name="TxtDestinatario_Des"]').fill("PARTES DRV")
        with pagina.expect_popup() as popup_info2:
            frm_main.locator('[name="TxtDestinatario_Des"]').press("Enter")

        popup2 = popup_info2.value
        popup2.wait_for_load_state('domcontentloaded')
        popup2.locator('[name="cboServicio"]').select_option('DV')
        popup2.wait_for_load_state('networkidle')
        popup2.locator('[name="cboRegion"]').select_option('5')
        popup2.wait_for_load_state('networkidle')
        popup2.get_by_title("Click para Seleccionar").click()

        frm_main.locator('[name="Cbo_TipoDocto"]').select_option('57')

        # Genera el texto del cometido
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Generando texto y rellenando materia en SSD")
        texto_materia = generar_texto_cometido_ssd(registro)
        time.sleep(0.5)
        frm_main.locator('[name="TxtDescripcion"]').fill(texto_materia)


        frm_main.locator('[name="TxtDirigido_Des"]').fill("PARTES DRV")
        with pagina.expect_popup() as popup_info3:
            frm_main.locator('[name="TxtDirigido_Des"]').press("Enter")

        popup3 = popup_info3.value
        popup3.wait_for_load_state('domcontentloaded')
        popup3.locator('[name="cboServicio"]').select_option('DV')
        popup3.wait_for_load_state('networkidle')
        popup3.locator('[name="cboRegion"]').select_option('5')
        popup3.wait_for_load_state('networkidle')
        popup3.get_by_title("Click para Seleccionar").click()
        
        
        # Guarda el documento y captura la alerta nativa con el número de proceso
        numero_capturado.clear()
        pagina.once("dialog", manejar_dialogo_ssd)

        frm_main.locator('[name="Grabar"]').click()

        numero_proceso = numero_capturado.get('numero', '')

        # Guarda el número de proceso en el registro y en disco para compartir con cometidos
        registro['numero_ssd'] = numero_proceso
        guardar_datos_automatizacion(datos_excel)
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle=f"N° SSD generado: {numero_proceso}")

        time.sleep(1)

    guardar_progreso(total_registros, total_registros, "SSD", "completado", detalle="Automatización de SSD finalizada exitosamente")

def ejecutar_ssd(datos_excel=None, pagina=None, headless=False):
    """
    Punto de entrada para ejecutar la automatización del Sistema SSD.
    Puede ejecutarse independientemente o reutilizando una página de Playwright existente.
    """
    if datos_excel is None:
        datos_excel = cargar_datos_automatizacion()

    usuario, clave = cargar_credenciales(sistema="ssd")

    if pagina is not None:
        return procesar_ssd_en_pagina(pagina, datos_excel, usuario, clave)

    try:
        with sync_playwright() as p:
            navegador = p.firefox.launch(headless=headless)
            contexto = navegador.new_context()
            pagina = contexto.new_page()
            procesar_ssd_en_pagina(pagina, datos_excel, usuario, clave)
            navegador.close()
    except Exception as e:
        guardar_progreso(0, len(datos_excel), f"Error SSD: {str(e)}", "error")
        raise e

if __name__ == "__main__":
    ejecutar_ssd()
