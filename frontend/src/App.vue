<template>
  <div v-if="authStore.isAuthenticated && $route.path !== '/login'" class="flex h-screen overflow-hidden">
    <!-- 侧边栏 - 机构终端风格 -->
    <aside class="w-56 flex flex-col flex-shrink-0" style="background: #0c1020; border-right: 1px solid #1e2740;">
      <!-- 品牌区 -->
      <div class="px-5 py-4" style="border-bottom: 1px solid #1e2740;">
        <div class="flex items-center gap-2">
          <div class="w-6 h-6 rounded flex items-center justify-center" style="background: linear-gradient(135deg, #d4a853, #b8922e);">
            <span class="text-[10px] font-black text-terminal">N</span>
          </div>
          <div>
            <h1 class="text-[13px] font-bold text-steel-100 tracking-tight leading-none">ALTCOIN</h1>
          <p class="text-[9px] font-mono text-gold-500 tracking-[0.2em] uppercase mt-0.5">NEXUS</p>
          </div>
        </div>
        <div class="mt-3 flex items-center gap-2">
          <span class="text-label text-steel-500">v4.0.0</span>
          <span class="text-[5px] text-steel-600">●</span>
          <span class="text-label text-steel-500">L4 自治系统</span>
        </div>
      </div>

      <!-- 导航分组 -->
      <nav class="flex-1 py-3 overflow-y-auto">
        <!-- 交易组 -->
        <div class="px-4 mb-1">
          <p class="text-[9px] font-mono text-gold-600/70 tracking-[0.25em] uppercase mb-2">交易</p>
        </div>
        <router-link
          v-for="item in tradingNav" :key="item.path" :to="item.path"
          class="group flex items-center gap-3 mx-2 px-3 py-2 rounded transition-all duration-150"
          :class="isActive(item.path)
            ? 'bg-gold-500/[0.08] text-gold-400'
            : 'text-steel-400 hover:text-steel-200 hover:bg-white/[0.02]'"
        >
          <span class="text-[13px] opacity-60" :class="isActive(item.path) ? 'opacity-100' : ''">{{ item.icon }}</span>
          <span class="text-[12px] font-medium">{{ item.label }}</span>
          <span v-if="isActive(item.path)" class="ml-auto w-1 h-1 rounded-full bg-gold-500"></span>
        </router-link>

        <!-- 系统组 -->
        <div class="px-4 mb-1 mt-5">
          <p class="text-[9px] font-mono text-gold-600/70 tracking-[0.25em] uppercase mb-2">系统</p>
        </div>
        <router-link
          v-for="item in systemNav" :key="item.path" :to="item.path"
          class="group flex items-center gap-3 mx-2 px-3 py-2 rounded transition-all duration-150"
          :class="isActive(item.path)
            ? 'bg-gold-500/[0.08] text-gold-400'
            : 'text-steel-400 hover:text-steel-200 hover:bg-white/[0.02]'"
        >
          <span class="text-[13px] opacity-60" :class="isActive(item.path) ? 'opacity-100' : ''">{{ item.icon }}</span>
          <span class="text-[12px] font-medium">{{ item.label }}</span>
          <span v-if="isActive(item.path)" class="ml-auto w-1 h-1 rounded-full bg-gold-500"></span>
        </router-link>
      </nav>

      <!-- 底部状态栏 -->
      <div class="px-4 py-3" style="border-top: 1px solid #1e2740;">
        <!-- 连接状态 -->
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span :class="wsConnected ? 'status-dot-active' : 'status-dot-error'"></span>
            <span class="text-[10px] font-mono tracking-wider" :class="wsConnected ? 'text-steel-300' : 'text-loss'">
              {{ wsConnected ? '已连接' : '离线' }}
            </span>
          </div>
          <span class="text-[9px] font-mono text-steel-600">WS</span>
        </div>
        <!-- 环境标识 -->
        <div class="flex items-center justify-between mb-3">
          <span class="text-[10px] font-mono text-steel-500">环境</span>
          <span class="badge-gold text-[8px] py-0 px-1.5">开发</span>
        </div>
        <!-- 退出 -->
        <button @click="handleLogout" class="w-full btn-ghost text-[10px] py-1.5">
          退出登录
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="flex-1 overflow-y-auto" style="background: #0a0e1a;">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
  <router-view v-else />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()
const wsConnected = ref(false)
let ws: WebSocket | null = null

const tradingNav = [
  { path: '/', icon: '◈', label: '仪表盘' },
  { path: '/trades', icon: '◉', label: '持仓管理' },
  { path: '/candidates', icon: '◎', label: '候选池' },
  { path: '/signals', icon: '◈', label: '信号日志' },
  { path: '/risk', icon: '◇', label: '风控状态' },
]

const systemNav = [
  { path: '/config', icon: '⚙', label: '策略配置' },
  { path: '/secrets', icon: '⊡', label: '密钥管理' },
  { path: '/optimization', icon: '△', label: '参数优化' },
  { path: '/backtesting', icon: '◐', label: '稳健性回测' },
  { path: '/system', icon: '▣', label: '系统监控' },
  { path: '/account', icon: '⊡', label: '账号安全' },
]

function isActive(path: string) {
  return route.path === path
}

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

<style scoped>
.page-enter-active {
  animation: page-in 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.page-leave-active {
  animation: page-out 0.15s ease both;
}
@keyframes page-in {
  0% { opacity: 0; transform: translateY(6px); }
  100% { opacity: 1; transform: translateY(0); }
}
@keyframes page-out {
  0% { opacity: 1; }
  100% { opacity: 0; }
}
</style>