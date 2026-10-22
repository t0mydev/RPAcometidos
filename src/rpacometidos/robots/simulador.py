import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    obtener_ruta_pdf_temporal,
    BASE_DIR
)
from rpacometidos.procesador_datos import normalizar_rut
from rpacometidos.robots.robot_ssd import generar_texto_cometido_ssd

# Carga variables de entorno desde .env
load_dotenv(BASE_DIR / ".env")

# El toggle se lee EXCLUSIVAMENTE desde el archivo .env
SIMULAR_FALLO = os.getenv("SIMULAR_FALLO", "false").lower() in ("true", "1", "yes")

def generar_pdf_simulado(rut_raw):
    """
    Crea un archivo PDF simulado válido en temp_pdfs si no existe,
    asegurando que las rutas temporales queden listas para el firmador.
    """
    ruta_pdf = obtener_ruta_pdf_temporal(f"cometido_{rut_raw}.pdf")
    if not ruta_pdf.exists():
        contenido_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n"
            b"0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n179\n%%EOF\n"
        )
        try:
            with open(ruta_pdf, "wb") as f:
                f.write(contenido_pdf)
        except Exception:
            pass
    return str(ruta_pdf)

def ejecutar_simulacion(datos_excel=None, delay=None):
    """
    Simulador de orquestación de alta fidelidad.
    Emite exactamente la misma secuencia atómica de micro-acciones que los robots reales
    (SSD -> Personal -> Firmador), reportando simultáneamente `accion_actual` y `detalle`.
    
    Tolerancia a fallos:
    Si la variable de entorno SIMULAR_FALLO=true en .env, simula un fallo en la atribución
    del primer cometido, demostrando que el robot no se cae, aísla el error y procesa
    exitosamente el segundo cometido.
    """
    if datos_excel is None:
        try:
            datos_excel = cargar_datos_automatizacion()
        except Exception:
            datos_excel = []

    # Garantiza al menos 2 cometidos para la demostración
    if len(datos_excel) < 2:
        registro_base = {
            "rut": "13193029-1",
            "sigla": "5F-KDMA-1604",
            "fechainicio": "05/10/2026",
            "fechatermino": "09/10/2026",
            "tipo_movilizacion": "Fiscal - Particular - Bus",
            "personal_trasladado": "H.SAAVEDRA/C.ALBANES",
            "fallback_considerando": "",
            "lugar_cometido": "LA LIGUA/CONCON",
            "regiones": "Valparaiso",
            "atribucion": "2698",
            "dias_salida": "Lunes, Martes, Miercoles, Jueves, Viernes",
            "tipo_imputacion_presupuestaria": "Contrata",
            "nombre_aprobador": "HERNAN SAAVEDRA GONZALEZ",
            "nombre_firmantes": "LEONARDO RODRIGUEZ PACHECO",
            "dias_100": "",
            "dias_70": "",
            "dias_60": "",
            "dias_50": "",
            "dias_40": "5",
            "dias_35": ""
        }
        registro_dos = dict(registro_base)
        registro_dos["fechainicio"] = "28/09/2026"
        registro_dos["fechatermino"] = "30/09/2026"
        registro_dos["atribucion"] = ""
        registro_dos["dias_40"] = "3"
        datos_excel = [registro_base, registro_dos]
        guardar_datos_automatizacion(datos_excel)

    total_registros = len(datos_excel)

    # Calibración de pausa entre micro-pasos (~15 a 20 segundos totales para 2 cometidos)
    if delay is None:
        delay = 0.14

    # ── FASE PRE-LOTE: Inicio de entorno y autenticación (fila=0, estado="iniciando") ──
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio", estado="iniciando",
        detalle="Iniciando entorno de automatización...",
        portal="inicio", paso_stepper=1, accion_actual="Iniciando entorno de automatización"
    )
    time.sleep(delay)

    # Login SSD
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión SSD", estado="iniciando",
        detalle="Iniciando sesión en Sistema SSD",
        portal="ssd", paso_stepper=2, accion_actual="Iniciando sesión en SSD"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión SSD", estado="iniciando",
        detalle="Ingresando usuario SSD: admin",
        portal="ssd", paso_stepper=2, accion_actual="Ingresando usuario SSD"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión SSD", estado="iniciando",
        detalle="Ingresando contraseña SSD: ***",
        portal="ssd", paso_stepper=2, accion_actual="Ingresando contraseña SSD"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión SSD", estado="iniciando",
        detalle="Enviando credenciales SSD",
        portal="ssd", paso_stepper=2, accion_actual="Enviando credenciales SSD"
    )
    time.sleep(delay)

    # Login Personal
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión Personal", estado="iniciando",
        detalle="Iniciando sesión en Portal Personal",
        portal="personal", paso_stepper=2, accion_actual="Iniciando sesión en Personal"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión Personal", estado="iniciando",
        detalle="Ingresando usuario Personal: admin",
        portal="personal", paso_stepper=2, accion_actual="Ingresando usuario Personal"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión Personal", estado="iniciando",
        detalle="Ingresando contraseña Personal: ***",
        portal="personal", paso_stepper=2, accion_actual="Ingresando contraseña Personal"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión Personal", estado="iniciando",
        detalle="Enviando credenciales Personal",
        portal="personal", paso_stepper=2, accion_actual="Enviando credenciales Personal"
    )
    time.sleep(delay)

    # Login Firmador
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión Firmador", estado="iniciando",
        detalle="Iniciando sesión en Sistema Firmador",
        portal="firmador", paso_stepper=2, accion_actual="Iniciando sesión en Firmador"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión Firmador", estado="iniciando",
        detalle="Ingresando usuario Firmador: admin",
        portal="firmador", paso_stepper=2, accion_actual="Ingresando usuario Firmador"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión Firmador", estado="iniciando",
        detalle="Ingresando contraseña Firmador: ***",
        portal="firmador", paso_stepper=2, accion_actual="Ingresando contraseña Firmador"
    )
    time.sleep(delay)
    guardar_progreso(
        paso=0, total=total_registros, nombre="Inicio de sesión Firmador", estado="iniciando",
        detalle="Enviando credenciales Firmador",
        portal="firmador", paso_stepper=2, accion_actual="Enviando credenciales Firmador"
    )
    time.sleep(delay)

    # ── BUCLE DE PROCESAMIENTO POR COMETIDO ──
    for fila, registro in enumerate(datos_excel, start=1):
        rut_raw = str(registro.get('rut', '')).strip() or "13193029-1"

        def emitir(portal, paso_stepper, accion, detalle="", estado_cometido=None):
            guardar_progreso(
                paso=fila,
                total=total_registros,
                nombre=rut_raw,
                estado="ejecutando",
                detalle=detalle or accion,
                portal=portal,
                paso_stepper=paso_stepper,
                accion_actual=accion,
                estado_cometido=estado_cometido
            )
            time.sleep(delay)

        def simular_popup_ssd(nombre_campo, valor):
            emitir("ssd", 2, f"Ingresando {nombre_campo} en SSD", f"Ingresando {nombre_campo} en SSD: {valor}")
            emitir("ssd", 2, f"Abriendo popup de búsqueda de {nombre_campo}")
            emitir("ssd", 2, f"Seleccionando servicio en popup de {nombre_campo}", f"Seleccionando servicio en popup de {nombre_campo}: DV")
            emitir("ssd", 2, f"Seleccionando región en popup de {nombre_campo}", f"Seleccionando región en popup de {nombre_campo}: 5")
            emitir("ssd", 2, f"Confirmando selección de {nombre_campo} en popup")

        # ══════════════════════════════════════════
        # 1. SISTEMA SSD (Paso Stepper 2)
        # ══════════════════════════════════════════
        if fila == 1:
            emitir("ssd", 2, "Abriendo formulario de despacho documentos en SSD")

        # 1. Remitente
        simular_popup_ssd("remitente", "HUMANO")

        # 2. Destinatario
        simular_popup_ssd("destinatario", "PARTES DRV")

        # 3. Tipo Documento
        emitir("ssd", 2, "Seleccionando tipo de documento en SSD", "Seleccionando tipo de documento en SSD: 57")

        # 4. Materia
        texto_materia = generar_texto_cometido_ssd(registro)
        emitir("ssd", 2, "Ingresando materia del documento en SSD", f"Ingresando materia del documento en SSD: {texto_materia}")

        # 5. Dirigido a
        simular_popup_ssd("dirigido a", "PARTES DRV")

        # 6. Grabar documento y capturar número
        emitir("ssd", 2, "Grabando documento en SSD")
        numero_ssd = f"20573{640 + fila}"
        registro['numero_ssd'] = numero_ssd
        guardar_datos_automatizacion(datos_excel)
        emitir("ssd", 2, f"N° SSD generado: {numero_ssd}", f"N° SSD generado: {numero_ssd}")

        # ══════════════════════════════════════════
        # 2. PORTAL PERSONAL (Paso Stepper 3)
        # ══════════════════════════════════════════
        emitir("personal", 3, "Abriendo FormCreaViatico", "Abriendo formulario de viático en Personal")

        rut_sin_dv = normalizar_rut(rut_raw)
        emitir("personal", 3, "Ingresando RUT funcionario", f"Ingresando RUT funcionario: {rut_sin_dv}")
        emitir("personal", 3, "Buscando funcionario por RUT")

        fecha_inicio_raw = str(registro.get('fechainicio', '')).strip()
        fecha_termino_raw = str(registro.get('fechatermino', '')).strip()

        emitir("personal", 3, "Ingresando fecha de inicio", f"Ingresando fecha de inicio: {fecha_inicio_raw}")
        emitir("personal", 3, "Ingresando fecha de término", f"Ingresando fecha de término: {fecha_termino_raw}")
        emitir("personal", 3, "Ingresando objetivo", "Ingresando objetivo: Traslado de personal")

        # Considerando
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

        emitir("personal", 3, "Ingresando texto considerando", f"Ingresando texto considerando: {texto_considerando}")
        emitir("personal", 3, "Seleccionando tipo de objetivo", "Seleccionando tipo de objetivo: 27")

        tipo_movilizacion = str(registro.get('tipo_movilizacion', '') or '').strip().upper()
        if tipo_movilizacion:
            emitir("personal", 3, "Seleccionando tipo de movilización", f"Seleccionando tipo de movilización: {tipo_movilizacion}")

        emitir("personal", 3, "Seleccionando región principal", "Seleccionando región principal: 5")
        emitir("personal", 3, "Ingresando lugar cometido", f"Ingresando lugar cometido: {str(registro.get('lugar_cometido', '')).strip()}")

        regiones_raw = str(registro.get('regiones', '')).strip()
        partes_regiones = [p.strip() for p in regiones_raw.split(",")] if regiones_raw else []
        for region in partes_regiones:
            if region:
                emitir("personal", 3, f"Marcando región {region}")

        # ── ATRIBUCIÓN (Punto donde se demuestra la resiliencia si SIMULAR_FALLO=true) ──
        atribucion_val = str(registro.get('atribucion', '') or '').strip()
        if atribucion_val:
            emitir("personal", 3, "Abriendo modal de atribución")
            emitir("personal", 3, "Buscando atribución", f"Buscando atribución: {atribucion_val}")

            if SIMULAR_FALLO and fila == 1:
                # Simula la captura exacta del fallo en la atribución igual que en orquestador.py
                error_simulado = {
                    "portal": "personal",
                    "paso_stepper": 3,
                    "accion": "Buscando atribución",
                    "mensaje": f"No apareció la opción para seleccionar la atribución '{atribucion_val}'",
                    "selector": "#btnSeleccionaConfiere"
                }
                registro['estado_proceso'] = 'fallido'
                registro['error'] = error_simulado
                guardar_datos_automatizacion(datos_excel)

                guardar_progreso(
                    paso=fila,
                    total=total_registros,
                    nombre=rut_raw,
                    estado="ejecutando",
                    detalle=f"Fallo en PERSONAL (Buscando atribución): {error_simulado['mensaje']}",
                    portal="personal",
                    paso_stepper=3,
                    accion_actual="Buscando atribución",
                    ultimo_error=error_simulado
                )
                time.sleep(delay * 3)
                continue

            emitir("personal", 3, "Confirmando atribución")

        # TD5
        emitir("personal", 3, "Abriendo modal TD5")
        emitir("personal", 3, "Seleccionando ítem TD5")

        # Calendario
        emitir("personal", 3, "Abriendo calendario de viáticos")
        dias_salida_raw = str(registro.get('dias_salida', '')).strip()
        if dias_salida_raw:
            emitir("personal", 3, "Marcando días de salida en calendario", f"Marcando días de salida en calendario: {dias_salida_raw}")
        emitir("personal", 3, "Grabando calendario de viáticos")

        # Porcentajes
        mapeo_porcentajes = ['dias_100', 'dias_70', 'dias_60', 'dias_50', 'dias_40', 'dias_35']
        for llave in mapeo_porcentajes:
            val = str(registro.get(llave, '')).strip()
            if val:
                pct = llave.split('_')[1]
                emitir("personal", 3, f"Ingresando días al {pct}%", f"Ingresando días al {pct}%: {val}")

        # Imputación
        tipo_imputacion = str(registro.get('tipo_imputacion_presupuestaria', '')).strip().upper() or "CONTRATA"
        emitir("personal", 3, "Abriendo modal imputación TD5")
        emitir("personal", 3, f"Seleccionando imputación {tipo_imputacion}")

        # N° Proceso SSD
        emitir("personal", 3, "Ingresando N° de proceso en Personal", f"Ingresando N° de proceso en Personal: {numero_ssd}")

        # Grabar cometido y PDF
        emitir("personal", 3, "Grabando cometido")
        emitir("personal", 3, "Cerrando confirmación de grabado")
        emitir("personal", 3, "Descargando PDF del cometido")

        ruta_pdf = generar_pdf_simulado(rut_raw)
        registro['ruta_pdf'] = ruta_pdf
        emitir("personal", 3, "PDF descargado correctamente", "Cometido guardado y PDF descargado exitosamente")

        # ══════════════════════════════════════════
        # 3. PORTAL FIRMADOR (Paso Stepper 4)
        # ══════════════════════════════════════════
        emitir("firmador", 4, "Abriendo Creacion_Flujo", "Abriendo formulario de creación de flujo en Firmador")
        emitir("firmador", 4, "Seleccionando tipo de documento en Firmador", "Seleccionando tipo de documento en Firmador: RESOLUCIÓN DE COMETIDO (OPV)")
        emitir("firmador", 4, "Ingresando N° de proceso en Firmador", f"Ingresando N° de proceso en Firmador: {numero_ssd}")
        emitir("firmador", 4, "Buscando N° de proceso en Firmador")
        emitir("firmador", 4, "Ingresando nombre de flujo", f"Ingresando nombre de flujo: {texto_materia[:80]}")
        emitir("firmador", 4, "Ingresando descripción de flujo", f"Ingresando descripción de flujo: {texto_materia[:180]}")

        # Firmantes
        nombre_firmantes = str(registro.get('nombre_firmantes', '')).strip()
        if nombre_firmantes:
            for firmante in nombre_firmantes.split(","):
                f_limpio = firmante.strip().upper()
                if f_limpio:
                    emitir("firmador", 4, "Seleccionando responsable en lista", f"Seleccionando responsable en lista: {f_limpio}")
                    emitir("firmador", 4, "Seleccionando rol de responsable", "Seleccionando rol de responsable: FIRMANTE")
                    emitir("firmador", 4, "Agregando responsable al flujo")

        # Aprobadores
        nombre_aprobador = str(registro.get('nombre_aprobador', '')).strip()
        if nombre_aprobador:
            for aprobador in nombre_aprobador.split(","):
                a_limpio = aprobador.strip().upper()
                if a_limpio:
                    emitir("firmador", 4, "Seleccionando responsable en lista", f"Seleccionando responsable en lista: {a_limpio}")
                    emitir("firmador", 4, "Seleccionando rol de responsable", "Seleccionando rol de responsable: APROBADOR")
                    emitir("firmador", 4, "Agregando responsable al flujo")

        # Adjuntar PDF
        emitir("firmador", 4, "Adjuntando PDF en Firmador", "Cargando archivo PDF")

        # Crear Flujo
        emitir("firmador", 4, "Creando flujo en Firmador")
        emitir("firmador", 4, "Seleccionando servicio en oficina de partes", "Seleccionando servicio en oficina de partes: 204")
        emitir("firmador", 4, "Seleccionando región en oficina de partes", "Seleccionando región en oficina de partes: 5")
        emitir("firmador", 4, "Seleccionando destino en oficina de partes", "Seleccionando destino en oficina de partes: 456")

        registro['estado_proceso'] = 'completado'
        registro['error'] = None
        guardar_datos_automatizacion(datos_excel)

        emitir("firmador", 4, "Flujo creado exitosamente", "Flujo de firmas creado exitosamente en Firmador", estado_cometido="completado")

    # ══════════════════════════════════════════
    # 4. FINALIZACIÓN EXITOSA DEL LOTE (Paso 5)
    # ══════════════════════════════════════════
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

if __name__ == "__main__":
    ejecutar_simulacion()
