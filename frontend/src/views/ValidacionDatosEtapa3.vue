<script setup>
import { ref } from 'vue'

const props = defineProps({
  filas: {
    type: Array,
    default: () => [],
  },
  fileName: {
    type: String,
    default: 'archivo.xlsx',
  },
})

const emit = defineEmits(['volver-inicio'])

const descargando = ref(false)
const descargarMensaje = ref('')

async function descargarExcelCorregido() {
  const archivo = window.__excelFile
  if (!archivo) {
    alert('No se encontró el archivo original en sesión. Vuelve al inicio.')
    return
  }

  descargando.value = true
  descargarMensaje.value = 'Generando archivo final...'

  const formData = new FormData()
  formData.append('documento_excel', archivo)

  const payload = props.filas.map(f => ({
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
    atribucion: f.atribucion,
    dias_salida: f.dias_salida,
    dias_100: f.dias_100,
    dias_70: f.dias_70,
    dias_60: f.dias_60,
    dias_50: f.dias_50,
    dias_40: f.dias_40,
    dias_35: f.dias_35,
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

    let filename = props.fileName.replace(/\.xlsx?$/, '_cometidos_procesados.xlsx')
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

    descargarMensaje.value = '¡Descarga completada!'
    setTimeout(() => {
      descargarMensaje.value = ''
    }, 3000)
  } catch (e) {
    console.error(e)
    alert(`Error al descargar el archivo: ${e.message}`)
  } finally {
    descargando.value = false
  }
}
</script>

<template>
  <div class="etapa3-contenedor">
    <div class="finalizado-card">
      <div class="finalizado-icono-wrapper">
        <i class="bi bi-check-circle-fill finalizado-icono"></i>
      </div>

      <h2 class="finalizado-titulo">¡Automatización Completada!</h2>
      <p class="finalizado-descripcion">
        Todos los cometidos han sido procesados y registrados exitosamente en los portales correspondientes.
      </p>

      <!-- Tarjeta informativa de resumen -->
      <div class="resumen-kpis">
        <div class="kpi-item">
          <i class="bi bi-file-earmark-check-fill text-primary"></i>
          <div class="kpi-texto">
            <span class="kpi-valor">{{ filas.length }}</span>
            <span class="kpi-label">Cometidos procesados</span>
          </div>
        </div>
        <div class="kpi-item">
          <i class="bi bi-shield-check text-success"></i>
          <div class="kpi-texto">
            <span class="kpi-valor">100%</span>
            <span class="kpi-label">Tasa de éxito</span>
          </div>
        </div>
      </div>

      <!-- Botones de Acción -->
      <div class="finalizado-acciones">
        <button
          class="btn btn-success btn-lg btn-accion"
          :disabled="descargando"
          @click="descargarExcelCorregido"
        >
          <span v-if="descargando" class="spinner-border spinner-border-sm me-2"></span>
          <i v-else class="bi bi-file-earmark-arrow-down-fill me-2"></i>
          {{ descargando ? 'Generando archivo...' : 'Descargar Resultados' }}
        </button>

        <button
          class="btn btn-outline-primary btn-lg btn-accion"
          @click="emit('volver-inicio')"
        >
          <i class="bi bi-house-fill me-2"></i>
          Volver al Inicio
        </button>
      </div>

      <p v-if="descargarMensaje" class="text-success small mt-3 fw-semibold">
        {{ descargarMensaje }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.etapa3-contenedor {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  width: 100%;
  flex: 1;
  box-sizing: border-box;
}

.finalizado-card {
  text-align: center;
  max-width: 580px;
  width: 100%;
  background-color: var(--color-white);
  border: 1px solid var(--color-neutral);
  border-radius: 12px;
  padding: 40px 32px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.finalizado-icono-wrapper {
  margin-bottom: 20px;
}

.finalizado-icono {
  font-size: 72px;
  color: #059669;
}

.finalizado-titulo {
  font-family: var(--font-title);
  font-size: 28px;
  font-weight: 700;
  color: var(--color-black);
  margin-bottom: 12px;
}

.finalizado-descripcion {
  font-size: 15px;
  color: var(--color-dark-gray);
  line-height: 1.5;
  margin-bottom: 28px;
}

/* ── KPIs ── */
.resumen-kpis {
  display: flex;
  gap: 16px;
  margin-bottom: 32px;
  width: 100%;
  justify-content: center;
}

.kpi-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 20px;
  flex: 1;
  max-width: 220px;
  text-align: left;
}

.kpi-item i {
  font-size: 28px;
}

.kpi-texto {
  display: flex;
  flex-direction: column;
}

.kpi-valor {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-black);
}

.kpi-label {
  font-size: 12px;
  color: var(--color-mid-gray);
}

/* ── Botones ── */
.finalizado-acciones {
  display: flex;
  gap: 16px;
  justify-content: center;
  flex-wrap: wrap;
  width: 100%;
}

.btn-accion {
  padding: 12px 24px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  transition: all 0.2s ease;
}

.btn-accion:hover {
  transform: translateY(-2px);
}
</style>
