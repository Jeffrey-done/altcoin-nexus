<template>
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="text-gray-400 border-b border-gray-700">
          <th class="text-left py-3 px-2">币种</th>
          <th class="text-left py-3 px-2">方向</th>
          <th class="text-right py-3 px-2">开仓价</th>
          <th class="text-right py-3 px-2">当前价</th>
          <th class="text-right py-3 px-2">盈亏</th>
          <th class="text-right py-3 px-2">保证金</th>
          <th class="text-left py-3 px-2">交易所</th>
          <th v-if="showActions" class="text-right py-3 px-2">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="trade in trades"
          :key="trade.id"
          class="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors"
        >
          <td class="py-3 px-2 font-medium">{{ formatSymbol(trade.symbol) }}</td>
          <td class="py-3 px-2">
            <span
              class="px-2 py-0.5 rounded text-xs font-medium"
              :class="trade.direction === 'SHORT' ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'"
            >
              {{ trade.direction === 'SHORT' ? '做空' : '做多' }}
            </span>
          </td>
          <td class="py-3 px-2 text-right font-mono">{{ formatPrice(trade.entry_price) }}</td>
          <td class="py-3 px-2 text-right font-mono">{{ formatPrice(trade.current_price || trade.entry_price) }}</td>
          <td class="py-3 px-2 text-right font-mono" :class="getPnlClass(trade)">
            {{ formatPnl(trade) }}
          </td>
          <td class="py-3 px-2 text-right font-mono">${{ trade.stake?.toFixed(2) }}</td>
          <td class="py-3 px-2">
            <span class="text-xs text-gray-500">{{ trade.exchange || 'shadow' }}</span>
          </td>
          <td v-if="showActions" class="py-3 px-2 text-right">
            <button
              v-if="trade.status === 'open'"
              @click="$emit('close', trade.id)"
              class="text-xs text-red-400 hover:text-red-300"
            >
              平仓
            </button>
          </td>
        </tr>
        <tr v-if="trades.length === 0">
          <td :colspan="showActions ? 8 : 7" class="py-8 text-center text-gray-500">
            {{ loading ? '加载中...' : '暂无数据' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  trades: any[]
  loading?: boolean
  showActions?: boolean
}>()

defineEmits<{
  close: [tradeId: string]
}>()

function formatSymbol(symbol: string): string {
  return symbol?.replace('/USDT', '') || '-'
}

function formatPrice(price: number): string {
  if (!price) return '-'
  return price < 1 ? price.toFixed(6) : price.toFixed(2)
}

function formatPnl(trade: any): string {
  const pnl = (trade.tp1_locked_pnl || 0) + (trade.pnl || 0)
  const prefix = pnl >= 0 ? '+' : ''
  return `${prefix}$${pnl.toFixed(2)}`
}

function getPnlClass(trade: any): string {
  const pnl = (trade.tp1_locked_pnl || 0) + (trade.pnl || 0)
  return pnl >= 0 ? 'text-profit' : 'text-loss'
}
</script>
