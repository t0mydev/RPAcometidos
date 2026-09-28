<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ─── Estado de datos ──────────────────────────────────────────
const conductores = ref([])
const cargando    = ref(true)
const errorCarga  = ref('')

// ─── Búsqueda ─────────────────────────────────────────────────
const textoBusqueda = ref('')
const conductoresFiltrados = computed(() => {
  const q = textoBusqueda.value.trim().toLowerCase()
  if (!q) return conductores.value
  return conductores.value.filter(c =>
    c.rut.includes(q) ||
    c.nombre.toLowerCase().includes(q) ||
    c.sigla.toLowerCase().includes(q)
  )
})

// ─── Modal agregar / editar ───────────────────────────────────
const modalVisible    = ref(false)
const modoEdicion     = ref(false)          // false = agregar, true = editar
const rutOriginal     = ref('')             // RUT antes de la edición (para el endpoint PUT)
const guardandoModal  = ref(false)
const errorModal      = ref('')

const form = ref({ rut: '', nombre: '', sigla: '' })

function abrirModalAgregar() {
  modoEdicion.value   = false
  rutOriginal.value   = ''
  form.value          = { rut: '', nombre: '', sigla: '' }
  errorModal.value    = ''
  modalVisible.value  = true
}

function abrirModalEditar(conductor) {
  modoEdicion.value   = true
  rutOriginal.value   = conductor.rut
  form.value          = { rut: conductor.rut, nombre: conductor.nombre, sigla: conductor.sigla }
  errorModal.value    = ''
  modalVisible.value  = true
}

function cerrarModal() {
  if (guardandoModal.value) return   // no cerrar mientras guarda
  modalVisible.value = false
}

// ─── Modal de confirmación de eliminación ─────────────────────
const confirmVisible      = ref(false)
const eliminandoRut       = ref(null)     // registro a eliminar
const procesandoEliminar  = ref(false)

function pedirConfirmarEliminar(conductor) {
  eliminandoRut.value  = conductor
  confirmVisible.value = true
}

function cancelarEliminar() {
  confirmVisible.value = false
  eliminandoRut.value  = null
}

// ─── Carga inicial ────────────────────────────────────────────
onMounted(cargarDatos)

async function cargarDatos() {
  cargando.value   = true
  errorCarga.value = ''
  try {
    const res = await fetch('/api/datos-conocidos')
    if (!res.ok) throw new Error(`Error del servidor: ${res.status}`)
    const data = await res.json()
    conductores.value = data.datos || []
  } catch (e) {
    errorCarga.value = e.message
  } finally {
    cargando.value = false
  }
}

// ─── Guardar (agregar o editar) ───────────────────────────────
async function guardarConductor() {
  errorModal.value = ''

  // Validación básica en el frontend
  const rut    = form.value.rut.trim()
  const nombre = form.value.nombre.trim()
  const sigla  = form.value.sigla.trim()

  if (!rut || !nombre || !sigla) {
    errorModal.value = 'Todos los campos son obligatorios.'
    return
  }

  guardandoModal.value = true
  try {
    let res
    if (modoEdicion.value) {
      // PUT — editar
      res = await fetch(`/api/datos-conocidos/${encodeURIComponent(rutOriginal.value)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rut, nombre, sigla })
      })
    } else {
      // POST — agregar
      res = await fetch('/api/datos-conocidos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rut, nombre, sigla })
      })
    }

    const data = await res.json()
    if (!res.ok) {
      errorModal.value = data.mensaje || 'Error inesperado.'
      return
    }

    modalVisible.value = false
    await cargarDatos()
  } catch (e) {
    errorModal.value = `Error de conexión: ${e.message}`
  } finally {
    guardandoModal.value = false
  }
}

// ─── Eliminar ─────────────────────────────────────────────────
async function confirmarEliminar() {
  if (!eliminandoRut.value) return
  procesandoEliminar.value = true
  try {
    const res = await fetch(`/api/datos-conocidos/${encodeURIComponent(eliminandoRut.value.rut)}`, {
      method: 'DELETE'
    })
    const data = await res.json()
    if (!res.ok) {
      alert(data.mensaje || 'No se pudo eliminar el registro.')
      return
    }
    confirmVisible.value = false
    eliminandoRut.value  = null
    await cargarDatos()
  } catch (e) {
    alert(`Error de conexión: ${e.message}`)
  } finally {
    procesandoEliminar.value = false
  }
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
        <button class="btn btn-outline-primary btn-sm btn-volver" @click="volverAlInicio">
          <i class="bi bi-arrow-left me-1"></i> Volver
        </button>
        <div class="header-texto">
          <h1 class="edicion-titulo">Padrón de Conductores</h1>
          <p class="edicion-subtitulo">
            Gestiona los RUT, nombres y matrículas utilizados por el sistema de validación.
          </p>
        </div>
      </div>
      <button class="btn btn-primary btn-agregar" @click="abrirModalAgregar">
        <i class="bi bi-person-fill-add me-2"></i>Agregar conductor
      </button>
    </div>

    <!-- ── Barra de búsqueda ── -->
    <div class="barra-busqueda">
      <i class="bi bi-search busqueda-icono"></i>
      <input
        v-model="textoBusqueda"
        type="text"
        class="busqueda-input"
        placeholder="Buscar por RUT, nombre o matrícula..."
      />
    </div>

    <!-- ── Estado: cargando ── -->
    <div v-if="cargando" class="estado-mensaje">
      <div class="spinner-border text-primary" role="status"></div>
      <span class="ms-3 text-mid-gray">Cargando datos...</span>
    </div>

    <!-- ── Estado: error de carga ── -->
    <div v-else-if="errorCarga" class="alert alert-danger d-flex align-items-center gap-2 mt-4">
      <i class="bi bi-exclamation-triangle-fill"></i>
      <span>No se pudo conectar con el servidor: <strong>{{ errorCarga }}</strong></span>
    </div>

    <!-- ── Tabla de conductores ── -->
    <div v-else class="tabla-wrapper">
      <p v-if="conductoresFiltrados.length === 0" class="tabla-vacia">
        <i class="bi bi-inbox me-2"></i>
        {{ textoBusqueda ? 'Sin resultados para la búsqueda.' : 'No hay conductores registrados.' }}
      </p>

      <table v-else class="tabla-conductores">
        <thead>
          <tr>
            <th class="col-rut">RUT</th>
            <th class="col-nombre">Nombre</th>
            <th class="col-sigla">Matrícula</th>
            <th class="col-acciones">Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(c, idx) in conductoresFiltrados" :key="c.rut" :class="{ 'fila-par': idx % 2 === 0 }">
            <td class="col-rut">
              <span class="badge-rut">{{ c.rut }}</span>
            </td>
            <td class="col-nombre">{{ c.nombre }}</td>
            <td class="col-sigla">
              <span class="badge-sigla">{{ c.sigla }}</span>
            </td>
            <td class="col-acciones">
              <div class="acciones-grupo">
                <button
                  class="btn btn-outline-primary btn-accion"
                  title="Editar conductor"
                  @click="abrirModalEditar(c)"
                >
                  <i class="bi bi-pencil-fill"></i>
                </button>
                <button
                  class="btn btn-outline-danger btn-accion"
                  title="Eliminar conductor"
                  @click="pedirConfirmarEliminar(c)"
                >
                  <i class="bi bi-trash3-fill"></i>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <p class="tabla-contador">
        {{ conductoresFiltrados.length }} de {{ conductores.length }} conductor(es)
      </p>
    </div>


    <!-- ════════════════════════════════════════════════════════ -->
    <!-- Modal Agregar / Editar                                   -->
    <!-- ════════════════════════════════════════════════════════ -->
    <Teleport to="body">
      <div v-if="modalVisible" class="modal-overlay" @click.self="cerrarModal">
        <div class="modal-panel ui-card">

          <!-- Cabecera del modal -->
          <div class="modal-cabecera">
            <h2 class="modal-titulo">
              <i :class="modoEdicion ? 'bi bi-pencil-square' : 'bi bi-person-fill-add'" class="me-2"></i>
              {{ modoEdicion ? 'Editar conductor' : 'Nuevo conductor' }}
            </h2>
            <button class="btn-cerrar-modal" @click="cerrarModal" :disabled="guardandoModal">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>

          <!-- Cuerpo: formulario -->
          <div class="modal-cuerpo">
            <div class="campo-grupo">
              <label :for="'modal-rut'">RUT <span class="campo-requerido">*</span></label>
              <input
                id="modal-rut"
                v-model="form.rut"
                type="text"
                class="form-control"
                placeholder="Ej: 12345678"
                :disabled="guardandoModal"
              />
              <span class="campo-hint">Sin puntos ni dígito verificador</span>
            </div>

            <div class="campo-grupo">
              <label :for="'modal-nombre'">Nombre completo <span class="campo-requerido">*</span></label>
              <input
                id="modal-nombre"
                v-model="form.nombre"
                type="text"
                class="form-control"
                placeholder="Ej: JUAN PÉREZ"
                :disabled="guardandoModal"
              />
            </div>

            <div class="campo-grupo">
              <label :for="'modal-sigla'">Matrícula (sigla) <span class="campo-requerido">*</span></label>
              <input
                id="modal-sigla"
                v-model="form.sigla"
                type="text"
                class="form-control"
                placeholder="Ej: 5F-KDMA-1557"
                :disabled="guardandoModal"
              />
            </div>

            <!-- Error del modal -->
            <div v-if="errorModal" class="modal-error">
              <i class="bi bi-exclamation-circle-fill me-2"></i>{{ errorModal }}
            </div>
          </div>

          <!-- Pie: botones -->
          <div class="modal-pie">
            <button class="btn btn-outline-primary" @click="cerrarModal" :disabled="guardandoModal">
              Cancelar
            </button>
            <button class="btn btn-primary" @click="guardarConductor" :disabled="guardandoModal">
              <span v-if="guardandoModal" class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
              <i v-else :class="modoEdicion ? 'bi bi-floppy-fill' : 'bi bi-plus-circle-fill'" class="me-1"></i>
              {{ guardandoModal ? 'Guardando...' : modoEdicion ? 'Guardar cambios' : 'Agregar' }}
            </button>
          </div>

        </div>
      </div>
    </Teleport>


    <!-- ════════════════════════════════════════════════════════ -->
    <!-- Modal Confirmación de Eliminación                        -->
    <!-- ════════════════════════════════════════════════════════ -->
    <Teleport to="body">
      <div v-if="confirmVisible" class="modal-overlay" @click.self="cancelarEliminar">
        <div class="modal-panel modal-panel--sm ui-card">

          <div class="modal-cabecera">
            <h2 class="modal-titulo text-danger">
              <i class="bi bi-exclamation-triangle-fill me-2"></i>Confirmar eliminación
            </h2>
            <button class="btn-cerrar-modal" @click="cancelarEliminar" :disabled="procesandoEliminar">
              <i class="bi bi-x-lg"></i>
            </button>
          </div>

          <div class="modal-cuerpo" v-if="eliminandoRut">
            <p class="mb-1">¿Estás seguro de eliminar al siguiente conductor?</p>
            <div class="confirm-detalle">
              <span class="badge-rut">{{ eliminandoRut.rut }}</span>
              <strong class="ms-2">{{ eliminandoRut.nombre }}</strong>
              <span class="badge-sigla ms-2">{{ eliminandoRut.sigla }}</span>
            </div>
            <p class="confirm-advertencia">Esta acción no se puede deshacer.</p>
          </div>

          <div class="modal-pie">
            <button class="btn btn-outline-primary" @click="cancelarEliminar" :disabled="procesandoEliminar">
              Cancelar
            </button>
            <button class="btn btn-danger" @click="confirmarEliminar" :disabled="procesandoEliminar">
              <span v-if="procesandoEliminar" class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
              <i v-else class="bi bi-trash3-fill me-1"></i>
              {{ procesandoEliminar ? 'Eliminando...' : 'Sí, eliminar' }}
            </button>
          </div>

        </div>
      </div>
    </Teleport>

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
  align-items: flex-start;
  gap: 16px;
}

.btn-volver {
  margin-top: 8px;
  white-space: nowrap;
  flex-shrink: 0;
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
  max-width: 520px;
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

/* ── Tabla ── */
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

.tabla-conductores {
  width: 100%;
  border-collapse: collapse;
}

.tabla-conductores thead tr {
  background-color: var(--color-tertiary);
  color: var(--color-white);
}

.tabla-conductores th {
  padding: 14px 20px;
  font-family: var(--font-title);
  font-weight: 500;
  font-size: 13px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.tabla-conductores td {
  padding: 14px 20px;
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
.col-rut      { width: 140px; }
.col-nombre   { min-width: 200px; }
.col-sigla    { width: 160px; }
.col-acciones { width: 110px; text-align: center; }

/* Badges */
.badge-rut {
  display: inline-block;
  background-color: #eaf3ff;
  color: var(--color-primary);
  border: 1px solid #b3d4f0;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.3px;
  font-family: 'Courier New', monospace;
}

.badge-sigla {
  display: inline-block;
  background-color: #f0f4f8;
  color: var(--color-dark-gray);
  border: 1px solid #d0dae3;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  font-family: 'Courier New', monospace;
}

/* Acciones */
.acciones-grupo {
  display: flex;
  gap: 6px;
  justify-content: center;
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

/* ════════════════════════════════════════════════════════ */
/* Modales                                                  */
/* ════════════════════════════════════════════════════════ */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 19, 45, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.modal-panel {
  width: 100%;
  max-width: 480px;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
  overflow: hidden;
  box-shadow: 0 16px 48px rgba(10, 19, 45, 0.22);
}

.modal-panel--sm {
  max-width: 420px;
}

/* Cabecera */
.modal-cabecera {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--color-neutral);
}

.modal-titulo {
  font-family: var(--font-title);
  font-size: 18px;
  font-weight: 500;
  color: var(--color-black);
  margin: 0;
}

.btn-cerrar-modal {
  background: none;
  border: none;
  color: var(--color-mid-gray);
  font-size: 16px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  line-height: 1;
  transition: color 0.15s;
}

.btn-cerrar-modal:hover {
  color: var(--color-black);
}

/* Cuerpo */
.modal-cuerpo {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.campo-grupo {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.campo-grupo label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-dark-gray);
}

.campo-requerido {
  color: var(--color-secondary);
  margin-left: 2px;
}

.campo-hint {
  font-size: 11px;
  color: var(--color-mid-gray);
  margin-top: 2px;
}

.modal-error {
  background-color: #fff0f0;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  color: #b91c1c;
  font-size: 13px;
  padding: 10px 14px;
}

/* Detalle confirm */
.confirm-detalle {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  background-color: #f5f7fa;
  border: 1px solid var(--color-neutral);
  border-radius: 8px;
  padding: 12px 16px;
  margin-top: 8px;
}

.confirm-advertencia {
  font-size: 13px;
  color: var(--color-mid-gray);
  margin: 4px 0 0;
}

/* Pie */
.modal-pie {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--color-neutral);
}
</style>
