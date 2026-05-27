<template>
  <div class="p-6 space-y-6">
    <h2 class="text-xl font-bold">密钥管理</h2>
    <p class="text-xs text-gray-400">管理交易所API密钥和Telegram配置。密钥仅显示掩码，更新后即时生效。</p>

    <!-- 交易所密钥 -->
    <div v-for="(info, ex) in exchanges" :key="ex" class="card">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-medium">{{ exLabel(ex as string) }}</h3>
        <span class="text-xs" :class="info.api_key_set ? 'text-emerald-400' : 'text-gray-500'">
          {{ info.api_key_set ? '已配置' : '未配置' }}
        </span>
      </div>
      <div v-if="info.api_key_masked" class="text-xs text-gray-500 mb-3 font-mono">Key: {{ info.api_key_masked }}</div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <label class="label">API Key</label>
          <input v-model="forms[ex as string].api_key" type="password" class="input" placeholder="输入新Key" />
        </div>
        <div>
          <label class="label">API Secret</label>
          <input v-model="forms[ex as string].api_secret" type="password" class="input" placeholder="输入新Secret" />
        </div>
        <div v-if="ex==='okx'||ex==='bitget'">
          <label class="label">Passphrase</label>
          <input v-model="forms[ex as string].passphrase" type="password" class="input" placeholder="Passphrase" />
        </div>
      </div>
      <button @click="saveExchange(ex as string)" class="btn-primary mt-3 text-xs">保存 {{ exLabel(ex as string) }}</button>
    </div>

    <!-- Telegram -->
    <div class="card">
      <h3 class="font-medium mb-3">Telegram 通知</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label class="label">Bot Token</label>
          <input v-model="tgForm.bot_token" type="password" class="input" placeholder="Bot Token" />
          <p v-if="tg.bot_token_masked" class="text-xs text-gray-500 mt-1 font-mono">{{ tg.bot_token_masked }}</p>
        </div>
        <div>
          <label class="label">Chat ID</label>
          <input v-model="tgForm.chat_id" class="input" placeholder="Chat ID" />
          <p v-if="tg.chat_id" class="text-xs text-gray-500 mt-1">当前: {{ tg.chat_id }}</p>
        </div>
      </div>
      <div class="flex items-center gap-3 mt-3">
        <label class="flex items-center gap-2 text-sm">
          <input v-model="tgForm.enabled" type="checkbox" class="rounded" /> 启用通知
        </label>
        <button @click="saveTelegram" class="btn-primary text-xs">保存 Telegram</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useConfigStore } from '@/stores'
import { secretsApi } from '@/api'

const store = useConfigStore()
const exchanges = computed(() => store.secrets)
const tg = computed(() => store.telegram)

const forms: Record<string, any> = reactive({
  binance: { api_key: '', api_secret: '', passphrase: '' },
  okx: { api_key: '', api_secret: '', passphrase: '' },
  bybit: { api_key: '', api_secret: '', passphrase: '' },
  gate: { api_key: '', api_secret: '', passphrase: '' },
  bitget: { api_key: '', api_secret: '', passphrase: '' },
})
const tgForm = reactive({ bot_token: '', chat_id: '', enabled: false })

function exLabel(ex: string) {
  const m: any = { binance:'Binance', okx:'OKX', bybit:'Bybit', gate:'Gate.io', bitget:'Bitget' }
  return m[ex] || ex
}

async function saveExchange(ex: string) {
  const f = forms[ex]
  if (!f.api_key && !f.api_secret) { alert('请输入密钥'); return }
  await secretsApi.updateExchange({ exchange: ex, ...f })
  f.api_key = ''; f.api_secret = ''; f.passphrase = ''
  store.fetchSecrets()
  alert(`${exLabel(ex)} 密钥已更新`)
}

async function saveTelegram() {
  await secretsApi.updateTelegram(tgForm)
  tgForm.bot_token = ''
  store.fetchTelegram()
  alert('Telegram 配置已更新')
}

onMounted(() => { store.fetchSecrets(); store.fetchTelegram() })
</script>
