<template>
  <div class="space-y-6">
    <!-- 系统信息 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">系统信息</h3>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <span class="text-gray-500">版本</span>
          <span class="ml-2 font-mono">{{ systemStore.status?.version || '-' }}</span>
        </div>
        <div>
          <span class="text-gray-500">环境</span>
          <span class="ml-2 font-mono">{{ systemStore.status?.environment || '-' }}</span>
        </div>
      </div>
    </div>

    <!-- 交易所配置 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">交易所配置</h3>
      <div class="space-y-4">
        <div class="flex items-center justify-between p-3 bg-gray-700 rounded-lg">
          <div class="flex items-center space-x-3">
            <span class="text-lg">🔶</span>
            <span>Binance</span>
          </div>
          <span class="text-sm" :class="exchangeStatus.binance ? 'text-green-400' : 'text-gray-500'">
            {{ exchangeStatus.binance ? '已连接' : '未配置' }}
          </span>
        </div>
        <div class="flex items-center justify-between p-3 bg-gray-700 rounded-lg">
          <div class="flex items-center space-x-3">
            <span class="text-lg">🔷</span>
            <span>OKX</span>
          </div>
          <span class="text-sm" :class="exchangeStatus.okx ? 'text-green-400' : 'text-gray-500'">
            {{ exchangeStatus.okx ? '已连接' : '未配置' }}
          </span>
        </div>
        <div class="flex items-center justify-between p-3 bg-gray-700 rounded-lg">
          <div class="flex items-center space-x-3">
            <span class="text-lg">🟡</span>
            <span>Bybit</span>
          </div>
          <span class="text-sm" :class="exchangeStatus.bybit ? 'text-green-400' : 'text-gray-500'">
            {{ exchangeStatus.bybit ? '已连接' : '未配置' }}
          </span>
        </div>
        <div class="flex items-center justify-between p-3 bg-gray-700 rounded-lg">
          <div class="flex items-center space-x-3">
            <span class="text-lg">🟢</span>
            <span>Gate.io</span>
          </div>
          <span class="text-sm" :class="exchangeStatus.gate ? 'text-green-400' : 'text-gray-500'">
            {{ exchangeStatus.gate ? '已连接' : '未配置' }}
          </span>
        </div>
        <div class="flex items-center justify-between p-3 bg-gray-700 rounded-lg">
          <div class="flex items-center space-x-3">
            <span class="text-lg">🔴</span>
            <span>Bitget</span>
          </div>
          <span class="text-sm" :class="exchangeStatus.bitget ? 'text-green-400' : 'text-gray-500'">
            {{ exchangeStatus.bitget ? '已连接' : '未配置' }}
          </span>
        </div>
      </div>
    </div>

    <!-- 风控参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">风控参数</h3>
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-gray-500">日最大亏损</span>
          <span class="font-mono">${{ systemStore.config?.risk?.max_daily_loss || 100 }}</span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-gray-500">日最大开仓</span>
          <span class="font-mono">{{ systemStore.config?.risk?.max_daily_trades || 10 }} 笔</span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-gray-500">连亏暂停</span>
          <span class="font-mono">{{ systemStore.config?.risk?.consecutive_loss_pause || 3 }} 次</span>
        </div>
      </div>
    </div>

    <!-- 策略参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">策略参数</h3>
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <span class="text-gray-500">最小成交量</span>
          <span class="font-mono">${{ (systemStore.config?.strategy?.vol_min || 500000).toLocaleString() }}</span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-gray-500">RSI 阈值</span>
          <span class="font-mono">{{ systemStore.config?.strategy?.daily_rsi_min || 70 }}</span>
        </div>
        <div class="flex items-center justify-between">
          <span class="text-gray-500">硬止损</span>
          <span class="font-mono">{{ systemStore.config?.strategy?.hard_stop_pct || 5 }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSystemStore } from '@/stores'

const systemStore = useSystemStore()

const exchangeStatus = ref({
  binance: false,
  okx: false,
  bybit: false,
  gate: false,
  bitget: false,
})

onMounted(async () => {
  await systemStore.fetchStatus()
  await systemStore.fetchConfig()
  
  // 模拟交易所状态
  exchangeStatus.value = {
    binance: true,
    okx: true,
    bybit: false,
    gate: false,
    bitget: false,
  }
})
</script>
