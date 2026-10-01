<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  filas: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['avanzar-reporte', 'cancelar'])

// ─── Sub-Stepper de 5 pasos del RPA ───────────────────────────
const subPasos = [
  { id: 1, label: 'Validación de datos en planilla Excel' },
  { id: 2, label: 'Ingreso de datos Portal SSD' },
  { id: 3, label: 'Ingreso de datos Portal Personal' },
  { id: 4, label: 'Ingreso de datos Portal Firmador' },
  { id: 5, label: 'Fin' },
]

const pasoActual = ref(2) // Paso 1 completado al entrar aquí
const automatizando = ref(true)
const completadoExitoso = ref(false)
const huboError = ref(false)
const mensajeEstado = ref('El bot está procesando los cometidos en segundo plano.\nEste proceso puede tardar varios minutos.')

// ─── Consola / Logs ───────────────────────────────────────────
const logsAutomatizacion = ref([])
const consolaCuerpoRef = ref(null)
let intervaloProgreso = null
const ultimoPasoRegistrado = ref(-1)
const ultimoMensajeRegistrado = ref('')

async function agregarLog(msg) {
  logsAutomatizacion.value.push(msg)
  await nextTick()
  if (consolaCuerpoRef.value) {
    consolaCuerpoRef.value.scrollTop = consolaCuerpoRef.value.scrollHeight
  }
}

// ─── Actualizar Sub-Paso según el texto del log ───────────────
function actualizarSubPasoPorDetalle(detalle) {
  if (!detalle) return
  const txt = String(detalle).toLowerCase()
  if (txt.includes('ssd')) {
    pasoActual.value = 2
  } else if (txt.includes('personal') || txt.includes('cometido') || txt.includes('formulario')) {
    pasoActual.value = 3
  } else if (txt.includes('firmador') || txt.includes('firma')) {
    pasoActual.value = 4
  }
}

// ─── Monitoreo de Progreso (Polling) ─────────────────────────
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
        pasoActual.value = 2
      } else if (data.estado === 'ejecutando') {
        if (data.paso !== ultimoPasoRegistrado.value) {
          ultimoPasoRegistrado.value = data.paso
          await agregarLog(`Cometido ${data.paso} de ${data.total}: Procesando ${data.nombre || ''}`)
        }

        if (data.detalle && ultimoMensajeRegistrado.value !== data.detalle) {
          ultimoMensajeRegistrado.value = data.detalle
          await agregarLog(data.detalle)
          actualizarSubPasoPorDetalle(data.detalle)
        }
      } else if (data.estado === 'completado') {
        await agregarLog('¡Automatización finalizada exitosamente!')
        detenerMonitoreoProgreso()
        pasoActual.value = 5
        automatizando.value = false
        completadoExitoso.value = true
        mensajeEstado.value = '¡Automatización finalizada con éxito! Ya puedes ver el reporte final.'
      } else if (data.estado === 'error') {
        const errDesc = data.nombre || 'Desconocido'
        await agregarLog(`Error durante la automatización: ${errDesc}`)
        detenerMonitoreoProgreso()
        automatizando.value = false
        huboError.value = true
        mensajeEstado.value = `Ocurrió un error en el proceso: ${errDesc}`
      }
    } catch (e) {
      console.error('Error al consultar progreso:', e)
    }
  }, 1000)
}

function detenerMonitoreoProgreso() {
  if (intervaloProgreso) {
    clearInterval(intervaloProgreso)
    intervaloProgreso = null
  }
}

// ─── Iniciar Ejecución al montar el componente ────────────────
async function iniciarEjecucion() {
  automatizando.value = true
  completadoExitoso.value = false
  huboError.value = false
  logsAutomatizacion.value = []
  pasoActual.value = 2

  await agregarLog('Iniciando el motor de automatización...')

  try {
    const payload = props.filas.map(f => ({
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
      body: JSON.stringify(payload),
    })

    if (!resp.ok) throw new Error(`El servidor respondió con estado ${resp.status}`)

    const data = await resp.json()
    if (data.status === 'iniciado') {
      comenzarMonitoreoProgreso()
    } else {
      await agregarLog(`Error al iniciar: ${data.mensaje}`)
      automatizando.value = false
      huboError.value = true
    }
  } catch (e) {
    await agregarLog(`Error de conexión: ${e.message}`)
    automatizando.value = false
    huboError.value = true
  }
}

// ─── Botonería de Control ─────────────────────────────────────
function irAlReporte() {
  emit('avanzar-reporte')
}

function cancelarAutomatizacion() {
  const confirmacion = window.confirm('¿Estás seguro de que deseas cancelar la automatización en curso?')
  if (!confirmacion) return

  detenerMonitoreoProgreso()
  automatizando.value = false
  emit('cancelar')
}

onMounted(() => {
  iniciarEjecucion()
})

onUnmounted(() => {
  detenerMonitoreoProgreso()
})
</script>

<template>
  <div class="etapa2-contenedor">
    <!-- 1. Título principal -->
    <div class="etapa2-encabezado">
      <h2 class="etapa2-titulo">Seguimiento de Automatización</h2>
    </div>

    <!-- 2. Sub-Stepper de 5 pasos del RPA -->
    <div class="substepper-wrapper">
      <div class="substepper-inner">
        <template v-for="(paso, index) in subPasos" :key="paso.id">
          <!-- Item del Paso -->
          <div
            class="subpaso-item"
            :class="{
              'subpaso--activo': pasoActual === paso.id && !completadoExitoso,
              'subpaso--completado': pasoActual > paso.id || (completadoExitoso && paso.id === 5),
              'subpaso--pendiente': pasoActual < paso.id,
            }"
          >
            <div class="subpaso-circulo">
              <i v-if="pasoActual > paso.id || (completadoExitoso && paso.id === 5)" class="bi bi-check-lg"></i>
              <span v-else>{{ paso.id }}</span>
            </div>
            <span class="subpaso-label">{{ paso.label }}</span>
          </div>

          <!-- Línea conectora entre sub-pasos -->
          <div
            v-if="index < subPasos.length - 1"
            class="subpaso-linea"
            :class="{ 'sublinea--completa': pasoActual > paso.id || completadoExitoso }"
          ></div>
        </template>
      </div>
    </div>

    <!-- 3. Indicador de carga (Círculo de procesamiento) y Estado -->
    <div class="estado-procesamiento">
      <div v-if="automatizando" class="spinner-border text-primary spinner-procesamiento" role="status">
        <span class="visually-hidden">Procesando...</span>
      </div>
      <div v-else-if="completadoExitoso" class="icono-exito-contenedor">
        <i class="bi bi-check-circle-fill icono-exito"></i>
      </div>
      <div v-else-if="huboError" class="icono-error-contenedor">
        <i class="bi bi-exclamation-triangle-fill icono-error"></i>
      </div>

      <p class="estado-mensaje">{{ mensajeEstado }}</p>
    </div>

    <!-- 4. Botón "Ir al reporte final" (Centrado arriba de la terminal) -->
    <div class="accion-reporte-zona">
      <button
        class="btn btn-primary btn-reporte"
        :disabled="!completadoExitoso"
        @click="irAlReporte"
      >
        <i class="bi bi-file-earmark-bar-graph me-2"></i>
        Ir al reporte final
        <i class="bi bi-arrow-right ms-2"></i>
      </button>
    </div>

    <!-- 5. Consola / Terminal de Procesos Responsiva -->
    <div class="consola-wrapper">
      <div class="consola-panel">
        <div class="consola-header">
          <div class="d-flex align-items-center">
            <i class="bi bi-terminal-fill me-2 text-primary"></i>
            <span class="fw-semibold">Consola de procesos</span>
            <span v-if="automatizando" class="cursor-blink ms-2">▌</span>
          </div>
          <span class="consola-badge" :class="{ 'badge-activa': automatizando, 'badge-fin': completadoExitoso }">
            {{ automatizando ? 'En ejecución' : (completadoExitoso ? 'Finalizado' : 'Detenido') }}
          </span>
        </div>

        <div class="consola-cuerpo" ref="consolaCuerpoRef">
          <div
            v-for="(log, idx) in logsAutomatizacion"
            :key="idx"
            class="consola-linea"
          >
            <span class="consola-prefijo">›</span>
            <span>{{ log }}</span>
          </div>
          <div v-if="automatizando" class="consola-linea consola-linea--activo">
            <span class="cursor-blink">▌</span> Procesando bot en segundo plano...
          </div>
          <div v-if="logsAutomatizacion.length === 0" class="text-muted small">
            Esperando eventos de Playwright...
          </div>
        </div>
      </div>
    </div>

    <!-- 6. Botón "Cancelar Automatización" (Fijo / Alineado abajo a la derecha) -->
    <div class="cancelar-zona">
      <button
        v-if="automatizando"
        class="btn btn-outline-danger btn-cancelar"
        @click="cancelarAutomatizacion"
      >
        <i class="bi bi-x-circle me-1"></i>
        Cancelar Automatización
      </button>
    </div>
  </div>
</template>

<style scoped>
.etapa2-contenedor {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 24px 48px;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  position: relative;
  min-height: calc(100vh - 140px);
  box-sizing: border-box;
}

/* ── 1. Encabezado ── */
.etapa2-encabezado {
  text-align: center;
  margin-bottom: 24px;
}

.etapa2-titulo {
  font-family: var(--font-title);
  font-size: 26px;
  font-weight: 700;
  color: var(--color-black);
  margin: 0;
}

/* ── 2. Sub-Stepper de 5 pasos ── */
.substepper-wrapper {
  width: 100%;
  max-width: 950px;
  margin-bottom: 24px;
  padding: 0 12px;
}

.substepper-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
}

.subpaso-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  width: 140px;
  flex-shrink: 0;
  z-index: 2;
}

.subpaso-circulo {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
  border: 2px solid #cbd5e1;
  background-color: var(--color-white);
  color: var(--color-mid-gray);
  transition: all 0.3s ease;
  margin-bottom: 8px;
}

.subpaso-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-dark-gray);
  line-height: 1.25;
  transition: color 0.3s ease;
}

/* Estados del sub-paso */
.subpaso--activo .subpaso-circulo {
  border-color: var(--color-primary);
  background-color: var(--color-primary);
  color: var(--color-white);
  box-shadow: 0 0 0 4px rgba(0, 111, 179, 0.2);
}

.subpaso--activo .subpaso-label {
  color: var(--color-primary);
  font-weight: 700;
}

.subpaso--completado .subpaso-circulo {
  border-color: #059669;
  background-color: #059669;
  color: var(--color-white);
}

.subpaso--completado .subpaso-label {
  color: #065f46;
  font-weight: 600;
}

.subpaso--pendiente .subpaso-circulo {
  background-color: #f8fafc;
  color: #94a3b8;
}

/* Línea conectora entre sub-pasos */
.subpaso-linea {
  flex: 1;
  height: 3px;
  background-color: #e2e8f0;
  margin: 0 4px;
  margin-bottom: 28px;
  transition: background-color 0.3s ease;
  z-index: 1;
}

.sublinea--completa {
  background-color: #059669;
}

/* ── 3. Estado y Spinner ── */
.estado-procesamiento {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  margin-bottom: 20px;
}

.spinner-procesamiento {
  width: 3rem;
  height: 3rem;
  border-width: 0.25rem;
  margin-bottom: 12px;
}

.icono-exito {
  font-size: 42px;
  color: #059669;
  margin-bottom: 8px;
}

.icono-error {
  font-size: 42px;
  color: #dc2626;
  margin-bottom: 8px;
}

.estado-mensaje {
  font-size: 14px;
  color: var(--color-dark-gray);
  margin: 0;
  white-space: pre-line;
}

/* ── 4. Botón Reporte Final ── */
.accion-reporte-zona {
  margin-bottom: 24px;
}

.btn-reporte {
  padding: 12px 32px;
  font-size: 15px;
  font-weight: 700;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.2s ease;
}

.btn-reporte:not(:disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0, 111, 179, 0.35);
}

.btn-reporte:disabled {
  background-color: #e2e8f0;
  border-color: #cbd5e1;
  color: #94a3b8;
  cursor: not-allowed;
  box-shadow: none;
}

/* ── 5. Consola / Terminal ── */
.consola-wrapper {
  width: 100%;
  max-width: 900px;
  margin-bottom: 32px;
}

.consola-panel {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #1e293b;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.consola-header {
  background-color: #1e293b;
  color: #f8fafc;
  padding: 10px 16px;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.consola-badge {
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

.consola-cuerpo {
  background-color: #0b1329;
  padding: 16px 20px;
  min-height: 180px;
  max-height: 280px;
  overflow-y: auto;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
}

.consola-linea {
  color: #94a3b8;
  display: flex;
  gap: 8px;
  padding: 3px 0;
  line-height: 1.4;
  word-break: break-word;
}

.consola-prefijo {
  color: #38bdf8;
  font-weight: bold;
}

.consola-linea--activo {
  color: #38bdf8;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #38bdf8;
}

/* ── 6. Botón Cancelar (Abajo a la derecha) ── */
.cancelar-zona {
  width: 100%;
  max-width: 900px;
  display: flex;
  justify-content: flex-end;
}

.btn-cancelar {
  font-size: 13px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 6px;
  transition: all 0.2s ease;
}

/* Responsividad para pantallas grandes y medianas */
@media (max-width: 768px) {
  .substepper-inner {
    flex-wrap: wrap;
    gap: 12px;
    justify-content: center;
  }
  .subpaso-linea {
    display: none;
  }
  .subpaso-item {
    width: 100px;
  }
}
</style>
