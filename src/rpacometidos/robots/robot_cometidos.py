import time
import os
from datetime import datetime, timedelta
from rpacometidos.robots.base import (
    guardar_progreso,
    obtener_ruta_pdf_temporal
)
from rpacometidos.robots.resiliencia import (
    ContextoRobot,
    esperar_overlays,
    AccionError,
    CredencialesInvalidasError
)
from rpacometidos.procesador_datos import normalizar_rut

def login_cometidos(pagina, usuario, clave):
    """
    Inicia sesión en el Portal Personal MOP de forma resiliente.
    """
    url_login_personal = "https://personal.mop.gob.cl"
    ctx = ContextoRobot(pagina, "personal", 2, fila=0, total=0, rut="Inicio de sesión")
    guardar_progreso(
        0, 0, "Inicio de sesión Personal", "iniciando",
        detalle="Iniciando sesión en Portal Personal",
        portal="personal", paso_stepper=2, accion_actual="Iniciando sesión en Personal"
    )
    pagina.goto(url_login_personal)
    ctx.escribir(pagina.locator('#iduser'), usuario, "Ingresando usuario Personal", sensible=False)
    ctx.escribir(pagina.locator('#idpassword'), clave, "Ingresando contraseña Personal", sensible=True)
    ctx.hacer_clic(pagina.locator('button[type="submit"]'), "Enviando credenciales Personal")
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)
    time.sleep(0.8)
    if pagina.locator('#iduser').is_visible() or pagina.locator('#idpassword').is_visible():
        raise CredencialesInvalidasError(
            portal="personal",
            mensaje="Usuario o contraseña incorrectos al iniciar sesión en el Portal Personal."
        )

def procesar_un_cometido(pagina, registro, fila=1, total_registros=1):
    """
    Procesa un único cometido en el portal de personal y retorna la ruta del PDF descargado.
    Cada acción cuenta con reintentos y trazabilidad vía ContextoRobot.
    """
    portal = "personal"
    paso_stepper = 3
    url_cometido = "https://personal.mop.gob.cl/Viatico/FormCreaViatico"
    rut_raw = str(registro.get('rut', '')).strip()

    ctx = ContextoRobot(pagina, portal, paso_stepper, fila=fila, total=total_registros, rut=rut_raw)

    guardar_progreso(
        fila, total_registros, rut_raw, "ejecutando",
        detalle="Abriendo formulario de viático en Personal",
        portal=portal, paso_stepper=paso_stepper, accion_actual="Abriendo FormCreaViatico"
    )

    # 1. Navega a la vista de crear cometido
    pagina.goto(url_cometido)
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)

    # 2. Extrae el RUT normalizado (sin dígito verificador) para el elemento #txtRut y busca funcionario
    rut_sin_dv = normalizar_rut(rut_raw)
    ctx.escribir(pagina.locator('#txtRut'), rut_sin_dv, "Ingresando RUT funcionario")
    ctx.hacer_clic(pagina.locator('#btnBuscarUsuario'), "Buscando funcionario por RUT")
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)

    # 3. Rellena fecha inicio y fecha término (campos con máscara)
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

    ctx.escribir(pagina.locator('#txtFechaInicio'), fecha_inicio, "Ingresando fecha de inicio", delay_ms=30, secuencial=True, valor_mostrar=fecha_inicio_raw)
    ctx.escribir(pagina.locator('#txtFechaTermino'), fecha_termino, "Ingresando fecha de término", delay_ms=30, secuencial=True, valor_mostrar=fecha_termino_raw)

    # 4. Objetivo (valor por defecto: "Traslado de personal")
    ctx.escribir(pagina.locator('#txtObjetivo'), "Traslado de personal", "Ingresando objetivo")

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

        texto_considerando = " ".join(partes_considerando).strip().upper()

    ctx.escribir(pagina.locator('#txtConsiderando'), texto_considerando, "Ingresando texto considerando")

    # 6. Tipo de objetivo (valor por defecto: '27')
    ctx.seleccionar(pagina.locator('#ddlTipoObjetivo'), '27', "Seleccionando tipo de objetivo")

    # 7. Tipo de movilización
    tipo_movilizacion = str(registro.get('tipo_movilizacion', '') or registro.get('tipomovilizacion', '')).strip().upper()
    if tipo_movilizacion:
        ctx.seleccionar(pagina.locator('#ddlTipoMovilizacion'), tipo_movilizacion, "Seleccionando tipo de movilización")

    # 8. Región Principal (valor por defecto: Valparaíso '5')
    ctx.seleccionar(pagina.locator('#ddlRegion'), '5', "Seleccionando región principal")

    # 9. Lugar Cometido
    ctx.escribir(pagina.locator('#txtLugar'), str(registro.get('lugar_cometido', '')).strip(), "Ingresando lugar cometido")

    # 10. Marca las regiones necesarias (llamada a marcar_checkbox corregida sin desplazamiento de args)
    regiones_raw = str(registro.get('regiones', '')).strip()
    partes_regiones = [p.strip() for p in regiones_raw.split(",")] if regiones_raw else []
    for region in partes_regiones:
        if region:
            try:
                ctx.marcar_checkbox(pagina.get_by_label(region, exact=False), f"Marcando región {region}", marcar=True)
            except Exception:
                pass

    # 11. Busca y selecciona Atribución (si viene especificada)
    atribucion_val = str(registro.get('atribucion', '') or '').strip()
    if atribucion_val:
        ctx.hacer_clic(pagina.locator('#btnModalConfiere'), "Abriendo modal de atribución")
        pagina.wait_for_load_state('networkidle')
        esperar_overlays(pagina)

        ctx.escribir(pagina.locator('#txtConfiereM'), atribucion_val, "Buscando atribución", delay_ms=40, secuencial=True)

        try:
            pagina.wait_for_function(
                "Array.from(document.querySelectorAll('#btnSeleccionaConfiere')).filter(b => b.offsetParent !== null).length === 1",
                timeout=8000
            )
        except Exception:
            raise AccionError(
                portal=portal, paso_stepper=paso_stepper,
                accion="Buscando atribución",
                mensaje=f"No apareció la opción para seleccionar la atribución '{atribucion_val}'.",
                selector="#btnSeleccionaConfiere"
            )

        ctx.hacer_clic(pagina.locator('#btnSeleccionaConfiere:visible'), "Confirmando atribución")

    # 12. Busca y selecciona TD5
    ctx.hacer_clic(pagina.locator('#btnModalTd5'), "Abriendo modal TD5")
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)
    ctx.hacer_clic(pagina.get_by_title("Seleccionar TD5").first, "Seleccionando ítem TD5")

    # 13. Elegir días de la semana en el calendario
    ctx.hacer_clic(pagina.locator('#btnCalendarioViatico'), "Abriendo calendario de viáticos")
    pagina.locator('#resultado_calendario tr').first.wait_for(state="visible", timeout=8000)

    dias_salida_raw = str(registro.get('dias_salida', '')).strip()
    if dias_salida_raw:
        ctx.registrar("Marcando días de salida en calendario", detalle=f"Marcando días de salida en calendario: {dias_salida_raw}")
        dias_solicitados = [
            d.strip().lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            for d in dias_salida_raw.split(",") if d.strip()
        ]
        filas_calendario = pagina.locator('#resultado_calendario tr')
        for i in range(filas_calendario.count()):
            fila_cal = filas_calendario.nth(i)
            nombre_dia = fila_cal.locator('td').nth(2).inner_text().strip().lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            if nombre_dia in dias_solicitados:
                chk = fila_cal.locator('input[type="checkbox"]')
                if not chk.is_checked():
                    chk.check()

    ctx.hacer_clic(pagina.locator('#btnGrabaCalendario'), "Grabando calendario de viáticos")
    esperar_overlays(pagina)

    # 14. Porcentajes por día
    mapeo_porcentajes = {
        'dias_100': '#cien1',
        'dias_70':  '#setenta1',
        'dias_60':  '#sesenta1',
        'dias_50':  '#cincuenta1',
        'dias_40':  '#cuarenta1',
        'dias_35':  '#treinta1'
    }

    try:
        pagina.locator('#cien1').clear()
        pagina.locator('#cuarenta1').clear()
    except Exception:
        pass

    for llave_json, id_selector in mapeo_porcentajes.items():
        valor = str(registro.get(llave_json, '')).strip()
        if valor:
            pct = llave_json.split('_')[1]
            ctx.escribir(pagina.locator(id_selector), valor, f"Ingresando días al {pct}%")

    # 15. Elegir Imputación presupuestaria
    ctx.hacer_clic(pagina.get_by_title("Buscar Asignación Td5"), "Abriendo modal imputación TD5")
    pagina.wait_for_load_state('networkidle')
    esperar_overlays(pagina)

    tipo_imputacion = str(registro.get('tipo_imputacion_presupuestaria', '')).strip().upper()
    if tipo_imputacion:
        if tipo_imputacion == "CONTRATA":
            ctx.hacer_clic(pagina.locator("button[onclick*='CONTRATA']"), "Seleccionando imputación CONTRATA")
        elif tipo_imputacion == "CODIGO DEL TRABAJO":
            ctx.hacer_clic(pagina.locator("button[onclick*='CODIGO']"), "Seleccionando imputación CÓDIGO DEL TRABAJO")

    # 16. Número Proceso SSD (obtenido desde robot_ssd)
    numero_ssd = str(registro.get('numero_ssd', '')).strip()
    if numero_ssd:
        ctx.escribir(pagina.locator('#txtNumeroProceso'), numero_ssd, "Ingresando N° de proceso en Personal")

    # 17. Guardar cometido y descargar PDF
    ctx.hacer_clic(pagina.locator('button#btnGrabarViatico', has_text="Grabar Cometido"), "Grabando cometido")

    # Espera el aviso modal de éxito y presiona Cerrar
    modal = pagina.locator('#mensajeModal')
    try:
        modal.wait_for(state="visible", timeout=12000)
        ctx.hacer_clic(modal.locator('button', has_text="Cerrar"), "Cerrando confirmación de grabado", esperar_oculto=modal)
    except Exception:
        raise AccionError(
            portal=portal, paso_stepper=paso_stepper,
            accion="Confirmación grabado",
            mensaje="No apareció o no se pudo cerrar el mensaje de confirmación al grabar.",
            selector="#mensajeModal"
        )

    # Captura la descarga del PDF al hacer clic en Imprimir Cometido
    ctx.registrar("Descargando PDF del cometido")
    esperar_overlays(pagina)

    try:
        with pagina.expect_download(timeout=15000) as download_info:
            pagina.locator('#btnImprimirViatico').click()
        descarga = download_info.value
        ruta_pdf = obtener_ruta_pdf_temporal(f"cometido_{rut_raw}.pdf")
        descarga.save_as(ruta_pdf)
    except Exception:
        raise AccionError(
            portal=portal, paso_stepper=paso_stepper,
            accion="Descargar PDF",
            mensaje="No se pudo descargar el PDF del cometido.",
            selector="#btnImprimirViatico"
        )

    # Verificación defensiva de la existencia y tamaño del archivo PDF
    if not os.path.exists(ruta_pdf) or os.path.getsize(ruta_pdf) == 0:
        raise AccionError(
            portal=portal, paso_stepper=paso_stepper,
            accion="Verificar PDF",
            mensaje=f"El PDF descargado no existe o está vacío: {ruta_pdf}"
        )

    registro['ruta_pdf'] = str(ruta_pdf)
    guardar_progreso(
        fila, total_registros, rut_raw, "ejecutando",
        detalle="Cometido guardado y PDF descargado exitosamente",
        portal=portal, paso_stepper=paso_stepper, accion_actual="PDF descargado correctamente"
    )

    time.sleep(1)
    return str(ruta_pdf)
