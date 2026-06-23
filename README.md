# RPA Cometidos

Este repositorio contiene el código fuente del sistema RPA Cometidos. La arquitectura del software está dividida en dos entornos principales que convergen en producción: un backend gestionado con Python/Flask y un frontend interactivo construido con Vue/Vite.

## Tecnologías Clave (Guía para el Equipo)

Antes de iniciar, es importante comprender dos herramientas no mencionadas anteriormente que orquestan este proyecto:

### 🐍 Backend: ¿Qué es Poetry?
En lugar de usar el clásico `pip` y un archivo `requirements.txt`, este proyecto utiliza **Poetry** como gestor oficial del backend. 
Poetry es una herramienta moderna que empaqueta y gestiona las dependencias de Python de forma estricta. Crea automáticamente el entorno virtual y asegura que todos los miembros del equipo instalen exactamente las mismas versiones de las librerías (gracias a su archivo `poetry.lock`), eliminando el clásico problema de *"en mi máquina sí funciona"*.
* 📖 **Documentación Oficial:** [python-poetry.org/docs](https://python-poetry.org/docs/)

### ⚡ Frontend: ¿Qué es Vite y cómo programar en él?
**Vite** es el motor de construcción de nuestro frontend junto a Vue. Para el equipo encargado de la interfaz, la regla es simple: **todo el desarrollo ocurre dentro de la carpeta `frontend/src/`**.
No necesitan modificar archivos HTML ni recargar la página web. Solo deben programar la interfaz visual editando los archivos `.vue` (que combinan HTML, JavaScript y CSS en un solo lugar). 
* 📖 **Documentación de Vite:** [vitejs.dev/guide](https://vitejs.dev/guide/)
* 📖 **Documentación de Vue 3:** [vuejs.org/guide](https://vuejs.org/guide/introduction.html)

## Requisitos Previos

Para colaborar en este proyecto, debes tener instaladas las siguientes herramientas en tu sistema operativo:
* **>=Python 3.14** y **Poetry** (para la gestión del entorno virtual y dependencias del backend).
* **Node.js** (se recomienda la versión LTS, la cual incluye el gestor de paquetes `npm` necesario para el frontend (instalar Vue.js)).
* **Git** (para clonar y gestionar las versiones del repositorio).

---

## Instrucciones de Instalación Local

Una vez realizado el `git clone` del repositorio en tu máquina local, debes inicializar ambos entornos de forma independiente.

### 1. Entorno Backend (Python / Flask)
En la raíz del proyecto (`RPAcometidos/`), abre tu terminal y ejecuta el siguiente comando para leer el archivo `pyproject.toml` y descargar las librerías de Python:
```
poetry install
```

### 2. Entorno Frontend (Node.js / Vue / Vite)

Navega hacia la carpeta del frontend y ejecuta la descarga de dependencias de JavaScript leyendo el archivo `package.json`:
```
cd frontend //Si es que estás en la raíz
npm install
```

## Flujo de Trabajo en Desarrollo

Para trabajar en la interfaz visual y la lógica del servidor de forma colaborativa y simultánea, debes levantar ambos servidores en terminales separadas.

### Terminal 1 (Backend - Lógica de Servidor):
Desde la raíz del proyecto, levanta Flask:
```
poetry run python src/rpacometidos/app.py
```
(El servidor Flask operará en http://127.0.0.1:5000)
actúa como "api" que realiza calculos que se reflejan en el frontend a través de vue

### Terminal 2 (Frontend - Interfaz de Usuario):
Desde la carpeta frontend/, levanta el motor interactivo:
```
cd frontend //Si es que estás en la raíz
npm run dev
```
(Vite operará en http://localhost:5173, reflejando cualquier cambio de código frontend en tiempo real)

## Compilación para Producción (Monolito)

El código fuente de Vue, que está en la carpeta `frontend/` es exclusivo para desarrollo. Cuando se termina de programar la interfaz visual y se necesita integrar al servidor Flask definitivo, se debe compilar solamente.

Desde la carpeta `frontend/`, ejecuta:
```
npm run build
```
> **IMPORTANTE**
Esto generará los archivos en versión estática dentro de la carpeta `RPAcometidos/src/rpacometidos/vue` esto se hace si se quiere comprobar que los archivos se generan correctamente sin errores, se recomienda que mientras están desarrollando esta carpeta no exista, osea que si la generan, la borren, y si quieren interactuar con el frontend o revisar como se ve se haga a través de lo explicado en el punto _Terminal 2 (Frontend - Interfaz de Usuario)_ cuando se levanta flask, flask renderiza el index.html que queda adentro de esa carpeta, son asíncronos hasta el momento que se va a producción, flask siempre va a renderizar algo diferente a vue hasta este.

## Arquitectura de Compilación:
Este comando procesará todo el código interactivo, lo minificará y depositará los archivos estáticos resultantes de forma automática en el directorio src/rpacometidos/Vue/.

A partir de este momento, el entorno de Node.js deja de ser necesario. Flask es capaz de leer esa carpeta y servir la interfaz final directamente en el puerto 5000 operando como un monolito unificado.
