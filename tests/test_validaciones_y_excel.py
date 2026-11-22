import io
import openpyxl
import pytest

from rpacometidos import app as app_module
from rpacometidos import lector_excel, procesador_datos


@pytest.fixture
def catalogo_aislado(monkeypatch, tmp_path):
    """Aísla datos_conocidos en un CSV temporal y restaura el estado en memoria al terminar."""
    csv_temp = tmp_path / "datos_conocidos_test.csv"
    csv_temp.write_text(
        "rut,nombre,sigla\n"
        "13193029,JUAN PEREZ,5F-KDMA-1604\n"
        "9361648,MARIA LOPEZ,AA-BB-11\n",
        encoding="utf-8",
    )
    with monkeypatch.context() as m:
        m.setattr(procesador_datos, "path_conocidos", csv_temp)
        procesador_datos.recargar_datos_conocidos()
        yield csv_temp
    procesador_datos.recargar_datos_conocidos()


def _registro_valido_base():
    return {
        "rut": "13193029-1",
        "sigla": "5F-KDMA-1604",
        "fechainicio": "05/10/2026",
        "fechatermino": "06/10/2026",
        "dias_salida": "Lunes, Martes",
        "dias_100": "",
        "dias_70": "",
        "dias_60": "",
        "dias_50": "",
        "dias_40": "2",
        "dias_35": "",
        "tipo_movilizacion": "Fiscal",
        "lugar_cometido": "Valparaiso - Viña del Mar",
        "region_principal": "Valparaiso",
        "tiene_col_region_principal": True,
        "regiones": "Valparaiso",
        "personal_trasladado": "A. GOMEZ",
        "fallback_considerando": "",
        "nombre_aprobador": "HERNAN SAAVEDRA",
        "nombre_firmantes": "LEONARDO RODRIGUEZ",
        "tipo_imputacion_presupuestaria": "Contrata",
        "atribucion": "2698",
    }


def test_normalizar_rut_formatos():
    """Verifica normalización de RUT con guión, puntos, K y DV pegado."""
    assert procesador_datos.normalizar_rut("13652729-0") == "13652729"
    assert procesador_datos.normalizar_rut("9361648-K") == "9361648"
    assert procesador_datos.normalizar_rut("13.652.729-0") == "13652729"
    assert procesador_datos.normalizar_rut("136527290") == "13652729"
    assert procesador_datos.normalizar_rut("9361648k") == "9361648"
    assert procesador_datos.normalizar_rut(None) == ""
    assert procesador_datos.normalizar_rut("   ") == ""


def test_contar_dias_salida_y_sumar_viaticos():
    """Verifica conteo de días de salida y suma decimal de porcentajes."""
    assert procesador_datos.contar_dias_salida("Lunes, Martes, Miercoles") == 3
    assert procesador_datos.contar_dias_salida("4") == 4
    assert procesador_datos.contar_dias_salida("") == 0

    suma = procesador_datos.sumar_viaticos({
        "dias_100": "1",
        "dias_40": "2,5",
        "dias_35": None,
        "dias_70": "invalido",
    })
    assert suma == pytest.approx(3.5)


def test_validar_registro_completo_valido(catalogo_aislado):
    """Un registro completo con datos consistentes pasa todas las validaciones."""
    res = procesador_datos.validar_registro(_registro_valido_base())
    assert res["rut_valido"] is True
    assert res["sigla_valida"] is True
    assert res["viaticos_validos"] is True
    assert res["fechas_validas"] is True
    assert res["admin_valido"] is True
    assert res["campos_faltantes"] == []
    assert res["errores"] == []


def test_validar_registro_fuzzy_matching_rut_y_sigla(catalogo_aislado):
    """Detecta similitud difusa con RapidFuzz para sugerir RUT y sigla conocidos."""
    reg = _registro_valido_base()
    reg["rut"] = "13193028-1"
    reg["sigla"] = "5F-KDMA-1605"
    res = procesador_datos.validar_registro(reg)

    assert res["rut_valido"] is False
    assert res["sigla_valida"] is False
    assert res["sugerencia_correccion_rut"] == "13193029"
    assert res["sugerencia_correccion_sigla"] == "5F-KDMA-1604"

    reg_rut_desconocido = _registro_valido_base()
    reg_rut_desconocido["rut"] = "22222222-2"
    reg_rut_desconocido["sigla"] = "5F-KDMA-1605"
    res2 = procesador_datos.validar_registro(reg_rut_desconocido)
    assert res2["sugerencia_correccion_sigla"] == "5F-KDMA-1604"


def test_validar_registro_inconsistencia_viaticos_y_dias(catalogo_aislado):
    """Bloquea descalces entre días de salida, porcentajes y rango de fechas."""
    reg_suma = _registro_valido_base()
    reg_suma["dias_40"] = "3"
    res_suma = procesador_datos.validar_registro(reg_suma)
    assert res_suma["viaticos_validos"] is False

    reg_ceros = _registro_valido_base()
    reg_ceros["dias_salida"] = ""
    reg_ceros["dias_40"] = ""
    res_ceros = procesador_datos.validar_registro(reg_ceros)
    assert res_ceros["viaticos_validos"] is False

    reg_dia_fuera = _registro_valido_base()
    reg_dia_fuera["dias_salida"] = "Viernes"
    reg_dia_fuera["dias_40"] = "1"
    res_dia_fuera = procesador_datos.validar_registro(reg_dia_fuera)
    assert res_dia_fuera["viaticos_validos"] is False


def test_validar_registro_coherencia_fechas(catalogo_aislado):
    """Rechaza fechas invertidas y cometidos que cruzan de mes."""
    reg_invertida = _registro_valido_base()
    reg_invertida["fechainicio"] = "10/10/2026"
    reg_invertida["fechatermino"] = "05/10/2026"
    res_inv = procesador_datos.validar_registro(reg_invertida)
    assert res_inv["fechas_validas"] is False
    assert res_inv["admin_valido"] is False

    reg_mes = _registro_valido_base()
    reg_mes["fechainicio"] = "29/09/2026"
    reg_mes["fechatermino"] = "02/10/2026"
    res_mes = procesador_datos.validar_registro(reg_mes)
    assert res_mes["fechas_validas"] is False
    assert res_mes["admin_valido"] is False


def test_validar_registro_campos_no_editables_y_fallback(catalogo_aislado):
    """Verifica detección de celdas vacías obligatorias y excepción de fallback_considerando."""
    reg_vacio = _registro_valido_base()
    reg_vacio["lugar_cometido"] = ""
    reg_vacio["atribucion"] = ""
    reg_vacio["personal_trasladado"] = ""
    reg_vacio["fallback_considerando"] = ""
    res_vacio = procesador_datos.validar_registro(reg_vacio)

    assert res_vacio["admin_valido"] is False
    assert "Lugar cometido" in res_vacio["campos_faltantes"]
    assert "Atribución" in res_vacio["campos_faltantes"]
    assert "Personal trasladado" in res_vacio["campos_faltantes"]

    reg_fallback = _registro_valido_base()
    reg_fallback["personal_trasladado"] = ""
    reg_fallback["fallback_considerando"] = "TRASLADO ESPECIAL CONSIDERANDO"
    res_fb = procesador_datos.validar_registro(reg_fallback)
    assert "Personal trasladado" not in res_fb["campos_faltantes"]


def test_procesar_planilla_completa_y_errores(catalogo_aislado):
    """Verifica lectura de Excel en memoria con encabezados en Fila 1 y error si faltan columnas."""
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

    reporte = lector_excel.procesar_planilla_completa(buf)
    assert len(reporte) == 1
    fila = reporte[0]
    assert fila["numero_fila_excel"] == 2
    assert fila["numero_cometido"] == 1
    assert fila["tiene_col_region_principal"] is True
    assert fila["rut_valido"] is True
    assert fila["admin_valido"] is True

    wb_malo = openpyxl.Workbook()
    wb_malo.active.append(["Columna A", "Columna B"])
    buf_malo = io.BytesIO()
    wb_malo.save(buf_malo)
    buf_malo.seek(0)

    with pytest.raises(ValueError, match="columnas principales"):
        lector_excel.procesar_planilla_completa(buf_malo)


def test_sanitizar_celda_excel():
    """Protege contra inyección de fórmulas sin alterar números negativos ni texto común."""
    assert app_module.sanitizar_celda_excel("=SUM(A1)") == "'=SUM(A1)"
    assert app_module.sanitizar_celda_excel("+CMD('calc')") == "'+CMD('calc')"
    assert app_module.sanitizar_celda_excel("-A1+B1") == "'-A1+B1"
    assert app_module.sanitizar_celda_excel("@SUM(1,2)") == "'@SUM(1,2)"
    assert app_module.sanitizar_celda_excel("\t=1") == "'\t=1"
    assert app_module.sanitizar_celda_excel("\r=1") == "'\r=1"

    assert app_module.sanitizar_celda_excel("-45") == "-45"
    assert app_module.sanitizar_celda_excel("-3,14") == "-3,14"
    assert app_module.sanitizar_celda_excel(-10) == -10
    assert app_module.sanitizar_celda_excel("Valparaiso") == "Valparaiso"
    assert app_module.sanitizar_celda_excel(None) == ""
