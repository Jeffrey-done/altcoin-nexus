<template>
  <div class="p-6 space-y-6">
    <h2 class="text-xl font-bold">策略与系统配置</h2>
    <!-- 策略参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">策略参数 (short_overbought)</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ConfigField v-for="f in strategyFields" :key="f.key" :label="f.label" :section="'strategy'" :field="f.key" :value="cfg.strategy?.[f.key]" :type="f.type" @save="saveConfig" />
      </div>
    </div>
    <!-- 风控参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">风控参数</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ConfigField v-for="f in riskFields" :key="f.key" :label="f.label" :section="'risk'" :field="f.key" :value="cfg.risk?.[f.key]" :type="f.type" @save="saveConfig" />
      </div>
    </div>
    <!-- 交易所参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">交易所参数</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ConfigField v-for="f in exchangeFields" :key="f.key" :label="f.label" :section="'exchange'" :field="f.key" :value="cfg.exchange?.[f.key]" :type="f.type" :options="f.options" @save="saveConfig" />
      </div>
    </div>
    <!-- 监控参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">监控参数</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ConfigField v-for="f in monitorFields" :key="f.key" :label="f.label" :section="'monitoring'" :field="f.key" :value="cfg.monitoring?.[f.key]" :type="f.type" @save="saveConfig" />
      </div>
    </div>
    <!-- 优化参数 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">WFA 优化</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ConfigField v-for="f in optFields" :key="f.key" :label="f.label" :section="'optimization'" :field="f.key" :value="cfg.optimization?.[f.key]" :type="f.type" @save="saveConfig" />
      </div>
    </div>
    <!-- 黑名单 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">黑名单管理</h3>
      <div class="flex gap-2 mb-3">
        <input v-model="newBlack" class="input flex-1" placeholder="PEPE/USDT" @keyup.enter="addBlack" />
        <button @click="addBlack" class="btn-primary">添加</button>
      </div>
      <div class="flex flex-wrap gap-2">
        <span v-for="s in blacklist" :key="s" class="inline-flex items-center gap-1 px-2 py-1 bg-gray-700 rounded text-xs">
          {{ s }} <button @click="removeBlack(s)" class="text-red-400 hover:text-red-300 ml-1">×</button>
        </span>
        <span v-if="blacklist.length===0" class="text-gray-500 text-xs">空</span>
      </div>
    </div>
    <!-- 市场状态 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-4">强制市场状态</h3>
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        <button v-for="r in regimes" :key="r.value" @click="forceRegime(r.value)" class="p-3 rounded-lg text-center bg-gray-700 hover:bg-gray-600 transition">
          <span class="text-xl">{{ r.icon }}</span>
          <p class="text-[10px] mt-1 text-gray-400">{{ r.label }}</p>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useConfigStore } from '@/stores'
import { configApi, strategyApi } from '@/api'
import ConfigField from '@/components/ConfigField.vue'

const store = useConfigStore()
const cfg = computed(() => store.config)
const blacklist = ref<string[]>([])
const newBlack = ref('')

const strategyFields = [
  { key: 'vol_min', label: '最小成交量(USDT)', type: 'number' },
  { key: 'price_max', label: '最大价格', type: 'number' },
  { key: 'pct_24h_min', label: '24h最小涨幅%', type: 'number' },
  { key: 'rsi_period', label: 'RSI周期', type: 'number' },
  { key: 'daily_rsi_min', label: '日线RSI阈值', type: 'number' },
  { key: 'h4_rsi_enter', label: '4H RSI入场', type: 'number' },
  { key: 'h4_rsi_drop', label: '4H RSI下降', type: 'number' },
  { key: 'oi_change_min', label: 'OI变化阈值%', type: 'number' },
  { key: 'funding_max', label: '费率上限', type: 'number' },
  { key: 'funding_min', label: '费率下限', type: 'number' },
  { key: 'tp1_pct', label: '止盈1 %', type: 'number' },
  { key: 'tp2_pct', label: '止盈2 %', type: 'number' },
  { key: 'tp1_close_ratio', label: 'TP1平仓比例', type: 'number' },
  { key: 'hard_stop_pct', label: '硬止损 %', type: 'number' },
  { key: 'trail_activate_pct', label: '追踪激活 %', type: 'number' },
  { key: 'trail_retrace_ratio', label: '追踪回撤比', type: 'number' },
  { key: 'max_hold_hours', label: '最长持仓(h)', type: 'number' },
  { key: 'score_full_threshold', label: '满仓阈值', type: 'number' },
  { key: 'score_half_threshold', label: '半仓阈值', type: 'number' },
  { key: 'btc_filter_enabled', label: 'BTC过滤', type: 'bool' },
  { key: 'btc_crash_threshold', label: 'BTC崩盘阈值', type: 'number' },
  { key: 'btc_pump_threshold', label: 'BTC暴涨阈值', type: 'number' },
]
const riskFields = [
  { key: 'max_daily_loss', label: '日最大亏损($)', type: 'number' },
  { key: 'max_daily_trades', label: '日最大开仓', type: 'number' },
  { key: 'max_daily_trades_short', label: '做空上限', type: 'number' },
  { key: 'max_daily_trades_long', label: '做多上限', type: 'number' },
  { key: 'consecutive_loss_pause', label: '连亏暂停(次)', type: 'number' },
  { key: 'pause_hours', label: '暂停时长(h)', type: 'number' },
  { key: 'default_stake', label: '默认保证金($)', type: 'number' },
  { key: 'max_stake', label: '最大总仓位($)', type: 'number' },
  { key: 'cooldown_hours', label: '冷却时间(h)', type: 'number' },
  { key: 'cooldown_scope', label: '冷却范围', type: 'text' },
]
const exchangeFields = [
  { key: 'primary_exchange', label: '主交易所', type: 'select', options: ['binance','okx','bybit','gate','bitget'] },
  { key: 'leverage', label: '杠杆倍数', type: 'number' },
  { key: 'max_open_trades', label: '最大开仓数', type: 'number' },
  { key: 'position_mode', label: '持仓模式', type: 'select', options: ['one_way','hedge'] },
  { key: 'slippage_alert_pct', label: '滑点告警%', type: 'number' },
]
const monitorFields = [
  { key: 'health_check_interval', label: '健康检查间隔(s)', type: 'number' },
  { key: 'reconciliation_interval_minutes', label: '对账间隔(min)', type: 'number' },
  { key: 'prometheus_enabled', label: 'Prometheus', type: 'bool' },
]
const optFields = [
  { key: 'wfa_enabled', label: 'WFA启用', type: 'bool' },
  { key: 'wfa_schedule_day', label: '运行日', type: 'text' },
  { key: 'wfa_lookback_days', label: '回溯天数', type: 'number' },
  { key: 'wfa_sharpe_threshold', label: 'Sharpe阈值', type: 'number' },
  { key: 'auto_update_enabled', label: '自动更新', type: 'bool' },
]
const regimes = [
  { value: 'trending_up', icon: '📈', label: '上涨' },
  { value: 'trending_down', icon: '📉', label: '下跌' },
  { value: 'ranging', icon: '↔️', label: '震荡' },
  { value: 'high_vol', icon: '🌊', label: '高波动' },
  { value: 'crash', icon: '💥', label: '崩盘' },
  { value: 'recovery', icon: '🔄', label: '恢复' },
]

async function saveConfig(section: string, key: string, value: any) {
  await configApi.update(section, key, value)
  store.fetchConfig()
}
async function loadBlacklist() {
  const res: any = await strategyApi.blacklist()
  blacklist.value = res.blacklist || []
}
async function addBlack() {
  if (!newBlack.value.trim()) return
  await strategyApi.addBlacklist(newBlack.value.trim())
  newBlack.value = ''
  loadBlacklist()
}
async function removeBlack(s: string) {
  await strategyApi.removeBlacklist(s)
  loadBlacklist()
}
async function forceRegime(r: string) {
  await strategyApi.forceRegime(r, '手动设置')
  alert(`市场状态已设为: ${r}`)
}

onMounted(() => { store.fetchConfig(); loadBlacklist() })
</script>
