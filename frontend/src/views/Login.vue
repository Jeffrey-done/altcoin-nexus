<template>
  <div class="min-h-screen flex items-center justify-center p-4" style="background: #0a0e1a;">
    <!-- 背景装饰 -->
    <div class="fixed inset-0 pointer-events-none" style="
      background:
        radial-gradient(ellipse 60% 40% at 50% 30%, rgba(212, 168, 83, 0.04) 0%, transparent 60%),
        radial-gradient(ellipse 80% 60% at 20% 80%, rgba(30, 39, 64, 0.4) 0%, transparent 50%);
    "></div>

    <div class="w-full max-w-sm relative z-10">
      <!-- 品牌 -->
      <div class="text-center mb-10">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-lg mb-4" style="background: linear-gradient(135deg, #d4a853, #9a7b1f);">
          <span class="text-lg font-black text-terminal">N</span>
        </div>
        <h1 class="text-xl font-bold text-steel-100 tracking-tight">ALTCOIN NEXUS</h1>
        <p class="text-label text-steel-500 mt-1.5 tracking-[0.3em]">交易终端</p>
        <p class="text-[10px] font-mono text-steel-600 mt-2">L4 级自治量化交易系统</p>
      </div>

      <!-- 登录表单 -->
      <form @submit.prevent="handleLogin" class="card p-6 space-y-5">
        <div class="flex items-center justify-between mb-2">
          <span class="text-label text-steel-500">身份认证</span>
          <span class="text-[8px] font-mono text-steel-600 tracking-wider">安全会话</span>
        </div>

        <div>
          <label class="label">用户名</label>
          <input
            v-model="form.username"
            type="text"
            class="input"
            placeholder="请输入用户名"
            autofocus
            autocomplete="username"
          />
        </div>

        <div>
          <label class="label">密码</label>
          <input
            v-model="form.password"
            type="password"
            class="input"
            placeholder="请输入密码"
            autocomplete="current-password"
          />
        </div>

        <div v-if="showTotp">
          <label class="label">双因素验证码</label>
          <input
            v-model="form.totp_code"
            type="text"
            class="input font-mono tracking-[0.3em] text-center"
            placeholder="000000"
            maxlength="6"
            inputmode="numeric"
          />
        </div>

        <!-- 错误信息 -->
        <div v-if="error" class="flex items-start gap-2 p-3 rounded" style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.15);">
          <span class="text-loss text-[10px] mt-0.5">⚠</span>
          <span class="text-[11px] text-loss/80">{{ error }}</span>
        </div>

        <button type="submit" class="w-full btn-gold py-3 text-[11px]" :disabled="loading">
          {{ loading ? '认证中...' : '登 录' }}
        </button>

        <!-- 底部信息 -->
        <div class="pt-3" style="border-top: 1px solid #1e2740;">
          <p class="text-[9px] font-mono text-steel-600 text-center tracking-wider">
            NEXUS v4.0.0 · 加密会话 · JWT 认证
          </p>
        </div>
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
    const msg = e.response?.data?.detail || '认证失败'
    if (msg.includes('2FA')) { showTotp.value = true }
    error.value = msg
  } finally { loading.value = false }
}
</script>