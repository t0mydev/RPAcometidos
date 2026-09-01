import time
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    cargar_credenciales
)

def procesar_cometidos_en_pagina(pagina, datos_excel, usuario, clave):
    """
    Ejecuta el flujo de cometidos dentro de una página (pestaña) de Playwright.
    """
    #url_login_personal = "https://personal.mop.gob.cl"
    #url_cometido = "https://personal.mop.gob.cl/Viatico/FormCreaViatico"
    url_login_personal = "file:///home/r0ars/Downloads/Portal%20Personal/Acceso%20__%20Sistema%20de%20Recursos%20Humanos%20__.html"
    url_cometido = "file:///home/r0ars/Downloads/Portal%20Personal/Crear%20Cometido%20Individual%20__%20Sistema%20de%20Recursos%20Humanos%20__.html"

    total_registros = len(datos_excel)

    # 1. Iniciar sesión en /personal/login
    guardar_progreso(0, total_registros, "Inicio de sesión", "iniciando", detalle="Iniciando sesión en Portal Personal")
    pagina.goto(url_login_personal)
    pagina.fill('#iduser', usuario)
    pagina.fill('#idpassword', clave)
    pagina.click('button[type="submit"]')
    pagina.wait_for_load_state('networkidle')

    # 2. Iterar por fila y completar cada cometido del Excel
    for fila, registro in enumerate(datos_excel, start=1):
        rut_raw = str(registro.get('rut', '')).strip()
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Buscando funcionario")
        print(f"[Cometidos] Procesando registro {fila}/{total_registros}: RUT {rut_raw}")

        # Navega a la vista de crear cometido
        pagina.goto(url_cometido)

        # Extrae el RUT sin dígito verificador para el elemento #txtRut
        rut_sin_dv = rut_raw.split('-')[0] if '-' in rut_raw else rut_raw

        # Rellena el RUT en el campo #txtRut y busca
        pagina.fill('#txtRut', rut_sin_dv)
        pagina.click('#btnBuscarUsuario')
        pagina.wait_for_load_state('networkidle')

        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Rellenando fechas y Considerando")

        # 3. Rellena fecha inicio y fecha término
        fecha_inicio = str(registro.get('fechainicio', '')).strip()
        fecha_termino = str(registro.get('fechatermino', '')).strip()

        dia_inicio = 0
        dia_termino = 0
        if "/" in fecha_inicio:
            d1, m1, a1 = fecha_inicio.split("/")
            fecha_inicio = f"{m1}{d1}{a1}"
            dia_inicio = int(d1)
        elif "-" in fecha_inicio:
            d1, m1, a1 = fecha_inicio.split("-")
            fecha_inicio = f"{m1}{d1}{a1}"
            dia_inicio = int(d1)

        if "/" in fecha_termino:
            d2, m2, a2 = fecha_termino.split("/")
            fecha_termino = f"{m2}{d2}{a2}"
            dia_termino = int(d2)
        elif "-" in fecha_termino:
            d2, m2, a2 = fecha_termino.split("-")
            fecha_termino = f"{m2}{d2}{a2}"
            dia_termino = int(d2)

        pagina.locator('#txtFechaInicio').click()
        pagina.locator('#txtFechaInicio').press_sequentially(fecha_inicio)

        pagina.locator('#txtFechaTermino').click()
        pagina.locator('#txtFechaTermino').press_sequentially(fecha_termino)

        # 4. Objetivo (valor por defecto: "Traslado de personal")
        pagina.locator('#txtObjetivo').fill("Traslado de personal")
    
        # 5. Arma texto y rellena Considerando
        fallback_val = str(registro.get('fallback_considerando', '') or '').strip()
        if fallback_val:
            texto_considerando = fallback_val
        else:
            sigla_val = str(registro.get('sigla', '')).strip()
            personal_raw = str(registro.get('personal_trasladado', '')).strip()
            partes_personal = [p.strip() for p in personal_raw.split("-")] if personal_raw else []

            dias_lista = []
            if dia_inicio and dia_termino and dia_inicio <= dia_termino:
                dias_lista = list(range(dia_inicio, dia_termino + 1))
            elif dia_inicio:
                dias_lista = [dia_inicio]

            partes_considerando = [f"SIGLA {sigla_val}"]
            if dias_lista:
                partes_considerando.append(f"DIA {dias_lista[0]}")
                if partes_personal and len(partes_personal) > 0 and partes_personal[0]:
                    partes_considerando.append(partes_personal[0])

                for i in range(1, len(dias_lista)):
                    dia_num = dias_lista[i]
                    partes_considerando.append(str(dia_num))
                    if i < len(partes_personal) and partes_personal[i]:
                        partes_considerando.append(partes_personal[i])

            texto_considerando = " ".join(partes_considerando).strip()

        pagina.locator('#txtConsiderando').fill(texto_considerando)

        # 6. Tipo de objetivo (valor por defecto: 27)
        pagina.locator('#ddlTipoObjetivo').select_option('27')

        # 7. Tipo de movilización
        tipo_movilizacion = str(registro.get('tipo_movilizacion', '') or registro.get('tipomovilizacion', '')).strip().upper()
        if tipo_movilizacion:
            try:
                pagina.locator('#ddlTipoMovilizacion').select_option(label=tipo_movilizacion)
            except Exception:
                pagina.locator('#ddlTipoMovilizacion').select_option(tipo_movilizacion)

        # 8. Región Principal (valor por defecto: Valparaíso '5')
        pagina.locator('#ddlRegion').select_option('5')

        # 9. Lugar Cometido
        pagina.locator('#txtLugar').fill(str(registro.get('lugar_cometido', '')).strip())

        # 10. Marca las regiones necesarias
        regiones_raw = str(registro.get('regiones', '')).strip()
        partes_regiones = [p.strip() for p in regiones_raw.split(",")] if regiones_raw else []
        for region in partes_regiones:
            if region:
                try:
                    pagina.get_by_label(region, exact=False).check()
                except Exception as e:
                    print(f"No se pudo marcar la región '{region}': {e}")

        # 11. Busca y selecciona Atribución
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Seleccionando Atribución y TD5")
        pagina.locator('#btnModalConfiere').click()
        pagina.wait_for_load_state('networkidle')
        pagina.locator('#txtConfiereM').press_sequentially(str(registro.get('atribucion', '')).strip())
        pagina.locator('#btnSeleccionaConfiere:visible').click()

        # 12. Busca y selecciona TD5
        pagina.locator('#btnModalTd5').click()
        pagina.wait_for_load_state('networkidle')
        pagina.get_by_title("Seleccionar TD5").click()

        # 13. Elegir días de la semana en el calendario
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Configurando calendario y porcentajes")
        mapeo_dias = {
            "lunes": "sel1",
            "martes": "sel2",
            "miercoles": "sel3", "miércoles": "sel3",
            "jueves": "sel4",
            "viernes": "sel5",
            "sabado": "sel6", "sábado": "sel6",
            "domingo": "sel7"
        }
        pagina.locator('#btnCalendarioViatico').click()

        dias_salida_raw = str(registro.get('dias_salida', '')).strip()
        if dias_salida_raw:
            dias_solicitados = [d.strip().lower() for d in dias_salida_raw.split(",")]
            checklist = [mapeo_dias[dia] for dia in dias_solicitados if dia in mapeo_dias]
            for sel in checklist:
                try:
                    pagina.locator(f'#{sel}').check()
                except Exception as e:
                    print(f"No se pudo marcar el selector '{sel}': {e}")

        pagina.locator('#btnGrabaCalendario').click()

        # 14. Porcentajes por día
        mapeo_porcentajes = {
            'dias_100': '#cien1',
            'dias_70':  '#setenta1',
            'dias_60':  '#sesenta1',
            'dias_50':  '#cincuenta1',
            'dias_40':  '#cuarenta1',
            'dias_35':  '#treinta1'
        }

        pagina.locator('#cien1').clear()
        pagina.locator('#cuarenta1').clear()

        for llave_json, id_selector in mapeo_porcentajes.items():
            valor = str(registro.get(llave_json, '')).strip()
            if valor:
                pagina.locator(id_selector).clear()
                pagina.locator(id_selector).fill(valor)

        # 15. Elegir Imputación presupuestaria
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Seleccionando imputación presupuestaria")
        pagina.get_by_title("Buscar Asignación Td5").click()
        pagina.wait_for_load_state('networkidle')

        tipo_imputacion = str(registro.get('tipo_imputacion_presupuestaria', '')).strip() or registro.get('tipo_imputacion_presupuestaria', '').strip()
        
        if tipo_imputacion:
            if tipo_imputacion == "Contrata":
                # Para hacer clic en la opción CONTRATA:
                pagina.locator("button[onclick*='CONTRATA']").click()
            elif tipo_imputacion == "Codigo del trabajo":
                # Para hacer clic en la opción CODIGO:
                pagina.locator("button[onclick*='CODIGO']").click()

        # 16. Número Proceso SSD (se integrará con robot_ssd)
        # time.sleep(2)
        # pagina.locator('#txtNumeroProceso').fill(registro.get('numero_ssd', ''))

        # 17. Guardar cometido
        # pagina.locator('#btnGrabarViatico').click()
        # pagina.wait_for_load_state('networkidle')

        time.sleep(2)

    guardar_progreso(total_registros, total_registros, "Cometidos", "completado", detalle="Automatización de cometidos finalizada exitosamente")
    print("[Cometidos] Automatización finalizada exitosamente.")

def ejecutar_cometidos(datos_excel=None, pagina=None, headless=False, slow_mo=600):
    """
    Punto de entrada para ejecutar la automatización de cometidos.
    Puede ejecutarse independientemente o reutilizando una página de Playwright existente.
    """
    if datos_excel is None:
        datos_excel = cargar_datos_automatizacion()

    usuario, clave = cargar_credenciales(sistema="cometidos")

    if pagina is not None:
        return procesar_cometidos_en_pagina(pagina, datos_excel, usuario, clave)

    try:
        with sync_playwright() as p:
            navegador = p.firefox.launch(headless=headless, slow_mo=slow_mo)
            contexto = navegador.new_context()
            pagina = contexto.new_page()
            procesar_cometidos_en_pagina(pagina, datos_excel, usuario, clave)
            navegador.close()
    except Exception as e:
        guardar_progreso(0, len(datos_excel), str(e), "error")
        raise e

if __name__ == "__main__":
    ejecutar_cometidos()
