import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    { path: '/', name: 'dashboard', component: () => import('@/views/Dashboard.vue'), meta: { auth: true } },
    { path: '/trades', name: 'trades', component: () => import('@/views/Trades.vue'), meta: { auth: true } },
    { path: '/candidates', name: 'candidates', component: () => import('@/views/Candidates.vue'), meta: { auth: true } },
    { path: '/signals', name: 'signals', component: () => import('@/views/Signals.vue'), meta: { auth: true } },
    { path: '/risk', name: 'risk', component: () => import('@/views/Risk.vue'), meta: { auth: true } },
    { path: '/config', name: 'config', component: () => import('@/views/Config.vue'), meta: { auth: true } },
    { path: '/secrets', name: 'secrets', component: () => import('@/views/Secrets.vue'), meta: { auth: true } },
    { path: '/system', name: 'system', component: () => import('@/views/System.vue'), meta: { auth: true } },
    { path: '/account', name: 'account', component: () => import('@/views/Account.vue'), meta: { auth: true } },
    { path: '/optimization', name: 'optimization', component: () => import('@/views/Optimization.vue'), meta: { auth: true } },
    { path: '/backtesting', name: 'backtesting', component: () => import('@/views/Backtesting.vue'), meta: { auth: true } },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('nexus_token')
  if (to.meta.auth && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
