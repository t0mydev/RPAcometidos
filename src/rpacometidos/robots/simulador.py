import time
from pathlib import Path
from rpacometidos.robots.base import (
    guardar_progreso,
    cargar_datos_automatizacion,
    guardar_datos_automatizacion,
    obtener_ruta_pdf_temporal,
    BASE_DIR
)

def generar_pdf_simulado(rut_raw):
    """
    Crea un archivo PDF simulado válido en temp_pdfs si no existe,
    asegurando que las rutas temporales queden listas.
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
    Simulador de orquestación para grabaciones y demos de sprint.
    Emite actualizaciones de progreso progresivas en progreso_automatizacion.json,
    permitiendo que el frontend transicione a través de los 5 sub-pasos
    sin interactuar con los portales reales del MOP.
    """
    if datos_excel is None:
        try:
            datos_excel = cargar_datos_automatizacion()
        except Exception:
            datos_excel = []

    total_registros = len(datos_excel)
    if total_registros == 0:
        guardar_progreso(1, 1, "Automatización", "completado", detalle="Todos los cometidos fueron procesados exitosamente")
        return

    # Ajuste dinámico de tiempo: ~18-24 segundos en total para un video ágil
    if delay is None:
        pasos_por_registro = 9
        total_pasos = total_registros * pasos_por_registro
        delay = max(0.8, min(1.5, 20.0 / total_pasos))

    guardar_progreso(0, total_registros, "Inicio", "iniciando", detalle="Iniciando entorno de automatización...")
    time.sleep(delay)

    for fila, registro in enumerate(datos_excel, start=1):
        rut_raw = str(registro.get('rut', '')).strip() or "13193029-1"

        # ── 1. PORTAL SSD (Sub-paso 2) ──
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Iniciando sesión en Sistema SSD")
        time.sleep(delay)

        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Configurando documento y rellenando materia en SSD")
        time.sleep(delay)

        numero_ssd = f"20573{640 + fila}"
        registro['numero_ssd'] = numero_ssd
        guardar_datos_automatizacion(datos_excel)
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle=f"N° SSD generado: {numero_ssd}")
        time.sleep(delay)

        # ── 2. PORTAL PERSONAL (Sub-paso 3) ──
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Iniciando sesión y buscando funcionario en Portal Personal")
        time.sleep(delay)

        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Rellenando fechas y viáticos en Portal Personal")
        time.sleep(delay)

        ruta_pdf = generar_pdf_simulado(rut_raw)
        registro['ruta_pdf'] = ruta_pdf
        guardar_datos_automatizacion(datos_excel)
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Cometido guardado y PDF descargado en Portal Personal")
        time.sleep(delay)

        # ── 3. PORTAL FIRMADOR (Sub-paso 4) ──
        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Iniciando sesión en Portal Firmador")
        time.sleep(delay)

        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Cargando PDF y asignando participantes en Firmador")
        time.sleep(delay)

        guardar_progreso(fila, total_registros, rut_raw, "ejecutando", detalle="Flujo de firmas creado exitosamente en Firmador")
        time.sleep(delay)

    # ── 4. FINALIZACIÓN EXITOSA (Sub-paso 5) ──
    guardar_progreso(total_registros, total_registros, "Automatización", "completado", detalle="Todos los cometidos fueron procesados exitosamente")

if __name__ == "__main__":
    ejecutar_simulacion()
