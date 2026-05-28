<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4 flex items-center justify-between" style="border-bottom: 1px solid #1e2740;">
      <div>
        <h1 class="text-heading text-steel-100">交易所账户管理</h1>
        <p class="text-label text-steel-500 mt-0.5">多账户 API 密钥管理与 Telegram 通知</p>
      </div>
      <button @click="showAdd = true" class="btn-primary">+ 添加账户</button>
    </header>
    <div class="p-8 space-y-6">
      <!-- 账户列表 -->
      <div v-for="a in accounts" :key="a.account_id" class="card p-5">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-3">
            <span class="text-data-lg font-bold text-steel-100">{{ exLabel(a.exchange) }}</span>
            <span class="text-data text-steel-400">{{ a.label }}</span>
            <span v-if="a.is_primary" class="badge-gold text-[9px]">主账户</span>
            <span v-if="!a.is_active" class="badge-short text-[9px]">已禁用</span>
          </div>
          <div class="flex items-center gap-2">
            <button @click="editAccount(a)" class="btn-ghost text-[9px]">编辑</button>
            <button v-if="!a.is_primary" @click="setPrimary(a.account_id)" class="btn-ghost text-[9px]">设为主</button>
            <button @click="removeAccount(a.account_id, a.label)" class="text-[9px] text-loss hover:text-red-300">删除</button>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-[11px]">
          <div><span class="text-steel-500">Account ID:</span> <span class="font-mono text-steel-200">{{ a.account_id }}</span></div>
          <div><span class="text-steel-500">API Key:</span> <span class="font-mono text-steel-200">{{ a.api_key_masked || '未设置' }}</span></div>
          <div><span class="text-steel-500">杠杆:</span> <span class="font-mono text-steel-200">{{ a.leverage }}x</span></div>
          <div><span class="text-steel-500">最大仓位:</span> <span class="font-mono text-steel-200">${{ a.max_stake }}</span></div>
        </div>
        <div v-if="a.note" class="mt-2 text-[10px] text-steel-500">备注: {{ a.note }}</div>
      </div>

      <div v-if="accounts.length === 0" class="card p-5 text-center text-steel-500 py-10">
        暂无账户，点击上方"添加账户"开始配置
      </div>

      <!-- Telegram 配置 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">Telegram 通知</span>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
          <div>
            <label class="label">Bot Token</label>
            <input v-model="tgForm.bot_token" type="password" class="input" placeholder="Bot Token" />
            <p v-if="tg.bot_token_masked" class="text-[10px] font-mono text-steel-500 mt-1">{{ tg.bot_token_masked }}</p>
          </div>
          <div>
            <label class="label">Chat ID</label>
            <input v-model="tgForm.chat_id" class="input" placeholder="Chat ID" />
            <p v-if="tg.chat_id" class="text-[10px] text-steel-500 mt-1">当前: {{ tg.chat_id }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3 mt-4">
          <label class="flex items-center gap-2 text-data text-steel-300">
            <input v-model="tgForm.enabled" type="checkbox" /> 启用通知
          </label>
          <button @click="saveTelegram" class="btn-primary text-[9px]">保存 Telegram</button>
        </div>
      </div>

      <!-- 添加/编辑弹窗 -->
      <div v-if="showAdd || showEdit" class="fixed inset-0 z-50 flex items-center justify-center p-4" style="background: rgba(0,0,0,0.7);" @click.self="closeModal">
        <div class="card p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
          <span class="text-label text-steel-500">{{ showEdit ? '编辑账户' : '添加账户' }}</span>
          <div class="space-y-4 mt-4">
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
                <label class="flex items-center gap-2 text-data text-steel-300">
                  <input v-model="form.is_primary" type="checkbox" /> 主账户
                </label>
                <label class="flex items-center gap-2 text-data text-steel-300">
                  <input v-model="form.is_active" type="checkbox" /> 启用
                </label>
              </div>
            </div>
            <div>
              <label class="label">备注</label>
              <input v-model="form.note" class="input" placeholder="可选备注" />
            </div>
          </div>
          <div class="flex justify-end gap-3 mt-6 pt-4" style="border-top: 1px solid #1e2740;">
            <button @click="closeModal" class="btn-ghost">取消</button>
            <button @click="submitForm" class="btn-primary">{{ showEdit ? '保存修改' : '创建账户' }}</button>
          </div>
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
  account_id: '', label: '', exchange: '', api_key: '', api_secret: '',
  passphrase: '', leverage: 10, position_mode: 'one_way', max_stake: 100,
  is_primary: false, is_active: true, note: '',
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
    account_id: a.account_id, label: a.label || '', exchange: a.exchange || '',
    api_key: '', api_secret: '', passphrase: '', leverage: a.leverage || 10,
    position_mode: a.position_mode || 'one_way', max_stake: a.max_stake || 100,
    is_primary: a.is_primary || false, is_active: a.is_active !== false, note: a.note || '',
  })
  showEdit.value = true
}

function closeModal() {
  showAdd.value = false; showEdit.value = false; editingId.value = ''; resetForm()
}

async function submitForm() {
  try {
    if (showEdit.value) {
      await accountsApi.update(editingId.value, { ...form })
    } else {
      if (!form.account_id || !form.exchange || !form.api_key || !form.api_secret) {
        alert('请填写必填字段: Account ID, 交易所, API Key, API Secret'); return
      }
      await accountsApi.create({ ...form })
    }
    closeModal(); store.fetchAccounts()
  } catch (e: any) { alert(e.response?.data?.detail || '操作失败') }
}

async function removeAccount(id: string, label: string) {
  if (!confirm(`确定删除账户 "${label}" (${id})？此操作不可恢复。`)) return
  await accountsApi.remove(id); store.fetchAccounts()
}

async function setPrimary(id: string) {
  await accountsApi.setPrimary(id); store.fetchAccounts()
}

async function saveTelegram() {
  await secretsApi.updateTelegram(tgForm); tgForm.bot_token = ''
  store.fetchTelegram(); alert('Telegram 配置已更新')
}

onMounted(() => { store.fetchAccounts(); store.fetchTelegram() })
</script>