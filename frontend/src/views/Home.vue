<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
const router = useRouter()

// Estado del drag-and-drop y archivo seleccionado
const isDragging = ref(false)
const selectedFile = ref(null)

// Gestores de eventos para arrastrar y soltar
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
    // Guardamos el archivo en sessionStorage para recuperarlo en la otra vista
    // (no podemos pasar un File object por el router)
    window.__excelFile = selectedFile.value
  }
}
</script>

<template>
  <div class="home-container d-flex flex-column align-items-center justify-content-start">
    <!-- Encabezado de la vista -->
    <div class="header-section text-center">
      <h1 class="main-title">Ingreso de Excel</h1>
      <p class="main-subtitle">
        Por favor ingrese el archivo Excel que contiene los datos necesarios para el proceso
      </p>
    </div>

    <!-- Zona de carga (Drag and Drop / Clic) -->
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

    <!-- Botón de acción principal (Revisar datos) -->
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
/* Contenedor principal ajustado para posicionar el contenido más arriba */
.home-container {
  padding: 60px 20px 40px 20px;
  background-color: var(--color-white);
  flex: 1;
}

.header-section {
  margin-top: 20px;
  margin-bottom: 30px;
}

/* Tipografía de títulos significativamente más grande */
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

/* Caja de carga de archivos de mayor tamaño para rellenar el espacio vacío */
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

/* Tipografía del área de carga agrandada */
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

/* Botón de envío */
.btn-submit {
  border-radius: 6px;
  transition: all 0.2s ease;
}

.btn-submit:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(0, 111, 179, 0.2);
}
</style>
