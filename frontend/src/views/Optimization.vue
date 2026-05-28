<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4 flex items-center justify-between" style="border-bottom: 1px solid #1e2740;">
      <div>
        <h1 class="text-heading text-steel-100">参数优化 (WFA)</h1>
        <p class="text-label text-steel-500 mt-0.5">Walk-Forward 分析与自动参数更新</p>
      </div>
      <button @click="runOptimization" class="btn-primary" :disabled="running">
        {{ running ? '优化中...' : '立即运行优化' }}
      </button>
    </header>
    <div class="p-8 space-y-6">
      <!-- 优化历史 -->
      <div class="card p-0">
        <div class="p-4" style="border-bottom: 1px solid #1e2740;">
          <span class="text-label text-steel-500">优化历史记录</span>
        </div>
        <div class="overflow-x-auto">
          <table class="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>触发方式</th>
                <th>回测区间</th>
                <th>更新参数</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="h in history" :key="h.timestamp">
                <td class="font-mono">{{ fmtTime(h.timestamp) }}</td>
                <td>{{ h.trigger }}</td>
                <td class="font-mono">{{ h.lookback_days }} 天</td>
                <td>
                  <div v-if="h.updated_params" class="text-[10px] space-y-0.5">
                    <div v-for="(v, k) in h.updated_params" :key="k" class="font-mono">
                      <span class="text-steel-500">{{ k }}:</span> <span class="text-steel-200">{{ v }}</span>
                    </div>
                  </div>
                  <span v-else class="text-steel-600">无</span>
                </td>
                <td>
                  <span v-if="h.status === 'completed'" class="text-gain">完成</span>
                  <span v-else-if="h.status === 'failed'" class="text-loss" :title="h.error">失败</span>
                  <span v-else class="text-steel-400">{{ h.status }}</span>
                </td>
              </tr>
              <tr v-if="history.length === 0">
                <td colspan="5" class="py-10 text-center text-steel-500">暂无优化记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { optimizationApi } from '@/api'

const history = ref<any[]>([])
const running = ref(false)

function fmtTime(ts: string) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
}

async function load() {
  const res: any = await optimizationApi.history()
  history.value = res.history || []
}

async function runOptimization() {
  if (!confirm('这可能需要一些时间，确定运行？')) return
  running.value = true
  try {
    await optimizationApi.run()
    alert('优化任务已进入队列，请稍后刷新查看结果')
    setTimeout(load, 5000)
  } catch (e: any) {
    alert('启动优化失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>