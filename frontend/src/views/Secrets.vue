<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold">交易所账户管理</h2>
      <button @click="showAdd = true" class="btn-primary">+ 添加账户</button>
    </div>
    <p class="text-xs text-gray-400">同一交易所支持多个独立API Key，每个账户独立风控和仓位管理。</p>

    <!-- 账户列表 -->
    <div v-for="a in accounts" :key="a.account_id" class="card">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <span class="text-lg font-bold">{{ exLabel(a.exchange) }}</span>
          <span class="text-sm text-gray-400">{{ a.label }}</span>
          <span v-if="a.is_primary" class="px-2 py-0.5 bg-sky-500/20 text-sky-400 rounded text-[10px] font-bold">主账户</span>
          <span v-if="!a.is_active" class="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-[10px]">已禁用</span>
        </div>
        <div class="flex items-center gap-2">
          <button @click="editAccount(a)" class="btn-ghost text-xs">编辑</button>
          <button v-if="!a.is_primary" @click="setPrimary(a.account_id)" class="btn-ghost text-xs">设为主</button>
          <button @click="removeAccount(a.account_id, a.label)" class="text-xs text-red-400 hover:text-red-300">删除</button>
        </div>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div><span class="text-gray-400">Account ID:</span> <span class="font-mono">{{ a.account_id }}</span></div>
        <div><span class="text-gray-400">API Key:</span> <span class="font-mono">{{ a.api_key_masked || '未设置' }}</span></div>
        <div><span class="text-gray-400">杠杆:</span> {{ a.leverage }}x</div>
        <div><span class="text-gray-400">最大仓位:</span> ${{ a.max_stake }}</div>
      </div>
      <div v-if="a.note" class="mt-2 text-xs text-gray-500">备注: {{ a.note }}</div>
    </div>

    <div v-if="accounts.length === 0" class="card text-center py-8 text-gray-500">
      暂无账户，点击上方"添加账户"开始配置
    </div>

    <!-- Telegram 配置 -->
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

    <!-- 添加/编辑弹窗 -->
    <div v-if="showAdd || showEdit" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" @click.self="closeModal">
      <div class="bg-gray-800 border border-gray-700 rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <h3 class="text-lg font-bold mb-4">{{ showEdit ? '编辑账户' : '添加账户' }}</h3>
        <div class="space-y-3">
          <div v-if="!showEdit">
            <label class="label">Account ID (唯一标识)</label>
            <input v-model="form.account_id" class="input" placeholder="如: binance_main, okx_sub1" />
          </div>
          <div>
            <label class="label">显示名称</label>
            <input v-model="form.label" class="input" placeholder="如: Binance 主账户" />
          </div>
          <div v-if="!showEdit">
            <label class="label">交易所</label>
            <select v-model="form.exchange" class="input">
              <option value="">选择交易所</option>
              <option v-for="ex in exchanges" :key="ex" :value="ex">{{ exLabel(ex) }}</option>
            </select>
          </div>
          <div>
            <label class="label">API Key</label>
            <input v-model="form.api_key" type="password" class="input" :placeholder="showEdit ? '留空不修改' : '输入API Key'" />
          </div>
          <div>
            <label class="label">API Secret</label>
            <input v-model="form.api_secret" type="password" class="input" :placeholder="showEdit ? '留空不修改' : '输入API Secret'" />
          </div>
          <div v-if="form.exchange === 'okx' || form.exchange === 'bitget'">
            <label class="label">Passphrase</label>
            <input v-model="form.passphrase" type="password" class="input" placeholder="OKX/Bitget 需要" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="label">杠杆倍数</label>
              <input v-model.number="form.leverage" type="number" class="input" min="1" max="125" />
            </div>
            <div>
              <label class="label">最大仓位 ($)</label>
              <input v-model.number="form.max_stake" type="number" class="input" min="0" step="10" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="label">持仓模式</label>
              <select v-model="form.position_mode" class="input">
                <option value="one_way">单向持仓</option>
                <option value="hedge">双向持仓</option>
              </select>
            </div>
            <div class="flex items-end gap-4">
              <label class="flex items-center gap-2 text-sm">
                <input v-model="form.is_primary" type="checkbox" /> 主账户
              </label>
              <label class="flex items-center gap-2 text-sm">
                <input v-model="form.is_active" type="checkbox" /> 启用
              </label>
            </div>
          </div>
          <div>
            <label class="label">备注</label>
            <input v-model="form.note" class="input" placeholder="可选备注" />
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-5">
          <button @click="closeModal" class="btn-ghost">取消</button>
          <button @click="submitForm" class="btn-primary">{{ showEdit ? '保存修改' : '创建账户' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useConfigStore } from '@/stores'
import { accountsApi, secretsApi } from '@/api'

const store = useConfigStore()
const accounts = computed(() => store.accounts)
const tg = computed(() => store.telegram)

const exchanges = ['binance', 'okx', 'bybit', 'gate', 'bitget']
const showAdd = ref(false)
const showEdit = ref(false)
const editingId = ref('')

const form = reactive({
  account_id: '',
  label: '',
  exchange: '',
  api_key: '',
  api_secret: '',
  passphrase: '',
  leverage: 10,
  position_mode: 'one_way',
  max_stake: 100,
  is_primary: false,
  is_active: true,
  note: '',
})

const tgForm = reactive({ bot_token: '', chat_id: '', enabled: false })

function exLabel(ex: string) {
  const m: Record<string, string> = { binance: 'Binance', okx: 'OKX', bybit: 'Bybit', gate: 'Gate.io', bitget: 'Bitget' }
  return m[ex] || ex
}

function resetForm() {
  Object.assign(form, {
    account_id: '', label: '', exchange: '', api_key: '', api_secret: '',
    passphrase: '', leverage: 10, position_mode: 'one_way', max_stake: 100,
    is_primary: false, is_active: true, note: '',
  })
}

function editAccount(a: any) {
  editingId.value = a.account_id
  Object.assign(form, {
    account_id: a.account_id,
    label: a.label || '',
    exchange: a.exchange || '',
    api_key: '',
    api_secret: '',
    passphrase: '',
    leverage: a.leverage || 10,
    position_mode: a.position_mode || 'one_way',
    max_stake: a.max_stake || 100,
    is_primary: a.is_primary || false,
    is_active: a.is_active !== false,
    note: a.note || '',
  })
  showEdit.value = true
}

function closeModal() {
  showAdd.value = false
  showEdit.value = false
  editingId.value = ''
  resetForm()
}

async function submitForm() {
  try {
    if (showEdit.value) {
      await accountsApi.update(editingId.value, { ...form })
    } else {
      if (!form.account_id || !form.exchange || !form.api_key || !form.api_secret) {
        alert('请填写必填字段: Account ID, 交易所, API Key, API Secret')
        return
      }
      await accountsApi.create({ ...form })
    }
    closeModal()
    store.fetchAccounts()
  } catch (e: any) {
    alert(e.response?.data?.detail || '操作失败')
  }
}

async function removeAccount(id: string, label: string) {
  if (!confirm(`确定删除账户 "${label}" (${id})？此操作不可恢复。`)) return
  await accountsApi.remove(id)
  store.fetchAccounts()
}

async function setPrimary(id: string) {
  await accountsApi.setPrimary(id)
  store.fetchAccounts()
}

async function saveTelegram() {
  await secretsApi.updateTelegram(tgForm)
  tgForm.bot_token = ''
  store.fetchTelegram()
  alert('Telegram 配置已更新')
}

onMounted(() => { store.fetchAccounts(); store.fetchTelegram() })
</script>
