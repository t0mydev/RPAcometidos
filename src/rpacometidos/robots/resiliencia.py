import time
from rpacometidos.robots.base import registrar_accion_progreso

class AccionError(Exception):
    """
    Excepción con metadatos específicos del punto exacto de fallo en un robot.
    Permite aislar fallos por cometido sin derribar la ejecución de los demás.
    """
    def __init__(self, portal, paso_stepper, accion, mensaje, selector=""):
        super().__init__(mensaje)
        self.portal = portal
        self.paso_stepper = paso_stepper
        self.accion = accion
        self.mensaje = mensaje
        self.selector = selector

    def a_dict(self):
        return {
            "portal": self.portal,
            "paso_stepper": self.paso_stepper,
            "accion": self.accion,
            "mensaje": self.mensaje,
            "selector": self.selector
        }


class CredencialesInvalidasError(Exception):
    """
    Excepción lanzada cuando un portal institucional rechaza el usuario o contraseña.
    """
    def __init__(self, portal, mensaje):
        super().__init__(mensaje)
        self.portal = portal
        self.mensaje = mensaje

def esperar_overlays(locator_o_pagina, timeout_ms=8000):
    """
    Espera de forma preventiva a que overlays o indicadores de carga conocidos
    se hayan ocultado antes de intentar interactuar con un elemento.
    """
    try:
        if hasattr(locator_o_pagina, 'page'):
            pagina = locator_o_pagina.page
        else:
            pagina = locator_o_pagina

        if not hasattr(pagina, 'locator'):
            return

        # 1. SweetAlert2 (común en Firmador)
        swal = pagina.locator('.swal2-container')
        if swal.is_visible():
            swal.wait_for(state="hidden", timeout=timeout_ms)

        # 2. Banners de carga de texto
        loader_flujo = pagina.get_by_text("Se está cargando la información", exact=False)
        if loader_flujo.is_visible():
            loader_flujo.wait_for(state="hidden", timeout=timeout_ms)

        loader_opv = pagina.get_by_text("Se esta cargando Oficinas de OPV", exact=False)
        if loader_opv.is_visible():
            loader_opv.wait_for(state="hidden", timeout=timeout_ms)
    except Exception:
        pass

def escribir(
    locator,
    valor,
    portal,
    paso_stepper,
    accion,
    fila=1,
    total=1,
    rut="",
    max_reintentos=2,
    sensible=False,
    delay_ms=10,
    secuencial=False,
    valor_mostrar=None
):
    """
    Escribe en un input de forma resiliente con verificación automática del valor ingresado.
    Si secuencial=True, escribe usando press_sequentially (ideal para campos con máscara/fechas).
    """
    valor_str = str(valor or "")
    texto_visible = "***" if sensible else str(valor_mostrar if valor_mostrar is not None else valor_str)
    detalle = f"{accion}: {texto_visible}" if (texto_visible and texto_visible not in accion) else accion
    registrar_accion_progreso(fila, total, rut, portal, paso_stepper, accion, detalle=detalle)

    esperar_overlays(locator)
    selector_str = str(locator)
    ultimo_valor_obtenido = ""

    # Si el valor a escribir viene vacío, limpiamos el campo y retornamos éxito de inmediato
    if not valor_str.strip():
        try:
            locator.wait_for(state="visible", timeout=7000)
            locator.clear()
        except Exception:
            pass
        return True

    for intento in range(1, max_reintentos + 1):
        try:
            locator.wait_for(state="visible", timeout=7000)

            if secuencial:
                locator.click()
                locator.clear()
                locator.press_sequentially(valor_str, delay=delay_ms)
            elif intento == 1:
                locator.fill(valor_str)
            else:
                time.sleep(0.2)
                locator.click()
                locator.clear()
                locator.press_sequentially(valor_str, delay=delay_ms)

            # Check de verificación
            ultimo_valor_obtenido = locator.input_value().strip()
            if secuencial:
                # En inputs con máscara o formato dinámico (ej: fechas), verificamos que no quede vacío
                if len(ultimo_valor_obtenido) > 0:
                    if len(valor_str) >= 8 and len(ultimo_valor_obtenido) < 8:
                        pass
                    else:
                        return True
            else:
                if ultimo_valor_obtenido == valor_str.strip():
                    return True

            time.sleep(0.25)
        except Exception:
            if intento == max_reintentos:
                raise AccionError(
                    portal=portal,
                    paso_stepper=paso_stepper,
                    accion=accion,
                    mensaje=f"No se pudo escribir en el campo tras {max_reintentos} intentos.",
                    selector=selector_str
                )
            time.sleep(0.3)

    raise AccionError(
        portal=portal,
        paso_stepper=paso_stepper,
        accion=accion,
        mensaje=f"El campo no retuvo el valor '{valor_str}'. Valor que quedó: '{ultimo_valor_obtenido}'",
        selector=selector_str
    )

def hacer_clic(
    locator,
    portal,
    paso_stepper,
    accion,
    fila=1,
    total=1,
    rut="",
    esperar_oculto=None,
    esperar_visible=None,
    max_reintentos=2,
    force=False
):
    """
    Ejecuta un clic de forma resiliente verificando overlays y elementos resultantes.
    """
    registrar_accion_progreso(fila, total, rut, portal, paso_stepper, accion, detalle=accion)
    esperar_overlays(locator)
    selector_str = str(locator)

    for intento in range(1, max_reintentos + 1):
        try:
            locator.wait_for(state="visible", timeout=7000)
            locator.click(force=force)

            if esperar_oculto:
                esperar_oculto.wait_for(state="hidden", timeout=7000)

            if esperar_visible:
                esperar_visible.wait_for(state="visible", timeout=7000)

            return True
        except Exception:
            if intento == max_reintentos:
                raise AccionError(
                    portal=portal,
                    paso_stepper=paso_stepper,
                    accion=accion,
                    mensaje=f"No se pudo hacer clic en el elemento tras {max_reintentos} intentos.",
                    selector=selector_str
                )
            time.sleep(0.5)

def seleccionar(
    locator,
    valor,
    portal,
    paso_stepper,
    accion,
    fila=1,
    total=1,
    rut="",
    max_reintentos=2
):
    """
    Selecciona una opción en un <select> esperando que esté disponible y verificando el valor.
    Soporta selección y validación tanto por value como por label / texto visible.
    """
    valor_str = str(valor or "").strip()
    detalle = f"{accion}: {valor_str}" if (valor_str and valor_str not in accion) else accion
    registrar_accion_progreso(fila, total, rut, portal, paso_stepper, accion, detalle=detalle)
    esperar_overlays(locator)
    selector_str = str(locator)

    for intento in range(1, max_reintentos + 1):
        try:
            locator.wait_for(state="visible", timeout=7000)
            try:
                locator.select_option(valor_str)
            except Exception:
                locator.select_option(label=valor_str)

            # Check de verificación: compara por value o por texto visible de la opción
            actual_val = locator.input_value().strip()
            if actual_val.lower() == valor_str.lower():
                return True
            try:
                actual_text = locator.locator('option:checked').inner_text().strip()
                if actual_text.lower() == valor_str.lower():
                    return True
            except Exception:
                pass

            time.sleep(0.2)
        except Exception:
            if intento == max_reintentos:
                raise AccionError(
                    portal=portal,
                    paso_stepper=paso_stepper,
                    accion=accion,
                    mensaje=f"No se pudo seleccionar la opción '{valor_str}'.",
                    selector=selector_str
                )
            time.sleep(0.3)

    raise AccionError(
        portal=portal,
        paso_stepper=paso_stepper,
        accion=accion,
        mensaje=f"El <select> no quedó con la opción esperada '{valor_str}'",
        selector=selector_str
    )

def marcar_checkbox(
    locator,
    portal,
    paso_stepper,
    accion,
    fila=1,
    total=1,
    rut="",
    marcar=True
):
    """
    Marca o desmarca un checkbox asegurando que quede en el estado deseado.
    """
    registrar_accion_progreso(fila, total, rut, portal, paso_stepper, accion, detalle=accion)
    esperar_overlays(locator)
    selector_str = str(locator)

    try:
        locator.wait_for(state="visible", timeout=5000)
        if marcar:
            locator.check()
        else:
            locator.uncheck()

        # Check de verificación
        if locator.is_checked() != marcar:
            locator.click(force=True)

        if locator.is_checked() == marcar:
            return True
    except Exception:
        raise AccionError(
            portal=portal,
            paso_stepper=paso_stepper,
            accion=accion,
            mensaje=f"No se pudo {'marcar' if marcar else 'desmarcar'} la casilla.",
            selector=selector_str
        )

    raise AccionError(
        portal=portal,
        paso_stepper=paso_stepper,
        accion=accion,
        mensaje=f"El checkbox no cambió al estado {'marcado' if marcar else 'desmarcado'}",
        selector=selector_str
    )

class ContextoRobot:
    """
    Contexto liviano para evitar 'tramp data' en las llamadas UI.
    Agrupa página, portal, paso_stepper, fila, total y rut.
    """
    def __init__(self, pagina, portal, paso_stepper, fila=1, total=1, rut=""):
        self.pagina = pagina
        self.portal = portal
        self.paso_stepper = paso_stepper
        self.fila = fila
        self.total = total
        self.rut = rut

    def registrar(self, accion, detalle=""):
        registrar_accion_progreso(
            self.fila, self.total, self.rut,
            self.portal, self.paso_stepper, accion,
            detalle=detalle or accion
        )

    def escribir(self, locator, valor, accion, sensible=False, delay_ms=10, secuencial=False, valor_mostrar=None):
        return escribir(
            locator, valor, self.portal, self.paso_stepper, accion,
            fila=self.fila, total=self.total, rut=self.rut,
            sensible=sensible, delay_ms=delay_ms, secuencial=secuencial, valor_mostrar=valor_mostrar
        )

    def hacer_clic(self, locator, accion, esperar_oculto=None, esperar_visible=None, force=False):
        return hacer_clic(
            locator, self.portal, self.paso_stepper, accion,
            fila=self.fila, total=self.total, rut=self.rut,
            esperar_oculto=esperar_oculto, esperar_visible=esperar_visible, force=force
        )

    def seleccionar(self, locator, valor, accion):
        return seleccionar(
            locator, valor, self.portal, self.paso_stepper, accion,
            fila=self.fila, total=self.total, rut=self.rut
        )

    def marcar_checkbox(self, locator, accion, marcar=True):
        return marcar_checkbox(
            locator, self.portal, self.paso_stepper, accion,
            fila=self.fila, total=self.total, rut=self.rut,
            marcar=marcar
        )

def recuperar_entorno_limpio(pagina_ssd, pagina_cometidos, pagina_firmador):
    """
    Restaura las páginas a un estado limpio entre cometidos si ocurrió un fallo,
    evitando que popups secundarios o formularios a medio llenar afecten al siguiente cometido.
    """
    # 1. En SSD: cerrar popups adicionales que hayan quedado abiertos en el contexto
    try:
        contexto = pagina_ssd.context
        for p in contexto.pages:
            if p not in (pagina_ssd, pagina_cometidos, pagina_firmador):
                try:
                    p.close()
                except Exception:
                    pass
    except Exception:
        pass

    # 2. En Personal: volver al formulario de viáticos en blanco
    try:
        url_cometido = "https://personal.mop.gob.cl/Viatico/FormCreaViatico"
        if pagina_cometidos.url != url_cometido:
            pagina_cometidos.goto(url_cometido, timeout=10000)
    except Exception:
        pass

    # 3. En Firmador: volver a creación de flujo en blanco
    try:
        url_flujo = "https://firmador.mop.gob.cl/Flujo/Creacion_Flujo"
        if pagina_firmador.url != url_flujo:
            pagina_firmador.goto(url_flujo, timeout=10000)
    except Exception:
        pass
