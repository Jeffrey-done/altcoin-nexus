<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4 flex items-center justify-between" style="border-bottom: 1px solid #1e2740;">
      <div>
        <h1 class="text-heading text-steel-100">持仓管理</h1>
        <p class="text-label text-steel-500 mt-0.5">活跃持仓与历史交易</p>
      </div>
      <button @click="store.fetchTrades()" class="btn-ghost text-[9px]">刷新</button>
    </header>
    <div class="p-8 space-y-6">
      <!-- 过滤器 -->
      <div class="card p-4 flex flex-wrap gap-3">
        <select v-model="filters.status" class="input w-32">
          <option value="">全部状态</option><option value="open">持仓中</option><option value="closed">已平仓</option>
        </select>
        <select v-model="filters.direction" class="input w-28">
          <option value="">全部方向</option><option value="SHORT">做空</option><option value="LONG">做多</option>
        </select>
        <select v-model="filters.exchange" class="input w-32">
          <option value="">全部交易所</option>
          <option v-for="ex in ['binance','okx','bybit','gate','bitget']" :key="ex" :value="ex">{{ ex }}</option>
        </select>
      </div>
      <!-- 表格 -->
      <div class="card overflow-x-auto p-0">
        <table class="data-table">
          <thead>
            <tr>
              <th>币种</th><th>方向</th>
              <th class="text-right">开仓价</th><th class="text-right">当前价</th>
              <th class="text-right">盈亏</th><th class="text-right">保证金</th>
              <th>交易所</th><th>策略</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in filtered" :key="t.id">
              <td class="font-medium text-steel-100">{{ t.symbol?.replace('/USDT','') }}</td>
              <td><span :class="t.direction==='SHORT'?'badge-short':'badge-long'">{{ t.direction==='SHORT'?'空':'多' }}</span></td>
              <td class="text-right">{{ fmtPrice(t.entry_price) }}</td>
              <td class="text-right">{{ fmtPrice(t.current_price||t.entry_price) }}</td>
              <td class="text-right font-semibold" :class="pnl(t)>=0?'text-gain':'text-loss'">{{ pnl(t)>=0?'+':'' }}${{ pnl(t).toFixed(2) }}</td>
              <td class="text-right">${{ (t.stake||0).toFixed(1) }}</td>
              <td class="text-center text-steel-400">{{ t.exchange||'shadow' }}</td>
              <td class="text-center text-steel-400">{{ t.strategy?.replace('_',' ') }}</td>
              <td class="text-center">
                <button v-if="t.status==='open'" @click="closeTrade(t.id)" class="text-[10px] text-loss hover:text-red-300">平仓</button>
              </td>
            </tr>
            <tr v-if="filtered.length===0"><td colspan="9" class="py-8 text-center text-steel-500">暂无数据</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, onMounted } from 'vue'
import { useTradeStore } from '@/stores'
import { tradeApi } from '@/api'

const store = useTradeStore()
const filters = reactive({ status: '', direction: '', exchange: '' })

const filtered = computed(() => store.trades.filter(t => {
  if (filters.status && t.status !== filters.status) return false
  if (filters.direction && t.direction !== filters.direction) return false
  if (filters.exchange && t.exchange !== filters.exchange) return false
  return true
}))

function pnl(t: any) { return (t.tp1_locked_pnl||0) + (t.pnl||0) }
function fmtPrice(p: number) { return p ? (p < 1 ? p.toFixed(6) : p.toFixed(2)) : '-' }
async function closeTrade(id: string) {
  if (!confirm('确定平仓？')) return
  await tradeApi.close(id)
  store.fetchTrades()
}

onMounted(() => store.fetchTrades())
</script>