<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import ValidacionDatosEtapa2 from './ValidacionDatosEtapa2.vue'
import ValidacionDatosEtapa3 from './ValidacionDatosEtapa3.vue'

const router = useRouter()

// ─── Stepper ──────────────────────────────────────────────────
const etapaActual = ref(1) // 1=validación, 2=ejecución, 3=finalizado
const etapas = [
  { numero: 1, label: 'Validación y Resumen', icono: 'bi-clipboard2-check-fill' },
  { numero: 2, label: 'Ejecución RPA',         icono: 'bi-robot'                },
  { numero: 3, label: 'Finalizado',            icono: 'bi-check2-all'           },
]

// ─── Estado general ───────────────────────────────────────────
const fileName            = ref(history.state?.fileName || 'archivo.xlsx')
const filas               = ref([])
const procesando          = ref(true)
const procesandoMensaje   = ref('Enviando archivo al servidor...')
const descargando         = ref(false)
const correccionesAplicadas = ref(false)

// ─── Grupos del Checklist (4 familias de reglas) ──────────────
const grupos = ref([
  {
    id: 'identidad',
    icono: 'bi-person-fill-check',
    titulo: 'Identidad y Conductor',
    descripcion: 'RUT y registro en el padrón',
    estado: 'pendiente',
    errores: [],
  },
  {
    id: 'vehiculo',
    icono: 'bi-truck-front-fill',
    titulo: 'Vehículo y Movilización',
    descripcion: 'Sigla/patente y tipo de traslado',
    estado: 'pendiente',
    errores: [],
  },
  {
    id: 'viaticos',
    icono: 'bi-cash-coin',
    titulo: 'Coherencia de Viáticos',
    descripcion: 'Días de salida vs porcentajes de pago',
    estado: 'pendiente',
    errores: [],
  },
  {
    id: 'admin',
    icono: 'bi-calendar2-check',
    titulo: 'Datos Administrativos',
    descripcion: 'Fechas y campos obligatorios',
    estado: 'pendiente',
    errores: [],
  },
])

// ─── Computados ───────────────────────────────────────────────
const totalErrores = computed(() =>
  grupos.value.reduce((sum, g) => sum + g.errores.length, 0)
)

const tieneSugerencias = computed(() =>
  filas.value.some(f =>
    (!f.rut_valido && f.sugerencia_correccion_rut) ||
    (!f.sigla_valida && f.sugerencia_correccion_sigla)
  )
)

const todasValidas = computed(() =>
  !procesando.value && totalErrores.value === 0
)

// ─── Helpers de validación y formato ──────────────────────────

// Cuenta días de salida separados por comas ("LUNES, MARTES" → 2)
function contarDiasSalida(diasStr) {
  if (!diasStr || String(diasStr).trim() === '') return 0
  return String(diasStr).split(',').filter(d => d.trim() !== '').length
}

// Suma los valores de las columnas de porcentaje de pago
function sumarViaticos(fila) {
  const campos = ['dias_100', 'dias_70', 'dias_60', 'dias_50', 'dias_40', 'dias_35']
  return campos.reduce((sum, c) => {
    const raw = String(fila[c] ?? '').replace(',', '.')
    const val = parseFloat(raw)
    return sum + (isNaN(val) ? 0 : val)
  }, 0)
}

// Formatea RUT chileno sin dígito verificador separado: "13652729" → "1.365.272-9"
function formatearRut(rut) {
  const str = String(rut ?? '').trim()
  if (!/^\d{6,8}[0-9Kk]$/.test(str)) return str
  const dv = str.slice(-1).toUpperCase()
  const cuerpoFormateado = str.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `${cuerpoFormateado}-${dv}`
}

// Resumen de viáticos para la columna de la tabla
function resumenViaticos(fila) {
  const mapa = {
    dias_100: '100%', dias_70: '70%', dias_60: '60%',
    dias_50: '50%', dias_40: '40%', dias_35: '35%',
  }
  const partes = []
  for (const [campo, etiq] of Object.entries(mapa)) {
    const val = parseFloat(String(fila[campo] ?? '').replace(',', '.'))
    if (!isNaN(val) && val > 0) partes.push(`${etiq}:${val}`)
  }
  return partes.join(' · ') || '—'
}

// Lista de errores semánticos de una fila específica (para la tabla)
function erroresDeFila(fila) {
  const e = []
  if (fila.rut_valido === false)   e.push('rut')
  if (fila.sigla_valida === false) e.push('sigla')
  const totalDias = contarDiasSalida(fila.dias_salida)
  const sumaPorc  = sumarViaticos(fila)
  if (totalDias > 0 && Math.abs(totalDias - sumaPorc) > 0.01) e.push('viaticos')
  const reqs = ['fechainicio', 'fechatermino', 'dias_salida', 'sigla']
  for (const c of reqs) {
    if (!fila[c] || String(fila[c]).trim() === '') {
      if (!e.includes(c)) e.push(c)
    }
  }
  if (fila.fechainicio && fila.fechatermino) {
    const ini = new Date(String(fila.fechainicio).split('/').reverse().join('-'))
    const ter = new Date(String(fila.fechatermino).split('/').reverse().join('-'))
    if (!isNaN(ini) && !isNaN(ter) && ini > ter) e.push('fechas')
  }
  return e
}

function filaTieneError(fila, campo) {
  return erroresDeFila(fila).includes(campo)
}

// ─── Carga y animación de grupos ─────────────────────────────
onMounted(async () => {
  const archivo = window.__excelFile
  if (!archivo) {
    procesandoMensaje.value = 'No se encontró el archivo. Vuelve al inicio.'
    procesando.value = false
    return
  }

  await delay(500)
  procesandoMensaje.value = 'Procesando con el servidor...'

  const formData = new FormData()
  formData.append('documento_excel', archivo)

  try {
    const resp = await fetch('/api/procesar-excel', { method: 'POST', body: formData })
    if (!resp.ok) throw new Error(`El servidor respondió con estado ${resp.status}`)
    const data = await resp.json()
    if (data.status === 'completado') {
      filas.value = data.resultados
    } else {
      procesandoMensaje.value = `Error: ${data.mensaje || 'Respuesta inesperada del servidor'}`
      procesando.value = false
      return
    }
  } catch (e) {
    procesandoMensaje.value = `Error de conexión: ${e.message}`
    procesando.value = false
    return
  }

  await animarTodosLosGrupos()
  procesando.value = false
})

async function animarTodosLosGrupos() {
  // Grupo 1 — Identidad y Conductor (validación backend: rut)
  await animarGrupo('identidad', (fila) => {
    if (fila.rut_valido !== false) return []
    return [{
      fila:         fila.numero_fila_excel,
      campo:        'rut',
      mensaje:      (fila.errores || []).find(e => e.toLowerCase().includes('rut')) || 'RUT inválido o no registrado',
      sugerencia:   fila.sugerencia_correccion_rut,
      valor_actual: fila.rut,
      fila_ref:     fila,
    }]
  }, 900)

  // Grupo 2 — Vehículo (validación backend: sigla)
  await animarGrupo('vehiculo', (fila) => {
    if (fila.sigla_valida !== false) return []
    return [{
      fila:         fila.numero_fila_excel,
      campo:        'sigla',
      mensaje:      (fila.errores || []).find(e => e.toLowerCase().includes('sigla')) || 'Sigla/patente inválida o no registrada',
      sugerencia:   fila.sugerencia_correccion_sigla,
      valor_actual: fila.sigla,
      fila_ref:     fila,
    }]
  }, 900)

  // Grupo 3 — Coherencia de Viáticos (validación local: matemática)
  await animarGrupo('viaticos', (fila) => {
    const totalDias = contarDiasSalida(fila.dias_salida)
    const sumaPorc  = sumarViaticos(fila)
    if (totalDias === 0 || Math.abs(totalDias - sumaPorc) <= 0.01) return []
    return [{
      fila:         fila.numero_fila_excel,
      campo:        'viaticos',
      mensaje:      `Fila ${fila.numero_fila_excel}: se indicaron ${totalDias} día(s) pero los porcentajes suman ${sumaPorc}`,
      sugerencia:   null,
      valor_actual: `${totalDias} días / suma ${sumaPorc}`,
      fila_ref:     fila,
    }]
  }, 800)

  // Grupo 4 — Datos Administrativos (validación local: campos requeridos y fechas)
  await animarGrupo('admin', (fila) => {
    const errores = []
    const reqs = [
      { campo: 'fechainicio',  label: 'Fecha de inicio' },
      { campo: 'fechatermino', label: 'Fecha de término' },
      { campo: 'dias_salida',  label: 'Días de salida' },
      { campo: 'sigla',        label: 'Sigla de vehículo' },
    ]
    for (const r of reqs) {
      if (!fila[r.campo] || String(fila[r.campo]).trim() === '') {
        errores.push({
          fila: fila.numero_fila_excel, campo: r.campo,
          mensaje: `Fila ${fila.numero_fila_excel}: "${r.label}" está vacío`,
          sugerencia: null, valor_actual: '(vacío)', fila_ref: fila,
        })
      }
    }
    if (fila.fechainicio && fila.fechatermino) {
      const ini = new Date(String(fila.fechainicio).split('/').reverse().join('-'))
      const ter = new Date(String(fila.fechatermino).split('/').reverse().join('-'))
      if (!isNaN(ini) && !isNaN(ter) && ini > ter) {
        errores.push({
          fila: fila.numero_fila_excel, campo: 'fechas',
          mensaje: `Fila ${fila.numero_fila_excel}: fecha de inicio es posterior a fecha de término`,
          sugerencia: null, valor_actual: `${fila.fechainicio} > ${fila.fechatermino}`, fila_ref: fila,
        })
      }
    }
    return errores
  }, 800)
}

async function animarGrupo(grupoId, evaluarFila, retardo = 800) {
  const idx = grupos.value.findIndex(g => g.id === grupoId)
  if (idx === -1) return
  grupos.value[idx].estado = 'revisando'
  await delay(retardo)
  const errores = filas.value.flatMap(evaluarFila)
  grupos.value[idx].errores = errores
  grupos.value[idx].estado  = errores.length === 0 ? 'ok' : 'error'
}

// ─── Recalcular grupos tras correcciones ──────────────────────
function recalcularGrupos() {
  const defs = [
    {
      id: 'identidad',
      fn: (fila) => fila.rut_valido === false ? [{
        fila: fila.numero_fila_excel, campo: 'rut',
        mensaje: 'RUT inválido', sugerencia: fila.sugerencia_correccion_rut,
        valor_actual: fila.rut, fila_ref: fila,
      }] : [],
    },
    {
      id: 'vehiculo',
      fn: (fila) => fila.sigla_valida === false ? [{
        fila: fila.numero_fila_excel, campo: 'sigla',
        mensaje: 'Sigla inválida', sugerencia: fila.sugerencia_correccion_sigla,
        valor_actual: fila.sigla, fila_ref: fila,
      }] : [],
    },
    {
      id: 'viaticos',
      fn: (fila) => {
        const td = contarDiasSalida(fila.dias_salida)
        const sp = sumarViaticos(fila)
        return td > 0 && Math.abs(td - sp) > 0.01 ? [{
          fila: fila.numero_fila_excel, campo: 'viaticos',
          mensaje: `${td} días vs ${sp} en porcentajes`, sugerencia: null,
          valor_actual: String(sp), fila_ref: fila,
        }] : []
      },
    },
    {
      id: 'admin',
      fn: (fila) => {
        const e = []
        for (const c of ['fechainicio', 'fechatermino', 'dias_salida', 'sigla']) {
          if (!fila[c] || String(fila[c]).trim() === '')
            e.push({ fila: fila.numero_fila_excel, campo: c, mensaje: `"${c}" vacío`, sugerencia: null, valor_actual: '(vacío)', fila_ref: fila })
        }
        return e
      },
    },
  ]
  for (const def of defs) {
    const idx = grupos.value.findIndex(g => g.id === def.id)
    if (idx === -1) continue
    const errores = filas.value.flatMap(def.fn)
    grupos.value[idx].errores = errores
    grupos.value[idx].estado  = errores.length === 0 ? 'ok' : 'error'
  }
}

// ─── Auto-corrección ──────────────────────────────────────────
function corregirFilaDirectamente(p) {
  if (!p?.sugerencia) return
  p.fila_ref[p.campo] = p.sugerencia
  p.fila_ref[p.campo === 'sigla' ? 'sigla_valida' : `${p.campo}_valido`] = true
  if (p.campo === 'rut')   p.fila_ref.sugerencia_correccion_rut   = null
  if (p.campo === 'sigla') p.fila_ref.sugerencia_correccion_sigla = null
  p.fila_ref.errores = (p.fila_ref.errores || []).filter(e =>
    !e.toLowerCase().includes(p.campo === 'rut' ? 'rut' : 'sigla')
  )
  recalcularGrupos()
  correccionesAplicadas.value = true
}

function aplicarTodasLasSugerencias() {
  filas.value.forEach(f => {
    if (!f.rut_valido && f.sugerencia_correccion_rut) {
      f.rut = f.sugerencia_correccion_rut
      f.rut_valido = true
      f.sugerencia_correccion_rut = null
      f.errores = (f.errores || []).filter(e => !e.toLowerCase().includes('rut'))
    }
    if (!f.sigla_valida && f.sugerencia_correccion_sigla) {
      f.sigla = f.sugerencia_correccion_sigla
      f.sigla_valida = true
      f.sugerencia_correccion_sigla = null
      f.errores = (f.errores || []).filter(e => !e.toLowerCase().includes('sigla'))
    }
  })
  recalcularGrupos()
  correccionesAplicadas.value = true
}

// ─── Descarga Excel corregido ─────────────────────────────────
async function descargarExcelCorregido() {
  const archivo = window.__excelFile
  if (!archivo) { alert('No se encontró el archivo original en sesión. Vuelve al inicio.'); return }
  descargando.value = true
  const formData = new FormData()
  formData.append('documento_excel', archivo)
  const payload = filas.value.map(f => ({
    numero_fila_excel: f.numero_fila_excel,
    rut: f.rut, nombre: f.nombre, sigla: f.sigla,
    lugar_cometido: f.lugar_cometido, region_principal: f.region_principal,
    regiones: f.regiones, personal_trasladado: f.personal_trasladado,
    nombre_aprobador: f.nombre_aprobador, nombre_firmantes: f.nombre_firmantes,
    tipo_imputacion_presupuestaria: f.tipo_imputacion_presupuestaria,
    fallback_considerando: f.fallback_considerando, atribucion: f.atribucion,
    dias_salida: f.dias_salida, dias_100: f.dias_100, dias_70: f.dias_70,
    dias_60: f.dias_60, dias_50: f.dias_50, dias_40: f.dias_40, dias_35: f.dias_35,
  }))
  formData.append('reporte_corregido', JSON.stringify(payload))
  try {
    const resp = await fetch('/api/descargar-excel-corregido', { method: 'POST', body: formData })
    if (!resp.ok) throw new Error(`Estado ${resp.status}`)
    const blob = await resp.blob()
    const urlBlob = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = urlBlob
    let filename = fileName.value.replace(/\.xlsx?$/, '_corregido.xlsx')
    const cd = resp.headers.get('Content-Disposition')
    if (cd) { const m = cd.match(/filename="?([^"]+)"?/); if (m) filename = m[1] }
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(urlBlob)
  } catch (e) {
    alert(`Error al descargar el archivo: ${e.message}`)
  } finally {
    descargando.value = false
  }
}

function empezarAutomatizacion() {
  etapaActual.value = 2
}

// ─── Navegación ───────────────────────────────────────────────
function volverAlInicio() {
  window.__excelFile = null
  router.push({ name: 'Home' })
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)) }
</script>

<template>
  <div class="validacion-container">

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- STEPPER DE ETAPAS                                      -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div class="stepper-barra">
      <div class="stepper-inner">
        <template v-for="(etapa, i) in etapas" :key="etapa.numero">
          <div
            class="stepper-paso"
            :class="{
              'paso--activo':     etapaActual === etapa.numero,
              'paso--completado': etapaActual >  etapa.numero,
              'paso--pendiente':  etapaActual <  etapa.numero,
            }"
          >
            <div class="paso-circulo">
              <i v-if="etapaActual > etapa.numero" class="bi bi-check-lg"></i>
              <i v-else :class="`bi ${etapa.icono}`"></i>
            </div>
            <span class="paso-label">{{ etapa.label }}</span>
          </div>
          <!-- Línea conectora entre pasos -->
          <div
            v-if="i < etapas.length - 1"
            class="stepper-linea"
            :class="{ 'linea--completa': etapaActual > etapa.numero }"
          ></div>
        </template>
      </div>
    </div>


    <!-- ══════════════════════════════════════════════════════ -->
    <!-- ETAPA 1: VALIDACIÓN Y RESUMEN                          -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div v-if="etapaActual === 1" class="etapa-layout">

      <!-- ── Panel izquierdo: Checklist ── -->
      <aside class="panel-checklist">
        <h2 class="checklist-titulo">Validación</h2>

        <!-- Estado: cargando -->
        <div v-if="procesando" class="checklist-cargando">
          <div class="spinner-border text-primary mb-2" style="width:2rem;height:2rem" role="status"></div>
          <p class="text-muted small mb-0">{{ procesandoMensaje }}</p>
        </div>

        <!-- Grupos de validación -->
        <ul v-else class="grupos-lista">
          <li
            v-for="grupo in grupos"
            :key="grupo.id"
            class="grupo-item"
            :class="`grupo--${grupo.estado}`"
          >
            <!-- Cabecera del grupo -->
            <div class="grupo-cabecera">
              <div class="grupo-icono">
                <i v-if="grupo.estado === 'ok'"          class="bi bi-check-circle-fill"></i>
                <i v-else-if="grupo.estado === 'error'"  class="bi bi-x-circle-fill"></i>
                <i v-else-if="grupo.estado === 'revisando'" class="bi bi-arrow-repeat spin"></i>
                <i v-else                                class="bi bi-circle"></i>
              </div>
              <div class="grupo-texto">
                <span class="grupo-nombre">{{ grupo.titulo }}</span>
                <span class="grupo-desc">{{ grupo.descripcion }}</span>
              </div>
              <span v-if="grupo.errores.length > 0" class="grupo-conteo">
                {{ grupo.errores.length }}
              </span>
            </div>

            <!-- Detalle de errores del grupo -->
            <ul v-if="grupo.estado === 'error' && grupo.errores.length" class="errores-lista">
              <li v-for="(err, idx) in grupo.errores" :key="idx" class="error-item">
                <div class="error-cabecera">
                  <i class="bi bi-exclamation-triangle-fill text-danger"></i>
                  <strong class="error-valor">{{ err.valor_actual || '(Vacío)' }}</strong>
                  <span class="error-fila">Fila {{ err.fila }}</span>
                </div>
              </li>
            </ul>
          </li>
        </ul>

        <!-- Acciones del sidebar -->
        <div class="sidebar-acciones" v-if="!procesando">
          <button
            v-if="tieneSugerencias"
            class="btn btn-warning w-100 mb-2 py-2 fw-bold d-flex align-items-center justify-content-center gap-2"
            @click="aplicarTodasLasSugerencias"
          >
            <i class="bi bi-magic"></i>Auto-corregir Todo
          </button>
          <button
            v-if="correccionesAplicadas"
            class="btn btn-success w-100 mb-2 py-2 fw-bold d-flex align-items-center justify-content-center gap-2"
            :disabled="descargando"
            @click="descargarExcelCorregido"
          >
            <span v-if="descargando" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-file-earmark-arrow-down-fill"></i>
            {{ descargando ? 'Generando...' : 'Descargar Excel Corregido' }}
          </button>
          <button class="btn btn-outline-secondary btn-sm w-100 mt-1" @click="volverAlInicio">
            <i class="bi bi-arrow-left me-1"></i>Volver al inicio
          </button>
        </div>
      </aside>

      <!-- ── Panel derecho: Tabla resumen ── -->
      <main class="panel-tabla">

        <!-- Cabecera de la tabla -->
        <div class="tabla-cabecera">
          <div>
            <h2 class="tabla-titulo">Validación y Resumen</h2>
            <p class="tabla-subtitulo">
              <i class="bi bi-file-earmark-excel-fill text-success me-1"></i>
              {{ fileName }}
              <span class="separador-cabecera">·</span>
              {{ filas.length }} cometido(s) encontrado(s)
            </p>
          </div>
          <!-- Indicadores de resumen cuando termina de cargar -->
          <div v-if="!procesando && filas.length > 0" class="tabla-kpis">
            <div class="kpi kpi--ok">
              <i class="bi bi-check-circle-fill"></i>
              <span>{{ filas.filter(f => erroresDeFila(f).length === 0).length }} válidos</span>
            </div>
            <div v-if="totalErrores > 0" class="kpi kpi--error">
              <i class="bi bi-exclamation-circle-fill"></i>
              <span>{{ filas.filter(f => erroresDeFila(f).length > 0).length }} con obs.</span>
            </div>
          </div>
        </div>

        <!-- Estado: procesando -->
        <div v-if="procesando" class="tabla-procesando">
          <div class="spinner-border text-primary mb-3" style="width:3rem;height:3rem" role="status"></div>
          <p class="text-muted">{{ procesandoMensaje }}</p>
          <p class="text-muted small">Analizando el archivo Excel...</p>
        </div>

        <!-- Tabla de cometidos -->
        <div v-else-if="filas.length > 0" class="tabla-wrapper">
          <table class="tabla-cometidos">
            <thead>
              <tr>
                <th class="col-n">#</th>
                <th class="col-conductor">RUT</th>
                <th class="col-fechas">Fechas</th>
                <th class="col-vehiculo">Vehículo</th>
                <th class="col-viaticos">Cantidad de Días</th>
                <th class="col-estado">Estado</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="fila in filas"
                :key="fila.numero_fila_excel"
                :class="{ 'fila-con-error': erroresDeFila(fila).length > 0 }"
              >
                <!-- # Cometido -->
                <td class="col-n">
                  <span class="badge-fila">#{{ fila.numero_fila_excel - 2 }}</span>
                </td>

                <!-- RUT -->
                <td class="col-conductor">
                  <div class="conductor-bloque">
                    <span class="conductor-rut" :class="{ 'celda-error': filaTieneError(fila, 'rut') }">
                      {{ formatearRut(fila.rut) }}
                      <i v-if="filaTieneError(fila, 'rut')" class="bi bi-exclamation-triangle-fill ms-1 text-danger"></i>
                    </span>
                    <!-- Sugerencia inline de RUT (corrección desde la tabla) -->
                    <div v-if="!fila.rut_valido && fila.sugerencia_correccion_rut" class="sugerencia-inline">
                      <i class="bi bi-lightbulb-fill text-warning"></i>
                      <span>¿{{ fila.sugerencia_correccion_rut }}?</span>
                      <button class="btn-corregir-inline"
                        @click="corregirFilaDirectamente({ campo:'rut', sugerencia: fila.sugerencia_correccion_rut, fila_ref: fila })">
                        Corregir
                      </button>
                    </div>
                  </div>
                </td>

                <!-- Fechas -->
                <td class="col-fechas">
                  <div class="fechas-bloque"
                    :class="{ 'celda-error': filaTieneError(fila,'fechas') || filaTieneError(fila,'fechainicio') || filaTieneError(fila,'fechatermino') }">
                    <span class="fecha-chip">{{ fila.fechainicio || '—' }}</span>
                    <i class="bi bi-arrow-right fecha-sep"></i>
                    <span class="fecha-chip">{{ fila.fechatermino || '—' }}</span>
                    <i v-if="filaTieneError(fila,'fechas')" class="bi bi-exclamation-triangle-fill text-danger ms-1"></i>
                  </div>
                </td>

                <!-- Vehículo / Sigla -->
                <td class="col-vehiculo">
                  <div class="vehiculo-bloque">
                    <span class="badge-sigla" :class="{ 'badge-sigla--error': filaTieneError(fila,'sigla') }">
                      {{ fila.sigla || '—' }}
                      <i v-if="filaTieneError(fila,'sigla')" class="bi bi-exclamation-triangle-fill ms-1"></i>
                    </span>
                    <!-- Sugerencia inline de sigla -->
                    <div v-if="!fila.sigla_valida && fila.sugerencia_correccion_sigla" class="sugerencia-inline">
                      <i class="bi bi-lightbulb-fill text-warning"></i>
                      <span>¿{{ fila.sugerencia_correccion_sigla }}?</span>
                      <button class="btn-corregir-inline"
                        @click="corregirFilaDirectamente({ campo:'sigla', sugerencia: fila.sugerencia_correccion_sigla, fila_ref: fila })">
                        Corregir
                      </button>
                    </div>
                  </div>
                </td>

                <!-- Viáticos -->
                <td class="col-viaticos">
                  <div class="viaticos-bloque" :class="{ 'celda-error': filaTieneError(fila,'viaticos') }">
                    <span class="viaticos-dias">
                      {{ contarDiasSalida(fila.dias_salida) }} día(s)
                      <i v-if="filaTieneError(fila,'viaticos')" class="bi bi-exclamation-triangle-fill text-danger ms-1"></i>
                    </span>
                    <span class="viaticos-detalle">{{ resumenViaticos(fila) }}</span>
                  </div>
                </td>

                <!-- Estado de la fila -->
                <td class="col-estado">
                  <span v-if="erroresDeFila(fila).length === 0" class="badge-estado badge-estado--ok">
                    <i class="bi bi-check-circle-fill"></i>Válido
                  </span>
                  <span v-else class="badge-estado badge-estado--error">
                    <i class="bi bi-exclamation-circle-fill"></i>
                    {{ erroresDeFila(fila).length }} obs.
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Sin filas -->
        <div v-else class="tabla-vacia">
          <i class="bi bi-inbox" style="font-size:48px;color:var(--color-neutral)"></i>
          <p class="mt-3 text-muted">No se encontraron registros en el archivo.</p>
          <button class="btn btn-outline-primary mt-2" @click="volverAlInicio">
            <i class="bi bi-arrow-left me-1"></i>Volver e intentar con otro archivo
          </button>
        </div>

        <!-- ── Botón de acción principal (CTA) ── -->
        <div v-if="!procesando && filas.length > 0" class="cta-zona">
          <p v-if="totalErrores > 0" class="cta-aviso">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            Corrige los <strong>{{ totalErrores }}</strong> problema(s) detectado(s) para poder continuar
          </p>
          <button
            class="btn btn-primary btn-cta"
            :disabled="!todasValidas"
            @click="empezarAutomatizacion"
          >
            <i class="bi bi-play-circle-fill me-2"></i>
            Iniciar Automatización ({{ filas.length }} cometido{{ filas.length > 1 ? 's' : '' }})
          </button>
        </div>

      </main>
    </div>


    <!-- ══════════════════════════════════════════════════════ -->
    <!-- ETAPA 2: EJECUCIÓN DEL BOT (COMPONENTE MODULAR)       -->
    <!-- ══════════════════════════════════════════════════════ -->
    <ValidacionDatosEtapa2
      v-if="etapaActual === 2"
      :filas="filas"
      @avanzar-reporte="etapaActual = 3"
      @cancelar="etapaActual = 1"
    />


    <!-- ══════════════════════════════════════════════════════ -->
    <!-- ETAPA 3: FINALIZADO (COMPONENTE MODULAR)               -->
    <!-- ══════════════════════════════════════════════════════ -->
    <ValidacionDatosEtapa3
      v-if="etapaActual === 3"
      :filas="filas"
      :fileName="fileName"
      @volver-inicio="volverAlInicio"
    />

  </div>
</template>

<style scoped>
/* ══════════════════════════════════════════════════════════════ */
/* Layout base                                                    */
/* ══════════════════════════════════════════════════════════════ */
.validacion-container {
  height: calc(100vh - 57px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--color-white);
  font-family: var(--font-body);
}

/* ══════════════════════════════════════════════════════════════ */
/* STEPPER                                                        */
/* ══════════════════════════════════════════════════════════════ */
.stepper-barra {
  background-color: var(--color-tertiary);
  padding: 20px 40px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

.stepper-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  max-width: 700px;
  margin: 0 auto;
}

.stepper-paso {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.paso-circulo {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  border: 2px solid rgba(255,255,255,0.25);
  color: rgba(255,255,255,0.35);
  background-color: transparent;
  transition: all 0.3s ease;
}

.paso-label {
  font-size: 11px;
  font-weight: 500;
  color: rgba(255,255,255,0.35);
  white-space: nowrap;
  letter-spacing: 0.3px;
  transition: color 0.3s ease;
}

/* Activo */
.paso--activo .paso-circulo {
  background-color: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-white);
  box-shadow: 0 0 0 4px rgba(0,111,179,0.35);
}
.paso--activo .paso-label { color: var(--color-white); font-weight: 700; }

/* Completado */
.paso--completado .paso-circulo {
  background-color: #1e7e53;
  border-color: #1e7e53;
  color: var(--color-white);
}
.paso--completado .paso-label { color: #6dddaa; }

/* Línea conectora */
.stepper-linea {
  flex: 1;
  height: 2px;
  background-color: rgba(255,255,255,0.12);
  margin: 0 12px;
  margin-bottom: 22px;
  transition: background-color 0.3s ease;
}
.linea--completa { background-color: #1e7e53; }

/* ══════════════════════════════════════════════════════════════ */
/* ETAPA 1: layout general                                        */
/* ══════════════════════════════════════════════════════════════ */
.etapa-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* ── Panel izquierdo ── */
.panel-checklist {
  width: 340px;
  min-width: 300px;
  flex-shrink: 0;
  padding: 32px 24px;
  border-right: 1px solid var(--color-neutral);
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.checklist-titulo {
  font-family: var(--font-title);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-black);
  margin: 0;
  letter-spacing: 0.3px;
}

.checklist-cargando {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;
  text-align: center;
}

/* Grupos */
.grupos-lista {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.grupo-item {
  border-radius: 8px;
  border: 1px solid var(--color-neutral);
  overflow: hidden;
  transition: border-color 0.2s;
}

.grupo--ok     { border-color: #d1fae5; }
.grupo--error  { border-color: #fecaca; }
.grupo--revisando { border-color: #bfdbfe; }

.grupo-cabecera {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
}

.grupo-icono {
  font-size: 18px;
  flex-shrink: 0;
  width: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.grupo--pendiente  .grupo-icono { color: var(--color-mid-gray); }
.grupo--revisando  .grupo-icono { color: var(--color-primary); }
.grupo--ok         .grupo-icono { color: #059669; }
.grupo--error      .grupo-icono { color: #dc2626; }

.grupo-texto {
  display: flex;
  flex-direction: column;
  gap: 1px;
  flex: 1;
}

.grupo-nombre {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-black);
}

.grupo--pendiente .grupo-nombre { color: var(--color-mid-gray); }
.grupo--ok        .grupo-nombre { color: #065f46; }
.grupo--error     .grupo-nombre { color: #991b1b; }

.grupo-desc {
  font-size: 12px;
  color: var(--color-mid-gray);
}

.grupo-conteo {
  background-color: #dc2626;
  color: white;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* Errores dentro del grupo */
.errores-lista {
  list-style: none;
  padding: 0 12px 10px 44px;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid #fecaca;
  padding-top: 8px;
}

.error-item { display: flex; flex-direction: column; gap: 4px; }

.error-cabecera {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #dc2626;
}

.error-valor { font-weight: 600; }
.error-fila  { color: var(--color-mid-gray); font-size: 10px; margin-left: auto; }

/* Sugerencia */
.sugerencia-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #1e293b;
  border: 1px solid #ca8a04;
  border-radius: 4px;
  padding: 4px 8px;
  gap: 6px;
}

.sugerencia-texto {
  font-size: 11px;
  color: #fbbf24;
  flex: 1;
}

.btn-corregir {
  background-color: #ca8a04;
  color: #111;
  border: none;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 0.15s;
}
.btn-corregir:hover { background-color: #f59e0b; }

/* Acciones del sidebar */
.sidebar-acciones {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--color-neutral);
  display: flex;
  flex-direction: column;
}

/* Animación spin */
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.spin { display: inline-block; animation: spin 0.8s linear infinite; }

/* ── Panel derecho: Tabla ── */
.panel-tabla {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.tabla-cabecera {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 28px 32px 16px;
  border-bottom: 1px solid var(--color-neutral);
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 12px;
}

.tabla-titulo {
  font-family: var(--font-title);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-black);
  margin: 0 0 4px;
}

.tabla-subtitulo {
  font-size: 13px;
  color: var(--color-mid-gray);
  margin: 0;
}

.separador-cabecera { margin: 0 6px; color: var(--color-neutral); }

/* KPIs de resumen */
.tabla-kpis {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
}

.kpi {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 20px;
}

.kpi--ok    { background-color: #d1fae5; color: #065f46; }
.kpi--error { background-color: #fee2e2; color: #991b1b; }

/* Estado procesando */
.tabla-procesando {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-mid-gray);
  gap: 4px;
}

/* Wrapper de la tabla */
.tabla-wrapper {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
}

.tabla-cometidos {
  width: 100%;
  border-collapse: collapse;
  font-size: 15px;
}

.tabla-cometidos thead tr {
  background-color: var(--color-tertiary);
  color: var(--color-white);
  position: sticky;
  top: 0;
  z-index: 1;
}

.tabla-cometidos th {
  padding: 14px 18px;
  font-family: var(--font-title);
  font-weight: 500;
  font-size: 13px;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  white-space: nowrap;
}

.tabla-cometidos td {
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-neutral);
  vertical-align: middle;
}

.tabla-cometidos tbody tr:hover { background-color: #f8fafc; }

/* Fila con error: fondo levemente rosado */
.fila-con-error { background-color: #fff7f7 !important; }
.fila-con-error:hover { background-color: #fff0f0 !important; }

/* Columnas */
.col-n        { width: 64px;   text-align: center; }
.col-conductor { min-width: 160px; }
.col-fechas   { width: 220px; white-space: nowrap; }
.col-vehiculo { width: 160px; }
.col-viaticos { width: 180px; }
.col-estado   { width: 120px; text-align: center; }

/* Badge de número de fila */
.badge-fila {
  background-color: #f1f5f9;
  color: var(--color-dark-gray);
  border-radius: 4px;
  padding: 3px 9px;
  font-size: 13px;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

/* RUT */
.conductor-bloque { display: flex; flex-direction: column; gap: 4px; }
.conductor-rut {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-dark-gray);
  font-family: 'Courier New', monospace;
  letter-spacing: 0.3px;
}

/* Celda con error */
.celda-error {
  color: #dc2626 !important;
  background-color: #fff1f2;
  border-radius: 4px;
  padding: 2px 6px;
}

/* Fechas — siempre en una sola línea */
.fechas-bloque {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}
.fecha-chip {
  background-color: #f1f5f9;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 13px;
  color: var(--color-dark-gray);
  font-family: 'Courier New', monospace;
  white-space: nowrap;
}
.fecha-sep { color: var(--color-mid-gray); font-size: 14px; flex-shrink: 0; }

/* Vehículo / Sigla */
.vehiculo-bloque { display: flex; flex-direction: column; gap: 4px; }

.badge-sigla {
  display: inline-flex;
  align-items: center;
  background-color: #f0f4f8;
  color: var(--color-dark-gray);
  border: 1px solid #d0dae3;
  border-radius: 4px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  letter-spacing: 0.5px;
}

.badge-sigla--error {
  background-color: #fee2e2;
  border-color: #fca5a5;
  color: #dc2626;
}

/* Viáticos */
.viaticos-bloque { display: flex; flex-direction: column; gap: 2px; }
.viaticos-dias   { font-size: 13px; font-weight: 600; color: var(--color-black); display: flex; align-items: center; }
.viaticos-detalle { font-size: 11px; color: var(--color-mid-gray); }

/* Sugerencia inline (en la tabla) — compacta, no se estira */
.sugerencia-inline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 5px;
  background-color: #1e293b;
  border: 1px solid #ca8a04;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 11px;
  width: fit-content;
  max-width: 100%;
}
.sugerencia-inline span { color: #fbbf24; white-space: nowrap; }

.btn-corregir-inline {
  background-color: #ca8a04;
  color: #111;
  border: none;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 7px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
.btn-corregir-inline:hover { background-color: #f59e0b; }

/* Badges de estado de la fila */
.badge-estado {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 12px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.badge-estado--ok    { background-color: #d1fae5; color: #065f46; }
.badge-estado--error { background-color: #fee2e2; color: #991b1b; }

/* Tabla vacía */
.tabla-vacia {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: var(--color-mid-gray);
}

/* ── CTA Principal ── */
.cta-zona {
  padding: 20px 32px 28px;
  border-top: 1px solid var(--color-neutral);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  background-color: #fafbfc;
}

.cta-aviso {
  margin: 0;
  font-size: 14px;
  color: #dc2626;
  background-color: #fff1f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 8px 16px;
  text-align: center;
}

.btn-cta {
  padding: 14px 48px;
  font-size: 16px;
  font-weight: 700;
  border-radius: 8px;
  letter-spacing: 0.3px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
}

.btn-cta:not(:disabled):hover {
  box-shadow: 0 6px 20px rgba(0, 111, 179, 0.3);
  transform: translateY(-1px);
}


/* ── Responsividad general ── */
/* Pantallas grandes (1280px+): más espacio en el checklist */
@media (min-width: 1280px) {
  .panel-checklist  { width: 360px; }
  .checklist-titulo { font-size: 21px; }
  .grupo-nombre     { font-size: 15px; }
  .tabla-cometidos  { font-size: 15px; }
}

/* Pantallas muy grandes (1600px+): escala adicional */
@media (min-width: 1600px) {
  .panel-checklist  { width: 400px; }
  .grupo-nombre     { font-size: 17px; }
  .grupo-desc       { font-size: 14px; }
  .tabla-cometidos  { font-size: 16px; }
  .conductor-rut    { font-size: 17px; }
  .fecha-chip       { font-size: 14px; }
}

/* Pantallas compactas (menos de 1024px): checklist más estrecho */
@media (max-width: 1024px) {
  .panel-checklist  { width: 260px; min-width: 220px; }
  .etapa-layout     { flex-direction: column; overflow: auto; }
  .panel-checklist  { width: 100%; border-right: none; border-bottom: 1px solid var(--color-neutral); padding: 20px; }
}
</style>