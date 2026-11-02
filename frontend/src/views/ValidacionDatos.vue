<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import EtapaFinal from './EtapaFinal.vue'

const router = useRouter()

// ─── Stepper global (3 etapas de la vista) ────────────────────
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

// ─── Sub-Stepper de 3 pasos del RPA (SSD → Personal → Firmador) ──
const subPasos = [
  { id: 2, label: 'Portal SSD',      icono: 'bi-file-earmark-text' },
  { id: 3, label: 'Portal Personal', icono: 'bi-person-badge'      },
  { id: 4, label: 'Portal Firmador', icono: 'bi-pen'               },
]
const pasoSubStepper = ref(0) // 0=ninguno, 2=SSD, 3=Personal, 4=Firmador

// ─── Estado de ejecución RPA ──────────────────────────────────
const automatizando       = ref(false)
const completadoExitoso   = ref(false)
const huboError           = ref(false)
const mensajeEstado       = ref('')
const mostrarTerminal     = ref(false)

// ─── Consola / Logs ───────────────────────────────────────────
const logsAutomatizacion  = ref([])
const consolaCuerpoRef    = ref(null)
let intervaloProgreso     = null
const ultimoDetalleRegistrado = ref('')

// Rastreadores para evitar duplicidad de checkpoints en polling
const cometidosIniciados = new Set()
const cometidosFallidosLogueados = new Set()
const cometidosCompletadosLogueados = new Set()
let resumenEmitido = false

// ─── Medición de Tiempos (Cronómetro Global y por Cometido) ───
const tiempoInicioGlobal       = ref(null)
const segundosTranscurridos     = ref(0)
let intervaloTiempo             = null
const tiemposCometidos          = ref({}) // Mapa: indice -> { inicio, fin, duracion }

// ─── Referencias de filas y micro-feedback de auto-corrección ──
const filasRefs                 = {}
const filasCorregidasRecientes  = ref(new Set())

function guardarRefFila(el, idx) {
  if (el) filasRefs[idx] = el
}

function formatearTiempoReloj(s) {
  const mins = Math.floor(s / 60)
  const secs = s % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function formatearSegundos(s) {
  const mins = Math.floor(s / 60)
  const secs = s % 60
  if (mins === 0) return `${secs}s`
  return `${mins}m ${secs.toString().padStart(2, '0')}s`
}

const tiempoTotalFormateado = computed(() => {
  return formatearSegundos(segundosTranscurridos.value)
})

const promedioPorCometidoTexto = computed(() => {
  const arr = Object.values(tiemposCometidos.value).filter(t => t.duracion > 0)
  if (arr.length === 0) return ''
  const avg = Math.round(arr.reduce((acc, t) => acc + t.duracion, 0) / arr.length)
  return formatearSegundos(avg)
})

function tiempoCometidoTexto(idx) {
  const t = tiemposCometidos.value[idx]
  if (!t) return ''
  if (t.fin) return formatearSegundos(t.duracion)
  const segs = Math.max(0, Math.floor((Date.now() - t.inicio) / 1000))
  return `${segs}s`
}

// ─── Sonido Sutil de Término (Web Audio API Nativa) ───────────
function emitirSonidoExito() {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext
    if (!AudioContextClass) return
    const audioCtx = new AudioContextClass()
    const notas = [523.25, 659.25, 783.99] // Acorde Do Mayor suave (C5 - E5 - G5)
    notas.forEach((freq, i) => {
      const osc = audioCtx.createOscillator()
      const gain = audioCtx.createGain()
      osc.frequency.value = freq
      osc.type = 'sine'
      gain.gain.setValueAtTime(0.06, audioCtx.currentTime + i * 0.09)
      gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + i * 0.09 + 0.45)
      osc.connect(gain)
      gain.connect(audioCtx.destination)
      osc.start(audioCtx.currentTime + i * 0.09)
      osc.stop(audioCtx.currentTime + i * 0.09 + 0.45)
    })
  } catch (e) {
    // Silencioso si el navegador restringe audio
  }
}

// Auto-scroll al abrir la terminal si ya hay logs
watch(mostrarTerminal, async (newVal) => {
  if (newVal) {
    await nextTick()
    if (consolaCuerpoRef.value) {
      consolaCuerpoRef.value.scrollTop = consolaCuerpoRef.value.scrollHeight
    }
  }
})

// ─── Estados por cometido (colores de las filas) ──────────────
// Mapa: indice del cometido → { estado, portal, accion_actual, detalle, ultimo_error }
const estadosCometidos = ref([])

// Contador visual: "Procesando cometido X de Y"
const cometidoActualIndice = ref(-1)
const totalCometidos       = ref(0)

// ─── Computados de Progreso y Errores ──────────────────────────
const cometidosProcesadosCount = computed(() => {
  return estadosCometidos.value.filter(c => c.estado === 'completado' || c.estado === 'fallido').length
})

const porcentajeAvance = computed(() => {
  if (totalCometidos.value === 0) return 0
  return Math.min(100, Math.round((cometidosProcesadosCount.value / totalCometidos.value) * 100))
})

const tieneErroresEnLogs = computed(() =>
  logsAutomatizacion.value.some(l => l.tipo === 'checkpoint_error')
)

// Modal de detalle de error al hacer clic en "Ver detalle" en la fila
const detalleErrorModal = ref(null)

function inspeccionarErrorFila(indice) {
  const logErr = logsAutomatizacion.value.find(
    l => l.tipo === 'checkpoint_error' && l.cometidoNum === indice + 1
  )
  if (logErr) {
    detalleErrorModal.value = logErr
    return
  }
  const ec = estadosCometidos.value.find(c => c.indice === indice)
  const mapaPortales = {
    ssd: 'Portal SSD (Gestión Documental)',
    personal: 'Portal Personal MOP (Viáticos)',
    firmador: 'Portal Firmador MOP (Firmas)',
    general: 'Sistema General',
  }
  const portalKey = ec?.ultimo_error?.portal || ec?.portal || ''
  detalleErrorModal.value = {
    cometidoNum: indice + 1,
    rut: formatearRut(ec?.rut || filas.value[indice]?.rut),
    portalNombre: mapaPortales[portalKey] || (portalKey ? String(portalKey).toUpperCase() : 'PORTAL INSTITUCIONAL'),
    accion: ec?.ultimo_error?.accion || ec?.accion_actual || 'Ejecutando acción',
    errorMensaje: ec?.ultimo_error?.mensaje || ec?.detalle || 'Error detectado en el proceso',
  }
}

function cerrarModalError() {
  detalleErrorModal.value = null
}

const totalErrores = computed(() =>
  grupos.value.reduce((sum, g) => sum + g.errores.length, 0)
)

const tieneSugerencias = computed(() =>
  filas.value.some(f => {
    if (!f.rut_valido && f.sugerencia_correccion_rut) return true
    if (!f.sigla_valida && f.sugerencia_correccion_sigla) return true
    const dIni = parsearFechaDMY(f.fechainicio)
    const dTer = parsearFechaDMY(f.fechatermino)
    const mismoMes = Boolean(dIni && dTer && dIni.getMonth() === dTer.getMonth() && dIni.getFullYear() === dTer.getFullYear())
    if (dIni && dTer && mismoMes && dIni > dTer) return true
    if (!String(f.dias_salida || '').trim() && dIni && dTer && mismoMes && dIni <= dTer) return true
    return false
  })
)

const todasValidas = computed(() =>
  !procesando.value && totalErrores.value === 0
)

// Determina el color de fondo de cada fila de la tabla según el estado del cometido
function colorFilaEjecucion(indice) {
  if (etapaActual.value !== 2) return ''
  const ec = estadosCometidos.value.find(c => c.indice === indice)
  if (!ec) return ''
  if (ec.estado === 'ejecutando')  return 'fila-ejecutando'
  if (ec.estado === 'completado')  return 'fila-completado'
  if (ec.estado === 'fallido')     return 'fila-fallido'
  return ''
}

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

// Formatea RUT chileno:
// - Si viene con guión ("13193029-9"), separa cuerpo y DV: "13.193.029-9"
// - Si viene sin guión ("13652729"), es el cuerpo directo del conductor: "13.652.729"
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

// Presentación de la sugerencia conservando el DV original de la celda
function sugerenciaRutConDv(fila) {
  if (!fila?.sugerencia_correccion_rut) return ''
  const valActual = String(fila.rut || '').trim()
  const dvOriginal = valActual.includes('-') ? valActual.split('-')[1] : ''
  const rutConDv = dvOriginal ? `${fila.sugerencia_correccion_rut}-${dvOriginal}` : fila.sugerencia_correccion_rut
  return formatearRut(rutConDv)
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

// Convierte "LUNES, MARTES, VIERNES" en chips abreviados ["LU", "MA", "VI"]
function chipsDias(diasStr) {
  if (!diasStr || String(diasStr).trim() === '') return []
  const mapa = {
    'lunes': 'LU', 'martes': 'MA', 'miercoles': 'MI', 'miércoles': 'MI',
    'jueves': 'JU', 'viernes': 'VI', 'sabado': 'SA', 'sábado': 'SA',
    'domingo': 'DO',
  }
  return String(diasStr).split(',')
    .map(d => d.trim().toLowerCase())
    .filter(d => d !== '')
    .map(d => mapa[d] || d.substring(0, 2).toUpperCase())
}

// Lista de errores semánticos de una fila específica según las validaciones del backend
function erroresDeFila(fila) {
  const e = []
  if (fila.rut_valido === false)   e.push('rut')
  if (fila.sigla_valida === false) e.push('sigla')
  if (fila.viaticos_validos === false) e.push('viaticos')
  if (fila.fechas_validas === false) e.push('fechas')
  if (fila.admin_valido === false) {
    for (const c of ['fechainicio', 'fechatermino', 'dias_salida']) {
      if (!fila[c] || String(fila[c]).trim() === '') {
        if (!e.includes(c)) e.push(c)
      }
    }
    if (!fila.sigla || String(fila.sigla).trim() === '') {
      if (!e.includes('sigla')) e.push('sigla')
    }
  }
  return e
}

function filaTieneError(fila, campo) {
  return erroresDeFila(fila).includes(campo)
}

// ─── Consola: agregar log con auto-scroll y metadatos ─────────
function agregarLog(entrada) {
  const ahora = new Date()
  const hora = ahora.toTimeString().split(' ')[0]
  let item = {}
  if (typeof entrada === 'string') {
    item = {
      id: Date.now() + Math.random(),
      hora,
      tipo: 'info',
      texto: entrada,
    }
  } else {
    item = {
      id: Date.now() + Math.random(),
      hora: entrada.hora || hora,
      ...entrada,
    }
  }
  logsAutomatizacion.value.push(item)
  nextTick(() => {
    if (consolaCuerpoRef.value) {
      consolaCuerpoRef.value.scrollTop = consolaCuerpoRef.value.scrollHeight
    }
  })
}

function copiarLogs() {
  if (logsAutomatizacion.value.length === 0) return
  const texto = logsAutomatizacion.value.map(l => {
    if (l.tipo === 'checkpoint_error') {
      const titulo = l.cometidoNum > 0
        ? `FALLO EN COMETIDO #${l.cometidoNum} (${l.portalNombre})`
        : `NO SE PUDO INICIAR LA AUTOMATIZACIÓN`
      const lineaFunc = l.rut && l.rut !== 'N/A' ? `\n  Funcionario: ${l.rut}` : ''
      return `[${l.hora}] ❌ ${titulo}${lineaFunc}\n  Paso: ${l.accion}\n  Motivo: ${l.errorMensaje}`
    } else if (l.tipo === 'checkpoint_exito') {
      return `[${l.hora}] ✔ ${l.texto}`
    } else if (l.tipo === 'inicio_cometido') {
      return `[${l.hora}] ▶ ${l.texto}`
    } else if (l.tipo === 'resumen') {
      return `[${l.hora}] 🏁 RESUMEN: Total: ${l.total} | Completados: ${l.completados} | Fallidos: ${l.fallidos}`
    }
    return `[${l.hora}] › ${l.texto}`
  }).join('\n')

  navigator.clipboard.writeText(texto)
    .then(() => alert('Logs copiados al portapapeles correctamente.'))
    .catch(() => {})
}

function limpiarLogs() {
  logsAutomatizacion.value = []
}

// Deducción dinámica del portal y paso del sub-stepper por cometido (SSD: 2, Personal: 3, Firmador: 4)
function deducirPasoStepper(activo, data) {
  const portalPasoMap = { ssd: 2, personal: 3, firmador: 4 }
  if (activo?.portal && portalPasoMap[activo.portal.toLowerCase()]) {
    return portalPasoMap[activo.portal.toLowerCase()]
  }
  if (data?.paso_stepper && data.paso_stepper >= 2 && data.paso_stepper <= 4) {
    return data.paso_stepper
  }
  const det = String(activo?.detalle || data?.detalle || '').toLowerCase()
  if (det.includes('firmador') || det.includes('firma')) return 4
  if (det.includes('personal') || det.includes('viático') || det.includes('viatico') || det.includes('atribución') || det.includes('atribucion')) return 3
  if (det.includes('ssd') || det.includes('documento')) return 2
  return 2
}

// ─── Polling: monitoreo de progreso del backend (ICD v1.0.0) ───
function comenzarMonitoreoProgreso() {
  if (intervaloProgreso) clearInterval(intervaloProgreso)
  ultimoDetalleRegistrado.value = ''
  cometidosIniciados.clear()
  cometidosFallidosLogueados.clear()
  cometidosCompletadosLogueados.clear()
  resumenEmitido = false

  intervaloProgreso = setInterval(async () => {
    try {
      const resp = await fetch('/api/progreso-automatizacion')
      if (!resp.ok) return

      const data = await resp.json()

      // Actualiza totales
      if (data.total_cometidos) totalCometidos.value = data.total_cometidos

      // Sincroniza colección reactiva de estados_cometidos
      if (Array.isArray(data.estados_cometidos)) {
        estadosCometidos.value = data.estados_cometidos

        // Registrar y actualizar tiempos individuales por cometido
        data.estados_cometidos.forEach(c => {
          if (c.estado === 'ejecutando') {
            if (!tiemposCometidos.value[c.indice]) {
              tiemposCometidos.value[c.indice] = { inicio: Date.now(), fin: null, duracion: 0 }
            }
          } else if (c.estado === 'completado' || c.estado === 'fallido') {
            if (tiemposCometidos.value[c.indice] && !tiemposCometidos.value[c.indice].fin) {
              tiemposCometidos.value[c.indice].fin = Date.now()
              tiemposCometidos.value[c.indice].duracion = Math.max(
                1,
                Math.round((tiemposCometidos.value[c.indice].fin - tiemposCometidos.value[c.indice].inicio) / 1000)
              )
            } else if (!tiemposCometidos.value[c.indice]) {
              tiemposCometidos.value[c.indice] = { inicio: Date.now() - 1000, fin: Date.now(), duracion: 1 }
            }
          }
        })
      }

      if (data.estado === 'iniciando') {
        // Fase de login en portales MOP (SSD, Personal, Firmador)
        if (data.detalle && ultimoDetalleRegistrado.value !== data.detalle) {
          ultimoDetalleRegistrado.value = data.detalle
          agregarLog({ tipo: 'info', texto: data.detalle })
        }
        pasoSubStepper.value = data.paso_stepper || 2

      } else if (data.estado === 'ejecutando') {
        // Actualiza cometido activo, sub-stepper dinámico por cometido y auto-scroll
        const activo = (data.estados_cometidos || []).find(c => c.estado === 'ejecutando')

        // Sincroniza dinámicamente el sub-stepper en cada ciclo (SSD -> Personal -> Firmador)
        pasoSubStepper.value = deducirPasoStepper(activo, data)

        if (activo) {
          if (cometidoActualIndice.value !== activo.indice) {
            cometidoActualIndice.value = activo.indice
            nextTick(() => {
              if (filasRefs[activo.indice]) {
                filasRefs[activo.indice].scrollIntoView({ behavior: 'smooth', block: 'nearest' })
              }
            })
          }
        }

        // 1. Detectar si un cometido entra en proceso por primera vez
        (data.estados_cometidos || []).forEach(c => {
          if (!cometidosIniciados.has(c.indice)) {
            cometidosIniciados.add(c.indice)
            const tot = data.total_cometidos || filas.value.length
            agregarLog({
              tipo: 'inicio_cometido',
              cometidoNum: c.indice + 1,
              total: tot,
              rut: formatearRut(c.rut),
              texto: `Iniciando Cometido #${c.indice + 1} de ${tot} — Funcionario RUT: ${formatearRut(c.rut)}`,
            })
          }
        })

        // 2. Detectar si un cometido falló (Checkpoint con alerta y output de Python)
        (data.estados_cometidos || []).forEach(c => {
          if (c.estado === 'fallido' && !cometidosFallidosLogueados.has(c.indice)) {
            cometidosFallidosLogueados.add(c.indice)

            const mapaPortales = {
              ssd: 'Portal SSD (Gestión Documental)',
              personal: 'Portal Personal MOP (Viáticos)',
              firmador: 'Portal Firmador MOP (Firmas)',
              general: 'Sistema General',
            }
            const portalNombre = mapaPortales[c.portal] || (c.portal ? String(c.portal).toUpperCase() : 'PORTAL INSTITUCIONAL')
            const err = c.ultimo_error

            const accion = err?.accion || c.accion_actual || 'Ejecutando acción'
            const mensaje = err?.mensaje || c.detalle || 'Error detectado en el proceso'

            agregarLog({
              tipo: 'checkpoint_error',
              cometidoNum: c.indice + 1,
              rut: formatearRut(c.rut),
              portalNombre,
              accion,
              errorMensaje: mensaje,
              texto: `❌ FALLO EN COMETIDO #${c.indice + 1} (${portalNombre})`,
            })
          }
        })

        // 3. Detectar si un cometido se completó exitosamente
        (data.estados_cometidos || []).forEach(c => {
          if (c.estado === 'completado' && !cometidosCompletadosLogueados.has(c.indice)) {
            cometidosCompletadosLogueados.add(c.indice)
            agregarLog({
              tipo: 'checkpoint_exito',
              cometidoNum: c.indice + 1,
              rut: formatearRut(c.rut),
              texto: `✔ Cometido #${c.indice + 1} finalizado con éxito (RUT: ${formatearRut(c.rut)})`,
            })
          }
        })

        // 4. Detalle atómico en vivo (si es un paso nuevo y no es duplicado del fallo)
        if (data.detalle && ultimoDetalleRegistrado.value !== data.detalle) {
          ultimoDetalleRegistrado.value = data.detalle
          if (!data.detalle.startsWith('Fallo en ') && !data.detalle.includes('Error inesperado')) {
            agregarLog({ tipo: 'info', texto: data.detalle })
          }
        }

      } else if (data.estado === 'completado') {
        // Sincroniza estados finales
        if (data.estados_cometidos) {
          estadosCometidos.value = data.estados_cometidos
          data.estados_cometidos.forEach(c => {
            if (tiemposCometidos.value[c.indice] && !tiemposCometidos.value[c.indice].fin) {
              tiemposCometidos.value[c.indice].fin = Date.now()
              tiemposCometidos.value[c.indice].duracion = Math.max(
                1,
                Math.round((tiemposCometidos.value[c.indice].fin - tiemposCometidos.value[c.indice].inicio) / 1000)
              )
            }
          })
        }

        // Asegurar que cometidos finales queden registrados en logs
        (data.estados_cometidos || []).forEach(c => {
          if (c.estado === 'fallido' && !cometidosFallidosLogueados.has(c.indice)) {
            cometidosFallidosLogueados.add(c.indice)
            const mapaPortales = {
              ssd: 'Portal SSD (Gestión Documental)',
              personal: 'Portal Personal MOP (Viáticos)',
              firmador: 'Portal Firmador MOP (Firmas)',
              general: 'Sistema General',
            }
            const portalNombre = mapaPortales[c.portal] || (c.portal ? String(c.portal).toUpperCase() : 'PORTAL INSTITUCIONAL')
            const err = c.ultimo_error
            const accion = err?.accion || c.accion_actual || 'Ejecutando acción'
            const mensaje = err?.mensaje || c.detalle || 'Error detectado en el proceso'

            agregarLog({
              tipo: 'checkpoint_error',
              cometidoNum: c.indice + 1,
              rut: formatearRut(c.rut),
              portalNombre,
              accion,
              errorMensaje: mensaje,
              texto: `❌ FALLO EN COMETIDO #${c.indice + 1} (${portalNombre})`,
            })
          } else if (c.estado === 'completado' && !cometidosCompletadosLogueados.has(c.indice)) {
            cometidosCompletadosLogueados.add(c.indice)
            agregarLog({
              tipo: 'checkpoint_exito',
              cometidoNum: c.indice + 1,
              rut: formatearRut(c.rut),
              texto: `✔ Cometido #${c.indice + 1} finalizado con éxito (RUT: ${formatearRut(c.rut)})`,
            })
          }
        })

        if (!resumenEmitido) {
          resumenEmitido = true
          const tot = data.total_cometidos || filas.value.length
          const comp = (data.estados_cometidos || []).filter(c => c.estado === 'completado').length
          const fall = (data.estados_cometidos || []).filter(c => c.estado === 'fallido').length

          agregarLog({
            tipo: 'resumen',
            total: tot,
            completados: comp,
            fallidos: fall,
            texto: `Automatización finalizada. Completados: ${comp} | Con errores: ${fall}`,
          })

          // Sonido armónico sutil al finalizar
          emitirSonidoExito()
        }

        detenerMonitoreoProgreso()
        pasoSubStepper.value = 5
        automatizando.value = false
        completadoExitoso.value = true
        const compFinal = (data.estados_cometidos || []).filter(c => c.estado === 'completado').length
        const fallFinal = (data.estados_cometidos || []).filter(c => c.estado === 'fallido').length
        if (fallFinal === 0) {
          mensajeEstado.value = '¡Automatización finalizada con éxito!'
        } else if (compFinal > 0) {
          mensajeEstado.value = `Automatización finalizada con observaciones (${compFinal} completado${compFinal !== 1 ? 's' : ''}, ${fallFinal} con error)`
        } else {
          mensajeEstado.value = `Automatización finalizada: los ${fallFinal} cometido(s) presentaron errores`
        }

      } else if (data.estado === 'error_credenciales') {
        const errDesc = data.detalle || 'Usuario o contraseña incorrectos. Verifica tus credenciales e intenta nuevamente.'
        agregarLog({
          tipo: 'checkpoint_error',
          cometidoNum: 0,
          rut: 'N/A',
          portalNombre: 'Inicio de Sesión MOP',
          accion: 'Verificación de credenciales',
          errorMensaje: errDesc,
          texto: errDesc,
        })
        detenerMonitoreoProgreso()
        automatizando.value = false
        huboError.value = true
        mensajeEstado.value = errDesc
        errorCredenciales.value = errDesc
        mostrarClave.value = false
        mostrarModalCredenciales.value = true

      } else if (data.estado === 'error') {
        const errDesc = data.detalle || 'No se pudo completar el inicio del proceso.'
        agregarLog({
          tipo: 'checkpoint_error',
          cometidoNum: 0,
          rut: 'N/A',
          portalNombre: 'Inicio de Automatización',
          accion: 'Conexión / Inicio de sesión en portales MOP',
          errorMensaje: errDesc,
          texto: errDesc,
        })
        detenerMonitoreoProgreso()
        automatizando.value = false
        huboError.value = true
        mensajeEstado.value = errDesc
      }
    } catch (e) {
      console.error('Error al consultar progreso:', e)
    }
  }, 500)
}

function detenerMonitoreoProgreso() {
  if (intervaloProgreso) {
    clearInterval(intervaloProgreso)
    intervaloProgreso = null
  }
  if (intervaloTiempo) {
    clearInterval(intervaloTiempo)
    intervaloTiempo = null
  }
}

// ─── Iniciar ejecución del bot ────────────────────────────────
async function iniciarEjecucion() {
  automatizando.value = true
  completadoExitoso.value = false
  huboError.value = false
  logsAutomatizacion.value = []
  estadosCometidos.value = []
  tiemposCometidos.value = {}
  cometidoActualIndice.value = -1
  pasoSubStepper.value = 2

  cometidosIniciados.clear()
  cometidosFallidosLogueados.clear()
  cometidosCompletadosLogueados.clear()
  resumenEmitido = false

  tiempoInicioGlobal.value = Date.now()
  segundosTranscurridos.value = 0
  if (intervaloTiempo) clearInterval(intervaloTiempo)
  intervaloTiempo = setInterval(() => {
    if (tiempoInicioGlobal.value) {
      segundosTranscurridos.value = Math.floor((Date.now() - tiempoInicioGlobal.value) / 1000)
    }
  }, 1000)

  agregarLog({
    tipo: 'info',
    texto: 'Iniciando el motor de automatización Playwright en segundo plano...',
  })

  try {
    const payload = filas.value.map(f => ({
      rut: f.rut,
      sigla: f.sigla,
      fechainicio: f.fechainicio,
      fechatermino: f.fechatermino,
      tipo_movilizacion: f.tipo_movilizacion,
      personal_trasladado: f.personal_trasladado,
      fallback_considerando: f.fallback_considerando,
      lugar_cometido: f.lugar_cometido,
      regiones: f.regiones,
      atribucion: f.atribucion,
      dias_salida: f.dias_salida,
      dias_100: f.dias_100,
      dias_70: f.dias_70,
      dias_60: f.dias_60,
      dias_50: f.dias_50,
      dias_40: f.dias_40,
      dias_35: f.dias_35,
      tipo_imputacion_presupuestaria: f.tipo_imputacion_presupuestaria,
      nombre_aprobador: f.nombre_aprobador,
      nombre_firmantes: f.nombre_firmantes,
    }))

    const resp = await fetch('/api/empezar-automatizacion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filas: payload,
        credenciales: {
          usuario_ssd: credencialUsuarioSsd.value.trim(),
          clave_ssd: credencialClaveSsd.value,
          usuario: credencialUsuario.value.trim(),
          clave: credencialClave.value,
        },
      }),
    })

    // Limpia las contraseñas en el navegador tras enviarlas al backend
    credencialClaveSsd.value = ''
    credencialClave.value = ''

    if (!resp.ok) throw new Error(`El servidor respondió con estado ${resp.status}`)

    const data = await resp.json()
    if (data.status === 'iniciado') {
      totalCometidos.value = filas.value.length
      comenzarMonitoreoProgreso()
    } else {
      agregarLog({
        tipo: 'checkpoint_error',
        cometidoNum: 0,
        rut: 'N/A',
        portalNombre: 'Servidor Local',
        accion: 'Iniciar automatización',
        errorMensaje: data.mensaje || 'Respuesta negativa del servidor',
        texto: `Error al iniciar: ${data.mensaje}`,
      })
      automatizando.value = false
      huboError.value = true
    }
  } catch (e) {
    agregarLog({
      tipo: 'checkpoint_error',
      cometidoNum: 0,
      rut: 'N/A',
      portalNombre: 'Red / Conexión',
      accion: 'Comunicación con el servidor local',
      errorMensaje: 'No se pudo contactar con el servidor de la aplicación.',
      texto: `Error de conexión: ${e.message}`,
    })
    automatizando.value = false
    huboError.value = true
  }
}

function cancelarAutomatizacion() {
  const confirmacion = window.confirm('¿Estás seguro de que deseas cancelar la automatización en curso?')
  if (!confirmacion) return
  detenerMonitoreoProgreso()
  automatizando.value = false
  etapaActual.value = 1
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

onUnmounted(() => {
  detenerMonitoreoProgreso()
})

async function animarTodosLosGrupos() {
  // Grupo 1 — Identidad y Conductor (validación backend: rut)
  await animarGrupo('identidad', (fila) => {
    if (fila.rut_valido !== false) return []
    const msgs = fila.errores_por_grupo?.identidad?.length
      ? fila.errores_por_grupo.identidad
      : [(fila.errores || []).find(e => e.toLowerCase().includes('rut')) || 'RUT inválido o no registrado']
    return msgs.map(m => ({
      fila:         fila.numero_fila_excel,
      campo:        'rut',
      mensaje:      m,
      sugerencia:   fila.sugerencia_correccion_rut,
      valor_actual: fila.rut,
      fila_ref:     fila,
    }))
  }, 900)

  // Grupo 2 — Vehículo (validación backend: sigla)
  await animarGrupo('vehiculo', (fila) => {
    if (fila.sigla_valida !== false) return []
    const msgs = fila.errores_por_grupo?.vehiculo?.length
      ? fila.errores_por_grupo.vehiculo
      : [(fila.errores || []).find(e => e.toLowerCase().includes('sigla')) || 'Sigla/patente inválida o no registrada']
    return msgs.map(m => ({
      fila:         fila.numero_fila_excel,
      campo:        'sigla',
      mensaje:      m,
      sugerencia:   fila.sugerencia_correccion_sigla,
      valor_actual: fila.sigla,
      fila_ref:     fila,
    }))
  }, 900)

  // Grupo 3 — Coherencia de Viáticos (validación backend)
  await animarGrupo('viaticos', (fila) => {
    if (fila.viaticos_validos !== false) return []
    const msgs = fila.errores_por_grupo?.viaticos?.length
      ? fila.errores_por_grupo.viaticos
      : ['Incoherencia en días de salida vs porcentajes de viático']
    const totalDias = contarDiasSalida(fila.dias_salida)
    const sumaPorc  = sumarViaticos(fila)
    return msgs.map(m => ({
      fila:         fila.numero_fila_excel,
      campo:        'viaticos',
      mensaje:      `Fila ${fila.numero_fila_excel}: ${m}`,
      sugerencia:   null,
      valor_actual: `${totalDias} días / suma ${sumaPorc}`,
      fila_ref:     fila,
    }))
  }, 800)

  // Grupo 4 — Datos Administrativos (validación backend)
  await animarGrupo('admin', (fila) => {
    if (fila.admin_valido !== false && fila.fechas_validas !== false) return []
    const msgs = fila.errores_por_grupo?.admin?.length
      ? fila.errores_por_grupo.admin
      : ['Datos administrativos o fechas con observaciones']
    return msgs.map(m => ({
      fila:         fila.numero_fila_excel,
      campo:        m.toLowerCase().includes('fecha') ? 'fechas' : 'admin',
      mensaje:      `Fila ${fila.numero_fila_excel}: ${m}`,
      sugerencia:   null,
      valor_actual: '(observado)',
      fila_ref:     fila,
    }))
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
      fn: (fila) => {
        if (fila.rut_valido !== false) return []
        const msgs = fila.errores_por_grupo?.identidad?.length
          ? fila.errores_por_grupo.identidad
          : ['RUT inválido']
        return msgs.map(m => ({
          fila: fila.numero_fila_excel, campo: 'rut',
          mensaje: m, sugerencia: fila.sugerencia_correccion_rut,
          valor_actual: fila.rut, fila_ref: fila,
        }))
      },
    },
    {
      id: 'vehiculo',
      fn: (fila) => {
        if (fila.sigla_valida !== false) return []
        const msgs = fila.errores_por_grupo?.vehiculo?.length
          ? fila.errores_por_grupo.vehiculo
          : ['Sigla inválida']
        return msgs.map(m => ({
          fila: fila.numero_fila_excel, campo: 'sigla',
          mensaje: m, sugerencia: fila.sugerencia_correccion_sigla,
          valor_actual: fila.sigla, fila_ref: fila,
        }))
      },
    },
    {
      id: 'viaticos',
      fn: (fila) => {
        if (fila.viaticos_validos !== false) return []
        const msgs = fila.errores_por_grupo?.viaticos?.length
          ? fila.errores_por_grupo.viaticos
          : ['Incoherencia de viáticos']
        const td = contarDiasSalida(fila.dias_salida)
        const sp = sumarViaticos(fila)
        return msgs.map(m => ({
          fila: fila.numero_fila_excel, campo: 'viaticos',
          mensaje: m, sugerencia: null,
          valor_actual: `${td} días / suma ${sp}`, fila_ref: fila,
        }))
      },
    },
    {
      id: 'admin',
      fn: (fila) => {
        if (fila.admin_valido !== false && fila.fechas_validas !== false) return []
        const msgs = fila.errores_por_grupo?.admin?.length
          ? fila.errores_por_grupo.admin
          : ['Datos administrativos observados']
        return msgs.map(m => ({
          fila: fila.numero_fila_excel,
          campo: m.toLowerCase().includes('fecha') ? 'fechas' : 'admin',
          mensaje: m, sugerencia: null, valor_actual: '(observado)', fila_ref: fila,
        }))
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
  if (p.campo === 'rut') {
    const valActual = String(p.fila_ref.rut || '').trim()
    const dvOriginal = valActual.includes('-') ? valActual.split('-')[1] : ''
    p.fila_ref.rut = dvOriginal ? `${p.sugerencia}-${dvOriginal}` : p.sugerencia
    p.fila_ref.rut_valido = true
    p.fila_ref.sugerencia_correccion_rut = null
    if (p.fila_ref.errores_por_grupo?.identidad) {
      p.fila_ref.errores_por_grupo.identidad = []
    }
  } else {
    p.fila_ref[p.campo] = p.sugerencia
    p.fila_ref[p.campo === 'sigla' ? 'sigla_valida' : `${p.campo}_valido`] = true
    if (p.campo === 'sigla') {
      p.fila_ref.sugerencia_correccion_sigla = null
      if (p.fila_ref.errores_por_grupo?.vehiculo) {
        p.fila_ref.errores_por_grupo.vehiculo = []
      }
    }
  }
  p.fila_ref.errores = (p.fila_ref.errores || []).filter(e =>
    !e.toLowerCase().includes(p.campo === 'rut' ? 'rut' : 'sigla')
  )
  recalcularGrupos()
  correccionesAplicadas.value = true

  // Micro-feedback visual
  filasCorregidasRecientes.value.add(p.fila_ref.numero_fila_excel)
  setTimeout(() => {
    filasCorregidasRecientes.value.delete(p.fila_ref.numero_fila_excel)
  }, 1400)
}

function aplicarTodasLasSugerencias() {
  filasCorregidasRecientes.value.clear()
  filas.value.forEach(f => {
    let modificada = false
    if (!f.rut_valido && f.sugerencia_correccion_rut) {
      const valActual = String(f.rut || '').trim()
      const dvOriginal = valActual.includes('-') ? valActual.split('-')[1] : ''
      f.rut = dvOriginal ? `${f.sugerencia_correccion_rut}-${dvOriginal}` : f.sugerencia_correccion_rut
      f.rut_valido = true
      f.sugerencia_correccion_rut = null
      if (f.errores_por_grupo?.identidad) {
        f.errores_por_grupo.identidad = []
      }
      f.errores = (f.errores || []).filter(e => !e.toLowerCase().includes('rut'))
      modificada = true
    }
    if (!f.sigla_valida && f.sugerencia_correccion_sigla) {
      f.sigla = f.sugerencia_correccion_sigla
      f.sigla_valida = true
      f.sugerencia_correccion_sigla = null
      if (f.errores_por_grupo?.vehiculo) {
        f.errores_por_grupo.vehiculo = []
      }
      f.errores = (f.errores || []).filter(e => !e.toLowerCase().includes('sigla'))
      modificada = true
    }
    // Auto-intercambiar fechas si inicio > término y pertenecen al mismo mes
    const dIni = parsearFechaDMY(f.fechainicio)
    const dTer = parsearFechaDMY(f.fechatermino)
    const mismoMes = Boolean(dIni && dTer && dIni.getMonth() === dTer.getMonth() && dIni.getFullYear() === dTer.getFullYear())
    if (dIni && dTer && mismoMes && dIni > dTer) {
      const tmp = f.fechainicio
      f.fechainicio = f.fechatermino
      f.fechatermino = tmp
      f.fechas_validas = true
      if (f.errores_por_grupo?.admin) {
        f.errores_por_grupo.admin = f.errores_por_grupo.admin.filter(m => !m.toLowerCase().includes('fecha'))
      }
      f.errores = (f.errores || []).filter(e => !e.toLowerCase().includes('fecha'))
      revalidarAdminFila(f)
      modificada = true
    }
    // Deducir días de salida si estaba vacío y las fechas son válidas
    const dIniOk = parsearFechaDMY(f.fechainicio)
    const dTerOk = parsearFechaDMY(f.fechatermino)
    const mismoMesOk = Boolean(dIniOk && dTerOk && dIniOk.getMonth() === dTerOk.getMonth() && dIniOk.getFullYear() === dTerOk.getFullYear())
    if (!String(f.dias_salida || '').trim() && dIniOk && dTerOk && mismoMesOk && dIniOk <= dTerOk) {
      const diasCalculados = calcularDiasSemanaEntreFechas(dIniOk, dTerOk)
      if (diasCalculados.length > 0) {
        f.dias_salida = diasCalculados.join(', ')
        if (f.errores_por_grupo?.admin) {
          f.errores_por_grupo.admin = f.errores_por_grupo.admin.filter(m => !m.toLowerCase().includes('días de salida'))
        }
        f.errores = (f.errores || []).filter(e => !e.toLowerCase().includes('días de salida'))
        revalidarAdminFila(f)
        if (Math.abs(diasCalculados.length - sumarViaticos(f)) < 0.01) {
          f.viaticos_validos = true
          if (f.errores_por_grupo?.viaticos) f.errores_por_grupo.viaticos = []
        }
        modificada = true
      }
    }
    if (modificada) {
      filasCorregidasRecientes.value.add(f.numero_fila_excel)
    }
  })
  recalcularGrupos()
  correccionesAplicadas.value = true

  // Micro-feedback de destello en celdas reparadas
  setTimeout(() => {
    filasCorregidasRecientes.value.clear()
  }, 1400)
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
    fechainicio: f.fechainicio, fechatermino: f.fechatermino,
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

// ─── Modal de Corrección de Días y Viáticos / Fechas ──────────
const DIAS_SEMANA_OPCIONES = [
  { id: 'LUNES',     label: 'Lunes',     corto: 'LU' },
  { id: 'MARTES',    label: 'Martes',    corto: 'MA' },
  { id: 'MIERCOLES', label: 'Miércoles', corto: 'MI' },
  { id: 'JUEVES',    label: 'Jueves',    corto: 'JU' },
  { id: 'VIERNES',   label: 'Viernes',   corto: 'VI' },
  { id: 'SABADO',    label: 'Sábado',    corto: 'SA' },
  { id: 'DOMINGO',   label: 'Domingo',   corto: 'DO' },
]

const PORCENTAJES_VIATICOS = [
  { campo: 'dias_100', label: 'Días al 100%' },
  { campo: 'dias_70',  label: 'Días al 70%'  },
  { campo: 'dias_60',  label: 'Días al 60%'  },
  { campo: 'dias_50',  label: 'Días al 50%'  },
  { campo: 'dias_40',  label: 'Días al 40%'  },
  { campo: 'dias_35',  label: 'Días al 35%'  },
]

const filaEditandoViaticos = ref(null)
const editDiasSeleccionados = ref([])
const editPorcentajes = ref({
  dias_100: 0, dias_70: 0, dias_60: 0, dias_50: 0, dias_40: 0, dias_35: 0,
})

const filaEditandoFechas = ref(null)
const editFechaInicio = ref('')
const editFechaTermino = ref('')
const errorModalFechas = ref('')

function normalizarNombreDia(d) {
  return String(d || '')
    .trim()
    .toUpperCase()
    .replace('Á', 'A')
    .replace('É', 'E')
    .replace('Í', 'I')
    .replace('Ó', 'O')
    .replace('Ú', 'U')
}

function parsearFechaDMY(str) {
  if (!str) return null
  const partes = String(str).trim().split(/[/-]/)
  if (partes.length !== 3) return null
  const [d, m, y] = partes.map(Number)
  if (!d || !m || !y || y < 1900) return null
  const dt = new Date(y, m - 1, d)
  if (dt.getFullYear() !== y || dt.getMonth() !== m - 1 || dt.getDate() !== d) return null
  return dt
}

function calcularDiasSemanaEntreFechas(dIni, dTer) {
  const mapaJs = ['DOMINGO', 'LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO']
  const diasSet = new Set()
  const curr = new Date(dIni)
  let guard = 0
  while (curr <= dTer && guard < 31) {
    diasSet.add(mapaJs[curr.getDay()])
    curr.setDate(curr.getDate() + 1)
    guard++
  }
  const orden = DIAS_SEMANA_OPCIONES.map(d => d.id)
  return [...diasSet].sort((a, b) => orden.indexOf(a) - orden.indexOf(b))
}

function abrirModalViaticos(fila) {
  filaEditandoViaticos.value = fila
  const actuales = String(fila.dias_salida || '')
    .split(',')
    .map(normalizarNombreDia)
    .filter(d => DIAS_SEMANA_OPCIONES.some(op => op.id === d))
  editDiasSeleccionados.value = [...new Set(actuales)]

  PORCENTAJES_VIATICOS.forEach(({ campo }) => {
    const val = parseFloat(String(fila[campo] ?? '').replace(',', '.'))
    editPorcentajes.value[campo] = !isNaN(val) && val > 0 ? val : 0
  })
}

function cerrarModalViaticos() {
  filaEditandoViaticos.value = null
}

function fechasMismoMes(dIni, dTer) {
  return Boolean(dIni && dTer && dIni.getMonth() === dTer.getMonth() && dIni.getFullYear() === dTer.getFullYear())
}

function fechasDeFilaValidas(fila) {
  if (!fila || fila.fechas_validas === false) return false
  const dIni = parsearFechaDMY(fila.fechainicio)
  const dTer = parsearFechaDMY(fila.fechatermino)
  return Boolean(dIni && dTer && fechasMismoMes(dIni, dTer) && dIni <= dTer)
}

const fechasViaticosValidas = computed(() => {
  return fechasDeFilaValidas(filaEditandoViaticos.value)
})

function irACorregirFechasDesdeViaticos() {
  const fila = filaEditandoViaticos.value
  cerrarModalViaticos()
  if (fila) abrirModalFechas(fila)
}

function obtenerDiasEsperadosDeFila(fila) {
  if (!fila) return []
  const dIni = parsearFechaDMY(fila.fechainicio)
  const dTer = parsearFechaDMY(fila.fechatermino)
  if (!dIni || !dTer || !fechasMismoMes(dIni, dTer) || dIni > dTer) return []
  return calcularDiasSemanaEntreFechas(dIni, dTer)
}

const diasEsperadosPorFecha = computed(() => {
  return obtenerDiasEsperadosDeFila(filaEditandoViaticos.value)
})

const diasEsperadosTexto = computed(() => {
  return diasEsperadosPorFecha.value
    .map(id => DIAS_SEMANA_OPCIONES.find(d => d.id === id)?.label || id)
    .join(', ')
})

const diasCoincidenConFecha = computed(() => {
  if (!fechasViaticosValidas.value) return false
  const esperados = diasEsperadosPorFecha.value
  const seleccionados = editDiasSeleccionados.value
  if (esperados.length === 0) return false
  if (seleccionados.length !== esperados.length) return false
  return esperados.every(d => seleccionados.includes(d))
})

function toggleDiaSeleccionado(diaId) {
  if (!fechasViaticosValidas.value) return
  const esperados = diasEsperadosPorFecha.value
  if (esperados.length > 0 && !esperados.includes(diaId)) return
  const idx = editDiasSeleccionados.value.indexOf(diaId)
  if (idx >= 0) {
    editDiasSeleccionados.value.splice(idx, 1)
  } else {
    editDiasSeleccionados.value.push(diaId)
    const orden = DIAS_SEMANA_OPCIONES.map(d => d.id)
    editDiasSeleccionados.value.sort((a, b) => orden.indexOf(a) - orden.indexOf(b))
  }
}

function deducirDiasDesdeFechas() {
  if (!filaEditandoViaticos.value || !fechasViaticosValidas.value) return
  const esperados = diasEsperadosPorFecha.value
  if (esperados.length > 0) {
    editDiasSeleccionados.value = [...esperados]
  }
}

function igualarPorcentajes(modo) {
  if (!fechasViaticosValidas.value) return
  const total = editDiasSeleccionados.value.length
  if (total <= 0) return
  PORCENTAJES_VIATICOS.forEach(({ campo }) => { editPorcentajes.value[campo] = 0 })
  if (modo === '40') {
    editPorcentajes.value.dias_40 = total
  } else if (modo === '100_40') {
    editPorcentajes.value.dias_100 = Math.max(0, total - 1)
    editPorcentajes.value.dias_40 = 1
  }
}

const sumaEditPorcentajes = computed(() => {
  return PORCENTAJES_VIATICOS.reduce((acc, { campo }) => {
    const v = parseFloat(editPorcentajes.value[campo])
    return acc + (isNaN(v) || v < 0 ? 0 : v)
  }, 0)
})

const viaticosEditCoinciden = computed(() => {
  if (!fechasViaticosValidas.value) return false
  const nDias = editDiasSeleccionados.value.length
  return diasCoincidenConFecha.value && nDias > 0 && Math.abs(nDias - sumaEditPorcentajes.value) < 0.01
})

function revalidarAdminFila(fila) {
  const dIni = parsearFechaDMY(fila.fechainicio)
  const dTer = parsearFechaDMY(fila.fechatermino)
  const fechasOk = Boolean(dIni && dTer && fechasMismoMes(dIni, dTer) && dIni <= dTer)
  fila.fechas_validas = fechasOk
  const obligatoriosOk = Boolean(
    String(fila.fechainicio || '').trim() &&
    String(fila.fechatermino || '').trim() &&
    String(fila.dias_salida || '').trim() &&
    String(fila.sigla || '').trim()
  )
  fila.admin_valido = fechasOk && obligatoriosOk
  if (fila.admin_valido && fila.errores_por_grupo) {
    fila.errores_por_grupo.admin = []
  }
}

function guardarCorreccionViaticos() {
  if (!filaEditandoViaticos.value || !viaticosEditCoinciden.value) return
  const fila = filaEditandoViaticos.value
  fila.dias_salida = editDiasSeleccionados.value.join(', ')
  PORCENTAJES_VIATICOS.forEach(({ campo }) => {
    const val = parseFloat(editPorcentajes.value[campo])
    fila[campo] = !isNaN(val) && val > 0 ? val : 0
  })
  fila.viaticos_validos = true
  if (fila.errores_por_grupo) {
    fila.errores_por_grupo.viaticos = []
    if (fila.errores_por_grupo.admin) {
      fila.errores_por_grupo.admin = fila.errores_por_grupo.admin.filter(
        m => !m.toLowerCase().includes('días de salida')
      )
    }
  }
  fila.errores = (fila.errores || []).filter(
    e => !e.toLowerCase().includes('porcentajes') && !e.toLowerCase().includes('días de salida')
  )
  revalidarAdminFila(fila)
  recalcularGrupos()
  correccionesAplicadas.value = true

  filasCorregidasRecientes.value.add(fila.numero_fila_excel)
  setTimeout(() => {
    filasCorregidasRecientes.value.delete(fila.numero_fila_excel)
  }, 1400)
  cerrarModalViaticos()
}

function abrirModalFechas(fila) {
  filaEditandoFechas.value = fila
  editFechaInicio.value = String(fila.fechainicio || '').trim()
  editFechaTermino.value = String(fila.fechatermino || '').trim()
  errorModalFechas.value = ''
}

function cerrarModalFechas() {
  filaEditandoFechas.value = null
  errorModalFechas.value = ''
}

const dIniModal = computed(() => parsearFechaDMY(editFechaInicio.value))
const dTerModal = computed(() => parsearFechaDMY(editFechaTermino.value))
const mesesModalCoinciden = computed(() => fechasMismoMes(dIniModal.value, dTerModal.value))
const fechasModalValidas = computed(() => Boolean(dIniModal.value && dTerModal.value && mesesModalCoinciden.value && dIniModal.value <= dTerModal.value))

function intercambiarFechasModal() {
  if (!mesesModalCoinciden.value) return
  const tmp = editFechaInicio.value
  editFechaInicio.value = editFechaTermino.value
  editFechaTermino.value = tmp
  errorModalFechas.value = ''
}

function revalidarViaticosFila(fila) {
  const esperados = obtenerDiasEsperadosDeFila(fila)
  const actuales = [...new Set(
    String(fila.dias_salida || '')
      .split(',')
      .map(normalizarNombreDia)
      .filter(d => DIAS_SEMANA_OPCIONES.some(op => op.id === d))
  )]
  const sumaPorc = PORCENTAJES_VIATICOS.reduce((acc, { campo }) => {
    const v = parseFloat(String(fila[campo] ?? '').replace(',', '.'))
    return acc + (isNaN(v) || v < 0 ? 0 : v)
  }, 0)

  const coincideFecha = esperados.length === 0
    ? actuales.length > 0
    : (actuales.length === esperados.length && esperados.every(d => actuales.includes(d)))
  const coincidePorc = actuales.length > 0 && Math.abs(actuales.length - sumaPorc) < 0.01

  fila.viaticos_validos = coincideFecha && coincidePorc
  if (!fila.errores_por_grupo) fila.errores_por_grupo = { rut: [], viaticos: [], admin: [] }

  if (fila.viaticos_validos) {
    fila.errores_por_grupo.viaticos = []
    fila.errores = (fila.errores || []).filter(
      e => !e.toLowerCase().includes('porcentajes') && !e.toLowerCase().includes('días de salida')
    )
  } else {
    const nuevosErrores = []
    if (!coincideFecha && esperados.length > 0) {
      const espTxt = esperados.map(id => DIAS_SEMANA_OPCIONES.find(d => d.id === id)?.label || id).join(', ')
      nuevosErrores.push(`Los días de salida no coinciden con el rango de fechas (según fechas corresponde: ${espTxt}).`)
    }
    if (!coincidePorc) {
      nuevosErrores.push(`Se indicaron ${actuales.length} día(s) de salida pero los porcentajes suman ${sumaPorc}.`)
    }
    fila.errores_por_grupo.viaticos = nuevosErrores
  }
}

function guardarCorreccionFechas() {
  if (!filaEditandoFechas.value) return
  const dIni = parsearFechaDMY(editFechaInicio.value)
  const dTer = parsearFechaDMY(editFechaTermino.value)
  if (!dIni || !dTer) {
    errorModalFechas.value = 'Ambas fechas deben tener formato válido DD/MM/AAAA.'
    return
  }
  if (!fechasMismoMes(dIni, dTer)) {
    errorModalFechas.value = 'Las fechas de inicio y término deben pertenecer al mismo mes.'
    return
  }
  if (dIni > dTer) {
    errorModalFechas.value = 'La fecha de inicio no puede ser posterior a la fecha de término.'
    return
  }
  const fila = filaEditandoFechas.value
  fila.fechainicio = editFechaInicio.value.trim()
  fila.fechatermino = editFechaTermino.value.trim()
  fila.fechas_validas = true
  if (fila.errores_por_grupo?.admin) {
    fila.errores_por_grupo.admin = fila.errores_por_grupo.admin.filter(
      m => !m.toLowerCase().includes('fecha')
    )
  }
  fila.errores = (fila.errores || []).filter(e => !e.toLowerCase().includes('fecha'))
  revalidarAdminFila(fila)
  revalidarViaticosFila(fila)
  recalcularGrupos()
  correccionesAplicadas.value = true

  filasCorregidasRecientes.value.add(fila.numero_fila_excel)
  setTimeout(() => {
    filasCorregidasRecientes.value.delete(fila.numero_fila_excel)
  }, 1400)
  cerrarModalFechas()
}

// ─── Modal de Credenciales ────────────────────────────────────
const mostrarModalCredenciales = ref(false)
const credencialUsuarioSsd     = ref('')
const credencialClaveSsd       = ref('')
const mostrarClaveSsd          = ref(false)
const credencialUsuario        = ref('')
const credencialClave          = ref('')
const mostrarClave             = ref(false)
const errorCredenciales        = ref('')

function empezarAutomatizacion() {
  errorCredenciales.value = ''
  mostrarClaveSsd.value = false
  mostrarClave.value = false
  mostrarModalCredenciales.value = true
}

function cerrarModalCredenciales() {
  mostrarModalCredenciales.value = false
  errorCredenciales.value = ''
  credencialClaveSsd.value = ''
  credencialClave.value = ''
}

function confirmarCredencialesEIniciar() {
  if (
    !credencialUsuarioSsd.value.trim() ||
    !credencialClaveSsd.value ||
    !credencialUsuario.value.trim() ||
    !credencialClave.value
  ) {
    errorCredenciales.value = 'Debes ingresar el usuario y contraseña tanto para SSD como para Personal y Firmador.'
    return
  }
  mostrarModalCredenciales.value = false
  etapaActual.value = 2
  iniciarEjecucion()
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

      <!-- Botón de terminal (extremo derecho a la altura del stepper principal) -->
      <button
        class="btn-terminal-icono"
        :class="{
          'btn-terminal-activo': mostrarTerminal,
          'btn-terminal--error': tieneErroresEnLogs,
          'btn-terminal--ejecutando': automatizando
        }"
        @click="mostrarTerminal = !mostrarTerminal"
        :title="mostrarTerminal ? 'Ocultar consola de logs' : 'Abrir consola de procesos RPA'"
      >
        <i class="bi bi-terminal-fill"></i>
        <!-- Indicador de alerta o pulso -->
        <span v-if="tieneErroresEnLogs" class="terminal-dot-alerta" title="Errores detectados en la ejecución"></span>
        <span v-else-if="automatizando" class="terminal-dot-pulso" title="Robot en ejecución"></span>
      </button>
    </div>

    <!-- Panel de terminal (desplegable flotante) -->
    <div v-show="mostrarTerminal" class="terminal-drawer">
      <div class="terminal-drawer-header">
        <div class="d-flex align-items-center gap-2">
          <i class="bi bi-terminal-fill text-info fs-6"></i>
          <span class="fw-bold">Consola de Procesos RPA</span>
          <span
            class="terminal-badge"
            :class="{
              'badge-activa': automatizando,
              'badge-fin': completadoExitoso && !tieneErroresEnLogs,
              'badge-error': tieneErroresEnLogs
            }"
          >
            {{ automatizando ? 'En ejecución' : (completadoExitoso ? (tieneErroresEnLogs ? 'Finalizado con obs.' : 'Finalizado OK') : 'Inactivo') }}
          </span>
        </div>
        <div class="d-flex align-items-center gap-1">
          <button class="btn-terminal-accion" @click="copiarLogs" title="Copiar logs al portapapeles">
            <i class="bi bi-clipboard"></i>
          </button>
          <button class="btn-terminal-accion" @click="limpiarLogs" title="Limpiar pantalla">
            <i class="bi bi-trash"></i>
          </button>
          <button class="btn-cerrar-terminal" @click="mostrarTerminal = false" title="Cerrar consola">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>
      </div>

      <div class="terminal-drawer-cuerpo" ref="consolaCuerpoRef">
        <!-- Sin logs aún -->
        <div v-if="logsAutomatizacion.length === 0" class="consola-vacia">
          <i class="bi bi-terminal mb-2 text-muted" style="font-size:26px"></i>
          <span>Aún no hay eventos registrados. Presiona <strong>Iniciar Automatización</strong> para ver la telemetría en tiempo real.</span>
        </div>

        <!-- Render de logs interactivo y con checkpoints -->
        <template v-for="log in logsAutomatizacion" :key="log.id">
          <!-- 1. Tarjeta de error clara para el usuario -->
          <div
            v-if="log.tipo === 'checkpoint_error'"
            class="consola-card-error"
            :id="'log-checkpoint-' + (log.cometidoNum - 1)"
          >
            <div class="card-error-header">
              <i class="bi bi-exclamation-octagon-fill text-danger fs-6"></i>
              <span v-if="log.cometidoNum > 0">Fallo en Cometido #{{ log.cometidoNum }} — {{ log.portalNombre }}</span>
              <span v-else>No se pudo iniciar la automatización</span>
            </div>
            <div class="card-error-detalles">
              <div v-if="log.rut && log.rut !== 'N/A'" class="error-dato-item">
                <span class="error-dato-clave">Funcionario:</span>
                <span class="error-dato-valor">{{ log.rut }}</span>
              </div>
              <div class="error-dato-item">
                <span class="error-dato-clave">Paso:</span>
                <span class="error-dato-accion">{{ log.accion }}</span>
              </div>
              <div class="error-dato-item">
                <span class="error-dato-clave">Motivo:</span>
                <span class="error-dato-valor">{{ log.errorMensaje }}</span>
              </div>
            </div>

            <div v-if="log.cometidoNum > 0" class="card-error-footer">
              <i class="bi bi-arrow-right-circle text-warning me-1"></i>
              Se omitió este cometido y el proceso continuó con el siguiente.
            </div>
          </div>

          <!-- 2. Checkpoint de cometido exitoso -->
          <div v-else-if="log.tipo === 'checkpoint_exito'" class="consola-card-exito">
            <span class="consola-hora">[{{ log.hora }}]</span>
            <i class="bi bi-check-circle-fill text-success me-1"></i>
            <span>{{ log.texto }}</span>
          </div>

          <!-- 3. Banner de inicio de cometido -->
          <div v-else-if="log.tipo === 'inicio_cometido'" class="consola-banner-inicio">
            <span class="consola-hora">[{{ log.hora }}]</span>
            <i class="bi bi-play-circle-fill text-info me-1"></i>
            <span>{{ log.texto }}</span>
          </div>

          <!-- 4. Resumen final de la corrida -->
          <div v-else-if="log.tipo === 'resumen'" class="consola-card-resumen">
            <div class="resumen-titulo">
              <i class="bi bi-flag-fill text-info"></i>
              <span>Resumen Final de Automatización</span>
            </div>
            <div class="resumen-estadisticas">
              <div class="resumen-kpi">
                <span class="kpi-num">{{ log.total }}</span>
                <span class="kpi-etiqueta">Total</span>
              </div>
              <div class="resumen-kpi text-success">
                <span class="kpi-num text-success">{{ log.completados }}</span>
                <span class="kpi-etiqueta">Completados</span>
              </div>
              <div class="resumen-kpi" :class="log.fallidos > 0 ? 'text-danger' : 'text-muted'">
                <span class="kpi-num" :class="log.fallidos > 0 ? 'text-danger' : 'text-muted'">{{ log.fallidos }}</span>
                <span class="kpi-etiqueta">Con Errores</span>
              </div>
            </div>
          </div>

          <!-- 5. Línea de log estándar -->
          <div v-else class="consola-linea">
            <span class="consola-hora">[{{ log.hora }}]</span>
            <span class="consola-prefijo">›</span>
            <span class="consola-texto">{{ log.texto }}</span>
          </div>
        </template>

        <!-- Indicador de ejecución en curso -->
        <div v-if="automatizando" class="consola-linea consola-linea--activo mt-1">
          <span class="cursor-blink">▌</span>
          <span>Procesando en segundo plano...</span>
        </div>
      </div>
    </div>


    <!-- ══════════════════════════════════════════════════════ -->
    <!-- ETAPA 1 y 2: comparten la misma tabla                  -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div v-if="etapaActual === 1 || etapaActual === 2" class="etapa-layout" :class="{ 'etapa-layout--ejecucion': etapaActual === 2 }">

      <!-- ── Panel izquierdo: Checklist simplificado + Botones ── -->
      <aside v-if="etapaActual === 1" class="panel-checklist">
        <h2 class="checklist-titulo">Validación</h2>

        <!-- Estado: cargando -->
        <div v-if="procesando" class="checklist-cargando">
          <div class="spinner-border text-primary mb-2" style="width:2rem;height:2rem" role="status"></div>
          <p class="text-muted small mb-0">{{ procesandoMensaje }}</p>
        </div>

        <!-- 4 Tarjetas de validación simplificadas (solo estado verde/rojo) -->
        <ul v-else class="grupos-lista">
          <li
            v-for="grupo in grupos"
            :key="grupo.id"
            class="grupo-item"
            :class="`grupo--${grupo.estado}`"
          >
            <div class="grupo-cabecera">
              <div class="grupo-icono">
                <i v-if="grupo.estado === 'ok'" class="bi bi-check-circle-fill"></i>
                <i v-else-if="grupo.estado === 'error'" class="bi bi-x-circle-fill"></i>
                <i v-else-if="grupo.estado === 'revisando'" class="bi bi-arrow-repeat spin"></i>
                <i v-else class="bi bi-circle"></i>
              </div>
              <div class="grupo-texto">
                <span class="grupo-nombre">{{ grupo.titulo }}</span>
                <span class="grupo-desc">{{ grupo.descripcion }}</span>
              </div>
              <div class="grupo-status-pill">
                <span v-if="grupo.estado === 'ok'" class="tag-status tag-ok">Válido</span>
                <span v-else-if="grupo.estado === 'error'" class="tag-status tag-error">Observado</span>
                <span v-else-if="grupo.estado === 'revisando'" class="tag-status tag-revisando">Revisando</span>
                <span v-else class="tag-status tag-pendiente">Pendiente</span>
              </div>
            </div>
          </li>
        </ul>

        <!-- Acciones del sidebar (se mantienen siempre) -->
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
            <h2 class="tabla-titulo">
              {{ etapaActual === 2 ? 'Ejecución de Automatización' : 'Validación y Resumen' }}
            </h2>
            <p class="tabla-subtitulo">
              <i class="bi bi-file-earmark-excel-fill text-success me-1"></i>
              {{ fileName }}
              <span class="separador-cabecera">·</span>
              <template v-if="etapaActual === 2 && totalCometidos > 0">
                <template v-if="completadoExitoso">
                  {{ totalCometidos }} cometido{{ totalCometidos > 1 ? 's' : '' }} procesado{{ totalCometidos > 1 ? 's' : '' }}
                </template>
                <template v-else>
                  <span class="cronometro-pill cronometro-pill--activo">
                    <i class="bi bi-stopwatch me-1"></i>
                    {{ formatearTiempoReloj(segundosTranscurridos) }}
                  </span>
                  <span class="separador-cabecera">·</span>
                  Procesando cometido {{ Math.max(1, cometidoActualIndice + 1) }} de {{ totalCometidos }}
                  <span v-if="automatizando" class="spinner-border spinner-border-sm ms-2" style="width:14px;height:14px"></span>
                </template>
              </template>
              <template v-else>
                {{ filas.length }} cometido(s) encontrado(s)
              </template>
            </p>
          </div>

          <!-- Sub-Stepper de 3 pasos (solo visible en Etapa 2) -->
          <div v-if="etapaActual === 2" class="sub-stepper-compact">
            <template v-for="(paso, idx) in subPasos" :key="paso.id">
              <div
                class="sub-paso-mini"
                :class="{
                  'sub-paso--activo':     pasoSubStepper === paso.id,
                  'sub-paso--completado': pasoSubStepper > paso.id,
                  'sub-paso--pendiente':  pasoSubStepper < paso.id || pasoSubStepper === 0,
                }"
              >
                <div class="sub-paso-dot">
                  <i v-if="pasoSubStepper > paso.id" class="bi bi-check-lg"></i>
                  <i v-else :class="`bi ${paso.icono}`"></i>
                </div>
                <span class="sub-paso-txt">{{ paso.label }}</span>
              </div>
              <div
                v-if="idx < subPasos.length - 1"
                class="sub-paso-conector"
                :class="{ 'conector--ok': pasoSubStepper > paso.id }"
              ></div>
            </template>
          </div>

          <!-- Indicadores de resumen cuando termina de cargar (solo Etapa 1) -->
          <div v-if="etapaActual === 1 && !procesando && filas.length > 0" class="tabla-kpis">
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
                <th class="col-n">N° de Cometido</th>
                <th class="col-conductor">RUT</th>
                <th class="col-fechas">Fechas</th>
                <th class="col-vehiculo">Vehículo</th>
                <th class="col-dias">Días</th>
                <th class="col-viaticos">Cantidad de Días</th>
                <th class="col-estado">Estado</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(fila, idx) in filas"
                :key="fila.numero_fila_excel"
                :ref="el => guardarRefFila(el, idx)"
                :class="[
                  etapaActual === 1 && erroresDeFila(fila).length > 0 ? 'fila-con-error' : '',
                  colorFilaEjecucion(idx),
                ]"
              >
                <!-- # Cometido -->
                <td class="col-n">
                  <span class="badge-fila">N°{{ fila.numero_cometido || (idx + 1) }}</span>
                </td>

                <!-- RUT -->
                <td class="col-conductor">
                  <div class="conductor-bloque" :class="{ 'celda-corregida-pulso': filasCorregidasRecientes.has(fila.numero_fila_excel) }">
                    <span class="conductor-rut" :class="{ 'celda-error': filaTieneError(fila, 'rut') }">
                      {{ formatearRut(fila.rut) }}
                      <i v-if="filaTieneError(fila, 'rut')" class="bi bi-exclamation-triangle-fill ms-1 text-danger"></i>
                    </span>
                    <!-- Sugerencia inline de RUT (corrección desde la tabla) -->
                    <div v-if="!fila.rut_valido && fila.sugerencia_correccion_rut" class="sugerencia-inline">
                      <i class="bi bi-lightbulb-fill text-warning"></i>
                      <span>¿{{ sugerenciaRutConDv(fila) }}?</span>
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
                    :class="{
                      'celda-error': filaTieneError(fila,'fechas') || filaTieneError(fila,'fechainicio') || filaTieneError(fila,'fechatermino'),
                      'celda-corregida-pulso': filasCorregidasRecientes.has(fila.numero_fila_excel)
                    }">
                    <div class="d-flex align-items-center gap-1 flex-wrap">
                      <span class="fecha-chip">{{ fila.fechainicio || '—' }}</span>
                      <i class="bi bi-arrow-right fecha-sep"></i>
                      <span class="fecha-chip">{{ fila.fechatermino || '—' }}</span>
                      <i v-if="filaTieneError(fila,'fechas') || filaTieneError(fila,'fechainicio') || filaTieneError(fila,'fechatermino')" class="bi bi-exclamation-triangle-fill text-danger ms-1"></i>
                    </div>
                    <div v-if="etapaActual === 1 && (filaTieneError(fila,'fechas') || filaTieneError(fila,'fechainicio') || filaTieneError(fila,'fechatermino'))" class="sugerencia-inline mt-1">
                      <i class="bi bi-lightbulb-fill text-warning"></i>
                      <span>Fechas observadas</span>
                      <button class="btn-corregir-inline" @click="abrirModalFechas(fila)">
                        Corregir
                      </button>
                    </div>
                  </div>
                </td>

                <!-- Vehículo / Sigla -->
                <td class="col-vehiculo">
                  <div class="vehiculo-bloque" :class="{ 'celda-corregida-pulso': filasCorregidasRecientes.has(fila.numero_fila_excel) }">
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

                <!-- Días de salida (chips abreviados) -->
                <td class="col-dias">
                  <div class="dias-chips" :class="{ 'celda-corregida-pulso': filasCorregidasRecientes.has(fila.numero_fila_excel) }">
                    <span
                      v-for="chip in chipsDias(fila.dias_salida)"
                      :key="chip"
                      class="dia-chip"
                    >{{ chip }}</span>
                    <span v-if="chipsDias(fila.dias_salida).length === 0" class="text-muted">—</span>
                  </div>
                </td>

                <!-- Viáticos -->
                <td class="col-viaticos">
                  <div class="viaticos-bloque"
                    :class="{
                      'celda-error': filaTieneError(fila,'viaticos') || filaTieneError(fila,'dias_salida'),
                      'celda-corregida-pulso': filasCorregidasRecientes.has(fila.numero_fila_excel)
                    }">
                    <span class="viaticos-dias">
                      {{ contarDiasSalida(fila.dias_salida) }} día(s)
                      <i v-if="filaTieneError(fila,'viaticos') || filaTieneError(fila,'dias_salida')" class="bi bi-exclamation-triangle-fill text-danger ms-1"></i>
                    </span>
                    <span class="viaticos-detalle">{{ resumenViaticos(fila) }}</span>
                    <!-- Corrección de Días y Viáticos -->
                    <div v-if="etapaActual === 1 && (filaTieneError(fila,'viaticos') || filaTieneError(fila,'dias_salida'))" class="sugerencia-inline mt-1">
                      <i class="bi bi-lightbulb-fill text-warning"></i>
                      <span>Suma {{ sumarViaticos(fila) }} vs {{ contarDiasSalida(fila.dias_salida) }}d</span>
                      <button class="btn-corregir-inline" @click="abrirModalViaticos(fila)">
                        Corregir
                      </button>
                    </div>
                  </div>
                </td>

                <!-- Estado de la fila -->
                <td class="col-estado">
                  <!-- En Etapa 1: muestra errores de validación -->
                  <template v-if="etapaActual === 1">
                    <span v-if="erroresDeFila(fila).length === 0" class="badge-estado badge-estado--ok">
                      <i class="bi bi-check-circle-fill"></i>Válido
                    </span>
                    <span v-else class="badge-estado badge-estado--error">
                      <i class="bi bi-exclamation-circle-fill"></i>
                      {{ erroresDeFila(fila).length }} obs.
                    </span>
                  </template>
                  <!-- En Etapa 2: muestra estado de ejecución con micro-tiempo y acceso a error -->
                  <template v-else-if="etapaActual === 2">
                    <span v-if="colorFilaEjecucion(idx) === 'fila-completado'" class="badge-estado badge-estado--ok">
                      <i class="bi bi-check-circle-fill"></i>Listo
                      <span v-if="tiempoCometidoTexto(idx)" class="badge-tiempo-txt">· {{ tiempoCometidoTexto(idx) }}</span>
                    </span>
                    <span v-else-if="colorFilaEjecucion(idx) === 'fila-ejecutando'" class="badge-estado badge-estado--ejecutando">
                      <span class="spinner-border spinner-border-sm me-1" style="width:12px;height:12px"></span>
                      En curso
                      <span v-if="tiempoCometidoTexto(idx)" class="badge-tiempo-txt">({{ tiempoCometidoTexto(idx) }})</span>
                    </span>
                    <div v-else-if="colorFilaEjecucion(idx) === 'fila-fallido'" class="estado-fallido-bloque">
                      <span class="badge-estado badge-estado--error">
                        <i class="bi bi-x-circle-fill"></i>Error
                        <span v-if="tiempoCometidoTexto(idx)" class="badge-tiempo-txt">· {{ tiempoCometidoTexto(idx) }}</span>
                      </span>
                      <button
                        class="btn-ver-error-fila"
                        @click.stop="inspeccionarErrorFila(idx)"
                        title="Ver detalle del error"
                      >
                        <i class="bi bi-eye-fill me-1"></i>Ver detalle
                      </button>
                    </div>
                    <span v-else class="badge-estado badge-estado--pendiente">
                      <i class="bi bi-clock"></i>Pendiente
                    </span>
                  </template>
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
        <div v-if="etapaActual === 1 && !procesando && filas.length > 0" class="cta-zona">
          <p v-if="totalErrores > 0" class="cta-aviso">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            Corrige los&nbsp;<strong>{{ totalErrores }}</strong>&nbsp;problema(s) detectado(s) para poder continuar
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

        <!-- Zona de acciones de Etapa 2: Barra de progreso lineal fina + Cancelar a la derecha -->
        <div v-if="etapaActual === 2" class="cta-zona cta-zona--ejecucion">
          <!-- Mensaje de estado al completar o fallar lote (ajustado al texto) -->
          <div v-if="completadoExitoso" class="cta-alerta-wrapper mb-2">
            <span :class="tieneErroresEnLogs ? 'cta-aviso' : 'cta-exito'">
              <i :class="tieneErroresEnLogs ? 'bi bi-exclamation-triangle-fill me-2' : 'bi bi-check-circle-fill me-2'"></i>{{ mensajeEstado }}
            </span>
          </div>
          <div v-if="huboError" class="cta-alerta-wrapper mb-2">
            <span class="cta-aviso">
              <i class="bi bi-exclamation-triangle-fill me-2"></i>{{ mensajeEstado }}
            </span>
          </div>

          <div class="progreso-lineal-wrapper">
            <!-- Barra de progreso lineal fina -->
            <div class="progreso-lineal-pista">
              <div
                class="progreso-lineal-barra"
                :class="{ 'progreso-lineal-barra--exito': completadoExitoso }"
                :style="{ width: `${porcentajeAvance}%` }"
              ></div>
            </div>

            <!-- Fila horizontal única (misma altura): Info izquierda | Tiempo total centro | Acciones derecha -->
            <div class="progreso-lineal-footer">
              <div class="progreso-info">
                <span class="progreso-pct-txt">{{ porcentajeAvance }}% completado</span>
                <span class="progreso-sep">·</span>
                <span class="progreso-count-txt">{{ cometidosProcesadosCount }} de {{ totalCometidos }} cometidos</span>
              </div>

              <!-- Tiempo total al centro horizontal (solo aparece al finalizar) -->
              <div class="progreso-centro">
                <span v-if="completadoExitoso" class="tiempo-total-pill">
                  <i class="bi bi-stopwatch me-1 text-secondary"></i>
                  Tiempo total: <strong>{{ tiempoTotalFormateado }}</strong>
                  <span v-if="promedioPorCometidoTexto" class="tiempo-promedio-txt ms-1">
                    (Promedio: {{ promedioPorCometidoTexto }} por cometido)
                  </span>
                </span>
              </div>

              <div class="progreso-acciones">
                <button
                  v-if="completadoExitoso"
                  class="btn btn-primary btn-cta btn-sm py-2 px-3"
                  @click="etapaActual = 3"
                >
                  <i class="bi bi-file-earmark-bar-graph me-1"></i>
                  Ir al reporte final
                  <i class="bi bi-arrow-right ms-1"></i>
                </button>
                <button
                  v-if="huboError && !automatizando"
                  class="btn btn-primary btn-cta btn-sm py-2 px-3"
                  @click="empezarAutomatizacion"
                >
                  <i class="bi bi-arrow-clockwise me-1"></i>
                  Reintentar automatización
                </button>
                <button
                  v-if="automatizando"
                  class="btn btn-outline-danger btn-sm btn-cancelar-derecha"
                  @click="cancelarAutomatizacion"
                >
                  <i class="bi bi-x-circle me-1"></i>Cancelar
                </button>
              </div>
            </div>
          </div>
        </div>

      </main>
    </div>


    <!-- ══════════════════════════════════════════════════════ -->
    <!-- ETAPA 3: FINALIZADO (COMPONENTE MODULAR)               -->
    <!-- ══════════════════════════════════════════════════════ -->
    <EtapaFinal
      v-if="etapaActual === 3"
      :filas="filas"
      :estadosCometidos="estadosCometidos"
      :fileName="fileName"
      @volver-inicio="volverAlInicio"
    />

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- MODAL DE CREDENCIALES                                  -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div
      v-if="mostrarModalCredenciales"
      class="modal-credenciales-backdrop"
      @click.self="cerrarModalCredenciales"
    >
      <div class="modal-credenciales-card">
        <div class="modal-credenciales-header">
          <div class="d-flex align-items-center gap-2">
            <div class="modal-credenciales-icono">
              <i class="bi bi-shield-lock-fill"></i>
            </div>
            <div>
              <h5 class="modal-credenciales-titulo mb-0">Credenciales Institucionales MOP</h5>
              <span class="modal-credenciales-subtitulo">Acceso para Sistema SSD, Portal Personal y Firmador</span>
            </div>
          </div>
          <button type="button" class="btn-cerrar-modal" @click="cerrarModalCredenciales">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>

        <form @submit.prevent="confirmarCredencialesEIniciar" class="modal-credenciales-body">
          <div class="modal-credenciales-aviso">
            <i class="bi bi-info-circle-fill me-2"></i>
            <span>
              Por seguridad, tus credenciales <strong>no se guardan en ningún archivo</strong> y se utilizan únicamente en memoria durante esta ejecución.
            </span>
          </div>

          <!-- Bloque 1: Sistema SSD -->
          <div class="credenciales-seccion mb-3">
            <div class="credenciales-seccion-titulo">
              <i class="bi bi-file-earmark-text me-1"></i>1. Sistema SSD
            </div>
            <div class="mb-2">
              <label class="form-label modal-credenciales-label">Usuario SSD</label>
              <div class="input-group">
                <span class="input-group-text modal-input-addon">
                  <i class="bi bi-person-fill"></i>
                </span>
                <input
                  v-model="credencialUsuarioSsd"
                  type="text"
                  class="form-control modal-input"
                  placeholder="Ingresa tu usuario de SSD"
                  autocomplete="username"
                  autofocus
                />
              </div>
            </div>

            <div>
              <label class="form-label modal-credenciales-label">Contraseña SSD</label>
              <div class="input-group">
                <span class="input-group-text modal-input-addon">
                  <i class="bi bi-key-fill"></i>
                </span>
                <input
                  v-model="credencialClaveSsd"
                  :type="mostrarClaveSsd ? 'text' : 'password'"
                  class="form-control modal-input"
                  placeholder="Ingresa tu contraseña de SSD"
                  autocomplete="current-password"
                />
                <button
                  type="button"
                  class="btn btn-outline-secondary modal-btn-ojo"
                  @click="mostrarClaveSsd = !mostrarClaveSsd"
                  tabindex="-1"
                >
                  <i :class="mostrarClaveSsd ? 'bi bi-eye-slash-fill' : 'bi bi-eye-fill'"></i>
                </button>
              </div>
            </div>
          </div>

          <!-- Bloque 2: Portal Personal y Firmador -->
          <div class="credenciales-seccion mb-2">
            <div class="credenciales-seccion-titulo">
              <i class="bi bi-person-badge me-1"></i>2. Portal Personal y Firmador
            </div>
            <div class="mb-2">
              <label class="form-label modal-credenciales-label">Usuario</label>
              <div class="input-group">
                <span class="input-group-text modal-input-addon">
                  <i class="bi bi-person-fill"></i>
                </span>
                <input
                  v-model="credencialUsuario"
                  type="text"
                  class="form-control modal-input"
                  placeholder="Ingresa tu usuario institucional"
                  autocomplete="username"
                />
              </div>
            </div>

            <div>
              <label class="form-label modal-credenciales-label">Contraseña</label>
              <div class="input-group">
                <span class="input-group-text modal-input-addon">
                  <i class="bi bi-key-fill"></i>
                </span>
                <input
                  v-model="credencialClave"
                  :type="mostrarClave ? 'text' : 'password'"
                  class="form-control modal-input"
                  placeholder="Ingresa tu contraseña"
                  autocomplete="current-password"
                />
                <button
                  type="button"
                  class="btn btn-outline-secondary modal-btn-ojo"
                  @click="mostrarClave = !mostrarClave"
                  tabindex="-1"
                >
                  <i :class="mostrarClave ? 'bi bi-eye-slash-fill' : 'bi bi-eye-fill'"></i>
                </button>
              </div>
            </div>
          </div>

          <div v-if="errorCredenciales" class="modal-credenciales-error mt-2">
            <i class="bi bi-exclamation-circle-fill me-1"></i>
            {{ errorCredenciales }}
          </div>

          <div class="modal-credenciales-footer mt-4">
            <button
              type="button"
              class="btn btn-outline-secondary btn-modal-cancelar"
              @click="cerrarModalCredenciales"
            >
              Cancelar
            </button>
            <button type="submit" class="btn btn-primary btn-modal-confirmar">
              <i class="bi bi-play-circle-fill me-2"></i>
              Confirmar e Iniciar ({{ filas.length }})
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- MODAL DETALLE DE ERROR DE COMETIDO                     -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div
      v-if="detalleErrorModal"
      class="modal-credenciales-backdrop"
      @click.self="cerrarModalError"
    >
      <div class="consola-card-error modal-error-card">
        <div class="card-error-header justify-content-between">
          <div class="d-flex align-items-center gap-2">
            <i class="bi bi-exclamation-octagon-fill text-danger fs-5"></i>
            <span>Fallo en Cometido #{{ detalleErrorModal.cometidoNum }} — {{ detalleErrorModal.portalNombre }}</span>
          </div>
          <button type="button" class="btn-cerrar-modal" @click="cerrarModalError" title="Cerrar">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>

        <div class="card-error-detalles">
          <div v-if="detalleErrorModal.rut && detalleErrorModal.rut !== 'N/A'" class="error-dato-item">
            <span class="error-dato-clave">Funcionario:</span>
            <span class="error-dato-valor">{{ detalleErrorModal.rut }}</span>
          </div>
          <div class="error-dato-item">
            <span class="error-dato-clave">Paso:</span>
            <span class="error-dato-accion">{{ detalleErrorModal.accion }}</span>
          </div>
          <div class="error-dato-item">
            <span class="error-dato-clave">Motivo:</span>
            <span class="error-dato-valor">{{ detalleErrorModal.errorMensaje }}</span>
          </div>
        </div>

        <div class="card-error-footer">
          <i class="bi bi-arrow-right-circle text-warning me-1"></i>
          Se omitió este cometido y el proceso continuó con el siguiente.
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- MODAL CORRECCIÓN DE DÍAS Y VIÁTICOS                    -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div
      v-if="filaEditandoViaticos"
      class="modal-credenciales-backdrop"
      @click.self="cerrarModalViaticos"
    >
      <div class="modal-credenciales-card modal-viaticos-card">
        <div class="modal-credenciales-header">
          <div class="d-flex align-items-center gap-2">
            <div class="modal-credenciales-icono">
              <i class="bi bi-calendar2-week-fill"></i>
            </div>
            <div>
              <h5 class="modal-credenciales-titulo mb-0">
                Corregir Días y Viáticos (Cometido N°{{ filaEditandoViaticos.numero_cometido || (filas.indexOf(filaEditandoViaticos) + 1) }})
              </h5>
              <span class="modal-credenciales-subtitulo">
                RUT: {{ formatearRut(filaEditandoViaticos.rut) }} · Fechas: {{ filaEditandoViaticos.fechainicio }} → {{ filaEditandoViaticos.fechatermino }}
              </span>
            </div>
          </div>
          <button type="button" class="btn-cerrar-modal" @click="cerrarModalViaticos">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>

        <form @submit.prevent="guardarCorreccionViaticos" class="modal-credenciales-body">
          <!-- Aviso de bloqueo cuando la fecha no es válida -->
          <div v-if="!fechasViaticosValidas" class="viaticos-bloqueo-fechas mb-3">
            <div class="d-flex align-items-start gap-2">
              <i class="bi bi-lock-fill fs-5 text-warning mt-1"></i>
              <div class="flex-grow-1">
                <div class="fw-bold mb-1">Primero debes corregir las fechas del cometido</div>
                <div class="small mb-2">
                  Las fechas actuales (<strong>{{ filaEditandoViaticos.fechainicio || '—' }} → {{ filaEditandoViaticos.fechatermino || '—' }}</strong>) no son válidas, por lo que esta corrección está bloqueada hasta definir el rango correcto.
                </div>
                <button
                  type="button"
                  class="btn btn-sm btn-warning fw-semibold"
                  @click="irACorregirFechasDesdeViaticos"
                >
                  <i class="bi bi-calendar-range me-1"></i>Corregir Fechas ahora
                </button>
              </div>
            </div>
          </div>

          <div :class="{ 'viaticos-seccion-bloqueada': !fechasViaticosValidas }">
            <!-- 1. Selección de días de salida -->
            <div class="mb-3">
              <div class="d-flex align-items-center justify-content-between mb-2">
                <label class="form-label modal-credenciales-label mb-0">
                  1. Días de salida ({{ editDiasSeleccionados.length }} seleccionado{{ editDiasSeleccionados.length === 1 ? '' : 's' }})
                </label>
                <button
                  type="button"
                  class="btn-atajo-viaticos"
                  :disabled="!fechasViaticosValidas"
                  @click="deducirDiasDesdeFechas"
                  title="Marcar automáticamente los días comprendidos entre Fecha Inicio y Fecha Término"
                >
                  <i class="bi bi-magic me-1"></i>Marcar según fechas
                </button>
              </div>
              <div class="dias-selector-grid">
                <button
                  v-for="dia in DIAS_SEMANA_OPCIONES"
                  :key="dia.id"
                  type="button"
                  class="dia-toggle-btn"
                  :class="{
                    'dia-toggle-btn--activo': editDiasSeleccionados.includes(dia.id),
                    'dia-toggle-btn--bloqueado': !fechasViaticosValidas || (diasEsperadosPorFecha.length > 0 && !diasEsperadosPorFecha.includes(dia.id))
                  }"
                  :disabled="!fechasViaticosValidas || (diasEsperadosPorFecha.length > 0 && !diasEsperadosPorFecha.includes(dia.id))"
                  @click="toggleDiaSeleccionado(dia.id)"
                >
                  <span class="dia-toggle-corto">{{ dia.corto }}</span>
                  <span class="dia-toggle-largo">{{ dia.label }}</span>
                </button>
              </div>
            </div>

            <!-- 2. Cantidad de días por porcentaje -->
            <div class="mb-3">
              <div class="d-flex align-items-center justify-content-between mb-2 flex-wrap gap-1">
                <label class="form-label modal-credenciales-label mb-0">
                  2. Cantidad de días por porcentaje
                </label>
                <div v-if="editDiasSeleccionados.length > 0" class="d-flex gap-1">
                  <button
                    type="button"
                    class="btn-atajo-viaticos"
                    :disabled="!fechasViaticosValidas"
                    @click="igualarPorcentajes('40')"
                  >
                    Todo al 40% ({{ editDiasSeleccionados.length }}d)
                  </button>
                  <button
                    v-if="editDiasSeleccionados.length >= 2"
                    type="button"
                    class="btn-atajo-viaticos"
                    :disabled="!fechasViaticosValidas"
                    @click="igualarPorcentajes('100_40')"
                  >
                    {{ editDiasSeleccionados.length - 1 }} al 100% + 1 al 40%
                  </button>
                </div>
              </div>

              <div class="porcentajes-grid">
                <div v-for="item in PORCENTAJES_VIATICOS" :key="item.campo" class="porcentaje-item">
                  <label class="porcentaje-label">{{ item.label }}</label>
                  <input
                    v-model.number="editPorcentajes[item.campo]"
                    type="number"
                    min="0"
                    max="31"
                    step="1"
                    :disabled="!fechasViaticosValidas"
                    class="form-control modal-input text-center fw-bold"
                  />
                </div>
              </div>
            </div>

            <!-- Indicador en vivo de coherencia -->
            <div
              v-if="fechasViaticosValidas"
              class="viaticos-balance-box"
              :class="viaticosEditCoinciden ? 'viaticos-balance-box--ok' : 'viaticos-balance-box--error'"
            >
              <div>
                <i :class="viaticosEditCoinciden ? 'bi bi-check-circle-fill me-2' : 'bi bi-exclamation-triangle-fill me-2'"></i>
                <span v-if="viaticosEditCoinciden">
                  <strong>Coherencia válida:</strong> Los {{ editDiasSeleccionados.length }} día(s) coinciden con las fechas ({{ diasEsperadosTexto }}) y los porcentajes suman {{ sumaEditPorcentajes }}.
                </span>
                <span v-else-if="!diasCoincidenConFecha">
                  <strong>Días no coinciden con las fechas:</strong> Según las fechas del cometido corresponden <strong>{{ diasEsperadosPorFecha.length }} día(s) ({{ diasEsperadosTexto }})</strong>. Presiona <em>"Marcar según fechas"</em>.
                </span>
                <span v-else>
                  <strong>Porcentajes no coinciden:</strong> Corresponden <strong>{{ editDiasSeleccionados.length }}</strong> día(s) según las fechas, pero los porcentajes suman <strong>{{ sumaEditPorcentajes }}</strong>.
                </span>
              </div>
            </div>
          </div>

          <div class="modal-credenciales-footer mt-4">
            <button type="button" class="btn btn-outline-secondary btn-modal-cancelar" @click="cerrarModalViaticos">
              Cancelar
            </button>
            <button
              type="submit"
              class="btn btn-primary btn-modal-confirmar"
              :disabled="!viaticosEditCoinciden"
            >
              <i class="bi bi-check2-circle me-1"></i>
              Aplicar Corrección
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- MODAL CORRECCIÓN DE FECHAS                             -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div
      v-if="filaEditandoFechas"
      class="modal-credenciales-backdrop"
      @click.self="cerrarModalFechas"
    >
      <div class="modal-credenciales-card">
        <div class="modal-credenciales-header">
          <div class="d-flex align-items-center gap-2">
            <div class="modal-credenciales-icono">
              <i class="bi bi-calendar-range-fill"></i>
            </div>
            <div>
              <h5 class="modal-credenciales-titulo mb-0">
                Corregir Fechas (Cometido N°{{ filaEditandoFechas.numero_cometido || (filas.indexOf(filaEditandoFechas) + 1) }})
              </h5>
              <span class="modal-credenciales-subtitulo">Formato requerido: DD/MM/AAAA</span>
            </div>
          </div>
          <button type="button" class="btn-cerrar-modal" @click="cerrarModalFechas">
            <i class="bi bi-x-lg"></i>
          </button>
        </div>

        <form @submit.prevent="guardarCorreccionFechas" class="modal-credenciales-body">
          <div class="d-flex justify-content-end mb-2">
            <button
              type="button"
              class="btn-atajo-viaticos"
              :disabled="!mesesModalCoinciden"
              :title="mesesModalCoinciden ? 'Intercambiar fecha de inicio y fecha de término' : 'No se puede intercambiar si las fechas pertenecen a distinto mes'"
              @click="intercambiarFechasModal"
            >
              <i class="bi bi-arrow-left-right me-1"></i>Intercambiar Inicio ↔ Término
            </button>
          </div>

          <div class="mb-3">
            <label class="form-label modal-credenciales-label">Fecha de Inicio (DD/MM/AAAA)</label>
            <input
              v-model="editFechaInicio"
              type="text"
              class="form-control modal-input"
              placeholder="Ej: 05/10/2026"
            />
          </div>

          <div class="mb-3">
            <label class="form-label modal-credenciales-label">Fecha de Término (DD/MM/AAAA)</label>
            <input
              v-model="editFechaTermino"
              type="text"
              class="form-control modal-input"
              placeholder="Ej: 09/10/2026"
            />
          </div>

          <!-- Diagnóstico en vivo del rango de fechas -->
          <div
            class="viaticos-balance-box"
            :class="fechasModalValidas ? 'viaticos-balance-box--ok' : 'viaticos-balance-box--error'"
          >
            <div>
              <i :class="fechasModalValidas ? 'bi bi-check-circle-fill me-2' : 'bi bi-exclamation-triangle-fill me-2'"></i>
              <span v-if="!dIniModal || !dTerModal">
                <strong>Formato inválido:</strong> Ambas fechas deben tener un formato válido <strong>DD/MM/AAAA</strong>.
              </span>
              <span v-else-if="!mesesModalCoinciden">
                <strong>Distinto mes detectado:</strong> La fecha de inicio (mes <strong>{{ String(dIniModal.getMonth() + 1).padStart(2, '0') }}/{{ dIniModal.getFullYear() }}</strong>) y la de término (mes <strong>{{ String(dTerModal.getMonth() + 1).padStart(2, '0') }}/{{ dTerModal.getFullYear() }}</strong>) no coinciden. Deben pertenecer al mismo mes (el botón de intercambiar está bloqueado).
              </span>
              <span v-else-if="dIniModal > dTerModal">
                <strong>Fechas invertidas (mismo mes):</strong> La fecha de inicio es posterior a la de término. Puedes usar <em>"Intercambiar Inicio ↔ Término"</em>.
              </span>
              <span v-else>
                <strong>Fechas válidas:</strong> El rango <strong>{{ editFechaInicio.trim() }} → {{ editFechaTermino.trim() }}</strong> pertenece al mismo mes y está en orden correcto.
              </span>
            </div>
          </div>

          <div v-if="errorModalFechas" class="modal-credenciales-error mt-2">
            <i class="bi bi-exclamation-circle-fill me-1"></i>
            {{ errorModalFechas }}
          </div>

          <div class="modal-credenciales-footer mt-4">
            <button type="button" class="btn btn-outline-secondary btn-modal-cancelar" @click="cerrarModalFechas">
              Cancelar
            </button>
            <button type="submit" class="btn btn-primary btn-modal-confirmar" :disabled="!fechasModalValidas">
              <i class="bi bi-check2-circle me-1"></i>
              Aplicar Corrección
            </button>
          </div>
        </form>
      </div>
    </div>

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
/* STEPPER GLOBAL                                                 */
/* ══════════════════════════════════════════════════════════════ */
.stepper-barra {
  position: relative;
  background-color: var(--color-tertiary);
  padding: 18px 40px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}

/* Botón Terminal (esquina derecha del stepper principal) */
.btn-terminal-icono {
  position: absolute;
  right: 28px;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  border-radius: 12px;
  border: 2px solid #38bdf8;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.22), rgba(15, 23, 42, 0.9));
  color: #38bdf8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  cursor: pointer;
  box-shadow: 0 0 16px rgba(56, 189, 248, 0.35);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 10;
}

.btn-terminal-icono:hover {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.35), rgba(15, 23, 42, 0.95));
  border-color: #7dd3fc;
  color: #ffffff;
  transform: translateY(-50%) scale(1.08);
  box-shadow: 0 0 24px rgba(56, 189, 248, 0.6);
}

.btn-terminal-activo {
  background: #0284c7 !important;
  border-color: #38bdf8 !important;
  color: #ffffff !important;
  box-shadow: 0 0 22px rgba(56, 189, 248, 0.7) !important;
}

.btn-terminal--error {
  border-color: #ef4444 !important;
  color: #f87171 !important;
  box-shadow: 0 0 18px rgba(239, 68, 68, 0.5) !important;
}

/* Indicadores de pulso y alerta en el botón */
.terminal-dot-pulso {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 10px;
  height: 10px;
  background-color: #38bdf8;
  border: 2px solid #0f172a;
  border-radius: 50%;
  animation: pulseCyan 1.5s infinite;
}

@keyframes pulseCyan {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7); }
  70% { transform: scale(1.1); box-shadow: 0 0 0 6px rgba(56, 189, 248, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
}

.terminal-dot-alerta {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 11px;
  height: 11px;
  background-color: #ef4444;
  border: 2px solid #0f172a;
  border-radius: 50%;
  animation: pulseRed 1.2s infinite;
}

@keyframes pulseRed {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8); }
  70% { transform: scale(1.15); box-shadow: 0 0 0 7px rgba(239, 68, 68, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

/* Modal / Drawer Terminal de Procesos */
.terminal-drawer {
  position: absolute;
  top: 82px;
  right: 28px;
  width: 780px;
  max-width: calc(100vw - 56px);
  max-height: 540px;
  background-color: #080e1e;
  border: 1px solid #1e293b;
  border-radius: 12px;
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.6);
  z-index: 100;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: fadeInDown 0.2s ease-out;
}

@keyframes fadeInDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.terminal-drawer-header {
  background-color: #0f172a;
  color: #f8fafc;
  padding: 11px 18px;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.btn-terminal-accion {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 5px;
  transition: all 0.15s;
}

.btn-terminal-accion:hover {
  color: #38bdf8;
  background-color: rgba(56, 189, 248, 0.15);
}

.btn-cerrar-terminal {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 5px;
  transition: all 0.15s;
}

.btn-cerrar-terminal:hover {
  color: #fff;
  background-color: rgba(239, 68, 68, 0.3);
}

.terminal-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 12px;
  background-color: #334155;
  color: #cbd5e1;
}

.badge-activa {
  background-color: rgba(0, 111, 179, 0.4);
  color: #60a5fa;
  border: 1px solid #3b82f6;
}

.badge-fin {
  background-color: rgba(5, 150, 105, 0.3);
  color: #34d399;
  border: 1px solid #059669;
}

.badge-error {
  background-color: rgba(220, 38, 38, 0.35);
  color: #fca5a5;
  border: 1px solid #dc2626;
}

.terminal-drawer-cuerpo {
  padding: 16px 20px;
  overflow-y: auto;
  font-family: 'Consolas', 'Courier New', Courier, monospace;
  font-size: 12.5px;
  min-height: 220px;
  max-height: 420px;
  background-color: #070d1e;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Scrollbar estilizada */
.terminal-drawer-cuerpo::-webkit-scrollbar {
  width: 8px;
}
.terminal-drawer-cuerpo::-webkit-scrollbar-track {
  background: #080e1e;
}
.terminal-drawer-cuerpo::-webkit-scrollbar-thumb {
  background: #1e293b;
  border-radius: 4px;
}
.terminal-drawer-cuerpo::-webkit-scrollbar-thumb:hover {
  background: #334155;
}

/* Estado sin logs */
.consola-vacia {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #94a3b8;
  text-align: center;
  font-size: 12.5px;
}

/* Línea de log estándar */
.consola-linea {
  color: #cbd5e1;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12.5px;
  line-height: 1.45;
  word-break: break-word;
}

.consola-hora {
  color: #64748b;
  font-size: 11px;
  font-family: monospace;
  flex-shrink: 0;
}

.consola-prefijo {
  color: #38bdf8;
  font-weight: 700;
  flex-shrink: 0;
}

.consola-texto {
  color: #e2e8f0;
}

.consola-linea--activo {
  color: #38bdf8;
  display: flex;
  align-items: center;
  gap: 8px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #38bdf8;
  font-weight: bold;
}

/* Banner de inicio de cometido */
.consola-banner-inicio {
  background: rgba(56, 189, 248, 0.1);
  border-left: 3px solid #38bdf8;
  padding: 8px 12px;
  border-radius: 4px;
  color: #7dd3fc;
  font-weight: 600;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Checkpoint de cometido exitoso */
.consola-card-exito {
  background: rgba(34, 197, 94, 0.12);
  border-left: 3px solid #22c55e;
  border-radius: 4px;
  padding: 8px 12px;
  color: #86efac;
  font-weight: 600;
  font-size: 12.5px;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Checkpoint de error con output de Python */
.consola-card-error {
  background-color: #170d14;
  border: 1px solid #ef4444;
  border-left: 4px solid #ef4444;
  border-radius: 8px;
  padding: 12px 14px;
  margin: 6px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 4px 18px rgba(239, 68, 68, 0.2);
}

.card-error-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 13px;
  color: #fca5a5;
  border-bottom: 1px solid rgba(239, 68, 68, 0.3);
  padding-bottom: 6px;
}

.card-error-detalles {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #cbd5e1;
}

.error-dato-item {
  display: flex;
  gap: 6px;
  align-items: baseline;
}

.error-dato-clave {
  color: #94a3b8;
  font-weight: 600;
  min-width: 140px;
  flex-shrink: 0;
}

.error-dato-valor {
  color: #f1f5f9;
}

.error-dato-accion {
  color: #fbbf24;
  font-weight: 600;
}

.error-selector-code {
  background-color: #261624;
  color: #f472b6;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11.5px;
  font-family: monospace;
  border: 1px solid rgba(244, 114, 182, 0.3);
}

/* Card Python Output */
.card-error-python {
  margin-top: 4px;
  background: #0b1120;
  border: 1px solid #1e293b;
  border-radius: 6px;
  padding: 8px 12px;
}

.python-header {
  font-size: 11px;
  font-weight: 700;
  color: #38bdf8;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.python-code {
  margin: 0;
  font-size: 11.5px;
  color: #e2e8f0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Consolas', monospace;
  line-height: 1.45;
}

.card-error-footer {
  font-size: 11.5px;
  color: #fef08a;
  background-color: rgba(234, 179, 8, 0.1);
  padding: 5px 10px;
  border-radius: 5px;
  border: 1px dashed rgba(234, 179, 8, 0.35);
  display: flex;
  align-items: center;
}

.card-error-footer code {
  color: #fde047;
  background: rgba(0,0,0,0.3);
  padding: 1px 4px;
  border-radius: 3px;
  margin: 0 4px;
}

/* Animación de checkpoint resaltado al inspeccionar error desde la fila */
.consola-card-error--resaltado {
  animation: highlightError 1.8s ease-in-out;
}

@keyframes highlightError {
  0% {
    transform: scale(1.02);
    box-shadow: 0 0 25px rgba(239, 68, 68, 0.95);
    border-color: #f87171;
  }
  50% {
    transform: scale(1.02);
    box-shadow: 0 0 32px rgba(239, 68, 68, 1);
    border-color: #ef4444;
  }
  100% {
    transform: scale(1);
    box-shadow: 0 4px 18px rgba(239, 68, 68, 0.2);
  }
}

/* Card de Resumen */
.consola-card-resumen {
  background: #0f172a;
  border: 1px solid #38bdf8;
  border-radius: 8px;
  padding: 12px 16px;
  margin: 8px 0;
  color: #f8fafc;
}

.resumen-titulo {
  font-weight: 700;
  font-size: 13px;
  color: #38bdf8;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.resumen-estadisticas {
  display: flex;
  gap: 20px;
}

.resumen-kpi {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #1e293b;
  padding: 6px 14px;
  border-radius: 6px;
  min-width: 80px;
}

.kpi-num {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.2;
}

.kpi-etiqueta {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
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
/* ETAPA 1 y 2: layout general                                    */
/* ══════════════════════════════════════════════════════════════ */
.etapa-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
  transition: all 0.3s ease;
}

/* Margen y separación elegante en Etapa de Ejecución */
.etapa-layout--ejecucion {
  padding: 16px 20px 24px;
  max-width: 1800px;
  margin: 0 auto;
  width: 100%;
}

.etapa-layout--ejecucion .panel-tabla {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.06);
  background-color: var(--color-white);
  overflow: hidden;
}

/* ── Panel izquierdo ── */
.panel-checklist {
  width: 350px;
  min-width: 320px;
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

/* Grupos simplificados (4 familias de validación) */
.grupos-lista {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.grupo-item {
  border-radius: 8px;
  border: 1px solid var(--color-neutral);
  overflow: hidden;
  transition: all 0.25s ease;
  background-color: #fafbfc;
}

.grupo--ok        { border-color: #bbf7d0; background-color: #f0fdf4; }
.grupo--error     { border-color: #fecaca; background-color: #fef2f2; }
.grupo--revisando { border-color: #bfdbfe; background-color: #eff6ff; }

.grupo-cabecera {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
}

.grupo-icono {
  font-size: 20px;
  flex-shrink: 0;
  width: 24px;
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
  gap: 2px;
  flex: 1;
}

.grupo-nombre {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-black);
}

.grupo--pendiente .grupo-nombre { color: var(--color-mid-gray); }
.grupo--ok        .grupo-nombre { color: #065f46; }
.grupo--error     .grupo-nombre { color: #991b1b; }

.grupo-desc {
  font-size: 11.5px;
  color: var(--color-mid-gray);
  line-height: 1.25;
}

.grupo-status-pill {
  margin-left: auto;
  flex-shrink: 0;
}

.tag-status {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  letter-spacing: 0.3px;
}

.tag-ok        { background-color: #d1fae5; color: #065f46; }
.tag-error     { background-color: #fee2e2; color: #991b1b; }
.tag-revisando { background-color: #dbeafe; color: #1e40af; }
.tag-pendiente { background-color: #f1f5f9; color: #64748b; }

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

/* Cronómetro global en vivo y al terminar */
.cronometro-pill {
  display: inline-flex;
  align-items: center;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
}
.cronometro-pill--activo {
  background-color: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
}

/* KPIs de resumen */
.tabla-kpis { display: flex; gap: 10px; align-items: center; flex-shrink: 0; }
.kpi { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; padding: 5px 12px; border-radius: 20px; }
.kpi--ok    { background-color: #d1fae5; color: #065f46; }
.kpi--error { background-color: #fee2e2; color: #991b1b; }

/* Estado procesando */
.tabla-procesando { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--color-mid-gray); gap: 4px; }

/* Wrapper de la tabla */
.tabla-wrapper { flex: 1; overflow-y: auto; overflow-x: auto; }

.tabla-cometidos { width: 100%; border-collapse: collapse; font-size: 15px; }

.tabla-cometidos thead tr {
  background-color: var(--color-tertiary);
  color: var(--color-white);
  position: sticky;
  top: 0;
  z-index: 1;
}

.tabla-cometidos th {
  padding: 12px 14px;
  font-family: var(--font-title);
  font-weight: 500;
  font-size: 13px;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  white-space: nowrap;
  text-align: center;
}

.tabla-cometidos td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-neutral);
  vertical-align: middle;
  text-align: center;
}

.tabla-cometidos tbody tr:hover { background-color: #f8fafc; }

/* Fila con error de validación: fondo levemente rosado */
.fila-con-error { background-color: #fff7f7 !important; }
.fila-con-error:hover { background-color: #fff0f0 !important; }

/* ── Colores dinámicos de filas durante la ejecución ── */
.fila-ejecutando {
  background-color: #fef9c3 !important;
  border-left: 4px solid #eab308;
}
.fila-ejecutando:hover { background-color: #fef08a !important; }

.fila-completado {
  background-color: #dcfce7 !important;
  border-left: 4px solid #22c55e;
}
.fila-completado:hover { background-color: #bbf7d0 !important; }

.fila-fallido {
  background-color: #fee2e2 !important;
  border-left: 4px solid #ef4444;
}
.fila-fallido:hover { background-color: #fecaca !important; }

/* Columnas con distribución balanceada y armoniosa */
.col-n         { width: 5%;  min-width: 48px;  text-align: center; }
.col-conductor { width: 18%; min-width: 150px; text-align: center; }
.col-fechas    { width: 22%; min-width: 200px; white-space: nowrap; text-align: center; }
.col-vehiculo  { width: 14%; min-width: 125px; text-align: center; }
.col-dias      { width: 16%; min-width: 135px; text-align: center; }
.col-viaticos  { width: 13%; min-width: 120px; text-align: center; }
.col-estado    { width: 12%; min-width: 130px; text-align: center; }

/* Badge de número de fila */
.badge-fila {
  background-color: #e0f2fe;
  color: #0369a1;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  padding: 3px 9px;
  font-size: 13px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  display: inline-block;
}

/* Micro-feedback visual al auto-corregir celdas */
@keyframes pulsoVerde {
  0% {
    background-color: rgba(34, 197, 94, 0.4);
    box-shadow: 0 0 10px rgba(34, 197, 94, 0.4);
  }
  100% {
    background-color: transparent;
    box-shadow: none;
  }
}
.celda-corregida-pulso {
  animation: pulsoVerde 1.4s ease-out;
  border-radius: 6px;
}

/* RUT */
.conductor-bloque {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
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

/* Fechas — siempre en una sola línea y centrado */
.fechas-bloque {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}
.fecha-chip {
  background-color: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 13px;
  font-weight: 600;
  color: #0284c7;
  font-family: 'Courier New', monospace;
  white-space: nowrap;
}
.fecha-sep {
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

/* Vehículo / Sigla — centrado y con tamaño agrandado */
.vehiculo-bloque {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  gap: 4px;
}

.badge-sigla {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  background-color: #f1f5f9;
  color: #0f172a;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 15px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  letter-spacing: 0.5px;
  white-space: nowrap;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.badge-sigla--error {
  background-color: #fee2e2;
  border-color: #fca5a5;
  color: #dc2626;
}

/* ── Chips de días de salida ── */
.dias-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: center;
  gap: 4px;
}

.dia-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background-color: #e0f2fe;
  color: #0369a1;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  min-width: 24px;
}

/* Viáticos */
.viaticos-bloque {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
}
.viaticos-dias {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-black);
  display: flex;
  align-items: center;
  justify-content: center;
}
.viaticos-detalle {
  font-size: 11px;
  color: var(--color-mid-gray);
  text-align: center;
}

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

/* Badges de estado de la fila — tamaño uniforme y centrado para todos los estados */
.badge-estado {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  width: 122px;
  height: 28px;
  box-sizing: border-box;
  border-radius: 14px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

/* Estado Listo / Válido: verde sutil y natural con borde gris neutro */
.badge-estado--ok {
  background-color: #bbf7d0;
  color: #166534;
  border: 1px solid #94a3b8;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.badge-estado--ok i {
  color: #16a34a;
}
.badge-estado--ok .badge-tiempo-txt {
  color: #15803d;
  font-weight: 600;
  opacity: 0.9;
}

/* Estado Error */
.badge-estado--error {
  background-color: #fee2e2;
  color: #991b1b;
  border: 1px solid #cbd5e1;
}
.badge-estado--error i {
  color: #dc2626;
}

/* Estado En curso */
.badge-estado--ejecutando {
  background-color: #fef3c7;
  color: #92400e;
  border: 1px solid #cbd5e1;
}

/* Estado Pendiente */
.badge-estado--pendiente {
  background-color: #f1f5f9;
  color: #64748b;
  border: 1px solid #cbd5e1;
}

.badge-tiempo-txt {
  font-size: 11px;
  opacity: 0.9;
  margin-left: 2px;
  font-weight: 500;
}

.estado-fallido-bloque {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.btn-ver-error-fila {
  background-color: #fee2e2;
  border: 1px solid #cbd5e1;
  color: #b91c1c;
  border-radius: 4px;
  font-size: 10.5px;
  font-weight: 700;
  padding: 2px 7px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 122px;
  box-sizing: border-box;
  transition: all 0.2s ease;
}

.btn-ver-error-fila:hover {
  background-color: #fecaca;
  color: #991b1b;
  transform: translateY(-1px);
}

/* Tabla vacía */
.tabla-vacia { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; color: var(--color-mid-gray); }

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

/* Contenedor de alerta centrado que no se expande a fullwidth */
.cta-alerta-wrapper {
  display: flex;
  justify-content: center;
  width: 100%;
}

.cta-aviso {
  margin: 0;
  font-size: 13.5px;
  color: #dc2626;
  background-color: #fff1f2;
  border: 1px solid #fecaca;
  border-radius: 20px;
  padding: 6px 18px;
  text-align: center;
  width: fit-content;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(220, 38, 38, 0.08);
}

.cta-exito {
  margin: 0;
  font-size: 13.5px;
  color: #065f46;
  background-color: #d1fae5;
  border: 1px solid #a7f3d0;
  border-radius: 20px;
  padding: 6px 18px;
  text-align: center;
  width: fit-content;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(6, 95, 70, 0.08);
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

/* ── Zona de acciones de Etapa 2: Barra de progreso + Cancelar a la derecha ── */
.cta-zona--ejecucion {
  padding: 16px 28px 20px;
  background-color: #f8fafc;
  border-top: 1px solid #e2e8f0;
  align-items: stretch;
}

.progreso-lineal-wrapper {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.progreso-lineal-pista {
  width: 100%;
  height: 6px;
  background-color: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}

.progreso-lineal-barra {
  height: 100%;
  background: linear-gradient(90deg, #0284c7, #006fb3);
  border-radius: 999px;
  transition: width 0.4s ease;
}

.progreso-lineal-barra--exito {
  background: linear-gradient(90deg, #10b981, #059669);
}

/* Footer en una sola fila horizontal a la misma altura: Info izquierda | Tiempo centro | Acciones derecha */
.progreso-lineal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 16px;
  margin-top: 4px;
}

.progreso-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  flex: 1;
  min-width: 0;
  justify-content: flex-start;
  white-space: nowrap;
}

.progreso-pct-txt {
  font-weight: 700;
  color: var(--color-black);
}

.progreso-sep {
  color: var(--color-mid-gray);
}

.progreso-count-txt {
  color: var(--color-dark-gray);
}

.progreso-centro {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tiempo-total-pill {
  display: inline-flex;
  align-items: center;
  background-color: #f1f5f9;
  color: #334155;
  border: 1px solid #cbd5e1;
  border-radius: 20px;
  padding: 4px 14px;
  font-size: 12.5px;
  font-weight: 500;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  white-space: nowrap;
}

.tiempo-total-pill strong {
  font-weight: 700;
  color: #0f172a;
  margin-left: 2px;
}

.tiempo-promedio-txt {
  font-size: 11.5px;
  color: #64748b;
}

.progreso-acciones {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  justify-content: flex-end;
  white-space: nowrap;
}

.btn-cancelar-derecha {
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 6px;
}

/* ══════════════════════════════════════════════════════════════ */
/* SUB-STEPPER (3 pasos: SSD → Personal → Firmador)             */
/* ══════════════════════════════════════════════════════════════ */
.sub-stepper-compact {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  background: #f8fafc;
  padding: 8px 16px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
}

.sub-paso-mini {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.sub-paso-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  border: 2px solid #cbd5e1;
  background-color: var(--color-white);
  color: var(--color-mid-gray);
  transition: all 0.3s ease;
  flex-shrink: 0;
}

.sub-paso-txt {
  font-size: 13.5px;
  font-weight: 600;
  color: #64748b;
  white-space: nowrap;
  transition: color 0.3s ease;
}

/* Sub-paso activo */
.sub-paso--activo .sub-paso-dot {
  border-color: var(--color-primary);
  background-color: var(--color-primary);
  color: var(--color-white);
  box-shadow: 0 0 0 4px rgba(0, 111, 179, 0.22);
}
.sub-paso--activo .sub-paso-txt {
  color: var(--color-primary);
  font-weight: 700;
}

/* Sub-paso completado */
.sub-paso--completado .sub-paso-dot {
  border-color: #059669;
  background-color: #059669;
  color: var(--color-white);
}
.sub-paso--completado .sub-paso-txt {
  color: #065f46;
  font-weight: 700;
}

/* Conector entre sub-pasos */
.sub-paso-conector {
  width: 26px;
  height: 3px;
  background-color: #cbd5e1;
  border-radius: 2px;
  flex-shrink: 0;
  transition: background-color 0.3s ease;
}
.conector--ok { background-color: #059669; }

/* ── Responsividad general ── */
@media (min-width: 1280px) {
  .panel-checklist  { width: 360px; }
  .checklist-titulo { font-size: 21px; }
  .grupo-nombre     { font-size: 15px; }
  .tabla-cometidos  { font-size: 15px; }
}

@media (min-width: 1600px) {
  .panel-checklist  { width: 400px; }
  .grupo-nombre     { font-size: 17px; }
  .grupo-desc       { font-size: 14px; }
  .tabla-cometidos  { font-size: 16px; }
  .conductor-rut    { font-size: 17px; }
  .fecha-chip       { font-size: 14px; }
  .badge-sigla      { font-size: 16px; }
}

@media (max-width: 1024px) {
  .panel-checklist  { width: 260px; min-width: 220px; }
  .etapa-layout     { flex-direction: column; overflow: auto; }
  .panel-checklist  { width: 100%; border-right: none; border-bottom: 1px solid var(--color-neutral); padding: 20px; }
  .sub-stepper-compact { flex-wrap: wrap; }
}

/* ══════════════════════════════════════════════════════════════ */
/* MODAL DE CREDENCIALES                                          */
/* ══════════════════════════════════════════════════════════════ */
.modal-credenciales-backdrop {
  position: fixed;
  inset: 0;
  background-color: rgba(15, 23, 42, 0.65);
  backdrop-filter: blur(4px);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: fadeInModal 0.18s ease-out;
}

@keyframes fadeInModal {
  from { opacity: 0; transform: scale(0.97); }
  to   { opacity: 1; transform: scale(1); }
}

.modal-credenciales-card {
  width: 100%;
  max-width: 460px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.35);
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.modal-credenciales-header {
  background-color: var(--color-tertiary, #0f172a);
  color: #ffffff;
  padding: 18px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-credenciales-icono {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(56, 189, 248, 0.18);
  border: 1px solid rgba(56, 189, 248, 0.4);
  color: #38bdf8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  flex-shrink: 0;
}

.modal-credenciales-titulo {
  font-size: 16px;
  font-weight: 700;
  color: #f8fafc;
}

.modal-credenciales-subtitulo {
  font-size: 12px;
  color: #94a3b8;
  display: block;
}

.btn-cerrar-modal {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.15s;
}

.btn-cerrar-modal:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.1);
}

.modal-credenciales-body {
  padding: 22px 24px 24px;
}

.modal-credenciales-aviso {
  background-color: #f0f9ff;
  border: 1px solid #bae6fd;
  color: #0369a1;
  font-size: 12.5px;
  line-height: 1.45;
  padding: 10px 13px;
  border-radius: 10px;
  margin-bottom: 18px;
  display: flex;
  align-items: flex-start;
}

.modal-credenciales-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 5px;
}

.credenciales-seccion {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 14px;
}

.credenciales-seccion-titulo {
  font-size: 12.5px;
  font-weight: 700;
  color: #0284c7;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 8px;
}

.modal-input-addon {
  background-color: #f8fafc;
  border-color: #cbd5e1;
  color: #64748b;
}

.modal-input {
  font-size: 14px;
  border-color: #cbd5e1;
  padding: 9px 12px;
}

.modal-input:focus {
  border-color: #0284c7;
  box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15);
}

.modal-btn-ojo {
  border-color: #cbd5e1;
  color: #64748b;
}

.modal-credenciales-error {
  font-size: 12.5px;
  font-weight: 600;
  color: #dc2626;
  background: #fef2f2;
  border: 1px solid #fecaca;
  padding: 8px 12px;
  border-radius: 8px;
}

.modal-credenciales-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-modal-cancelar {
  font-size: 13.5px;
  font-weight: 600;
  padding: 8px 16px;
  border-radius: 8px;
}

.btn-modal-confirmar {
  font-size: 13.5px;
  font-weight: 600;
  padding: 8px 18px;
  border-radius: 8px;
}

.modal-error-card {
  width: 100%;
  max-width: 580px;
  padding: 18px 22px;
  gap: 12px;
  font-family: 'Consolas', 'Courier New', Courier, monospace;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.55), 0 0 24px rgba(239, 68, 68, 0.25);
}

.modal-error-card .card-error-header {
  font-size: 14px;
  padding-bottom: 10px;
}

.modal-error-card .card-error-detalles {
  font-size: 13.5px;
  gap: 8px;
  padding: 4px 0;
}

.modal-viaticos-card {
  max-width: 540px;
}

.dias-selector-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
}

.dia-toggle-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s ease;
}

.dia-toggle-btn:hover {
  border-color: #94a3b8;
  background: #f1f5f9;
}

.dia-toggle-btn--activo {
  background: #0284c7 !important;
  border-color: #0284c7 !important;
  color: #ffffff !important;
  box-shadow: 0 2px 8px rgba(2, 132, 199, 0.3);
}

.dia-toggle-btn--bloqueado {
  opacity: 0.38;
  cursor: not-allowed;
  background: #f1f5f9;
}

.dia-toggle-corto {
  font-size: 13px;
  font-weight: 800;
}

.dia-toggle-largo {
  font-size: 10px;
  opacity: 0.85;
}

.porcentajes-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.porcentaje-item {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
}

.porcentaje-label {
  display: block;
  font-size: 11.5px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 4px;
}

.btn-atajo-viaticos {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 11.5px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-atajo-viaticos:hover {
  background: #dbeafe;
  border-color: #93c5fd;
}

.viaticos-balance-box {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.4;
}

.viaticos-balance-box--ok {
  background-color: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
}

.viaticos-balance-box--error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.viaticos-bloqueo-fechas {
  background-color: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
  padding: 12px 14px;
  border-radius: 10px;
}

.viaticos-seccion-bloqueada {
  opacity: 0.45;
  pointer-events: none;
  user-select: none;
}

.btn-atajo-viaticos:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
