import time
import csv
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
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
    Ejemplo: COMETIDO DE SERVICIO HERNAN SAAVEDRA 17 21 AGOSTO 2026
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
    return f"COMETIDO DE SERVICIO {nombre} {dia_ini_num} {dia_ter_num} {nombre_mes} {anio}".strip()

def procesar_ssd_en_pagina(pagina, datos_excel, usuario, clave):
    """
    Ejecuta el flujo de SSD dentro de una página (pestaña) de Playwright.
    """
    total_registros = len(datos_excel)
    url_login_ssd = "https://ejemplo-ssd.gob.cl/login"

    guardar_progreso(0, total_registros, "Inicio de sesión SSD", "iniciando")
    print(f"[SSD] Iniciando sesión con usuario: {usuario}")

    # 1. Login en el sistema SSD
    # pagina.goto(url_login_ssd)
    # pagina.fill('#username', usuario)
    # pagina.fill('#password', clave)
    # pagina.click('#btnLogin')
    # pagina.wait_for_load_state('networkidle')

    # 2. Procesar cada registro para generar el número de proceso SSD
    for fila, registro in enumerate(datos_excel, start=1):
        rut_raw = registro.get('rut', '')
        guardar_progreso(fila, total_registros, f"SSD: {rut_raw}", "ejecutando")
        print(f"[SSD] Procesando registro {fila}/{total_registros}: RUT {rut_raw}")

        # TODO: Implementar pasos del sistema SSD aquí


        pagina.locator('#divoCMenu0_0').hover()
        pagina.get_by_alt_text("Despachar Documentos No Originados como respuesta a otros").click()
        pagina.wait_for_load_state('networkidle')


        pagina.locator('#TxtOriginado_Des').fill("HUMANO")
        # Espera a que se abra la ventana emergente al presionar Enter
        with pagina.expect_popup() as popup_info1:
            pagina.locator("#TxtOriginado_Des").press("Enter")
    
        popup1 = popup_info1.value

        popup1.locator('#cboServicio').select_option('DV')
        popup1.locator('#cboRegion').select_option('5')
        popup1.get_by_title("Click para Seleccionar").click()


        pagina.locator('#TxtDestinatario_Des').fill("PARTES DRV")
        with pagina.expect_popup() as popup_info2:
            pagina.locator("#TxtDestinatario_Des").press("Enter")

        popup2 = popup_info2.value
        popup2.locator('#cboServicio').select_option('DV')
        popup2.locator('#cboRegion').select_option('5')
        popup2.get_by_title("Click para Seleccionar").click()

        pagina.locator('#Cbo_TipoDocto').select_option('57')

        # Genera el texto del cometido
        texto_materia = generar_texto_cometido_ssd(registro)
        

        time.sleep(1)

    guardar_progreso(total_registros, total_registros, "SSD completado", "completado")
    print("[SSD] Automatización de SSD finalizada.")

def ejecutar_ssd(datos_excel=None, pagina=None, headless=False, slow_mo=600):
    """
    Punto de entrada para ejecutar la automatización del Sistema SSD.
    Puede ejecutarse independientemente o reutilizando una página de Playwright existente.
    """
    if datos_excel is None:
        datos_excel = cargar_datos_automatizacion()

    usuario, clave = cargar_credenciales()

    if pagina is not None:
        return procesar_ssd_en_pagina(pagina, datos_excel, usuario, clave)

    try:
        with sync_playwright() as p:
            navegador = p.firefox.launch(headless=headless, slow_mo=slow_mo)
            contexto = navegador.new_context()
            pagina = contexto.new_page()
            procesar_ssd_en_pagina(pagina, datos_excel, usuario, clave)
            navegador.close()
    except Exception as e:
        guardar_progreso(0, len(datos_excel), f"Error SSD: {str(e)}", "error")
        raise e

if __name__ == "__main__":
    ejecutar_ssd()
