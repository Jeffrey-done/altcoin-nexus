<template>
  <div class="space-y-6">
    <!-- 系统控制面板 -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-medium text-gray-400">系统控制</h3>
        <div class="flex items-center space-x-2">
          <span 
            class="w-2 h-2 rounded-full"
            :class="systemPaused ? 'bg-red-400' : 'bg-green-400'"
          ></span>
          <span class="text-sm" :class="systemPaused ? 'text-red-400' : 'text-green-400'">
            {{ systemPaused ? '已暂停' : '运行中' }}
          </span>
        </div>
      </div>
      
      <div class="flex flex-wrap gap-2">
        <button 
          @click="togglePause"
          :class="systemPaused ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'"
          class="px-4 py-2 rounded text-sm"
        >
          {{ systemPaused ? '恢复交易' : '暂停交易' }}
        </button>
        <button 
          @click="panicSell"
          class="px-4 py-2 bg-red-800 hover:bg-red-900 rounded text-sm"
        >
          紧急全平仓
        </button>
        <button 
          @click="runOptimization"
          class="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded text-sm"
        >
          立即优化
        </button>
      </div>
    </div>

    <!-- 交易所配置 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">交易所配置</h3>
      <div class="space-y-4">
        <!-- 主交易所选择 -->
        <div>
          <label class="text-sm text-gray-500">主交易所</label>
          <select 
            v-model="config.exchange.primary_exchange"
            @change="saveConfig('exchange.primary_exchange', config.exchange.primary_exchange)"
            class="mt-1 w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
          >
            <option value="binance">Binance</option>
            <option value="okx">OKX</option>
            <option value="bybit">Bybit</option>
            <option value="gate">Gate.io</option>
            <option value="bitget">Bitget</option>
          </select>
        </div>

        <!-- 杠杆设置 -->
        <div>
          <label class="text-sm text-gray-500">杠杆倍数</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.exchange.leverage"
              type="range" 
              min="1" 
              max="20" 
              class="flex-1"
            />
            <span class="font-mono w-12 text-right">{{ config.exchange.leverage }}x</span>
            <button 
              @click="saveConfig('exchange.leverage', config.exchange.leverage)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs"
            >
              保存
            </button>
          </div>
        </div>

        <!-- 最大开仓数 -->
        <div>
          <label class="text-sm text-gray-500">最大开仓数</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.exchange.max_open_trades"
              type="number" 
              min="1" 
              max="20"
              class="w-24 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            />
            <button 
              @click="saveConfig('exchange.max_open_trades', config.exchange.max_open_trades)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 风控参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">风控参数</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- 日最大亏损 -->
        <div>
          <label class="text-sm text-gray-500">日最大亏损 ($)</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.risk.max_daily_loss"
              type="number" 
              min="0" 
              step="10"
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            />
            <button 
              @click="saveConfig('risk.max_daily_loss', config.risk.max_daily_loss)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs whitespace-nowrap"
            >
              保存
            </button>
          </div>
        </div>

        <!-- 日最大开仓 -->
        <div>
          <label class="text-sm text-gray-500">日最大开仓 (笔)</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.risk.max_daily_trades"
              type="number" 
              min="1" 
              max="50"
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            />
            <button 
              @click="saveConfig('risk.max_daily_trades', config.risk.max_daily_trades)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs whitespace-nowrap"
            >
              保存
            </button>
          </div>
        </div>

        <!-- 连亏暂停 -->
        <div>
          <label class="text-sm text-gray-500">连亏暂停 (次)</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.risk.consecutive_loss_pause"
              type="number" 
              min="1" 
              max="10"
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            />
            <button 
              @click="saveConfig('risk.consecutive_loss_pause', config.risk.consecutive_loss_pause)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs whitespace-nowrap"
            >
              保存
            </button>
          </div>
        </div>

        <!-- 暂停时长 -->
        <div>
          <label class="text-sm text-gray-500">暂停时长 (小时)</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.risk.pause_hours"
              type="number" 
              min="1" 
              max="24"
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            />
            <button 
              @click="saveConfig('risk.pause_hours', config.risk.pause_hours)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs whitespace-nowrap"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 策略参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">策略参数</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- 最小成交量 -->
        <div>
          <label class="text-sm text-gray-500">最小成交量 (USDT)</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.strategy.vol_min"
              type="number" 
              min="0" 
              step="100000"
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            />
            <button 
              @click="saveConfig('strategy.vol_min', config.strategy.vol_min)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs whitespace-nowrap"
            >
              保存
            </button>
          </div>
        </div>

        <!-- RSI 阈值 -->
        <div>
          <label class="text-sm text-gray-500">RSI 阈值</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.strategy.daily_rsi_min"
              type="range" 
              min="50" 
              max="90" 
              class="flex-1"
            />
            <span class="font-mono w-12 text-right">{{ config.strategy.daily_rsi_min }}</span>
            <button 
              @click="saveConfig('strategy.daily_rsi_min', config.strategy.daily_rsi_min)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs"
            >
              保存
            </button>
          </div>
        </div>

        <!-- 硬止损 -->
        <div>
          <label class="text-sm text-gray-500">硬止损 (%)</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.strategy.hard_stop_pct"
              type="number" 
              min="1" 
              max="20" 
              step="0.5"
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            />
            <button 
              @click="saveConfig('strategy.hard_stop_pct', config.strategy.hard_stop_pct)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs whitespace-nowrap"
            >
              保存
            </button>
          </div>
        </div>

        <!-- TP1 -->
        <div>
          <label class="text-sm text-gray-500">止盈1 (%)</label>
          <div class="flex items-center space-x-2 mt-1">
            <input 
              v-model.number="config.strategy.tp1_pct"
              type="number" 
              min="1" 
              max="20" 
              step="0.5"
              class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
            />
            <button 
              @click="saveConfig('strategy.tp1_pct', config.strategy.tp1_pct)"
              class="px-2 py-1 bg-primary-600 hover:bg-primary-700 rounded text-xs whitespace-nowrap"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 黑名单管理 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">黑名单管理</h3>
      
      <!-- 添加黑名单 -->
      <div class="flex space-x-2 mb-4">
        <input 
          v-model="newBlacklistSymbol"
          placeholder="输入币种，如 PEPE/USDT"
          class="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm"
          @keyup.enter="addToBlacklist"
        />
        <button 
          @click="addToBlacklist"
          class="px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded text-sm"
        >
          添加
        </button>
      </div>
      
      <!-- 黑名单列表 -->
      <div class="space-y-2">
        <div 
          v-for="symbol in blacklist" 
          :key="symbol"
          class="flex items-center justify-between p-2 bg-gray-700 rounded"
        >
          <span class="text-sm">{{ symbol }}</span>
          <button 
            @click="removeFromBlacklist(symbol)"
            class="text-red-400 hover:text-red-300 text-sm"
          >
            移除
          </button>
        </div>
        <div v-if="blacklist.length === 0" class="text-center text-gray-500 text-sm py-4">
          黑名单为空
        </div>
      </div>
    </div>

    <!-- 市场状态 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">市场状态</h3>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <button 
          v-for="regime in regimes" 
          :key="regime.value"
          @click="forceRegime(regime.value)"
          class="p-3 rounded-lg text-center transition-colors"
          :class="currentRegime === regime.value ? 'bg-primary-600' : 'bg-gray-700 hover:bg-gray-600'"
        >
          <span class="text-2xl">{{ regime.icon }}</span>
          <p class="text-xs mt-1">{{ regime.label }}</p>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useSystemStore } from '@/stores'
import api from '@/api'

const systemStore = useSystemStore()

// 系统状态
const systemPaused = ref(false)
const currentRegime = ref('ranging')

// 配置
const config = reactive({
  exchange: {
    primary_exchange: 'binance',
    leverage: 10,
    max_open_trades: 8,
  },
  risk: {
    max_daily_loss: 100,
    max_daily_trades: 10,
    consecutive_loss_pause: 3,
    pause_hours: 4,
  },
  strategy: {
    vol_min: 500000,
    daily_rsi_min: 70,
    hard_stop_pct: 5,
    tp1_pct: 3,
  },
})

// 黑名单
const blacklist = ref<string[]>([])
const newBlacklistSymbol = ref('')

// 市场状态
const regimes = [
  { value: 'trending_up', label: '上涨趋势', icon: '📈' },
  { value: 'trending_down', label: '下跌趋势', icon: '📉' },
  { value: 'ranging', label: '震荡', icon: '↔️' },
  { value: 'high_vol', label: '高波动', icon: '🌊' },
  { value: 'crash', label: '崩盘', icon: '💥' },
  { value: 'recovery', label: '恢复', icon: '🔄' },
]

// 加载配置
async function loadConfig() {
  try {
    const data = await systemStore.fetchConfig()
    if (data) {
      Object.assign(config.exchange, data.exchange || {})
      Object.assign(config.risk, data.risk || {})
      Object.assign(config.strategy, data.strategy || {})
    }
  } catch (e) {
    console.error('Failed to load config:', e)
  }
}

// 保存配置
async function saveConfig(key: string, value: any) {
  try {
    await api.post('/config', { key, value })
    alert('配置已保存')
  } catch (e) {
    console.error('Failed to save config:', e)
    alert('保存失败')
  }
}

// 切换暂停
async function togglePause() {
  try {
    await api.post('/risk/toggle-pause', {
      paused: !systemPaused.value,
      reason: systemPaused.value ? '手动恢复' : '手动暂停',
    })
    systemPaused.value = !systemPaused.value
  } catch (e) {
    console.error('Failed to toggle pause:', e)
  }
}

// 紧急全平仓
async function panicSell() {
  if (!confirm('确定要紧急全平仓吗？这将立即关闭所有持仓。')) return
  
  try {
    await api.post('/execution/panic-sell-all')
    alert('紧急平仓指令已发送')
  } catch (e) {
    console.error('Failed to panic sell:', e)
    alert('操作失败')
  }
}

// 立即优化
async function runOptimization() {
  try {
    await api.post('/optimization/run-now')
    alert('优化任务已启动')
  } catch (e) {
    console.error('Failed to run optimization:', e)
    alert('操作失败')
  }
}

// 加载黑名单
async function loadBlacklist() {
  try {
    const data = await api.get('/strategy/blacklist')
    blacklist.value = data.blacklist || []
  } catch (e) {
    console.error('Failed to load blacklist:', e)
  }
}

// 添加黑名单
async function addToBlacklist() {
  if (!newBlacklistSymbol.value.trim()) return
  
  try {
    await api.post('/strategy/blacklist', {
      symbol: newBlacklistSymbol.value.trim(),
      reason: '手动添加',
    })
    newBlacklistSymbol.value = ''
    await loadBlacklist()
  } catch (e) {
    console.error('Failed to add to blacklist:', e)
    alert('添加失败')
  }
}

// 移除黑名单
async function removeFromBlacklist(symbol: string) {
  try {
    await api.delete(`/strategy/blacklist/${symbol}`)
    await loadBlacklist()
  } catch (e) {
    console.error('Failed to remove from blacklist:', e)
  }
}

// 强制市场状态
async function forceRegime(regime: string) {
  try {
    await api.post('/config/regime', {
      regime,
      reason: '手动设置',
    })
    currentRegime.value = regime
    alert(`市场状态已设置为: ${regime}`)
  } catch (e) {
    console.error('Failed to force regime:', e)
    alert('操作失败')
  }
}

onMounted(async () => {
  await loadConfig()
  await loadBlacklist()
  await systemStore.fetchStatus()
})
</script>
