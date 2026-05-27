<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold">蒙特卡洛稳健性测试</h2>
      <button @click="runTest" class="btn-primary" :disabled="running">
        {{ running ? '测试中...' : '运行稳健性测试' }}
      </button>
    </div>

    <div v-if="result" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="card">
        <p class="text-xs text-gray-400">稳健性评分</p>
        <div class="flex items-end gap-2 mt-1">
          <p class="stat-value" :class="result.is_robust ? 'text-emerald-400' : 'text-red-400'">
            {{ result.robustness_score?.toFixed(0) }}<span class="text-sm font-normal text-gray-400">/100</span>
          </p>
          <span class="text-xs mb-1" :class="result.is_robust ? 'text-emerald-400' : 'text-red-400'">
            {{ result.is_robust ? '稳健' : '非稳健' }}
          </span>
        </div>
      </div>
      
      <div class="card">
        <p class="text-xs text-gray-400">平均收益 / 95% VaR</p>
        <p class="stat-value mt-1">{{ result.mean_return?.toFixed(2) }}% / {{ result.var_95?.toFixed(2) }}%</p>
      </div>

      <div class="card">
        <p class="text-xs text-gray-400">平均胜率</p>
        <p class="stat-value mt-1">{{ result.win_rate_mean?.toFixed(1) }}%</p>
      </div>

      <div class="card">
        <p class="text-xs text-gray-400">平均盈亏比</p>
        <p class="stat-value mt-1">{{ result.profit_factor_mean?.toFixed(2) }}</p>
      </div>

      <div class="card">
        <p class="text-xs text-gray-400">最差回撤 (均值)</p>
        <p class="stat-value mt-1 text-red-400">{{ result.max_drawdown_mean?.toFixed(2) }}%</p>
      </div>

      <div class="card">
        <p class="text-xs text-gray-400">5%分位收益 (最差情况)</p>
        <p class="stat-value mt-1">{{ result.percentile_5?.toFixed(2) }}%</p>
      </div>

      <div class="card">
        <p class="text-xs text-gray-400">95%分位收益 (最好情况)</p>
        <p class="stat-value mt-1">{{ result.percentile_95?.toFixed(2) }}%</p>
      </div>
    </div>
    
    <div v-else-if="!running" class="card text-center py-10 text-gray-500">
      点击上方按钮运行测试，基于历史已平仓订单进行 1000 次蒙特卡洛重采样模拟
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { backtestingApi } from '@/api'

const result = ref<any>(null)
const running = ref(false)

async function runTest() {
  running.value = true
  result.value = null
  try {
    const res: any = await backtestingApi.monteCarlo()
    result.value = res
  } catch (e: any) {
    alert('运行测试失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    running.value = false
  }
}
</script>
