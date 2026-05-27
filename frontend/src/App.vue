<template>
  <div class="min-h-screen bg-gray-900">
    <!-- 侧边栏 -->
    <aside class="fixed inset-y-0 left-0 w-64 bg-gray-800 border-r border-gray-700">
      <div class="flex flex-col h-full">
        <!-- Logo -->
        <div class="p-4 border-b border-gray-700">
          <h1 class="text-xl font-bold text-primary-400">
            <span class="text-2xl">◆</span> Altcoin Nexus
          </h1>
          <p class="text-xs text-gray-500 mt-1">L4级量化交易系统</p>
        </div>

        <!-- 导航菜单 -->
        <nav class="flex-1 p-4 space-y-1">
          <router-link
            v-for="item in menuItems"
            :key="item.path"
            :to="item.path"
            class="flex items-center px-3 py-2 rounded-lg transition-colors"
            :class="[
              $route.path === item.path
                ? 'bg-primary-600 text-white'
                : 'text-gray-400 hover:bg-gray-700 hover:text-white'
            ]"
          >
            <span class="mr-3 text-lg">{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </router-link>
        </nav>

        <!-- 系统状态 -->
        <div class="p-4 border-t border-gray-700">
          <div class="flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full" :class="systemStatusClass"></span>
            <span class="text-sm text-gray-400">{{ systemStatusText }}</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="ml-64 min-h-screen">
      <!-- 顶部栏 -->
      <header class="sticky top-0 z-10 bg-gray-800/80 backdrop-blur-sm border-b border-gray-700">
        <div class="flex items-center justify-between px-6 py-3">
          <h2 class="text-lg font-semibold">{{ currentPageTitle }}</h2>
          <div class="flex items-center space-x-4">
            <!-- 余额显示 -->
            <div class="text-sm">
              <span class="text-gray-400">余额:</span>
              <span class="ml-1 font-mono">${{ balance?.toLocaleString() || '0' }}</span>
            </div>
            <!-- 时间 -->
            <div class="text-sm text-gray-400 font-mono">
              {{ currentTime }}
            </div>
          </div>
        </div>
      </header>

      <!-- 页面内容 -->
      <div class="p-6">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useSystemStore } from '@/stores'

const route = useRoute()
const systemStore = useSystemStore()

const currentTime = ref('')
const balance = ref(1000)
let timeInterval: ReturnType<typeof setInterval>

const menuItems = [
  { path: '/', label: '仪表盘', icon: '📊' },
  { path: '/trades', label: '交易管理', icon: '📈' },
  { path: '/candidates', label: '候选池', icon: '🎯' },
  { path: '/signals', label: '信号日志', icon: '📡' },
  { path: '/risk', label: '风控状态', icon: '🛡️' },
  { path: '/settings', label: '系统设置', icon: '⚙️' },
]

const currentPageTitle = computed(() => {
  const item = menuItems.find(m => m.path === route.path)
  return item?.label || '仪表盘'
})

const systemStatusClass = computed(() => 
  systemStore.status ? 'bg-green-400' : 'bg-gray-500'
)

const systemStatusText = computed(() => 
  systemStore.status ? '运行中' : '未连接'
)

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  systemStore.fetchStatus()
})

onUnmounted(() => {
  clearInterval(timeInterval)
})
</script>
