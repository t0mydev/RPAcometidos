<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ─── Estado general ───────────────────────────────────────────
const fileName = ref(history.state?.fileName || 'archivo.xlsx')
const checks = ref([
  { id: 'rut',      label: 'Revisando RUT...',              estado: 'pendiente' },
  { id: 'sigla',  label: 'Revisando sigla vehículo...', estado: 'pendiente' },
])
const problemas = ref([])        // lista de errores con meta para el modal
const procesando = ref(true)
const procesandoMensaje = ref('Enviando archivo al servidor...')
const descargando = ref(false)
const descargarMensaje = ref('')

const filas = ref([]) // copia reactiva de los registros procesados
const correccionesAplicadas = ref(false)

// ─── Computado: si tiene alguna sugerencia automática pendiente
const tieneSugerencias = computed(() => {
  return filas.value.some(f => 
    (!f.rut_valido && f.sugerencia_correccion_rut) ||
    (!f.sigla_valida && f.sugerencia_correccion_sigla)
  )
})

// ─── Llamada a la API Flask ───────────────────────────────────
onMounted(async () => {
  const archivo = window.__excelFile
  if (!archivo) {
    procesandoMensaje.value = 'No se encontró el archivo. Vuelve al inicio.'
    procesando.value = false
    return
  }

  await delay(600)

  const formData = new FormData()
  formData.append('documento_excel', archivo)

  let resultados = []
  try {
    procesandoMensaje.value = 'Procesando con el servidor...'
    const resp = await fetch('/api/procesar-excel', {
      method: 'POST',
      body: formData,
    })

    if (!resp.ok) {
      throw new Error(`El servidor respondió con estado ${resp.status}`)
    }

    const data = await resp.json()

    if (data.status === 'completado') {
      resultados = data.resultados
      filas.value = resultados
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

  await animarChecks(resultados)
  procesando.value = false
})

// ─── Animación secuencial de checks ──────────────────────────
async function animarChecks(resultados) {
  const camposCheck = ['rut', 'sigla']

  for (let i = 0; i < checks.value.length; i++) {
    checks.value[i].estado = 'revisando'
    await delay(900)

    const campo = camposCheck[i]
    // Buscar si hay algún error en ese campo en cualquier fila
    const erroresCampo = []
    for (const fila of resultados) {
      const esCampoValido = campo === 'sigla' ? fila.sigla_valida : fila[`${campo}_valido`]
      const erroresFila = fila.errores || []

      if (esCampoValido === false) {
        const mensajeError = erroresFila.find(e =>
          e.toLowerCase().includes(campo === 'rut' ? 'rut' : 'sigla')
        )
        erroresCampo.push({
          fila: fila.numero_fila_excel,
          campo,
          mensaje: mensajeError || `${campo} inválido.`,
          sugerencia: campo === 'rut' ? fila.sugerencia_correccion_rut 
                    : campo === 'sigla' ? fila.sugerencia_correccion_sigla 
                    : null,
          valor_actual: fila[campo],
          fila_ref: fila
        })
      }
    }

    if (erroresCampo.length === 0) {
      checks.value[i].estado = 'ok'
    } else {
      checks.value[i].estado = 'error'
      checks.value[i].erroresCampo = erroresCampo
      problemas.value.push(...erroresCampo)
    }
  }
}

// ─── Recalcular problemas y checks tras correcciones ──────────
function actualizarProblemasYChecks() {
  const camposCheck = ['rut', 'sigla']
  const labels = {
    rut: 'Revisando RUT...',
    sigla: 'Revisando sigla vehículo...'
  }

  problemas.value = []

  checks.value = camposCheck.map((campo) => {
    const checkId = campo
    const erroresCampo = []
    
    for (const fila of filas.value) {
      const esCampoValido = campo === 'sigla' ? fila.sigla_valida : fila[`${campo}_valido`]
      const erroresFila = fila.errores || []

      if (esCampoValido === false) {
        const mensajeError = erroresFila.find(e =>
          e.toLowerCase().includes(campo === 'rut' ? 'rut' : 'sigla')
        )
        erroresCampo.push({
          fila: fila.numero_fila_excel,
          campo,
          mensaje: mensajeError || `${campo} inválido.`,
          sugerencia: campo === 'rut' ? fila.sugerencia_correccion_rut 
                    : campo === 'sigla' ? fila.sugerencia_correccion_sigla 
                    : null,
          valor_actual: fila[campo],
          fila_ref: fila
        })
      }
    }

    const estado = erroresCampo.length === 0 ? 'ok' : 'error'
    if (estado === 'error') {
      problemas.value.push(...erroresCampo)
    }

    return {
      id: checkId,
      label: labels[campo],
      estado,
      erroresCampo
    }
  })
}

// ─── Corregir Fila Directamente (aplica sugerencia automática) ──
function corregirFilaDirectamente(p) {
  if (p && p.sugerencia) {
    // Actualiza el valor en la referencia de la fila con la sugerencia
    p.fila_ref[p.campo] = p.sugerencia
    // Marca el campo como válido
    p.fila_ref[p.campo === 'sigla' ? 'sigla_valida' : `${p.campo}_valido`] = true
    
    // Remove la sugerencia ya que fue aplicada
    if (p.campo === 'rut') {
      p.fila_ref.sugerencia_correccion_rut = null
    } else if (p.campo === 'sigla') {
      p.fila_ref.sugerencia_correccion_sigla = null
    }

    // Remove de los errores del registro el mensaje correspondiente
    p.fila_ref.errores = p.fila_ref.errores.filter(err => 
      !err.toLowerCase().includes(p.campo === 'rut' ? 'rut' : 'sigla')
    )

    actualizarProblemasYChecks()
    correccionesAplicadas.value = true
  }
}

// ─── Aplicar todas las sugerencias automáticamente ─────────────
function aplicarTodasLasSugerencias() {
  let count = 0
  filas.value.forEach(f => {
    // RUT
    if (!f.rut_valido && f.sugerencia_correccion_rut) {
      f.rut = f.sugerencia_correccion_rut
      f.rut_valido = true
      f.sugerencia_correccion_rut = null
      f.errores = f.errores.filter(err => !err.toLowerCase().includes('rut'))
      count++
    }
    // sigla
    if (!f.sigla_valida && f.sugerencia_correccion_sigla) {
      f.sigla = f.sugerencia_correccion_sigla
      f.sigla_valida = true
      f.sugerencia_correccion_sigla = null
      f.errores = f.errores.filter(err => !err.toLowerCase().includes('sigla'))
      count++
    }
  })
  if (count > 0) {
    actualizarProblemasYChecks()
    correccionesAplicadas.value = true
  }
}

// ─── Descargar Excel Corregido ─────────────────────────────────
async function descargarExcelCorregido() {
  const archivo = window.__excelFile
  if (!archivo) {
    alert('No se encontró el archivo original en sesión. Vuelve al inicio.')
    return
  }

  descargando.value = true
  descargarMensaje.value = 'Generando archivo corregido...'

  const formData = new FormData()
  formData.append('documento_excel', archivo)

  // Formatea los registros para que la API en Flask los reciba correctamente
  const payload = filas.value.map(f => ({
    numero_fila_excel: f.numero_fila_excel,
    rut: f.rut,
    nombre: f.nombre,
    sigla: f.sigla,
    lugar_cometido: f.lugar_cometido,
    region_principal: f.region_principal,
    regiones: f.regiones,
    personal_trasladado: f.personal_trasladado,
    nombre_aprobador: f.nombre_aprobador,
    nombre_firmantes: f.nombre_firmantes,
    tipo_imputacion_presupuestaria: f.tipo_imputacion_presupuestaria,
    fallback_considerando: f.fallback_considerando,
    regiones: f.regiones,
    atribucion: f.atribucion,
    dias_salida: f.dias_salida,
    dias_100: f.dias_100,
    dias_70: f.dias_70,
    dias_60: f.dias_60,
    dias_50: f.dias_50,
    dias_40: f.dias_40,
    dias_35: f.dias_35
  }))

  formData.append('reporte_corregido', JSON.stringify(payload))

  try {
    const resp = await fetch('/api/descargar-excel-corregido', {
      method: 'POST',
      body: formData,
    })

    if (!resp.ok) {
      throw new Error(`El servidor respondió con estado ${resp.status}`)
    }

    const blob = await resp.blob()
    const urlBlob = window.URL.createObjectURL(blob)

    const link = document.createElement('a')
    link.href = urlBlob

    let filename = fileName.value.replace(/\.xlsx?$/, '_corregido.xlsx')
    const contentDisposition = resp.headers.get('Content-Disposition')
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^"]+)"?/)
      if (match) filename = match[1]
    }

    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(urlBlob)

    descargarMensaje.value = '¡Descarga exitosa!'
    setTimeout(() => { descargarMensaje.value = '' }, 3000)

  } catch (e) {
    console.error(e)
    alert(`Error al descargar el archivo: ${e.message}`)
  } finally {
    descargando.value = false
  }
}

const automatizando = ref(false)
const enAutomatizacion = ref(false)
const logsAutomatizacion = ref([])
const consolaCuerpoRef = ref(null)

let intervaloProgreso = null
const ultimoPasoRegistrado = ref(-1)
const ultimoMensajeRegistrado = ref('')

async function agregarLog(mensaje) {
  logsAutomatizacion.value.push(mensaje)
  await nextTick()
  if (consolaCuerpoRef.value) {
    consolaCuerpoRef.value.scrollTop = consolaCuerpoRef.value.scrollHeight
  }
}

function comenzarMonitoreoProgreso() {
  if (intervaloProgreso) clearInterval(intervaloProgreso)
  ultimoPasoRegistrado.value = -1
  ultimoMensajeRegistrado.value = ''

  intervaloProgreso = setInterval(async () => {
    try {
      const resp = await fetch('/api/progreso-automatizacion')
      if (!resp.ok) return

      const data = await resp.json()
      
      if (data.estado === 'iniciando') {
        const msg = data.detalle || 'Cargando entorno de Playwright...'
        if (!logsAutomatizacion.value.includes(msg)) {
          await agregarLog(msg)
        }
      } else if (data.estado === 'ejecutando') {
        const detalleMsg = data.detalle ? ` (${data.detalle})` : ''
        const logMsg = `Paso ${data.paso} de ${data.total}: Procesando ${data.nombre}${detalleMsg}`
        // Si el mensaje cambió (porque avanzó de paso o cambió de etapa/detalle), lo mostramos:
        if (ultimoMensajeRegistrado.value !== logMsg) {
          ultimoMensajeRegistrado.value = logMsg
          await agregarLog(logMsg)
        }
      } else if (data.estado === 'completado') {
        await agregarLog('¡Automatización finalizada exitosamente!')
        detenerMonitoreoProgreso()
        automatizando.value = false
      } else if (data.estado === 'error') {
        await agregarLog(`Error durante la automatización: ${data.nombre || 'Desconocido'}`)
        detenerMonitoreoProgreso()
        automatizando.value = false
      }
    } catch (e) {
      console.error('Error al consultar el progreso:', e)
    }
  }, 1000)
}

function detenerMonitoreoProgreso() {
  if (intervaloProgreso) {
    clearInterval(intervaloProgreso)
    intervaloProgreso = null
  }
}

onUnmounted(() => {
  detenerMonitoreoProgreso()
})

async function empezarAutomatizacion() {
  automatizando.value = true
  enAutomatizacion.value = true
  logsAutomatizacion.value = []
  await agregarLog('Iniciando el motor de automatización...')
  
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
      tipo_imputacion_presupuestaria: f.tipo_imputacion_presupuestaria
    }))

    const resp = await fetch('/api/empezar-automatizacion', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    if (!resp.ok) {
      throw new Error(`El servidor respondió con estado ${resp.status}`)
    }

    const data = await resp.json()
    if (data.status === 'iniciado') {
      comenzarMonitoreoProgreso()
    } else {
      await agregarLog(`Error al iniciar la automatización: ${data.mensaje}`)
      automatizando.value = false
    }
  } catch (e) {
    console.error(e)
    await agregarLog(`Error al conectar con el servidor: ${e.message}`)
    automatizando.value = false
  }
}

// ─── Volver al inicio ─────────────────────────────────────────
function volverAlInicio() {
  window.__excelFile = null
  router.push({ name: 'Home' })
}

// ─── Helpers ──────────────────────────────────────────────────
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
</script>

<template>
  <div class="validacion-container">

    <!-- ── Panel izquierdo: Check List ── -->
    <aside class="panel-checklist">
      <h2 class="checklist-title">Check List:</h2>
      <ul class="checklist-lista">
        <li
          v-for="check in checks"
          :key="check.id"
          class="checklist-item"
          :class="{
            'estado-pendiente': check.estado === 'pendiente',
            'estado-revisando': check.estado === 'revisando',
            'estado-ok':        check.estado === 'ok',
            'estado-error':     check.estado === 'error',
          }"
        >
          <!-- Icono de estado -->
          <span class="check-icono">
            <i v-if="check.estado === 'ok'"       class="bi bi-check-circle-fill"></i>
            <i v-else-if="check.estado === 'error'" class="bi bi-x-circle-fill"></i>
            <i v-else-if="check.estado === 'revisando'" class="bi bi-arrow-repeat spin"></i>
            <i v-else class="bi bi-circle"></i>
          </span>
          <span class="check-label">{{ check.label }}</span>

          <!-- Mini-lista de errores clickeables si el estado es error -->
          <ul v-if="check.estado === 'error' && check.erroresCampo" class="sub-errores">
            <li
              v-for="(err, idx) in check.erroresCampo"
              :key="idx"
              class="sub-error-item d-flex flex-column gap-1 mb-2"
            >
              <div class="d-flex align-items-center justify-content-between">
                <span><strong class="text-dark">{{ err.valor_actual || '(Vacío)' }}</strong></span>
              </div>
              <div v-if="err.sugerencia" class="d-flex align-items-center justify-content-between bg-dark p-1 rounded border border-warning mt-1">
                <span class="text-warning small me-2" style="font-size: 11px;">
                  <i class="bi bi-lightbulb-fill"></i> ¿{{ err.sugerencia }}?
                </span>
                <button 
                  class="btn btn-xs btn-warning py-0 px-2 fw-bold text-dark"
                  style="font-size: 10px;"
                  @click="corregirFilaDirectamente(err)"
                >
                  Corregir
                </button>
              </div>
            </li>
          </ul>
        </li>
      </ul>

      <!-- Acciones de archivo -->
      <div class="actions-container">
        <!-- Botón Auto-corregir -->
        <button 
          v-if="!procesando && tieneSugerencias"
          class="btn btn-warning w-100 mb-2 py-2 fw-bold text-dark d-flex align-items-center justify-content-center gap-2"
          @click="aplicarTodasLasSugerencias"
        >
          <i class="bi bi-magic"></i>
          <span>Auto-corregir Todo</span>
        </button>

        <!-- Botón Empezar automatización -->
        <button 
          v-if="!procesando && problemas.length === 0"
          class="btn btn-primary w-100 mb-2 py-2 fw-bold d-flex align-items-center justify-content-center gap-2"
          :disabled="automatizando"
          @click="empezarAutomatizacion"
        >
          <span v-if="automatizando" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
          <i v-else class="bi bi-play-circle-fill"></i>
          <span>{{ automatizando ? 'Ejecutando...' : 'Empezar automatización' }}</span>
        </button>

        <!-- Botón descargar corregido -->
        <button 
          v-if="!procesando"
          class="btn btn-success w-100 mb-3 py-2 fw-bold d-flex align-items-center justify-content-center gap-2"
          :disabled="descargando || !correccionesAplicadas"
          @click="descargarExcelCorregido"
        >
          <span v-if="descargando" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
          <i v-else class="bi bi-file-earmark-arrow-down-fill"></i>
          <span>{{ descargando ? 'Generando...' : 'Descargar Excel' }}</span>
        </button>

        <!-- Botón volver -->
        <button class="btn btn-outline-primary btn-volver w-100 py-2" @click="volverAlInicio">
          <i class="bi bi-arrow-left me-2"></i>Volver al inicio
        </button>
      </div>
    </aside>

    <!-- ── Panel derecho: Consola de problemas ── -->
    <main class="panel-consola">
      <div class="consola-header">
        <i class="bi bi-terminal-fill me-2"></i>
        <span v-if="enAutomatizacion">Progreso de la Automatización:</span>
        <span v-else>Problemas Específicos Identificados:</span>
      </div>

      <div class="consola-cuerpo" ref="consolaCuerpoRef">
        <!-- Estado: procesando -->
        <div v-if="procesando" class="consola-procesando">
          <span class="cursor-blink">▌</span>
          {{ procesandoMensaje }}
        </div>

        <!-- Si esta en automatización -->
        <template v-else-if="enAutomatizacion">
          <div class="consola-intro">
            Ejecutando robot de automatización en Playwright
          </div>
          <div
            v-for="(log, idx) in logsAutomatizacion"
            :key="idx"
            class="consola-linea py-2"
          >
            <div>
              <span class="linea-prefijo">› </span>
              <span class="linea-mensaje text-white">{{ log }}</span>
            </div>
          </div>
          <!-- Si sigue automatizando, show cursor blink -->
          <div v-if="automatizando" class="consola-procesando mt-2">
            <span class="cursor-blink">▌</span>
            Ejecutando...
          </div>
        </template>

        <!-- Sin problemas -->
        <div v-else-if="problemas.length === 0" class="consola-ok d-flex flex-column align-items-center justify-content-center text-center p-4">
          <i class="bi bi-check2-circle mb-3 text-success" style="font-size: 48px;"></i>
          <div class="mb-3 text-white">
            No se encontraron problemas en el archivo <strong>{{ fileName }}</strong>.
          </div>
          <button 
            class="btn btn-primary px-4 py-2 fw-bold d-flex align-items-center gap-2 border-0"
            style="background-color: var(--color-primary);"
            :disabled="automatizando"
            @click="empezarAutomatizacion"
          >
            <span v-if="automatizando" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            <i v-else class="bi bi-play-circle-fill"></i>
            <span>{{ automatizando ? 'Iniciando...' : 'Empezar automatización' }}</span>
          </button>
        </div>

        <!-- Lista de problemas -->
        <template v-else>
          <div class="consola-intro">
            Archivo: <span class="consola-filename">{{ fileName }}</span>
            — {{ problemas.length }} problema(s) encontrado(s)
          </div>
          <div
            v-for="(p, idx) in problemas"
            :key="idx"
            class="consola-linea py-2"
          >
            <div>
              <span class="linea-prefijo">› </span>
              <span class="linea-mensaje">{{ p.mensaje }}</span>
            </div>
          </div>
        </template>
      </div>
    </main>

  </div>
</template>

<style scoped>
/* ── Layout principal ── */
.validacion-container {
  display: flex;
  min-height: calc(100vh - 57px); /* descuenta el navbar */
  background-color: var(--color-white);
  color: var(--color-black);
  font-family: var(--font-body);
  position: relative;
}

/* ── Panel izquierdo ── */
.panel-checklist {
  width: 320px;
  min-width: 260px;
  padding: 48px 32px;
  border-right: 1px solid rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
}

.checklist-title {
  font-family: var(--font-title);
  font-size: 18px;
  font-weight: 500;
  color: var(--color-black);
  margin-bottom: 24px;
  letter-spacing: 0.5px;
}

.checklist-lista {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.checklist-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* Primera línea del check: icono + label */
.check-icono {
  font-size: 16px;
  margin-right: 10px;
}

.checklist-item > span,
.checklist-item > .check-label {
  display: inline;
}

/* La primera fila del item */
.checklist-item {
  font-size: 14px;
  line-height: 1.4;
}

/* Los span de icono y label están dentro del li, así que ajustamos */
.checklist-item .check-icono,
.checklist-item .check-label {
  vertical-align: middle;
}

/* Colores por estado */
.estado-pendiente .check-label { color: var(--color-mid-gray); }
.estado-pendiente .check-icono { color: var(--color-mid-gray); }

.estado-revisando .check-label { color: var(--color-primary); }
.estado-revisando .check-icono { color: var(--color-primary); }

.estado-ok .check-label { color: #1e7e53; }
.estado-ok .check-icono { color: #1e7e53; }

.estado-error .check-label { color: #d93025; }
.estado-error .check-icono { color: #d93025; }

/* Sub-lista de errores clicables */
.sub-errores {
  list-style: none;
  padding: 4px 0 0 24px;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sub-error-item {
  font-size: 12px;
  color: #d93025;
  opacity: 0.85;
}

.sub-error-item.clickeable {
  cursor: pointer;
  transition: opacity 0.15s;
}
.sub-error-item.clickeable:hover {
  opacity: 1;
  text-decoration: underline;
}

/* Animación spinner */
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
.spin {
  display: inline-block;
  animation: spin 0.8s linear infinite;
}

/* Acciones container en sidebar */
.actions-container {
  margin-top: auto;
  display: flex;
  flex-direction: column;
}

/* Botón volver */
.btn-volver {
  font-size: 14px;
  color: var(--color-accent);
  border-color: var(--color-accent);
  background: transparent;
}
.btn-volver:hover {
  background: rgba(255,255,255,0.08);
  color: var(--color-white);
  border-color: var(--color-white);
}

/* ── Panel derecho: consola ── */
.panel-consola {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 48px 40px;
}

.consola-header {
  font-family: var(--font-title);
  font-size: 15px;
  font-weight: 500;
  color: var(--color-white);
  padding: 10px 16px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  border-radius: 8px 8px 0 0;
  background: #1e293b; /* Slate 800 */
  display: flex;
  align-items: center;
}

.consola-cuerpo {
  flex: 1;
  border: 1px solid rgba(0, 0, 0, 0.15);
  border-top: none;
  border-radius: 0 0 8px 8px;
  background: #0f172a; /* Slate 900 dark bg */
  padding: 20px 24px;
  min-height: 320px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  overflow-y: auto;
}

/* Procesando */
.consola-procesando {
  color: #6db3f2;
  display: flex;
  align-items: center;
  gap: 8px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #6db3f2;
}

/* Sin errores */
.consola-ok {
  color: #4caf82;
  font-size: 14px;
}

/* Intro */
.consola-intro {
  color: var(--color-accent);
  margin-bottom: 16px;
  font-size: 12px;
}
.consola-filename {
  color: var(--color-white);
  font-weight: bold;
}

/* Líneas de problemas */
.consola-linea {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  color: var(--color-secondary);
}

.consola-linea:last-child {
  border-bottom: none;
}

.linea-clickeable {
  cursor: pointer;
  transition: background 0.15s;
  border-radius: 4px;
  padding: 6px 4px;
}
.linea-clickeable:hover {
  background: rgba(255, 255, 255, 0.06);
}

.linea-prefijo { color: var(--color-accent); }
.linea-fila    { color: var(--color-white); font-weight: bold; }
.linea-mensaje { color: var(--color-secondary); flex: 1; }

.linea-badge-sugerencia {
  font-size: 11px;
  background: rgba(168, 183, 199, 0.2);
  color: #f5d76e;
  border: 1px solid rgba(245, 215, 110, 0.4);
  border-radius: 4px;
  padding: 2px 8px;
  white-space: nowrap;
}

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 19, 45, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  background: #141e38;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  width: 480px;
  max-width: 90vw;
  box-shadow: 0 24px 60px rgba(0,0,0,0.5);
}

.modal-box-header {
  padding: 18px 24px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  font-family: var(--font-title);
  font-size: 16px;
  color: var(--color-white);
  display: flex;
  align-items: center;
}

.modal-box-body {
  padding: 24px;
}

.modal-campo-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--color-mid-gray);
  margin-bottom: 4px;
}

.modal-campo-valor {
  font-size: 15px;
  font-weight: 500;
  margin-bottom: 0;
}

.error-text { color: var(--color-secondary); }
.ok-text    { color: #4caf82; }

.modal-nota {
  font-size: 12px;
  color: var(--color-mid-gray);
  margin-top: 12px;
  font-style: italic;
}

.modal-box-footer {
  padding: 16px 24px;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: flex;
  justify-content: flex-end;
}

/* Transición del modal */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>