<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-900 p-4">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-sky-400">Altcoin Nexus</h1>
        <p class="text-gray-500 text-sm mt-1">L4级自治量化交易系统</p>
      </div>
      <form @submit.prevent="handleLogin" class="card space-y-4">
        <div>
          <label class="label">用户名</label>
          <input v-model="form.username" type="text" class="input" placeholder="admin" autofocus />
        </div>
        <div>
          <label class="label">密码</label>
          <input v-model="form.password" type="password" class="input" placeholder="••••••••" />
        </div>
        <div v-if="showTotp">
          <label class="label">2FA 验证码</label>
          <input v-model="form.totp_code" type="text" class="input" placeholder="6位数字" maxlength="6" />
        </div>
        <div v-if="error" class="text-red-400 text-xs bg-red-500/10 p-2 rounded">{{ error }}</div>
        <button type="submit" class="w-full btn-primary" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()
const form = reactive({ username: '', password: '', totp_code: '' })
const error = ref('')
const loading = ref(false)
const showTotp = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(form.username, form.password, form.totp_code || undefined)
    router.push('/')
  } catch (e: any) {
    const msg = e.response?.data?.detail || '登录失败'
    if (msg.includes('2FA')) { showTotp.value = true }
    error.value = msg
  } finally { loading.value = false }
}
</script>
