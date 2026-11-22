import io
import json
import openpyxl
import pytest

from rpacometidos import app as app_module
from rpacometidos import historial_db, lector_excel, procesador_datos


def _crear_excel_en_memoria():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([
        lector_excel.HEADER_RUT,
        lector_excel.HEADER_FECHA_INICIO,
        lector_excel.HEADER_FECHA_TERMINO,
        lector_excel.HEADER_TIPO_MOVILIZACION,
        lector_excel.HEADER_SIGLA,
        lector_excel.HEADER_LUGAR_COMETIDO,
        lector_excel.HEADER_REGION_PRINCIPAL,
        lector_excel.HEADER_REGIONES,
        lector_excel.HEADER_PERSONAL_TRASLADADO,
        lector_excel.HEADER_NOMBRE_APROBADOR,
        lector_excel.HEADER_NOMBRE_FIRMANTES,
        lector_excel.HEADER_TIPO_IMPUTACION_PRESUPUESTARIA,
        lector_excel.HEADER_FALLBACK_CONSIDERANDO,
        lector_excel.HEADER_ATRIBUCION_ACTUAL,
        lector_excel.HEADER_DIAS_SALIDA,
        lector_excel.HEADER_DIAS_40,
    ])
    ws.append([
        "13193029-1", "05/10/2026", "06/10/2026", "Fiscal", "5F-KDMA-1604",
        "Valparaiso", "Valparaiso", "Valparaiso", "A. GOMEZ",
        "HERNAN SAAVEDRA", "LEONARDO RODRIGUEZ", "Contrata", "", "2698",
        "Lunes, Martes", 2,
    ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    """Cliente Flask aislado usando tmp_path para datos, progreso, CSV y SQLite."""
    csv_temp = tmp_path / "datos_conocidos_api.csv"
    csv_temp.write_text("rut,nombre,sigla\n13193029,JUAN PEREZ,5F-KDMA-1604\n", encoding="utf-8")
    db_temp = tmp_path / "historial_api.db"

    def _obtener_historial_aislado(limite=50):
        return historial_db.obtener_historial_ejecuciones(limite=limite, db_path=db_temp)

    def _obtener_ejecucion_aislada(ejecucion_id):
        return historial_db.obtener_ejecucion_por_id(ejecucion_id, db_path=db_temp)

    with monkeypatch.context() as m:
        m.setattr(app_module, "BASE_DIR", tmp_path)
        m.setattr(historial_db, "BASE_DIR", tmp_path)
        m.setattr(app_module, "obtener_historial_ejecuciones", _obtener_historial_aislado)
        m.setattr(app_module, "obtener_ejecucion_por_id", _obtener_ejecucion_aislada)
        m.setattr(procesador_datos, "path_conocidos", csv_temp)
        procesador_datos.recargar_datos_conocidos()

        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as c:
            yield c, tmp_path, db_temp
    procesador_datos.recargar_datos_conocidos()


def test_api_procesar_excel(cliente):
    c, _, _ = cliente

    resp_sin_archivo = c.post("/api/procesar-excel")
    assert resp_sin_archivo.status_code == 400

    resp_nombre_vacio = c.post(
        "/api/procesar-excel",
        data={"documento_excel": (io.BytesIO(b""), "")},
        content_type="multipart/form-data",
    )
    assert resp_nombre_vacio.status_code == 400

    resp_ok = c.post(
        "/api/procesar-excel",
        data={"documento_excel": (_crear_excel_en_memoria(), "planilla.xlsx")},
        content_type="multipart/form-data",
    )
    assert resp_ok.status_code == 200
    body = resp_ok.get_json()
    assert body["status"] == "completado"
    assert len(body["resultados"]) == 1
    assert body["resultados"][0]["rut_valido"] is True


def test_api_descargar_excel_corregido_con_y_sin_auditoria(cliente):
    c, _, _ = cliente
    payload = [
        {
            "numero_fila_excel": 2,
            "rut": "13193029-1",
            "lugar_cometido": "=SUM(A1:A2)",
        }
    ]

    # Sin auditoría: no añade columnas de auditoría pero sí sanitiza celdas
    resp_sin = c.post(
        "/api/descargar-excel-corregido",
        data={
            "documento_excel": (_crear_excel_en_memoria(), "planilla.xlsx"),
            "reporte_corregido": json.dumps(payload),
        },
        content_type="multipart/form-data",
    )
    assert resp_sin.status_code == 200
    wb_sin = openpyxl.load_workbook(io.BytesIO(resp_sin.data))
    hoja_sin = wb_sin.active
    headers_sin = [celda.value for celda in hoja_sin[1]]
    assert "N° PROCESO SSD" not in headers_sin
    col_lugar = headers_sin.index(lector_excel.HEADER_LUGAR_COMETIDO) + 1
    assert hoja_sin.cell(row=2, column=col_lugar).value == "'=SUM(A1:A2)"

    # Con auditoría explícita usando estados_cometidos
    estados = [
        {
            "indice": 0,
            "numero_ssd": "SSD-777",
            "numero_cometido_personal": "COM-888",
            "numero_expediente_firmador": "EXP-999",
            "estado": "completado",
        }
    ]
    resp_con = c.post(
        "/api/descargar-excel-corregido",
        data={
            "documento_excel": (_crear_excel_en_memoria(), "planilla.xlsx"),
            "reporte_corregido": json.dumps(payload),
            "incluir_auditoria": "true",
            "estados_cometidos": json.dumps(estados),
        },
        content_type="multipart/form-data",
    )
    assert resp_con.status_code == 200
    wb_con = openpyxl.load_workbook(io.BytesIO(resp_con.data))
    hoja_con = wb_con.active
    headers_con = [celda.value for celda in hoja_con[1]]
    assert "N° PROCESO SSD" in headers_con
    assert "N° EXPEDIENTE FIRMADOR" in headers_con
    col_ssd = headers_con.index("N° PROCESO SSD") + 1
    col_est = headers_con.index("ESTADO EJECUCIÓN RPA") + 1
    assert hoja_con.cell(row=2, column=col_ssd).value == "SSD-777"
    assert hoja_con.cell(row=2, column=col_est).value == "COMPLETADO"


def test_api_empezar_automatizacion_credenciales_solo_en_ram(cliente, monkeypatch):
    """RNF-04: las claves viajan en env del subproceso y jamás se persisten en disco."""
    c, tmp_path, _ = cliente
    llamadas_popen = []

    def fake_popen(cmd, cwd=None, env=None):
        llamadas_popen.append({"cmd": cmd, "cwd": cwd, "env": env})
        return None

    monkeypatch.setattr(app_module.subprocess, "Popen", fake_popen)

    # Simula un archivo de progreso previo que debe eliminarse al iniciar
    (tmp_path / "progreso_automatizacion.json").write_text('{"estado":"completado"}', encoding="utf-8")

    resp = c.post(
        "/api/empezar-automatizacion",
        json={
            "nombre_archivo": "lote_demo.xlsx",
            "filas": [{"rut": "13193029-1", "sigla": "5F-KDMA-1604", "dias_40": 0}],
            "credenciales": {
                "usuario_ssd": "user_ssd",
                "clave_ssd": "SecretoSSD123",
                "usuario": "user_mop",
                "clave": "SecretoMOP456",
            },
        },
    )
    assert resp.status_code == 200
    assert not (tmp_path / "progreso_automatizacion.json").exists()

    datos_disco = (tmp_path / "datos_automatizacion.json").read_text(encoding="utf-8")
    assert "SecretoSSD123" not in datos_disco
    assert "SecretoMOP456" not in datos_disco
    datos_parsed = json.loads(datos_disco)
    assert datos_parsed[0]["dias_40"] == 0

    assert len(llamadas_popen) == 1
    env_hijo = llamadas_popen[0]["env"]
    assert env_hijo["RPA_CLAVE_SSD"] == "SecretoSSD123"
    assert env_hijo["RPA_CLAVE_MOP"] == "SecretoMOP456"
    assert env_hijo["RPA_NOMBRE_ARCHIVO"] == "lote_demo.xlsx"


def test_api_progreso_crud_conocidos_e_historial(cliente):
    c, tmp_path, db_temp = cliente

    # Progreso no iniciado vs iniciado
    resp_no_init = c.get("/api/progreso-automatizacion")
    assert resp_no_init.status_code == 200
    assert resp_no_init.get_json()["estado"] == "no_iniciado"

    (tmp_path / "progreso_automatizacion.json").write_text(
        json.dumps({"estado": "ejecutando", "paso_stepper": 2}),
        encoding="utf-8",
    )
    resp_prog = c.get("/api/progreso-automatizacion")
    assert resp_prog.status_code == 200
    assert resp_prog.get_json()["estado"] == "ejecutando"

    # CRUD /api/datos-conocidos (200, 201, 400, 404, 409)
    assert c.get("/api/datos-conocidos").status_code == 200
    assert c.post("/api/datos-conocidos", json={"rut": "", "nombre": "X", "sigla": "Y"}).status_code == 400
    assert c.post("/api/datos-conocidos", json={"rut": "13193029-1", "nombre": "DUP", "sigla": "XX"}).status_code == 409
    assert c.post("/api/datos-conocidos", json={"rut": "9361648-K", "nombre": "MARIA", "sigla": "AA-11"}).status_code == 201
    assert c.put("/api/datos-conocidos/9361648", json={"rut": "9361648-K", "nombre": "MARIA 2", "sigla": "AA-22"}).status_code == 200
    assert c.put("/api/datos-conocidos/11111111", json={"rut": "11111111-1", "nombre": "X", "sigla": "Y"}).status_code == 404
    assert c.delete("/api/datos-conocidos/9361648").status_code == 200
    assert c.delete("/api/datos-conocidos/9361648").status_code == 404

    # Historial y descarga Excel
    ej_id = historial_db.registrar_ejecucion_historial(
        datos_excel=[{"rut": "13193029-1", "sigla": "5F-KDMA-1604", "numero_ssd": "100", "estado_proceso": "completado"}],
        usuario_ssd="u_ssd",
        usuario_mop="u_mop",
        nombre_archivo="demo.xlsx",
        db_path=db_temp,
    )
    resp_hist = c.get("/api/historial")
    assert resp_hist.status_code == 200
    assert len(resp_hist.get_json()["ejecuciones"]) == 1

    resp_excel = c.get(f"/api/historial/{ej_id}/excel")
    assert resp_excel.status_code == 200
    wb_hist = openpyxl.load_workbook(io.BytesIO(resp_excel.data))
    assert wb_hist.active.cell(row=1, column=1).value == "REPORTE DE TRAZABILIDAD DE EJECUCIÓN RPA - MOP"

    assert c.get("/api/historial/99999/excel").status_code == 404
