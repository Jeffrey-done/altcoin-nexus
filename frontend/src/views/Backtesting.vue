<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4 flex items-center justify-between" style="border-bottom: 1px solid #1e2740;">
      <div>
        <h1 class="text-heading text-steel-100">蒙特卡洛稳健性测试</h1>
        <p class="text-label text-steel-500 mt-0.5">基于历史订单的策略稳健性评估</p>
      </div>
      <button @click="runTest" class="btn-primary" :disabled="running">
        {{ running ? '测试中...' : '运行稳健性测试' }}
      </button>
    </header>
    <div class="p-8 space-y-6">
      <!-- 测试结果 -->
      <div v-if="result" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="card-accent p-5 anim-in anim-d1">
          <span class="text-label text-steel-500">稳健性评分</span>
          <div class="flex items-end gap-2 mt-2">
            <p class="stat-value" :class="result.is_robust ? 'text-gain' : 'text-loss'">
              {{ result.robustness_score?.toFixed(0) }}<span class="text-[11px] font-normal text-steel-500">/100</span>
            </p>
            <span class="text-[10px] font-mono mb-1" :class="result.is_robust ? 'text-gain' : 'text-loss'">
              {{ result.is_robust ? '稳健' : '非稳健' }}
            </span>
          </div>
        </div>
        <div class="card p-5 anim-in anim-d2">
          <span class="text-label text-steel-500">平均收益 / 95% VaR</span>
          <p class="text-data-lg font-mono text-steel-100 mt-2">{{ result.mean_return?.toFixed(2) }}% / {{ result.var_95?.toFixed(2) }}%</p>
        </div>
        <div class="card p-5 anim-in anim-d3">
          <span class="text-label text-steel-500">平均胜率</span>
          <p class="text-data-lg font-mono text-gold-400 mt-2">{{ result.win_rate_mean?.toFixed(1) }}%</p>
        </div>
        <div class="card p-5 anim-in anim-d4">
          <span class="text-label text-steel-500">平均盈亏比</span>
          <p class="text-data-lg font-mono text-steel-100 mt-2">{{ result.profit_factor_mean?.toFixed(2) }}</p>
        </div>
        <div class="card p-5 anim-in anim-d5">
          <span class="text-label text-steel-500">最差回撤 (均值)</span>
          <p class="text-data-lg font-mono text-loss mt-2">{{ result.max_drawdown_mean?.toFixed(2) }}%</p>
        </div>
        <div class="card p-5 anim-in anim-d6">
          <span class="text-label text-steel-500">5%分位收益 (最差情况)</span>
          <p class="text-data-lg font-mono text-steel-200 mt-2">{{ result.percentile_5?.toFixed(2) }}%</p>
        </div>
        <div class="card p-5 anim-in anim-d7">
          <span class="text-label text-steel-500">95%分位收益 (最好情况)</span>
          <p class="text-data-lg font-mono text-gain mt-2">{{ result.percentile_95?.toFixed(2) }}%</p>
        </div>
      </div>

      <div v-else-if="!running" class="card p-10 text-center">
        <p class="text-steel-500 text-data">点击上方按钮运行测试</p>
        <p class="text-steel-600 text-[11px] mt-1">基于历史已平仓订单进行 1000 次蒙特卡洛重采样模拟</p>
      </div>
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