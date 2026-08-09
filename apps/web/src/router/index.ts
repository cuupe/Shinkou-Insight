import { createRouter, createWebHistory } from 'vue-router'
import AuthView from '@/views/auth/AuthView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: { name: 'login' },
    },
    {
      path: '/login',
      name: 'login',
      component: AuthView,
    },
    {
      path: '/register',
      name: 'register',
      component: AuthView,
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: { name: 'login' },
    },
  ],
})

export default router
