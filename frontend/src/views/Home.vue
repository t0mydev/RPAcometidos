<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
const router = useRouter()

// ─── Estado del archivo ───────────────────────────────────────
const isDragging = ref(false)
const selectedFile = ref(null)

// ─── Estado del panel de Cuentas ─────────────────────────────
const menuAbierto = ref(false)
const mostrarConfirmacion = ref(false)
const guardando = ref(false)

// Cada portal tiene su ID para el JSON, nombre, usuario, contraseña y flags de edición
const portales = ref([
  {
    id: 'cometidos',
    nombre: 'Portal de Cometidos',
    usuario: '',
    contrasena: '',
    editandoUsuario: false,
    editandoContrasena: false,
    ingresandoUsuario: false,
    ingresandoContrasena: false,
    verContrasena: false,
  },
  {
    id: 'ssd',
    nombre: 'Portal SSD',
    usuario: '',
    contrasena: '',
    editandoUsuario: false,
    editandoContrasena: false,
    ingresandoUsuario: false,
    ingresandoContrasena: false,
    verContrasena: false,
  },
  {
    id: 'firmador',
    nombre: 'Portal Firmador',
    usuario: '',
    contrasena: '',
    editandoUsuario: false,
    editandoContrasena: false,
    ingresandoUsuario: false,
    ingresandoContrasena: false,
    verContrasena: false,
  },
])

// Cargar credenciales guardadas al iniciar la vista
onMounted(async () => {
  try {
    const res = await fetch('/api/obtener-credenciales')
    if (res.ok) {
      const data = await res.json()
      if (data.status === 'completado' && data.credenciales) {
        portales.value.forEach(p => {
          if (data.credenciales[p.id]) {
            p.usuario = data.credenciales[p.id].usuario || ''
            p.contrasena = data.credenciales[p.id].clave || ''
          }
        })
      }
    }
  } catch (error) {
    console.error('No se pudieron cargar las credenciales previas:', error)
  }
})

// Alternar apertura del panel
const toggleMenu = () => {
  menuAbierto.value = !menuAbierto.value
  mostrarConfirmacion.value = false
}

// Habilitar edición de un campo que ya tiene valor (botón ✏️)
const activarEdicionUsuario = (portal) => {
  portal.editandoUsuario = true
}
const activarEdicionContrasena = (portal) => {
  portal.editandoContrasena = true
}

// Un campo es editable si: está vacío Y el usuario está ingresando datos por primera vez,
// O si el usuario presionó el botón "Editar" (editando = true).
const usuarioEditable = (portal) => portal.usuario === '' || portal.ingresandoUsuario || portal.editandoUsuario
const contrasenaEditable = (portal) => portal.contrasena === '' || portal.ingresandoContrasena || portal.editandoContrasena

// Cuando el usuario hace foco en un campo vacío, marcamos que está ingresando
const enfocarUsuario = (portal) => {
  if (portal.usuario === '') 
    portal.ingresandoUsuario = true
}
const enfocarContrasena = (portal) => {
  if (portal.contrasena === '') portal.ingresandoContrasena = true
}

// Cuando el usuario sale del campo (blur o Enter), bloqueamos si tiene valor
const blurUsuario = (portal) => {
  portal.ingresandoUsuario = false
  portal.editandoUsuario = false
}
const blurContrasena = (portal) => {
  portal.ingresandoContrasena = false
  portal.editandoContrasena = false
}

// Al guardar: bloquea campos y envía el JSON a Flask para crear credenciales.json
const guardarCuentas = async () => {
  guardando.value = true
  
  // Estructura de credenciales que leen los robots de Python
  const credencialesJSON = {}
  portales.value.forEach((p) => {
    credencialesJSON[p.id] = {
      usuario: p.usuario,
      clave: p.contrasena
    }
    p.editandoUsuario = false
    p.editandoContrasena = false
    p.verContrasena = false
  })

  try {
    const res = await fetch('/api/guardar-credenciales', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(credencialesJSON)
    })
    
    if (!res.ok) {
      throw new Error(`Error en el servidor: ${res.status}`)
    }
    
    menuAbierto.value = false
  } catch (error) {
    console.error('Error al guardar credenciales:', error)
  } finally {
    guardando.value = false
  }
}

// Solicitar confirmación antes de borrar
const pedirConfirmacion = () => {
  mostrarConfirmacion.value = true
}

// Borrar todas las cuentas (limpia en la vista y en el archivo credenciales.json)
const confirmarBorrado = async () => {
  const credencialesVacias = {}
  portales.value.forEach((p) => {
    p.usuario = ''
    p.contrasena = ''
    p.editandoUsuario = false
    p.editandoContrasena = false
    p.verContrasena = false
    credencialesVacias[p.id] = {
      usuario: '',
      clave: ''
    }
  })

  try {
    await fetch('/api/guardar-credenciales', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(credencialesVacias)
    })
  } catch (error) {
    console.error('Error al borrar credenciales en el backend:', error)
  }

  mostrarConfirmacion.value = false
}

const cancelarBorrado = () => {
  mostrarConfirmacion.value = false
}

// ─── Gestores del área de carga ──────────────────────────────
const handleDragOver = (e) => {
  e.preventDefault()
  isDragging.value = true
}

const handleDragLeave = () => {
  isDragging.value = false
}

const handleDrop = (e) => {
  e.preventDefault()
  isDragging.value = false
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    selectedFile.value = e.dataTransfer.files[0]
  }
}
// Gestor de selección manual de archivo
const handleFileSelect = (e) => {
  if (e.target.files && e.target.files.length > 0) {
    selectedFile.value = e.target.files[0]
  }
}

// Acción del botón principal
const handleProcess = () => {
  if (selectedFile.value) {
    router.push({
      name: 'ValidacionDatos',
      state: { fileName: selectedFile.value.name }
    })
    // Guardamos el archivo en memoria para recuperarlo en la otra vista
    window.__excelFile = selectedFile.value
  }
}
</script>

<template>
  <div class="home-container d-flex flex-column align-items-center justify-content-start">

    <!-- ─── Botón "Cuentas de Usuario" (esquina superior derecha) ─── -->
    <div class="cuentas-wrapper">
      <button class="btn btn-outline-primary btn-cuentas" @click="toggleMenu" id="btn-cuentas-usuario">
        <i class="bi bi-person-fill-gear me-2"></i>
        Cuentas de Usuario
        <i :class="menuAbierto ? 'bi bi-chevron-up ms-2' : 'bi bi-chevron-down ms-2'"></i>
      </button>

      <!-- Panel desplegable -->
      <div v-if="menuAbierto" class="cuentas-panel ui-card" id="panel-cuentas">

        <!-- Aviso de confirmación de borrado -->
        <div v-if="mostrarConfirmacion" class="confirmacion-box">
          <p class="mb-3 fw-bold text-danger">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            ¿Estás seguro de borrar todas las cuentas registradas?
          </p>
          <p class="mb-3 text-muted" style="font-size: 13px;">
            Esta acción eliminará los usuarios y contraseñas de los 3 portales y no se puede deshacer.
          </p>
          <div class="d-flex gap-2 justify-content-end">
            <button class="btn btn-sm btn-outline-primary" @click="cancelarBorrado">Cancelar</button>
            <button class="btn btn-sm btn-danger" @click="confirmarBorrado">Sí, borrar todo</button>
          </div>
        </div>

        <!-- Contenido normal del panel -->
        <template v-else>
          <!-- Sección por cada portal -->
          <div
            v-for="(portal, index) in portales"
            :key="index"
            class="portal-seccion"
            :class="{ 'portal-seccion--separador': index < portales.length - 1 }"
          >
            <h3 class="portal-titulo">{{ portal.nombre }}</h3>

            <!-- Fila de Usuario -->
            <div class="campo-fila">
              <input
                type="text"
                class="form-control"
                :placeholder="'Usuario ' + portal.nombre"
                v-model="portal.usuario"
                :disabled="!usuarioEditable(portal)"
                :id="'usuario-' + index"
                @focus="enfocarUsuario(portal)"
                @blur="blurUsuario(portal)"
                @keyup.enter="blurUsuario(portal)"
              />
              <button
                class="btn btn-outline-primary btn-icon"
                :title="'Editar usuario de ' + portal.nombre"
                @click="activarEdicionUsuario(portal)"
                :disabled="usuarioEditable(portal)"
              >
                <i class="bi bi-pencil-fill"></i>
              </button>
            </div>

            <!-- Fila de Contraseña -->
            <div class="campo-fila">
              <input
                :type="portal.verContrasena ? 'text' : 'password'"
                class="form-control"
                :placeholder="'Contraseña ' + portal.nombre"
                v-model="portal.contrasena"
                :disabled="!contrasenaEditable(portal)"
                :id="'contrasena-' + index"
                @focus="enfocarContrasena(portal)"
                @blur="blurContrasena(portal)"
                @keyup.enter="blurContrasena(portal)"
              />
              <button
                class="btn btn-outline-primary btn-icon"
                :title="'Editar contraseña de ' + portal.nombre"
                @click="activarEdicionContrasena(portal)"
                :disabled="contrasenaEditable(portal)"
              >
                <i class="bi bi-pencil-fill"></i>
              </button>
              <button
                class="btn btn-outline-primary btn-icon"
                :title="portal.verContrasena ? 'Ocultar contraseña' : 'Ver contraseña'"
                @click="portal.verContrasena = !portal.verContrasena"
              >
                <i :class="portal.verContrasena ? 'bi bi-eye-slash-fill' : 'bi bi-eye-fill'"></i>
              </button>
            </div>
          </div>

          <!-- Botones del pie del panel -->
          <div class="panel-footer d-flex gap-2 justify-content-between mt-3">
            <button class="btn btn-outline-primary" @click="pedirConfirmacion" id="btn-borrar-cuentas">
              <i class="bi bi-trash3-fill me-1"></i>
              Reiniciar todas las cuentas
            </button>
            <button class="btn btn-primary" @click="guardarCuentas" id="btn-guardar-cuentas" :disabled="guardando">
              <span v-if="guardando" class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
              <i v-else class="bi bi-floppy-fill me-1"></i>
              {{ guardando ? 'Guardando...' : 'Guardar' }}
            </button>
          </div>
        </template>

      </div>
    </div>

    <!-- ─── Encabezado de la vista ──────────────────────────────── -->
    <div class="header-section text-center">
      <h1 class="main-title">Ingreso de Excel</h1>
      <p class="main-subtitle">
        Por favor ingrese el archivo Excel que contiene los datos necesarios para el proceso
      </p>
    </div>

    <!-- ─── Zona de carga (Drag and Drop / Clic) ───────────────── -->
    <div
      class="upload-box mt-4"
      :class="{ 'dragging': isDragging }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <div class="upload-content d-flex flex-column align-items-center justify-content-center">
        <!-- Icono de nube dinámico -->
        <i class="bi bi-cloud-arrow-up cloud-icon mb-3"></i>
        <!-- Texto explicativo dinámico según el estado de selección -->
        <p class="drop-text m-0" v-if="!selectedFile">
          Arrastra tu archivo aquí para subirlo<br>
          <span class="sub-text">o haz clic para explorar en tu equipo</span>
        </p>
        <p class="drop-text m-0 fw-bold text-success" v-else>
          <i class="bi bi-file-earmark-excel-fill me-2 fs-4"></i>{{ selectedFile.name }}
        </p>

        <!-- Botón para explorar archivos (vinculado al input oculto) -->
        <label class="btn btn-primary btn-lg mt-4 px-5 py-3 d-flex align-items-center gap-2 cursor-pointer">
          <span>{{ selectedFile ? 'Cambiar archivo' : 'Cargar archivo' }}</span>
          <i class="bi bi-upload"></i>
          <input
            type="file"
            class="d-none"
            accept=".xlsx, .xls"
            @change="handleFileSelect"
          />
        </label>
      </div>
    </div>

    <!-- ─── Botón de acción principal (Revisar datos) ───────────── -->
    <div class="mt-4 w-100 d-flex justify-content-center" style="max-width: 760px;">
      <button
        class="btn btn-primary w-100 py-3 fw-bold btn-submit fs-5"
        :disabled="!selectedFile"
        @click="handleProcess"
      >
        Revisar datos
      </button>
    </div>
  </div>
</template>

<style scoped>
/* ─── Contenedor principal ─────────────────────────────────── */
.home-container {
  padding: 60px 20px 40px 20px;
  background-color: var(--color-white);
  flex: 1;
  position: relative;
}

/* ─── Botón y panel de Cuentas de Usuario ──────────────────── */
.cuentas-wrapper {
  position: absolute;
  top: 16px;
  right: 24px;
  z-index: 100;
}

.btn-cuentas {
  font-size: 16px;
  font-weight: 600;
  padding: 10px 20px;
  white-space: nowrap;
}

.cuentas-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 420px;
  max-height: 75vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(10, 19, 45, 0.18);
  z-index: 200;
}

/* ─── Sección de cada portal ───────────────────────────────── */
.portal-seccion {
  padding: 12px 0;
}

.portal-seccion--separador {
  border-bottom: 1px solid var(--color-neutral);
  margin-bottom: 4px;
}

.portal-titulo {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-tertiary);
  margin-bottom: 10px;
}

/* ─── Filas de campos (input + botones) ────────────────────── */
.campo-fila {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.campo-fila .form-control {
  flex: 1;
  font-size: 14px;
}

/* Botón icono cuadrado pequeño */
.btn-icon {
  width: 36px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 14px;
  border-radius: 4px;
}

/* ─── Aviso de confirmación de borrado ─────────────────────── */
.confirmacion-box {
  padding: 8px 4px;
}

/* ─── Pie del panel ────────────────────────────────────────── */
.panel-footer {
  border-top: 1px solid var(--color-neutral);
  padding-top: 12px;
}

/* ─── Encabezado ───────────────────────────────────────────── */
.header-section {
  margin-top: 20px;
  margin-bottom: 30px;
}

.main-title {
  font-size: 48px;
  font-weight: 700;
  color: var(--color-black);
  margin-bottom: 16px;
}

.main-subtitle {
  font-size: 18px;
  font-weight: 500;
  color: var(--color-mid-gray);
  max-width: 650px;
  line-height: 1.5;
}

/* ─── Zona de carga ────────────────────────────────────────── */
.upload-box {
  width: 100%;
  max-width: 760px;
  height: 320px;
  border: 2px dashed var(--color-primary);
  border-radius: 12px;
  background-color: #fafbfc;
  transition: all 0.25s ease;
  cursor: pointer;
}

.upload-box:hover, .upload-box.dragging {
  background-color: #f0f7ff;
  border-color: var(--color-primary);
  box-shadow: 0 8px 24px rgba(0, 111, 179, 0.08);
}

.upload-content {
  height: 100%;
  padding: 40px;
}

.cloud-icon {
  font-size: 64px;
  color: var(--color-primary);
  transition: transform 0.2s ease;
}

.upload-box:hover .cloud-icon {
  transform: translateY(-4px);
}

.drop-text {
  font-size: 20px;
  color: var(--color-dark-gray);
  text-align: center;
  line-height: 1.5;
}

.sub-text {
  font-size: 15px;
  color: var(--color-mid-gray);
  display: inline-block;
  margin-top: 4px;
}

.cursor-pointer {
  cursor: pointer;
}

/* ─── Botón de envío ───────────────────────────────────────── */
.btn-submit {
  border-radius: 6px;
  transition: all 0.2s ease;
}

.btn-submit:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(0, 111, 179, 0.2);
}
</style>
