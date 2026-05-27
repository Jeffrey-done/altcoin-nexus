<template>
  <div class="space-y-6">
    <!-- 风控状态卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div class="card">
        <h3 class="text-sm font-medium text-gray-400 mb-4">日亏损限制</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-500">当前亏损</span>
            <span class="font-mono" :class="riskData.daily_loss > 0 ? 'text-loss' : 'text-profit'">
              ${{ riskData.daily_loss.toFixed(2) }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">限制</span>
            <span class="font-mono">${{ riskData.daily_loss_limit }}</span>
          </div>
          <div class="w-full bg-gray-700 rounded-full h-2">
            <div
              class="h-2 rounded-full transition-all"
              :class="dailyLossPercent > 80 ? 'bg-red-500' : dailyLossPercent > 50 ? 'bg-yellow-500' : 'bg-green-500'"
              :style="{ width: `${dailyLossPercent}%` }"
            ></div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3 class="text-sm font-medium text-gray-400 mb-4">今日开仓</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-500">已开仓</span>
            <span class="font-mono">{{ riskData.today_trades }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">限制</span>
            <span class="font-mono">{{ riskData.daily_trades_limit }}</span>
          </div>
          <div class="w-full bg-gray-700 rounded-full h-2">
            <div
              class="h-2 rounded-full bg-primary-500 transition-all"
              :style="{ width: `${(riskData.today_trades / riskData.daily_trades_limit) * 100}%` }"
            ></div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3 class="text-sm font-medium text-gray-400 mb-4">连续亏损</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-500">连续亏损</span>
            <span class="font-mono" :class="riskData.consecutive_losses > 0 ? 'text-loss' : ''">
              {{ riskData.consecutive_losses }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">暂停阈值</span>
            <span class="font-mono">{{ riskData.consecutive_loss_limit }}</span>
          </div>
          <div class="flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full" :class="riskData.is_paused ? 'bg-red-400' : 'bg-green-400'"></span>
            <span class="text-sm" :class="riskData.is_paused ? 'text-red-400' : 'text-green-400'">
              {{ riskData.is_paused ? '已暂停' : '正常' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 持仓集中度 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">持仓集中度</h3>
      <div class="space-y-2">
        <div class="flex justify-between">
          <span class="text-gray-500">总持仓</span>
          <span class="font-mono">${{ riskData.total_stake?.toFixed(2) || '0' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">最大限制</span>
          <span class="font-mono">${{ riskData.max_stake }}</span>
        </div>
        <div class="w-full bg-gray-700 rounded-full h-2">
          <div
            class="h-2 rounded-full transition-all"
            :class="stakePercent > 80 ? 'bg-red-500' : stakePercent > 50 ? 'bg-yellow-500' : 'bg-green-500'"
            :style="{ width: `${stakePercent}%` }"
          ></div>
        </div>
      </div>
    </div>

    <!-- 风控事件 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">最近风控事件</h3>
      <RiskEventList />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { riskApi } from '@/api'
import RiskEventList from '@/components/RiskEventList.vue'

const riskData = ref({
  account_id: '',
  is_paused: false,
  daily_loss: 0,
  daily_loss_limit: 100,
  consecutive_losses: 0,
  consecutive_loss_limit: 3,
  today_trades: 0,
  daily_trades_limit: 10,
  total_stake: 0,
  max_stake: 100,
})

const dailyLossPercent = computed(() => 
  Math.min((riskData.value.daily_loss / riskData.value.daily_loss_limit) * 100, 100)
)

const stakePercent = computed(() => 
  Math.min((riskData.value.total_stake / riskData.value.max_stake) * 100, 100)
)

onMounted(async () => {
  try {
    riskData.value = await riskApi.getStatus('default')
  } catch (e) {
    console.error('Failed to fetch risk status:', e)
  }
})
</script>
