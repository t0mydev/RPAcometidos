from unittest.mock import MagicMock
import pytest

from rpacometidos.robots import orquestador, resiliencia


class _FakePlaywrightCM:
    def __init__(self, pw):
        self._pw = pw

    def __enter__(self):
        return self._pw

    def __exit__(self, exc_type, exc, tb):
        return False


def _armar_playwright_falso():
    pagina_ssd = MagicMock(name="pagina_ssd")
    pagina_cometidos = MagicMock(name="pagina_cometidos")
    pagina_firmador = MagicMock(name="pagina_firmador")
    popup_extra = MagicMock(name="popup_extra")

    contexto = MagicMock()
    contexto.pages = [pagina_ssd, pagina_cometidos, pagina_firmador, popup_extra]
    contexto.new_page.side_effect = [pagina_ssd, pagina_cometidos, pagina_firmador]
    pagina_ssd.context = contexto

    navegador = MagicMock()
    navegador.new_context.return_value = contexto

    pw = MagicMock()
    pw.chromium.launch.return_value = navegador
    return _FakePlaywrightCM(pw), navegador, pagina_ssd, pagina_cometidos, pagina_firmador, popup_extra


def test_resiliencia_wrappers_y_reintentos(monkeypatch):
    """Verifica captura de AccionError en wrappers, recuperación en 2° intento y limpieza."""
    monkeypatch.setattr(resiliencia.time, "sleep", lambda _: None)
    monkeypatch.setattr(resiliencia, "registrar_accion_progreso", lambda *a, **k: None)

    # 1. escribir() falla intento 1 (fill) y logra recuperar en intento 2 (press_sequentially)
    loc_recuperable = MagicMock()
    loc_recuperable.fill.side_effect = RuntimeError("Element detached")
    loc_recuperable.input_value.return_value = "2698"
    assert resiliencia.escribir(loc_recuperable, "2698", "personal", 3, "Escribir atribución") is True
    loc_recuperable.press_sequentially.assert_called_once()

    # 2. escribir() persistente lanza AccionError con metadatos completos
    loc_roto = MagicMock()
    loc_roto.wait_for.side_effect = TimeoutError("Timeout")
    with pytest.raises(resiliencia.AccionError) as exc_esc:
        resiliencia.escribir(loc_roto, "abc", "ssd", 2, "Ingresar materia")
    assert exc_esc.value.portal == "ssd"
    assert exc_esc.value.paso_stepper == 2
    assert exc_esc.value.accion == "Ingresar materia"

    # 3. hacer_clic() lanza AccionError al agotar reintentos
    with pytest.raises(resiliencia.AccionError) as exc_clic:
        resiliencia.hacer_clic(loc_roto, "personal", 3, "Grabar cometido")
    assert exc_clic.value.portal == "personal"

    # 4. seleccionar() lanza AccionError si el select no retiene el valor
    loc_select = MagicMock()
    loc_select.input_value.return_value = "OTRO"
    loc_checked = MagicMock()
    loc_checked.inner_text.return_value = "OTRO TEXTO"
    loc_select.locator.return_value = loc_checked
    with pytest.raises(resiliencia.AccionError) as exc_sel:
        resiliencia.seleccionar(loc_select, "Contrata", "personal", 3, "Seleccionar imputación")
    assert "Contrata" in exc_sel.value.mensaje

    # 4b. marcar_checkbox() marca correctamente y lanza AccionError si no cambia de estado
    loc_chk = MagicMock()
    loc_chk.is_checked.return_value = True
    assert resiliencia.marcar_checkbox(loc_chk, "personal", 3, "Marcar región", marcar=True) is True
    loc_chk_roto = MagicMock()
    loc_chk_roto.is_checked.return_value = False
    with pytest.raises(resiliencia.AccionError):
        resiliencia.marcar_checkbox(loc_chk_roto, "personal", 3, "Marcar región", marcar=True)

    # 5. recuperar_entorno_limpio() cierra popups extras y navega formularios de vuelta
    _, _, p_ssd, p_com, p_fir, popup_extra = _armar_playwright_falso()
    p_com.url = "https://personal.mop.gob.cl/OtroEstado"
    p_fir.url = "https://firmador.mop.gob.cl/OtroEstado"
    resiliencia.recuperar_entorno_limpio(p_ssd, p_com, p_fir)

    popup_extra.close.assert_called_once()
    p_com.goto.assert_called_once_with("https://personal.mop.gob.cl/Viatico/FormCreaViatico", timeout=10000)
    p_fir.goto.assert_called_once_with("https://firmador.mop.gob.cl/Flujo/Creacion_Flujo", timeout=10000)


def test_orquestador_fallo_credenciales_corta_lote_sin_ensuciar_bd(monkeypatch):
    """Ante CredencialesInvalidasError reporta error_credenciales y NO registra historial."""
    pw_cm, _, _, _, _, _ = _armar_playwright_falso()
    progresos = []
    llamadas_historial = []
    llamadas_ssd = []

    monkeypatch.setattr(orquestador, "sync_playwright", lambda: pw_cm)
    monkeypatch.setattr(orquestador, "cargar_credenciales", lambda sistema="mop": ("usuario", "mala"))
    monkeypatch.setattr(orquestador, "limpiar_pdfs_temporales", lambda: None)
    monkeypatch.setattr(
        orquestador,
        "guardar_progreso",
        lambda *a, **k: progresos.append({"args": a, "kwargs": k}),
    )
    monkeypatch.setattr(
        orquestador,
        "login_ssd",
        MagicMock(side_effect=resiliencia.CredencialesInvalidasError("ssd", "Clave incorrecta")),
    )
    monkeypatch.setattr(orquestador, "procesar_un_ssd", lambda *a, **k: llamadas_ssd.append(a))
    monkeypatch.setattr(orquestador, "registrar_ejecucion_historial", lambda **k: llamadas_historial.append(k))

    orquestador.ejecutar_orquestador(datos_excel=[{"rut": "13193029-1"}], headless=True, slow_mo=0)

    assert len(llamadas_ssd) == 0
    assert len(llamadas_historial) == 0
    ultimo = progresos[-1]
    assert "error_credenciales" in ultimo["args"] or ultimo["kwargs"].get("estado") == "error_credenciales"


def test_orquestador_aisla_fallo_en_segundo_cometido_y_continua(monkeypatch):
    """RNF-03: un AccionError en el 2° cometido recupera el entorno, completa el 3° y guarda en BD."""
    pw_cm, navegador, p_ssd, p_com, p_fir, _ = _armar_playwright_falso()
    progresos = []
    recuperaciones = []
    historial_llamadas = []

    monkeypatch.setattr(orquestador, "sync_playwright", lambda: pw_cm)
    monkeypatch.setattr(orquestador, "cargar_credenciales", lambda sistema="mop": ("u_demo", "p_demo"))
    monkeypatch.setattr(orquestador, "limpiar_pdfs_temporales", lambda: None)
    monkeypatch.setattr(orquestador, "guardar_datos_automatizacion", lambda d: None)
    monkeypatch.setattr(orquestador, "guardar_progreso", lambda *a, **k: progresos.append((a, k)))

    monkeypatch.setattr(orquestador, "login_ssd", lambda *a, **k: None)
    monkeypatch.setattr(orquestador, "login_cometidos", lambda *a, **k: None)
    monkeypatch.setattr(orquestador, "login_firmador", lambda *a, **k: None)

    def fake_ssd(pag, reg, fila, tot):
        return f"SSD-{fila}"

    def fake_cometido(pag, reg, fila, tot):
        if fila == 2:
            raise resiliencia.AccionError(
                portal="personal",
                paso_stepper=3,
                accion="Buscando atribución",
                mensaje="No apareció atribución",
                selector="#btnSeleccionaConfiere",
            )
        return f"/tmp/cometido_{fila}.pdf"

    def fake_firmador(pag, reg, fila, tot):
        reg["numero_expediente_firmador"] = f"EXP-{fila}"

    monkeypatch.setattr(orquestador, "procesar_un_ssd", fake_ssd)
    monkeypatch.setattr(orquestador, "procesar_un_cometido", fake_cometido)
    monkeypatch.setattr(orquestador, "procesar_un_firmador", fake_firmador)
    monkeypatch.setattr(
        orquestador,
        "recuperar_entorno_limpio",
        lambda ps, pc, pf: recuperaciones.append((ps, pc, pf)),
    )
    monkeypatch.setattr(
        orquestador,
        "registrar_ejecucion_historial",
        lambda **kwargs: historial_llamadas.append(kwargs),
    )

    lote = [
        {"rut": "11111111-1"},
        {"rut": "22222222-2"},
        {"rut": "33333333-3"},
    ]
    orquestador.ejecutar_orquestador(datos_excel=lote, headless=True, slow_mo=0)

    assert lote[0]["estado_proceso"] == "completado"
    assert lote[0]["numero_ssd"] == "SSD-1"
    assert lote[0]["numero_expediente_firmador"] == "EXP-1"

    assert lote[1]["estado_proceso"] == "fallido"
    assert lote[1]["error"]["portal"] == "personal"
    assert lote[1]["error"]["accion"] == "Buscando atribución"

    assert lote[2]["estado_proceso"] == "completado"
    assert lote[2]["numero_ssd"] == "SSD-3"
    assert lote[2]["numero_expediente_firmador"] == "EXP-3"

    assert len(recuperaciones) == 1
    assert recuperaciones[0] == (p_ssd, p_com, p_fir)

    assert len(historial_llamadas) == 1
    assert historial_llamadas[0]["modo"] == "real"
    assert historial_llamadas[0]["datos_excel"] == lote
    navegador.close.assert_called_once()
