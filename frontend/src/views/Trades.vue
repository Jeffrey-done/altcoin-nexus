<template>
  <div class="p-6 space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold">交易管理</h2>
      <button @click="store.fetchTrades()" class="btn-ghost text-xs">刷新</button>
    </div>
    <!-- 过滤器 -->
    <div class="card flex flex-wrap gap-3">
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
    <div class="card overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-gray-400 border-b border-gray-700">
            <th class="text-left py-2 px-2">币种</th><th class="text-left py-2">方向</th>
            <th class="text-right py-2">开仓价</th><th class="text-right py-2">当前价</th>
            <th class="text-right py-2">盈亏</th><th class="text-right py-2">保证金</th>
            <th class="py-2">交易所</th><th class="py-2">策略</th><th class="py-2">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in filtered" :key="t.id" class="border-b border-gray-700/40 hover:bg-gray-700/20">
            <td class="py-2 px-2 font-medium">{{ t.symbol?.replace('/USDT','') }}</td>
            <td><span :class="t.direction==='SHORT'?'badge-short':'badge-long'">{{ t.direction==='SHORT'?'空':'多' }}</span></td>
            <td class="text-right font-mono">{{ fmtPrice(t.entry_price) }}</td>
            <td class="text-right font-mono">{{ fmtPrice(t.current_price||t.entry_price) }}</td>
            <td class="text-right font-mono" :class="pnl(t)>=0?'text-profit':'text-loss'">{{ pnl(t)>=0?'+':'' }}${{ pnl(t).toFixed(2) }}</td>
            <td class="text-right font-mono">${{ (t.stake||0).toFixed(1) }}</td>
            <td class="text-center text-xs text-gray-400">{{ t.exchange||'shadow' }}</td>
            <td class="text-center text-xs text-gray-400">{{ t.strategy?.replace('_',' ') }}</td>
            <td class="text-center">
              <button v-if="t.status==='open'" @click="closeTrade(t.id)" class="text-xs text-red-400 hover:text-red-300">平仓</button>
            </td>
          </tr>
          <tr v-if="filtered.length===0"><td colspan="9" class="py-8 text-center text-gray-500">暂无数据</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
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
