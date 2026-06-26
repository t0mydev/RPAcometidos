<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ─── Estado general ───────────────────────────────────────────
const fileName = ref(history.state?.fileName || 'archivo.xlsx')
const checks = ref([
  { id: 'nombres',  label: 'Revisando nombres...',          estado: 'pendiente' },
  { id: 'rut',      label: 'Revisando RUT...',              estado: 'pendiente' },
  { id: 'patente',  label: 'Revisando Patente vehículo...', estado: 'pendiente' },
])
const problemas = ref([])        // lista de errores con meta para el modal
const procesando = ref(true)
const procesandoMensaje = ref('Enviando archivo al servidor...')

// ─── Modal de sugerencia ──────────────────────────────────────
const modalVisible = ref(false)
const modalProblema = ref(null)  // el problema seleccionado

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
  const camposCheck = ['nombre', 'rut', 'patente']

  for (let i = 0; i < checks.value.length; i++) {
    checks.value[i].estado = 'revisando'
    await delay(900)

    const campo = camposCheck[i]
    // Buscar si hay algún error en ese campo en cualquier fila
    const erroresCampo = []
    for (const fila of resultados) {
      const esCampoValido = fila[`${campo}_valido`]
      const erroresFila = fila.errores || []

      if (esCampoValido === false) {
        const mensajeError = erroresFila.find(e =>
          e.toLowerCase().includes(campo === 'rut' ? 'rut' : campo === 'patente' ? 'patente' : 'nombre')
        )
        erroresCampo.push({
          fila: fila.numero_fila_excel,
          campo,
          mensaje: mensajeError || `Fila ${fila.numero_fila_excel}: ${campo} inválido.`,
          sugerencia: campo === 'nombre' ? fila.sugerencia_correccion_nombre : null,
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

// ─── Abrir modal de sugerencia ────────────────────────────────
function abrirSugerencia(problema) {
  modalProblema.value = problema
  modalVisible.value = true
}

function cerrarModal() {
  modalVisible.value = false
  modalProblema.value = null
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
              class="sub-error-item clickeable"
              @click="abrirSugerencia(err)"
            >
              <i class="bi bi-chevron-right me-1"></i>
              <span>Fila {{ err.fila }}: ver detalle</span>
            </li>
          </ul>
        </li>
      </ul>

      <!-- Botón volver -->
      <button class="btn btn-outline-primary btn-volver mt-4" @click="volverAlInicio">
        <i class="bi bi-arrow-left me-2"></i>Volver al inicio
      </button>
    </aside>

    <!-- ── Panel derecho: Consola de problemas ── -->
    <main class="panel-consola">
      <div class="consola-header">
        <i class="bi bi-terminal-fill me-2"></i>
        Problemas Específicos Identificados:
      </div>

      <div class="consola-cuerpo">
        <!-- Estado: procesando -->
        <div v-if="procesando" class="consola-procesando">
          <span class="cursor-blink">▌</span>
          {{ procesandoMensaje }}
        </div>

        <!-- Sin problemas -->
        <div v-else-if="problemas.length === 0" class="consola-ok">
          <i class="bi bi-check2-circle me-2"></i>
          No se encontraron problemas en el archivo <strong>{{ fileName }}</strong>.
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
            class="consola-linea"
            :class="{ 'linea-clickeable': p.sugerencia }"
            @click="p.sugerencia ? abrirSugerencia(p) : null"
          >
            <span class="linea-prefijo">› </span>
            <span class="linea-fila">[Fila {{ p.fila }}]</span>
            <span class="linea-mensaje">{{ p.mensaje }}</span>
            <span v-if="p.sugerencia" class="linea-badge-sugerencia">
              <i class="bi bi-lightbulb-fill me-1"></i>Sugerencia disponible
            </span>
          </div>
        </template>
      </div>
    </main>

    <!-- ── Modal de sugerencia ── -->
    <Transition name="modal-fade">
      <div v-if="modalVisible" class="modal-overlay" @click.self="cerrarModal">
        <div class="modal-box">
          <div class="modal-box-header">
            <i class="bi bi-lightbulb-fill me-2 text-warning"></i>
            Sugerencia de corrección
          </div>
          <div class="modal-box-body" v-if="modalProblema">
            <p class="modal-campo-label">Campo con problema:</p>
            <p class="modal-campo-valor error-text">{{ modalProblema.mensaje }}</p>

            <template v-if="modalProblema.sugerencia">
              <p class="modal-campo-label mt-3">Posible corrección:</p>
              <p class="modal-campo-valor ok-text">
                <i class="bi bi-arrow-right-circle-fill me-2"></i>
                {{ modalProblema.sugerencia }}
              </p>
              <p class="modal-nota">
                Esta sugerencia proviene de los registros conocidos. Verifica antes de aplicar.
              </p>
            </template>
            <template v-else>
              <p class="modal-nota mt-3">No se encontró una sugerencia automática para este campo.</p>
            </template>
          </div>
          <div class="modal-box-footer">
            <button class="btn btn-primary px-4" @click="cerrarModal">Entendido</button>
          </div>
        </div>
      </div>
    </Transition>

  </div>
</template>

<style scoped>
/* ── Layout principal ── */
.validacion-container {
  display: flex;
  min-height: calc(100vh - 57px); /* descuenta el navbar */
  background-color: var(--color-tertiary);
  color: var(--color-white);
  font-family: var(--font-body);
  position: relative;
}

/* ── Panel izquierdo ── */
.panel-checklist {
  width: 320px;
  min-width: 260px;
  padding: 48px 32px;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
}

.checklist-title {
  font-family: var(--font-title);
  font-size: 18px;
  font-weight: 500;
  color: var(--color-white);
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

.estado-revisando .check-label { color: #6db3f2; }
.estado-revisando .check-icono { color: #6db3f2; }

.estado-ok .check-label { color: #4caf82; }
.estado-ok .check-icono { color: #4caf82; }

.estado-error .check-label { color: var(--color-secondary); }
.estado-error .check-icono { color: var(--color-secondary); }

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
  color: var(--color-secondary);
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

/* Botón volver */
.btn-volver {
  margin-top: auto;
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
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 8px 8px 0 0;
  background: rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
}

.consola-cuerpo {
  flex: 1;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-top: none;
  border-radius: 0 0 8px 8px;
  background: rgba(0, 0, 0, 0.25);
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