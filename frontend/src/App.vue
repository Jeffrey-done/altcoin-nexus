<template>
  <div v-if="authStore.isAuthenticated && $route.path !== '/login'" class="flex h-screen">
    <!-- 侧边栏 -->
    <aside class="w-56 bg-gray-800 border-r border-gray-700 flex flex-col flex-shrink-0">
      <div class="p-4 border-b border-gray-700">
        <h1 class="text-lg font-bold text-sky-400">Altcoin Nexus</h1>
        <p class="text-[10px] text-gray-500 mt-0.5">L4 自治量化系统 v4.0</p>
      </div>
      <nav class="flex-1 p-3 space-y-1 overflow-y-auto">
        <router-link v-for="item in nav" :key="item.path" :to="item.path"
          class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors"
          :class="$route.path === item.path ? 'bg-sky-600/20 text-sky-400' : 'text-gray-400 hover:bg-gray-700 hover:text-white'">
          <span class="text-base">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="p-3 border-t border-gray-700">
        <div class="flex items-center gap-2 mb-2">
          <span class="w-2 h-2 rounded-full" :class="wsConnected ? 'bg-emerald-400' : 'bg-red-400'"></span>
          <span class="text-xs text-gray-400">{{ wsConnected ? '实时连接' : '未连接' }}</span>
        </div>
        <button @click="handleLogout" class="w-full btn-ghost text-xs">退出登录</button>
      </div>
    </aside>
    <!-- 主内容 -->
    <main class="flex-1 overflow-y-auto">
      <router-view />
    </main>
  </div>
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'

const authStore = useAuthStore()
const router = useRouter()
const wsConnected = ref(false)
let ws: WebSocket | null = null

const nav = [
  { path: '/', icon: '📊', label: '仪表盘' },
  { path: '/trades', icon: '📈', label: '交易管理' },
  { path: '/candidates', icon: '🎯', label: '候选池' },
  { path: '/signals', icon: '📡', label: '信号日志' },
  { path: '/risk', icon: '🛡️', label: '风控状态' },
  { path: '/config', icon: '⚙️', label: '策略配置' },
  { path: '/secrets', icon: '🔑', label: '密钥管理' },
  { path: '/optimization', icon: '⚡', label: '参数优化' },
  { path: '/backtesting', icon: '🧪', label: '稳健性回测' },
  { path: '/system', icon: '🖥️', label: '系统监控' },
  { path: '/account', icon: '👤', label: '账号安全' },
]

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${proto}//${location.host}/ws`)
  ws.onopen = () => { wsConnected.value = true }
  ws.onclose = () => { wsConnected.value = false; setTimeout(connectWs, 3000) }
  ws.onerror = () => { ws?.close() }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

onMounted(() => {
  if (authStore.isAuthenticated) { authStore.fetchMe(); connectWs() }
})
onUnmounted(() => { ws?.close() })
</script>
