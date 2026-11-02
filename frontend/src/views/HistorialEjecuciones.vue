<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ─── Estado de datos ──────────────────────────────────────────
const ejecuciones        = ref([])
const cargando           = ref(true)
const errorCarga         = ref('')
const ejecucionExpandida = ref(null)

// ─── Búsqueda ─────────────────────────────────────────────────
const textoBusqueda = ref('')
const ejecucionesFiltradas = computed(() => {
  const q = textoBusqueda.value.trim().toLowerCase()
  if (!q) return ejecuciones.value
  return ejecuciones.value.filter(ej => {
    const coincideCabecera =
      String(ej.id).includes(q) ||
      (ej.nombre_archivo || '').toLowerCase().includes(q) ||
      (ej.usuario_ssd || '').toLowerCase().includes(q) ||
      (ej.usuario_mop || '').toLowerCase().includes(q) ||
      (ej.fecha_inicio || '').toLowerCase().includes(q)

    const coincideCometido = (ej.cometidos || []).some(c =>
      (c.rut || '').toLowerCase().includes(q) ||
      (c.nombre || '').toLowerCase().includes(q) ||
      (c.sigla || '').toLowerCase().includes(q) ||
      (c.numero_ssd || '').toLowerCase().includes(q) ||
      (c.numero_cometido || '').toLowerCase().includes(q) ||
      (c.numero_expediente || '').toLowerCase().includes(q)
    )
    return coincideCabecera || coincideCometido
  })
})

// ─── Carga inicial ────────────────────────────────────────────
onMounted(cargarHistorial)

async function cargarHistorial() {
  cargando.value   = true
  errorCarga.value = ''
  try {
    const res = await fetch('/api/historial')
    if (!res.ok) throw new Error(`Error del servidor: ${res.status}`)
    const data = await res.json()
    ejecuciones.value = data.ejecuciones || []
    if (ejecuciones.value.length > 0 && ejecucionExpandida.value === null) {
      ejecucionExpandida.value = ejecuciones.value[0].id
    }
  } catch (e) {
    errorCarga.value = e.message
  } finally {
    cargando.value = false
  }
}

// ─── Acciones de visualización y exportación ──────────────────
function alternarDetalle(id) {
  ejecucionExpandida.value = ejecucionExpandida.value === id ? null : id
}

function exportarExcelEjecucion(id) {
  window.open(`/api/historial/${id}/excel`, '_blank')
}

function formatearDuracion(seg) {
  const s = Number(seg) || 0
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const resto = s % 60
  return `${m}m ${resto}s`
}

// ─── Formateo de RUT chileno (solo visualización) ────────────
function formatearRut(rut) {
  if (rut == null) return ''
  const str = String(rut).trim()
  if (!str) return ''
  if (str.includes('-')) {
    const [cuerpo, dv] = str.split('-')
    const cuerpoLimpio = cuerpo.replace(/\./g, '')
    const cuerpoFormateado = cuerpoLimpio.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
    return `${cuerpoFormateado}-${dv.toUpperCase()}`
  }
  const soloDigitos = str.replace(/\./g, '')
  if (/^\d+$/.test(soloDigitos)) {
    return soloDigitos.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  }
  return str
}

// ─── Navegación ───────────────────────────────────────────────
function volverAlInicio() {
  router.push({ name: 'Home' })
}
</script>

<template>
  <div class="edicion-container">

    <!-- ── Encabezado ── -->
    <div class="edicion-header">
      <div class="header-izq">
        <!-- Botón Volver: encima del título -->
        <button class="btn btn-outline-primary btn-volver" @click="volverAlInicio">
          <i class="bi bi-arrow-left me-2"></i>Volver al inicio
        </button>
        <div class="header-texto">
          <h1 class="edicion-titulo">Historial de Ejecuciones</h1>
          <p class="edicion-subtitulo">
            Registro auditable de lotes procesados, cuentas ejecutoras y números de folio generados en SSD, Personal y Firmador.
          </p>
        </div>
      </div>
      <button class="btn btn-outline-primary btn-agregar" @click="cargarHistorial" :disabled="cargando">
        <i class="bi bi-arrow-clockwise me-2"></i>Actualizar historial
      </button>
    </div>

    <!-- ── Barra de búsqueda ── -->
    <div class="barra-busqueda">
      <i class="bi bi-search busqueda-icono"></i>
      <input
        v-model="textoBusqueda"
        type="text"
        class="busqueda-input"
        placeholder="Buscar por N° SSD, N° Cometido, N° Expediente, RUT, funcionario, matrícula o archivo..."
      />
    </div>

    <!-- ── Estado: cargando ── -->
    <div v-if="cargando" class="estado-mensaje">
      <div class="spinner-border text-primary" role="status"></div>
      <span class="ms-3 text-mid-gray">Cargando historial...</span>
    </div>

    <!-- ── Estado: error de carga ── -->
    <div v-else-if="errorCarga" class="alert alert-danger d-flex align-items-center gap-2 mt-4">
      <i class="bi bi-exclamation-triangle-fill"></i>
      <span>No se pudo conectar con el servidor: <strong>{{ errorCarga }}</strong></span>
    </div>

    <!-- ── Lista de ejecuciones ── -->
    <div v-else class="tabla-wrapper">
      <p v-if="ejecucionesFiltradas.length === 0" class="tabla-vacia">
        <i class="bi bi-inbox me-2"></i>
        {{ textoBusqueda ? 'Sin resultados para la búsqueda.' : 'No hay ejecuciones registradas aún.' }}
      </p>

      <div v-else class="lista-lotes">
        <div
          v-for="ej in ejecucionesFiltradas"
          :key="ej.id"
          class="lote-bloque"
        >
          <!-- Cabecera de cada ejecución -->
          <div class="lote-cabecera" @click="alternarDetalle(ej.id)">
            <div class="lote-info-izq">
              <span class="badge-rut">#{{ ej.id }}</span>
              <div class="lote-textos">
                <div class="lote-archivo">
                  <i class="bi bi-file-earmark-excel-fill text-success me-2"></i>
                  {{ ej.nombre_archivo || 'planilla_cometidos.xlsx' }}
                </div>
                <div class="lote-metadatos">
                  <span><i class="bi bi-calendar3 me-1"></i>{{ ej.fecha_inicio }}</span>
                  <span><i class="bi bi-stopwatch me-1"></i>{{ formatearDuracion(ej.duracion_segundos) }}</span>
                  <span><i class="bi bi-person-badge me-1"></i>Usuario SSD: <strong>{{ ej.usuario_ssd || 'N/A' }}</strong></span>
                  <span><i class="bi bi-person-check me-1"></i>Usuario MOP: <strong>{{ ej.usuario_mop || 'N/A' }}</strong></span>
                </div>
              </div>
            </div>

            <div class="lote-info-der" @click.stop>
              <span class="badge-estado badge-estado--ok">
                <i class="bi bi-check-circle-fill me-1"></i>{{ ej.completados }}/{{ ej.total_cometidos }} exitosos
              </span>
              <span v-if="ej.fallidos > 0" class="badge-estado badge-estado--error">
                <i class="bi bi-exclamation-triangle-fill me-1"></i>{{ ej.fallidos }} con error
              </span>

              <button
                class="btn btn-outline-primary btn-exportar"
                title="Descargar reporte en Excel"
                @click="exportarExcelEjecucion(ej.id)"
              >
                <i class="bi bi-file-earmark-arrow-down-fill me-1"></i>Exportar Excel
              </button>

              <button
                class="btn btn-outline-primary btn-accion"
                title="Ver detalle de cometidos"
                @click="alternarDetalle(ej.id)"
              >
                <i class="bi" :class="ejecucionExpandida === ej.id ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
              </button>
            </div>
          </div>

          <!-- Tabla interna de cometidos del lote -->
          <div v-if="ejecucionExpandida === ej.id" class="lote-detalle">
            <table class="tabla-conductores">
              <thead>
                <tr>
                  <th class="col-num">#</th>
                  <th class="col-rut">RUT</th>
                  <th class="col-nombre">Funcionario</th>
                  <th class="col-sigla">Matrícula</th>
                  <th>Fechas</th>
                  <th>N° Proceso SSD</th>
                  <th>N° Cometido</th>
                  <th>N° Expediente</th>
                  <th>Estado</th>
                  <th>Observación</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(c, idx) in ej.cometidos"
                  :key="c.id"
                  :class="{ 'fila-par': idx % 2 === 0 }"
                >
                  <td class="col-num">{{ c.fila_orden }}</td>
                  <td class="col-rut">
                    <span class="badge-rut">{{ formatearRut(c.rut) || '—' }}</span>
                  </td>
                  <td class="col-nombre">{{ c.nombre || '—' }}</td>
                  <td class="col-sigla">
                    <span class="badge-sigla">{{ c.sigla || '—' }}</span>
                  </td>
                  <td class="col-fechas">
                    {{ c.fechainicio || '—' }} al {{ c.fechatermino || '—' }}
                  </td>
                  <td>
                    <span v-if="c.numero_ssd" class="badge-rut">{{ c.numero_ssd }}</span>
                    <span v-else class="text-mid-gray">—</span>
                  </td>
                  <td>
                    <span v-if="c.numero_cometido" class="badge-rut">{{ c.numero_cometido }}</span>
                    <span v-else class="text-mid-gray">—</span>
                  </td>
                  <td>
                    <span v-if="c.numero_expediente" class="badge-rut">{{ c.numero_expediente }}</span>
                    <span v-else class="text-mid-gray">—</span>
                  </td>
                  <td>
                    <span v-if="c.estado === 'completado'" class="badge-estado badge-estado--ok">
                      Completado
                    </span>
                    <span v-else-if="c.estado === 'fallido'" class="badge-estado badge-estado--error">
                      Fallido
                    </span>
                    <span v-else class="badge-sigla">{{ c.estado }}</span>
                  </td>
                  <td class="col-obs">
                    <span v-if="c.mensaje_error" class="texto-error">
                      <strong>[{{ (c.portal_error || 'PORTAL').toUpperCase() }}]</strong> {{ c.mensaje_error }}
                    </span>
                    <span v-else class="texto-exito">
                      Procesado correctamente
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <p class="tabla-contador">
        {{ ejecucionesFiltradas.length }} de {{ ejecuciones.length }} ejecución(es)
      </p>
    </div>

  </div>
</template>

<style scoped>
/* ── Layout principal ── */
.edicion-container {
  min-height: calc(100vh - 57px);
  padding: 48px 56px;
  background-color: var(--color-white);
  font-family: var(--font-body);
}

/* ── Encabezado ── */
.edicion-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 32px;
  flex-wrap: wrap;
}

.header-izq {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.btn-volver {
  padding: 8px 20px;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
}

.header-texto {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.edicion-titulo {
  font-family: var(--font-title);
  font-size: 32px;
  font-weight: 700;
  color: var(--color-black);
  margin: 0;
}

.edicion-subtitulo {
  font-size: 15px;
  color: var(--color-mid-gray);
  margin: 0;
  max-width: 680px;
}

.btn-agregar {
  padding: 10px 20px;
  font-weight: 600;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── Barra de búsqueda ── */
.barra-busqueda {
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: #f5f7fa;
  border: 1px solid var(--color-neutral);
  border-radius: 8px;
  padding: 10px 16px;
  margin-bottom: 28px;
}

.busqueda-icono {
  color: var(--color-mid-gray);
  font-size: 16px;
  flex-shrink: 0;
}

.busqueda-input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 15px;
  color: var(--color-black);
  flex: 1;
}

.busqueda-input::placeholder {
  color: var(--color-mid-gray);
}

/* ── Estado cargando ── */
.estado-mensaje {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}

/* ── Contenedor de tabla / lotes ── */
.tabla-wrapper {
  border: 1px solid var(--color-neutral);
  border-radius: 10px;
  overflow: hidden;
}

.tabla-vacia {
  text-align: center;
  padding: 48px 24px;
  color: var(--color-mid-gray);
  font-size: 15px;
  margin: 0;
}

.lista-lotes {
  display: flex;
  flex-direction: column;
}

.lote-bloque {
  border-bottom: 1px solid var(--color-neutral);
}

.lote-bloque:last-child {
  border-bottom: none;
}

.lote-cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  background-color: var(--color-white);
  cursor: pointer;
  flex-wrap: wrap;
}

.lote-cabecera:hover {
  background-color: #fafbfc;
}

.lote-info-izq {
  display: flex;
  align-items: center;
  gap: 14px;
}

.lote-textos {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.lote-archivo {
  font-family: var(--font-title);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-black);
}

.lote-metadatos {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--color-mid-gray);
}

.lote-info-der {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.btn-exportar {
  font-size: 13px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 6px;
}

.lote-detalle {
  border-top: 1px solid var(--color-neutral);
  overflow-x: auto;
}

/* ── Tabla ── */
.tabla-conductores {
  width: 100%;
  border-collapse: collapse;
}

.tabla-conductores thead tr {
  background-color: var(--color-tertiary);
  color: var(--color-white);
}

.tabla-conductores th {
  padding: 12px 16px;
  font-family: var(--font-title);
  font-weight: 500;
  font-size: 12px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  white-space: nowrap;
}

.tabla-conductores td {
  padding: 12px 16px;
  font-size: 14px;
  color: var(--color-black);
  border-bottom: 1px solid var(--color-neutral);
}

.tabla-conductores tbody tr:last-child td {
  border-bottom: none;
}

.fila-par {
  background-color: #fafbfc;
}

/* Columnas */
.col-num    { width: 50px; font-weight: 700; color: var(--color-mid-gray); }
.col-rut    { width: 150px; }
.col-nombre { min-width: 180px; }
.col-sigla  { width: 160px; }
.col-fechas { white-space: nowrap; font-size: 13px; }
.col-obs    { min-width: 200px; font-size: 13px; }

/* Badges */
.badge-rut {
  display: inline-block;
  background-color: #eaf3ff;
  color: var(--color-primary);
  border: 1px solid #b3d4f0;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.5px;
  font-family: 'Courier New', monospace;
  white-space: nowrap;
}

.badge-sigla {
  display: inline-block;
  background-color: #f0f4f8;
  color: var(--color-dark-gray);
  border: 1px solid #d0dae3;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.8px;
  font-family: 'Courier New', monospace;
  white-space: nowrap;
}

.badge-estado {
  display: inline-flex;
  align-items: center;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.badge-estado--ok {
  background-color: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
}

.badge-estado--error {
  background-color: #fff0f0;
  color: #b91c1c;
  border: 1px solid #fca5a5;
}

.texto-error {
  color: #b91c1c;
}

.texto-exito {
  color: #059669;
  font-weight: 500;
}

.btn-accion {
  width: 34px;
  height: 34px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  border-radius: 6px;
  flex-shrink: 0;
}

/* Contador */
.tabla-contador {
  text-align: right;
  font-size: 12px;
  color: var(--color-mid-gray);
  padding: 10px 20px 12px;
  margin: 0;
  border-top: 1px solid var(--color-neutral);
  background-color: #fafbfc;
}
</style>
