import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import ValidacionDatos from '../views/ValidacionDatos.vue'

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
  }
]

const router = createRouter({
  history: createWebHistory('/vue/'),
  routes
})

export default router