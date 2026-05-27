<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold">参数优化 (WFA)</h2>
      <button @click="runOptimization" class="btn-primary" :disabled="running">
        {{ running ? '优化中...' : '立即运行优化' }}
      </button>
    </div>

    <!-- 优化历史 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">优化历史记录</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead>
            <tr class="text-gray-400 border-b border-gray-700">
              <th class="pb-2">时间</th>
              <th class="pb-2">触发方式</th>
              <th class="pb-2">回测区间</th>
              <th class="pb-2">更新参数</th>
              <th class="pb-2">详情</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in history" :key="h.timestamp" class="border-b border-gray-700/50">
              <td class="py-3">{{ fmtTime(h.timestamp) }}</td>
              <td>{{ h.trigger }}</td>
              <td>{{ h.lookback_days }} 天</td>
              <td>
                <div v-if="h.updated_params" class="text-xs space-y-1">
                  <div v-for="(v, k) in h.updated_params" :key="k">
                    <span class="text-gray-400">{{ k }}:</span> {{ v }}
                  </div>
                </div>
                <span v-else class="text-gray-500">无</span>
              </td>
              <td>
                <span v-if="h.status === 'completed'" class="text-emerald-400">完成</span>
                <span v-else-if="h.status === 'failed'" class="text-red-400" :title="h.error">失败</span>
                <span v-else class="text-gray-400">{{ h.status }}</span>
              </td>
            </tr>
            <tr v-if="history.length === 0">
              <td colspan="5" class="py-4 text-center text-gray-500">暂无优化记录</td>
            </tr>
          </tbody>
        </table>
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
