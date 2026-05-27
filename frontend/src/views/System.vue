<template>
  <div class="p-6 space-y-6">
    <h2 class="text-xl font-bold">系统监控</h2>

    <!-- 系统状态 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="card">
        <p class="text-xs text-gray-400">系统状态</p>
        <div class="flex items-center gap-2 mt-2">
          <span class="w-3 h-3 rounded-full bg-emerald-400"></span>
          <span class="text-emerald-400 font-medium">运行中</span>
        </div>
        <p class="text-xs text-gray-500 mt-1">v{{ health.version }} / {{ health.environment }}</p>
      </div>
      <div class="card">
        <p class="text-xs text-gray-400">对账状态</p>
        <div class="flex items-center gap-2 mt-2">
          <span class="w-3 h-3 rounded-full" :class="recon.status==='active'?'bg-emerald-400':'bg-gray-500'"></span>
          <span class="text-sm">{{ recon.status==='active'?'运行中':'未启动' }}</span>
        </div>
        <p class="text-xs text-gray-500 mt-1">检查 {{ recon.stats?.total_checks||0 }} 次 / 差异 {{ recon.stats?.discrepancies_found||0 }}</p>
      </div>
      <div class="card">
        <p class="text-xs text-gray-400">自动纠正</p>
        <p class="stat-value text-sky-400">{{ recon.stats?.auto_corrections||0 }}</p>
      </div>
    </div>

    <!-- 熔断器 -->
    <div class="card">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-medium text-gray-400">熔断器状态</h3>
        <button @click="doRecover" class="btn-ghost text-xs" :disabled="!hasOpen">一键恢复</button>
      </div>
      <div class="space-y-2">
        <div v-for="(b, ex) in breakers" :key="ex" class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full" :class="bClass(b.state)"></span>
            <span class="text-sm font-medium">{{ ex }}</span>
            <span class="text-xs text-gray-400">{{ bLabel(b.state) }}</span>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-xs text-gray-500">失败: {{ b.failure_count }}</span>
            <button v-if="b.state!=='closed'" @click="resetBreaker(ex as string)" class="text-xs text-sky-400 hover:text-sky-300">重置</button>
          </div>
        </div>
        <div v-if="Object.keys(breakers).length===0" class="text-center py-4 text-gray-500 text-sm">无熔断器记录</div>
      </div>
    </div>

    <!-- 操作 -->
    <div class="card flex flex-wrap gap-3">
      <button @click="runRecon" class="btn-ghost">手动对账</button>
      <button @click="doRecover" class="btn-success">系统恢复</button>
    </div>

    <!-- 系统事件 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-3">最近系统事件</h3>
      <div class="space-y-2 max-h-80 overflow-y-auto">
        <div v-for="ev in events" :key="ev.id" class="flex justify-between p-2 bg-gray-700/50 rounded text-xs">
          <span class="text-gray-300">{{ ev.event_type }} <span v-if="ev.symbol" class="text-gray-500">{{ ev.symbol }}</span></span>
          <span class="text-gray-500">{{ fmtTime(ev.timestamp) }}</span>
        </div>
        <div v-if="events.length===0" class="text-center py-4 text-gray-500 text-sm">暂无事件</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { systemApi } from '@/api'

const health = ref<any>({})
const recon = ref<any>({})
const events = ref<any[]>([])

const breakers = computed(() => recon.value.circuit_breakers || {})
const hasOpen = computed(() => Object.values(breakers.value).some((b: any) => b.state !== 'closed'))

function bClass(state: string) {
  if (state === 'closed') return 'bg-emerald-400'
  if (state === 'half_open') return 'bg-yellow-400'
  return 'bg-red-400'
}
function bLabel(state: string) {
  if (state === 'closed') return '正常'
  if (state === 'half_open') return '探测中'
  return '熔断中'
}
function fmtTime(ts: string) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit' })
}

async function load() {
  health.value = await systemApi.health()
  recon.value = await systemApi.reconciliation()
  const res: any = await systemApi.events({ limit: 30 })
  events.value = res.events || []
}
async function runRecon() {
  await systemApi.runReconciliation()
  alert('对账已触发')
  load()
}
async function resetBreaker(ex: string) {
  await systemApi.resetBreaker(ex)
  load()
}
async function doRecover() {
  if (!confirm('确定执行系统恢复？')) return
  const res: any = await systemApi.recover()
  alert(`已恢复，重置 ${res.reset_breakers} 个熔断器`)
  load()
}

onMounted(load)
</script>
