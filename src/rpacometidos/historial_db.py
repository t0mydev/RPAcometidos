import json
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "historial_ejecuciones.db"


def inicializar_db(db_path=DB_PATH):
    """
    Crea las tablas de auditoría y trazabilidad de ejecuciones si no existen.
    Utiliza exclusivamente sqlite3 nativo de Python (cero dependencias externas).
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ejecuciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_inicio TEXT NOT NULL,
                fecha_termino TEXT NOT NULL,
                duracion_segundos INTEGER DEFAULT 0,
                nombre_archivo TEXT DEFAULT '',
                usuario_ssd TEXT DEFAULT '',
                usuario_mop TEXT DEFAULT '',
                modo TEXT DEFAULT 'real',
                estado_global TEXT DEFAULT 'completado',
                total_cometidos INTEGER DEFAULT 0,
                completados INTEGER DEFAULT 0,
                fallidos INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS detalle_cometidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ejecucion_id INTEGER NOT NULL,
                fila_orden INTEGER DEFAULT 1,
                numero_fila_excel INTEGER DEFAULT 0,
                rut TEXT DEFAULT '',
                nombre TEXT DEFAULT '',
                sigla TEXT DEFAULT '',
                fechainicio TEXT DEFAULT '',
                fechatermino TEXT DEFAULT '',
                lugar_cometido TEXT DEFAULT '',
                numero_ssd TEXT DEFAULT '',
                numero_cometido TEXT DEFAULT '',
                numero_expediente TEXT DEFAULT '',
                estado TEXT DEFAULT 'pendiente',
                portal_error TEXT DEFAULT '',
                accion_error TEXT DEFAULT '',
                mensaje_error TEXT DEFAULT '',
                datos_json TEXT DEFAULT '{}',
                FOREIGN KEY (ejecucion_id) REFERENCES ejecuciones(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def registrar_ejecucion_historial(
    datos_excel,
    fecha_inicio_dt=None,
    usuario_ssd="",
    usuario_mop="",
    nombre_archivo="",
    modo="real",
    db_path=DB_PATH
):
    """
    Registra una ejecución finalizada y el detalle de cada cometido procesado en SQLite.
    Combina la información de `datos_automatizacion.json` y `progreso_automatizacion.json`.
    """
    try:
        inicializar_db(db_path)

        ahora = datetime.now()
        if fecha_inicio_dt is None:
            fecha_inicio_dt = ahora

        fecha_inicio_str = fecha_inicio_dt.strftime("%Y-%m-%d %H:%M:%S")
        fecha_termino_str = ahora.strftime("%Y-%m-%d %H:%M:%S")
        duracion = max(1, int((ahora - fecha_inicio_dt).total_seconds()))

        # Carga progreso_automatizacion.json si existe para enriquecer errores o estados
        estados_map = {}
        path_progreso = BASE_DIR / "progreso_automatizacion.json"
        if path_progreso.exists():
            try:
                with open(path_progreso, "r", encoding="utf-8") as f:
                    prog = json.load(f)
                    for item in prog.get("estados_cometidos", []):
                        idx = item.get("indice")
                        if idx is not None:
                            estados_map[int(idx)] = item
            except Exception:
                pass

        # Carga nombres conocidos para completar el nombre del funcionario si no venía en el registro
        mapa_nombres = {}
        try:
            from rpacometidos.procesador_datos import obtener_datos_conocidos, normalizar_rut
            for reg_con in obtener_datos_conocidos():
                r_norm = normalizar_rut(reg_con.get("rut"))
                if r_norm:
                    mapa_nombres[r_norm] = str(reg_con.get("nombre") or "").strip()
        except Exception as e:
            print(f"[HISTORIAL DB] Aviso al cargar mapa de nombres: {e}")
            try:
                from rpacometidos.procesador_datos import normalizar_rut
            except Exception:
                normalizar_rut = lambda x: str(x or "").strip()

        total = len(datos_excel or [])
        completados = 0
        fallidos = 0
        filas_insertar = []

        for idx, reg in enumerate(datos_excel or []):
            prog_item = estados_map.get(idx, {})
            estado_c = reg.get("estado_proceso") or prog_item.get("estado") or "no_procesado"
            if estado_c == "completado":
                completados += 1
            elif estado_c == "fallido":
                fallidos += 1

            err = reg.get("error") or prog_item.get("ultimo_error") or {}
            if not isinstance(err, dict):
                err = {}

            rut_val = str(reg.get("rut", "") or "").strip()
            nombre_val = str(reg.get("nombre", "") or "").strip()
            if not nombre_val and rut_val:
                try:
                    nombre_val = mapa_nombres.get(normalizar_rut(rut_val), "")
                except Exception:
                    pass

            filas_insertar.append({
                "fila_orden": idx + 1,
                "numero_fila_excel": int(reg.get("numero_fila_excel") or (idx + 3)),
                "rut": rut_val,
                "nombre": nombre_val,
                "sigla": str(reg.get("sigla", "") or "").strip(),
                "fechainicio": str(reg.get("fechainicio", "") or "").strip(),
                "fechatermino": str(reg.get("fechatermino", "") or "").strip(),
                "lugar_cometido": str(reg.get("lugar_cometido", "") or "").strip(),
                "numero_ssd": str(reg.get("numero_ssd", "") or "").strip(),
                "numero_cometido": str(reg.get("numero_cometido_personal", "") or "").strip(),
                "numero_expediente": str(reg.get("numero_expediente_firmador", "") or "").strip(),
                "estado": estado_c,
                "portal_error": str(err.get("portal") or prog_item.get("portal") or "").strip(),
                "accion_error": str(err.get("accion") or prog_item.get("accion_actual") or "").strip(),
                "mensaje_error": str(err.get("mensaje") or "").strip(),
                "datos_json": json.dumps(reg, ensure_ascii=False)
            })

        if fallidos == 0 and completados > 0:
            estado_global = "completado"
        elif completados > 0 and fallidos > 0:
            estado_global = "con_observaciones"
        else:
            estado_global = "fallido"

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ejecuciones (
                    fecha_inicio, fecha_termino, duracion_segundos,
                    nombre_archivo, usuario_ssd, usuario_mop, modo,
                    estado_global, total_cometidos, completados, fallidos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fecha_inicio_str,
                    fecha_termino_str,
                    duracion,
                    str(nombre_archivo or "planilla_cometidos.xlsx").strip(),
                    str(usuario_ssd or "N/A").strip(),
                    str(usuario_mop or "N/A").strip(),
                    str(modo or "real").strip(),
                    estado_global,
                    total,
                    completados,
                    fallidos,
                ),
            )
            ejecucion_id = cursor.lastrowid

            for item in filas_insertar:
                cursor.execute(
                    """
                    INSERT INTO detalle_cometidos (
                        ejecucion_id, fila_orden, numero_fila_excel,
                        rut, nombre, sigla, fechainicio, fechatermino, lugar_cometido,
                        numero_ssd, numero_cometido, numero_expediente,
                        estado, portal_error, accion_error, mensaje_error, datos_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ejecucion_id,
                        item["fila_orden"],
                        item["numero_fila_excel"],
                        item["rut"],
                        item["nombre"],
                        item["sigla"],
                        item["fechainicio"],
                        item["fechatermino"],
                        item["lugar_cometido"],
                        item["numero_ssd"],
                        item["numero_cometido"],
                        item["numero_expediente"],
                        item["estado"],
                        item["portal_error"],
                        item["accion_error"],
                        item["mensaje_error"],
                        item["datos_json"],
                    ),
                )
            conn.commit()
            return ejecucion_id
    except Exception as e:
        print(f"[HISTORIAL DB] Error crítico al persistir ejecución en SQLite: {e}")
        return None


def obtener_historial_ejecuciones(limite=50, db_path=DB_PATH):
    """
    Devuelve la lista de ejecuciones recientes (de más nueva a más antigua)
    incluyendo sus cometidos asociados.
    """
    inicializar_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM ejecuciones
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,),
        )
        ejecuciones_rows = cursor.fetchall()

        resultado = []
        for ej in ejecuciones_rows:
            ej_dict = dict(ej)
            cursor.execute(
                """
                SELECT
                    id, fila_orden, numero_fila_excel, rut, nombre, sigla,
                    fechainicio, fechatermino, lugar_cometido,
                    numero_ssd, numero_cometido, numero_expediente,
                    estado, portal_error, accion_error, mensaje_error
                FROM detalle_cometidos
                WHERE ejecucion_id = ?
                ORDER BY fila_orden ASC
                """,
                (ej_dict["id"],),
            )
            ej_dict["cometidos"] = [dict(c) for c in cursor.fetchall()]
            resultado.append(ej_dict)

        return resultado


def obtener_ejecucion_por_id(ejecucion_id, db_path=DB_PATH):
    """
    Obtiene una ejecución específica por su ID junto con todos sus cometidos y datos_json.
    """
    inicializar_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ejecuciones WHERE id = ?", (ejecucion_id,))
        row = cursor.fetchone()
        if not row:
            return None
        ej_dict = dict(row)
        cursor.execute(
            "SELECT * FROM detalle_cometidos WHERE ejecucion_id = ? ORDER BY fila_orden ASC",
            (ejecucion_id,),
        )
        ej_dict["cometidos"] = [dict(c) for c in cursor.fetchall()]
        return ej_dict
