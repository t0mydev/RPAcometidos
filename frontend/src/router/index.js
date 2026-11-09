import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import ValidacionDatos from '../views/ValidacionDatos.vue'
import EdicionDatos from '../views/EdicionDatos.vue'
import HistorialEjecuciones from '../views/HistorialEjecuciones.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/validacion',
    name: 'ValidacionDatos',
    component: ValidacionDatos
  },
  {
    path: '/edicion-datos',
    name: 'EdicionDatos',
    component: EdicionDatos
  },
  {
    path: '/historial',
    name: 'HistorialEjecuciones',
    component: HistorialEjecuciones
  }
]

const router = createRouter({
  history: createWebHistory('/vue/'),
  routes
})

export default router