<script setup>
</script>

<template>
  <div class="app-wrapper">
    <!-- Navbar Institucional -->
    <nav class="navbar ui-navbar px-4">
      <div class="container-fluid p-0">
        <a class="navbar-brand p-0 m-0" href="#">
          <div class="gob-logo-grid">
            <!-- Tira superior de colores patrios -->
            <div class="strip-blue"></div>
            <div class="strip-split"></div>
            <div class="strip-red"></div>
            
            <!-- Icono del Palacio de La Moneda (SVG con máscara para transparencias) -->
            <div class="logo-building-box">
              <svg class="building-logo" viewBox="0 0 64 28" fill="white">
                <defs>
                  <mask id="building-mask">
                    <!-- El fondo blanco hace visible el relleno blanco del grupo -->
                    <rect x="0" y="0" width="64" height="28" fill="white" />
                    <!-- Ventanas del ala izquierda (cortes transparentes) -->
                    <rect x="3" y="15" width="4" height="4" fill="black" />
                    <rect x="10" y="15" width="4" height="4" fill="black" />
                    <rect x="17" y="15" width="4" height="4" fill="black" />
                    <rect x="3" y="21" width="4" height="4" fill="black" />
                    <rect x="10" y="21" width="4" height="4" fill="black" />
                    <rect x="17" y="21" width="4" height="4" fill="black" />
                    <!-- Ventanas del ala derecha (cortes transparentes) -->
                    <rect x="43" y="15" width="4" height="4" fill="black" />
                    <rect x="50" y="15" width="4" height="4" fill="black" />
                    <rect x="57" y="15" width="4" height="4" fill="black" />
                    <rect x="43" y="21" width="4" height="4" fill="black" />
                    <rect x="50" y="21" width="4" height="4" fill="black" />
                    <rect x="57" y="21" width="4" height="4" fill="black" />
                    <!-- Entrada principal / Arco central (corte transparente) -->
                    <rect x="29" y="18" width="6" height="10" rx="1.5" fill="black" />
                    <!-- Columnas/Ventanas centrales superiores -->
                    <rect x="27" y="11" width="2" height="5" fill="black" />
                    <rect x="31" y="11" width="2" height="5" fill="black" />
                    <rect x="35" y="11" width="2" height="5" fill="black" />
                  </mask>
                </defs>
                <!-- Aplicamos la máscara al dibujo del edificio -->
                <g mask="url(#building-mask)">
                  <rect x="0" y="12" width="64" height="16" />
                  <rect x="24" y="8" width="16" height="20" />
                  <rect x="27" y="5" width="10" height="3" />
                  <!-- Postes del ala izquierda -->
                  <rect x="2" y="8" width="1.5" height="4" />
                  <rect x="11" y="10" width="1.5" height="2" />
                  <rect x="20" y="10" width="1.5" height="2" />
                  <!-- Postes del ala derecha -->
                  <rect x="42.5" y="10" width="1.5" height="2" />
                  <rect x="51.5" y="10" width="1.5" height="2" />
                  <rect x="60.5" y="8" width="1.5" height="4" />
                </g>
              </svg>
            </div>
            
            <!-- Separador vertical -->
            <div class="logo-separator-box">
              <div class="brand-separator"></div>
            </div>
            
            <!-- Texto institucional -->
            <div class="logo-text-box">
              <span class="brand-text">Gob.cl</span>
            </div>
          </div>
        </a>
      </div>
    </nav>

    <!-- Contenido principal -->
    <router-view></router-view>
  </div>
</template>

<style scoped>
.app-wrapper {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Navbar principal */
.ui-navbar {
  background-color: var(--color-tertiary);
  padding-top: 0;
  padding-bottom: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

/* Cuadrícula para el diseño del logotipo institucional */
.gob-logo-grid {
  display: grid;
  grid-template-columns: auto 1px auto;
  grid-template-rows: 6px auto;
  align-items: center;
}

/* Tiras de colores patrios en la fila superior */
.strip-blue {
  grid-row: 1;
  grid-column: 1;
  background-color: #0056b3;
  height: 6px;
}

.strip-split {
  grid-row: 1;
  grid-column: 2;
  /* El degradado asegura que la división azul/roja ocurra exactamente sobre el separador de 1px */
  background: linear-gradient(to right, #0056b3 50%, #e3000f 50%);
  height: 6px;
}

.strip-red {
  grid-row: 1;
  grid-column: 3;
  background-color: #e3000f;
  height: 6px;
}

/* Contenedores del logo en la fila inferior */
.logo-building-box {
  grid-row: 2;
  grid-column: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 12px 18px 10px 18px;
}

.building-logo {
  width: 58px;
  height: 25px;
}

.logo-separator-box {
  grid-row: 2;
  grid-column: 2;
  display: flex;
  justify-content: center;
  align-items: stretch;
  height: 24px;
}

.brand-separator {
  width: 1px;
  background-color: rgba(255, 255, 255, 0.7);
  height: 100%;
}

.logo-text-box {
  grid-row: 2;
  grid-column: 3;
  display: flex;
  align-items: center;
  padding: 12px 18px 10px 18px;
}

.brand-text {
  color: var(--color-white);
  font-family: var(--font-body);
  font-weight: 700;
  font-size: 25px;
  letter-spacing: -0.5px;
  line-height: 1;
}
</style>
