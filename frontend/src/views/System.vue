<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4" style="border-bottom: 1px solid #1e2740;">
      <h1 class="text-heading text-steel-100">系统监控</h1>
      <p class="text-label text-steel-500 mt-0.5">健康状态、对账、熔断器、系统事件</p>
    </header>
    <div class="p-8 space-y-6">
      <!-- 状态卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="card p-5 anim-in anim-d1">
          <span class="text-label text-steel-500">系统状态</span>
          <div class="flex items-center gap-2 mt-3">
            <span class="status-dot-active"></span>
            <span class="text-data font-medium text-gain">运行中</span>
          </div>
          <p class="text-[10px] font-mono text-steel-500 mt-2">v{{ health.version }} / {{ health.environment }}</p>
        </div>
        <div class="card p-5 anim-in anim-d2">
          <span class="text-label text-steel-500">事件闭环验证</span>
          <div class="flex items-center gap-2 mt-3">
            <span :class="validation?.is_healthy ? 'status-dot-active' : 'status-dot-error'"></span>
            <span class="text-data font-medium" :class="validation?.is_healthy ? 'text-gain' : 'text-loss'">
              得分: {{ (validation?.health_score)?.toFixed(1) }}%
            </span>
          </div>
          <p class="text-[10px] font-mono text-steel-500 mt-2">完成: {{ validation?.chains?.completed || 0 }} / 失败: {{ validation?.chains?.failed || 0 }}</p>
        </div>
        <div class="card p-5 anim-in anim-d3">
          <span class="text-label text-steel-500">对账状态</span>
          <div class="flex items-center gap-2 mt-3">
            <span :class="recon.status==='active'?'status-dot-active':'status-dot-warning'"></span>
            <span class="text-data">{{ recon.status==='active'?'运行中':'未启动' }}</span>
          </div>
          <p class="text-[10px] font-mono text-steel-500 mt-2">检查 {{ recon.stats?.total_checks||0 }} 次 / 差异 {{ recon.stats?.discrepancies_found||0 }}</p>
        </div>
        <div class="card p-5 anim-in anim-d4">
          <span class="text-label text-steel-500">自动纠正</span>
          <p class="stat-value text-primary-400 mt-2">{{ recon.stats?.auto_corrections||0 }}</p>
        </div>
      </div>

      <!-- 熔断器 -->
      <div class="card p-5">
        <div class="flex items-center justify-between mb-4">
          <span class="text-label text-steel-500">熔断器状态</span>
          <button @click="doRecover" class="btn-ghost text-[9px]" :disabled="!hasOpen">一键恢复</button>
        </div>
        <div class="space-y-2">
          <div v-for="(b, ex) in breakers" :key="ex" class="flex items-center justify-between p-3 rounded-card" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(30,39,64,0.4);">
            <div class="flex items-center gap-2">
              <span :class="bClass(b.state)"></span>
              <span class="text-data font-medium text-steel-200">{{ ex }}</span>
              <span class="text-[10px] font-mono text-steel-500">{{ bLabel(b.state) }}</span>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-[10px] font-mono text-steel-500">失败: {{ b.failure_count }}</span>
              <button v-if="b.state!=='closed'" @click="resetBreaker(ex as string)" class="text-[10px] text-primary-400 hover:text-primary-300">重置</button>
            </div>
          </div>
          <div v-if="Object.keys(breakers).length===0" class="text-center py-6 text-steel-500 text-data">无熔断器记录</div>
        </div>
      </div>

      <!-- 操作 -->
      <div class="card p-5 flex flex-wrap gap-3">
        <button @click="runRecon" class="btn-ghost">手动对账</button>
        <button @click="doRecover" class="btn-success">系统恢复</button>
      </div>

      <!-- 系统事件 -->
      <div class="card p-0">
        <div class="p-4" style="border-bottom: 1px solid #1e2740;">
          <span class="text-label text-steel-500">最近系统事件</span>
        </div>
        <div class="max-h-80 overflow-y-auto divide-y" style="border-color: rgba(30,39,64,0.4);">
          <div v-for="ev in events" :key="ev.id" class="flex justify-between items-center px-4 py-3">
            <span class="text-data text-steel-200">{{ ev.event_type }} <span v-if="ev.symbol" class="font-mono text-steel-500">{{ ev.symbol }}</span></span>
            <span class="text-[10px] font-mono text-steel-500">{{ fmtTime(ev.timestamp) }}</span>
          </div>
          <div v-if="events.length===0" class="py-10 text-center text-steel-500">暂无事件</div>
        </div>
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
const validation = ref<any>(null)

const breakers = computed(() => recon.value.circuit_breakers || {})
const hasOpen = computed(() => Object.values(breakers.value).some((b: any) => b.state !== 'closed'))

function bClass(state: string) {
  if (state === 'closed') return 'status-dot-active'
  if (state === 'half_open') return 'status-dot-warning'
  return 'status-dot-error'
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
  validation.value = await systemApi.validation()
  const res: any = await systemApi.events({ limit: 30 })
  events.value = res.events || []
}
async function runRecon() {
  await systemApi.runReconciliation(); alert('对账已触发'); load()
}
async function resetBreaker(ex: string) {
  await systemApi.resetBreaker(ex); load()
}
async function doRecover() {
  if (!confirm('确定执行系统恢复？')) return
  const res: any = await systemApi.recover()
  alert(`已恢复，重置 ${res.reset_breakers} 个熔断器`); load()
}

onMounted(load)
</script>