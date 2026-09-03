import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    cargar_credenciales,
    obtener_ruta_pdf_temporal
)

def procesar_cometidos_en_pagina(pagina, datos_excel, usuario, clave):
    """
    Ejecuta el flujo de cometidos dentro de una página (pestaña) de Playwright.
    """
    url_login_personal = "https://personal.mop.gob.cl"
    url_cometido = "https://personal.mop.gob.cl/Viatico/FormCreaViatico"
    #url_login_personal = "file:///home/r0ars/Downloads/Portal%20Personal/Acceso%20__%20Sistema%20de%20Recursos%20Humanos%20__.html"
    #url_cometido = "file:///home/r0ars/Downloads/test_descarga_pdf.html"

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
        fecha_inicio_raw = str(registro.get('fechainicio', '')).strip()
        fecha_termino_raw = str(registro.get('fechatermino', '')).strip()
        fecha_inicio = fecha_inicio_raw
        fecha_termino = fecha_termino_raw

        if "/" in fecha_inicio:
            d1, m1, a1 = fecha_inicio.split("/")
            fecha_inicio = f"{m1}{d1}{a1}"
        elif "-" in fecha_inicio:
            d1, m1, a1 = fecha_inicio.split("-")
            fecha_inicio = f"{m1}{d1}{a1}"

        if "/" in fecha_termino:
            d2, m2, a2 = fecha_termino.split("/")
            fecha_termino = f"{m2}{d2}{a2}"
        elif "-" in fecha_termino:
            d2, m2, a2 = fecha_termino.split("-")
            fecha_termino = f"{m2}{d2}{a2}"

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
            try:
                sep_ini = "/" if "/" in fecha_inicio_raw else "-"
                sep_ter = "/" if "/" in fecha_termino_raw else "-"
                curr = datetime.strptime(fecha_inicio_raw, f"%d{sep_ini}%m{sep_ini}%Y")
                fin = datetime.strptime(fecha_termino_raw, f"%d{sep_ter}%m{sep_ter}%Y")
                while curr <= fin:
                    dias_lista.append(curr.day)
                    curr += timedelta(days=1)
            except Exception:
                pass

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
                except Exception:
                    pass

        # 11. Busca y selecciona Atribución
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Seleccionando Atribución y TD5")
        pagina.locator('#btnModalConfiere').click()
        pagina.wait_for_load_state('networkidle')
        pagina.locator('#txtConfiereM').press_sequentially(str(registro.get('atribucion', '')).strip(), delay=40)
        pagina.wait_for_function("Array.from(document.querySelectorAll('#btnSeleccionaConfiere')).filter(b => b.offsetParent !== null).length === 1")
        pagina.locator('#btnSeleccionaConfiere:visible').click()

        # 12. Busca y selecciona TD5
        pagina.locator('#btnModalTd5').click()
        pagina.wait_for_load_state('networkidle')
        pagina.get_by_title("Seleccionar TD5").click()

        # 13. Elegir días de la semana en el calendario
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Configurando calendario y porcentajes")
        pagina.locator('#btnCalendarioViatico').click()
        pagina.locator('#resultado_calendario tr').first.wait_for(state="visible")

        dias_salida_raw = str(registro.get('dias_salida', '')).strip()
        if dias_salida_raw:
            

            dias_solicitados = [d.strip().lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u') for d in dias_salida_raw.split(",") if d.strip()]
            filas_calendario = pagina.locator('#resultado_calendario tr')
            for i in range(filas_calendario.count()):
                fila_cal = filas_calendario.nth(i)
                nombre_dia = fila_cal.locator('td').nth(2).inner_text().strip().lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                if nombre_dia in dias_solicitados:
                    fila_cal.locator('input[type="checkbox"]').check()

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

        # 16. Número Proceso SSD (obtenido desde robot_ssd)
        numero_ssd = str(registro.get('numero_ssd', '')).strip()
        if numero_ssd:
            guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle=f"Ingresando N° SSD: {numero_ssd}")
            pagina.locator('#txtNumeroProceso').fill(numero_ssd)

        # 17. Guardar cometido y descargar PDF
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Guardando cometido y descargando PDF")
        pagina.locator('button#btnGrabarViatico', has_text="Grabar Cometido").click()

        # Espera el aviso modal de éxito y presiona Cerrar
        modal = pagina.locator('#mensajeModal')
        modal.wait_for(state="visible")
        modal.locator('button', has_text="Cerrar").click()
        modal.wait_for(state="hidden")

        # Captura la descarga del PDF al hacer clic en Imprimir Cometido
        with pagina.expect_download() as download_info:
            pagina.locator('#btnImprimirViatico').click()

        descarga = download_info.value
        ruta_pdf = obtener_ruta_pdf_temporal(f"cometido_{rut_raw}.pdf")
        descarga.save_as(ruta_pdf)

        registro['ruta_pdf'] = str(ruta_pdf)
        guardar_datos_automatizacion(datos_excel)
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Cometido guardado y PDF descargado")

        time.sleep(2)

    guardar_progreso(total_registros, total_registros, "Cometidos", "completado", detalle="Automatización de cometidos finalizada exitosamente")

def ejecutar_cometidos(datos_excel=None, pagina=None, headless=False):
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
            navegador = p.firefox.launch(headless=headless)
            contexto = navegador.new_context()
            pagina = contexto.new_page()
            procesar_cometidos_en_pagina(pagina, datos_excel, usuario, clave)
            navegador.close()
    except Exception as e:
        guardar_progreso(0, len(datos_excel), str(e), "error")
        raise e

if __name__ == "__main__":
    ejecutar_cometidos()
