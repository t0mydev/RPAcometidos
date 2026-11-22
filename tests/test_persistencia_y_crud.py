import json
from datetime import datetime, timedelta
import pytest

from rpacometidos import historial_db, procesador_datos


def test_sqlite_persistencia_historial_y_folios(monkeypatch, tmp_path):
    """Verifica creación de tablas SQLite, persistencia de 3 folios y errores de ejecución."""
    db_path = tmp_path / "test_historial.db"
    csv_temp = tmp_path / "conocidos_test.csv"
    csv_temp.write_text(
        "rut,nombre,sigla\n"
        "13193029,JUAN PEREZ,5F-KDMA-1604\n"
        "9361648,MARIA LOPEZ,AA-BB-11\n",
        encoding="utf-8",
    )

    progreso_path = tmp_path / "progreso_automatizacion.json"
    progreso_path.write_text(
        json.dumps(
            {
                "estado": "completado",
                "estados_cometidos": [
                    {"indice": 0, "estado": "completado"},
                    {
                        "indice": 1,
                        "estado": "fallido",
                        "portal": "personal",
                        "accion_actual": "Descargar PDF",
                        "ultimo_error": {
                            "portal": "personal",
                            "accion": "Descargar PDF",
                            "mensaje": "Timeout",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    datos_excel = [
        {
            "numero_fila_excel": 2,
            "rut": "13193029-1",
            "sigla": "5F-KDMA-1604",
            "fechainicio": "05/10/2026",
            "fechatermino": "06/10/2026",
            "lugar_cometido": "Valparaiso",
            "numero_ssd": "SSD-101",
            "numero_cometido_personal": "COM-202",
            "numero_expediente_firmador": "EXP-303",
            "estado_proceso": "completado",
        },
        {
            "numero_fila_excel": 3,
            "rut": "9361648-K",
            "sigla": "AA-BB-11",
            "fechainicio": "07/10/2026",
            "fechatermino": "07/10/2026",
            "lugar_cometido": "Quillota",
            "estado_proceso": "fallido",
            "error": {
                "portal": "personal",
                "accion": "Descargar PDF",
                "mensaje": "Timeout",
            },
        },
    ]

    with monkeypatch.context() as m:
        m.setattr(historial_db, "BASE_DIR", tmp_path)
        m.setattr(procesador_datos, "path_conocidos", csv_temp)
        procesador_datos.recargar_datos_conocidos()

        ejecucion_id = historial_db.registrar_ejecucion_historial(
            datos_excel=datos_excel,
            fecha_inicio_dt=datetime.now() - timedelta(seconds=15),
            usuario_ssd="u_ssd",
            usuario_mop="u_mop",
            nombre_archivo="planilla_prueba.xlsx",
            modo="real",
            db_path=db_path,
        )
    procesador_datos.recargar_datos_conocidos()

    assert isinstance(ejecucion_id, int)

    detalle = historial_db.obtener_ejecucion_por_id(ejecucion_id, db_path=db_path)
    assert detalle is not None
    assert detalle["estado_global"] == "con_observaciones"
    assert detalle["total_cometidos"] == 2
    assert detalle["completados"] == 1
    assert detalle["fallidos"] == 1
    assert detalle["nombre_archivo"] == "planilla_prueba.xlsx"

    c1, c2 = detalle["cometidos"]
    assert c1["nombre"] == "JUAN PEREZ"
    assert c1["numero_ssd"] == "SSD-101"
    assert c1["numero_cometido"] == "COM-202"
    assert c1["numero_expediente"] == "EXP-303"
    assert c1["estado"] == "completado"

    assert c2["nombre"] == "MARIA LOPEZ"
    assert c2["estado"] == "fallido"
    assert c2["portal_error"] == "personal"
    assert c2["accion_error"] == "Descargar PDF"
    assert c2["mensaje_error"] == "Timeout"

    lista = historial_db.obtener_historial_ejecuciones(limite=10, db_path=db_path)
    assert len(lista) == 1
    assert lista[0]["id"] == ejecucion_id
    assert len(lista[0]["cometidos"]) == 2


def test_crud_datos_conocidos_csv(monkeypatch, tmp_path):
    """Verifica alta, duplicados, edición, eliminación y errores en el CSV de conocidos."""
    csv_temp = tmp_path / "conocidos_crud.csv"
    csv_temp.write_text(
        "rut,nombre,sigla\n"
        "13193029,JUAN PEREZ,5F-KDMA-1604\n",
        encoding="utf-8",
    )

    with monkeypatch.context() as m:
        m.setattr(procesador_datos, "path_conocidos", csv_temp)
        procesador_datos.recargar_datos_conocidos()

        # Alta con formato y normalización
        rut_guardado = procesador_datos.agregar_dato_conocido("9.361.648-k", "maria lopez", "aa-bb-11")
        assert rut_guardado == "9361648"
        registros = procesador_datos.obtener_datos_conocidos()
        assert len(registros) == 2
        assert any(r["rut"] == "9361648" and r["nombre"] == "MARIA LOPEZ" and r["sigla"] == "AA-BB-11" for r in registros)

        # Duplicado lanza KeyError
        with pytest.raises(KeyError):
            procesador_datos.agregar_dato_conocido("9361648-K", "OTRO", "XX-11")

        # Edición exitosa y error si no existe
        procesador_datos.editar_dato_conocido("9361648-K", "9361648-K", "MARIA EDITADA", "ZZ-99")
        registros_post_edit = procesador_datos.obtener_datos_conocidos()
        assert any(r["rut"] == "9361648" and r["nombre"] == "MARIA EDITADA" and r["sigla"] == "ZZ-99" for r in registros_post_edit)

        with pytest.raises(FileNotFoundError):
            procesador_datos.editar_dato_conocido("11111111-1", "11111111-1", "NADIE", "XX-00")

        # Eliminación exitosa y error si no existe
        procesador_datos.eliminar_dato_conocido("9361648-K")
        registros_final = procesador_datos.obtener_datos_conocidos()
        assert [r["rut"] for r in registros_final] == ["13193029"]

        with pytest.raises(FileNotFoundError):
            procesador_datos.eliminar_dato_conocido("9361648-K")

    procesador_datos.recargar_datos_conocidos()
