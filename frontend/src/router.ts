import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/Dashboard.vue'),
    },
    {
      path: '/trades',
      name: 'trades',
      component: () => import('@/views/Trades.vue'),
    },
    {
      path: '/candidates',
      name: 'candidates',
      component: () => import('@/views/Candidates.vue'),
    },
    {
      path: '/risk',
      name: 'risk',
      component: () => import('@/views/Risk.vue'),
    },
    {
      path: '/signals',
      name: 'signals',
      component: () => import('@/views/Signals.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/Settings.vue'),
    },
  ],
})

export default router
