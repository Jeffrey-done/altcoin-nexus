<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4" style="border-bottom: 1px solid #1e2740;">
      <h1 class="text-heading text-steel-100">策略与系统配置</h1>
      <p class="text-label text-steel-500 mt-0.5">策略参数、风控、交易所、监控配置</p>
    </header>
    <div class="p-8 space-y-6">
      <!-- 策略参数 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">策略参数</span>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
          <ConfigField v-for="f in strategyFields" :key="f.key" :label="f.label" :section="'strategy'" :field="f.key" :value="cfg.strategy?.[f.key]" :type="f.type" :readonly="f.readonly" @save="saveConfig" />
        </div>
      </div>
      <!-- 风控参数 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">风控参数</span>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
          <ConfigField v-for="f in riskFields" :key="f.key" :label="f.label" :section="'risk'" :field="f.key" :value="cfg.risk?.[f.key]" :type="f.type" :readonly="f.readonly" @save="saveConfig" />
        </div>
      </div>
      <!-- 交易所参数 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">交易所参数</span>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
          <ConfigField v-for="f in exchangeFields" :key="f.key" :label="f.label" :section="'exchange'" :field="f.key" :value="cfg.exchange?.[f.key]" :type="f.type" :options="f.options" :readonly="f.readonly" @save="saveConfig" />
        </div>
      </div>
      <!-- 监控参数 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">监控参数</span>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <ConfigField v-for="f in monitorFields" :key="f.key" :label="f.label" :section="'monitoring'" :field="f.key" :value="cfg.monitoring?.[f.key]" :type="f.type" :readonly="f.readonly" @save="saveConfig" />
        </div>
      </div>
      <!-- 优化参数 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">WFA 优化</span>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <ConfigField v-for="f in optFields" :key="f.key" :label="f.label" :section="'optimization'" :field="f.key" :value="cfg.optimization?.[f.key]" :type="f.type" :readonly="f.readonly" @save="saveConfig" />
        </div>
      </div>
      <!-- 黑名单 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">黑名单管理</span>
        <div class="flex gap-2 mt-4 mb-4">
          <input v-model="newBlack" class="input flex-1" placeholder="PEPE/USDT" @keyup.enter="addBlack" />
          <button @click="addBlack" class="btn-primary">添加</button>
        </div>
        <div class="flex flex-wrap gap-2">
          <span v-for="s in blacklist" :key="s" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-mono" style="background: rgba(255,255,255,0.04); border: 1px solid #1e2740;">
            {{ s }} <button @click="removeBlack(s)" class="text-loss hover:text-red-300 ml-1">×</button>
          </span>
          <span v-if="blacklist.length===0" class="text-steel-500 text-[11px]">黑名单为空</span>
        </div>
      </div>
      <!-- 市场状态 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">强制市场状态</span>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 mt-4">
          <button v-for="r in regimes" :key="r.value" @click="forceRegime(r.value)" class="p-3 rounded-card text-center transition-all hover:scale-[1.02]" style="background: rgba(255,255,255,0.03); border: 1px solid #1e2740;">
            <span class="text-lg">{{ r.icon }}</span>
            <p class="text-[10px] mt-1 text-steel-400">{{ r.label }}</p>
          </button>
        </div>
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
  { key: 'vol_min', label: '最小成交量(USDT)', type: 'number', readonly: true },
  { key: 'price_max', label: '最大价格', type: 'number', readonly: true },
  { key: 'pct_24h_min', label: '24h最小涨幅', type: 'number', readonly: true },
  { key: 'rsi_period', label: 'RSI周期', type: 'number', readonly: true },
  { key: 'daily_rsi_min', label: '日线RSI阈值', type: 'number', readonly: true },
  { key: 'h4_rsi_enter', label: '4H RSI入场', type: 'number', readonly: true },
  { key: 'h4_rsi_drop', label: '4H RSI下降', type: 'number', readonly: true },
  { key: 'oi_change_min', label: 'OI变化阈值', type: 'number', readonly: true },
  { key: 'funding_max', label: '费率上限', type: 'number', readonly: true },
  { key: 'funding_min', label: '费率下限', type: 'number', readonly: true },
  { key: 'tp1_pct', label: '止盈1 %', type: 'number', readonly: false },
  { key: 'tp2_pct', label: '止盈2 %', type: 'number', readonly: false },
  { key: 'tp1_close_ratio', label: 'TP1平仓比例', type: 'number', readonly: true },
  { key: 'hard_stop_pct', label: '硬止损%', type: 'number', readonly: false },
  { key: 'trail_activate_pct', label: '追踪激活%', type: 'number', readonly: true },
  { key: 'trail_retrace_ratio', label: '追踪回撤比', type: 'number', readonly: true },
  { key: 'max_hold_hours', label: '最长持仓(h)', type: 'number', readonly: true },
  { key: 'score_full_threshold', label: '满仓阈值', type: 'number', readonly: true },
  { key: 'score_half_threshold', label: '半仓阈值', type: 'number', readonly: true },
  { key: 'btc_filter_enabled', label: 'BTC过滤', type: 'bool', readonly: true },
  { key: 'btc_crash_threshold', label: 'BTC崩盘阈值', type: 'number', readonly: true },
  { key: 'btc_pump_threshold', label: 'BTC暴涨阈值', type: 'number', readonly: true },
]
const riskFields = [
  { key: 'max_daily_loss', label: '日最大亏损($)', type: 'number', readonly: false },
  { key: 'max_daily_trades', label: '日最大开仓', type: 'number', readonly: false },
  { key: 'max_daily_trades_short', label: '做空上限', type: 'number', readonly: true },
  { key: 'max_daily_trades_long', label: '做多上限', type: 'number', readonly: true },
  { key: 'consecutive_loss_pause', label: '连亏暂停(次)', type: 'number', readonly: false },
  { key: 'pause_hours', label: '暂停时长(h)', type: 'number', readonly: true },
  { key: 'default_stake', label: '默认保证金($)', type: 'number', readonly: true },
  { key: 'max_stake', label: '最大总仓位($)', type: 'number', readonly: true },
  { key: 'cooldown_hours', label: '冷却时间(h)', type: 'number', readonly: true },
  { key: 'cooldown_scope', label: '冷却范围', type: 'text', readonly: true },
]
const exchangeFields = [
  { key: 'primary_exchange', label: '主交易所', type: 'select', options: ['binance','okx','bybit','gate','bitget'], readonly: true },
  { key: 'leverage', label: '杠杆倍数', type: 'number', readonly: false },
  { key: 'max_open_trades', label: '最大开仓数', type: 'number', readonly: false },
  { key: 'position_mode', label: '持仓模式', type: 'select', options: ['one_way','hedge'], readonly: true },
  { key: 'slippage_alert_pct', label: '滑点告警%', type: 'number', readonly: true },
]
const monitorFields = [
  { key: 'health_check_interval', label: '健康检查间隔(s)', type: 'number', readonly: true },
  { key: 'reconciliation_interval_minutes', label: '对账间隔(min)', type: 'number', readonly: true },
  { key: 'prometheus_enabled', label: 'Prometheus', type: 'bool', readonly: true },
]
const optFields = [
  { key: 'wfa_enabled', label: 'WFA启用', type: 'bool', readonly: true },
  { key: 'wfa_schedule_day', label: '运行日', type: 'text', readonly: true },
  { key: 'wfa_lookback_days', label: '回溯天数', type: 'number', readonly: true },
  { key: 'wfa_sharpe_threshold', label: 'Sharpe阈值', type: 'number', readonly: true },
  { key: 'auto_update_enabled', label: '自动更新', type: 'bool', readonly: true },
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