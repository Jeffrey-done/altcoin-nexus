<template>
  <div class="min-h-screen" style="background: #0a0e1a;">
    <header class="px-8 py-4" style="border-bottom: 1px solid #1e2740;">
      <h1 class="text-heading text-steel-100">账号安全</h1>
      <p class="text-label text-steel-500 mt-0.5">认证信息、双因素认证、会话管理</p>
    </header>
    <div class="p-8 space-y-6">
      <!-- 账号信息 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">账号信息</span>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-data">
          <div>
            <span class="text-steel-500">用户名:</span>
            <span class="ml-2 font-mono text-steel-100">{{ user?.username || 'admin' }}</span>
          </div>
          <div>
            <span class="text-steel-500">2FA 状态:</span>
            <span class="ml-2 font-medium" :class="user?.totp_enabled ? 'text-gain' : 'text-yellow-400'">
              {{ user?.totp_enabled ? '已启用' : '未启用' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 2FA 设置 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">双因素认证 (TOTP)</span>
        <p class="text-[11px] text-steel-500 mt-2 mb-4">使用 Google Authenticator / Authy 等应用扫码绑定</p>
        <div v-if="totpInfo">
          <div class="rounded-card p-4 mb-3" style="background: rgba(255,255,255,0.03); border: 1px solid #1e2740;">
            <p class="text-[10px] text-steel-500 mb-1">TOTP 密钥 (手动输入):</p>
            <p class="font-mono text-data text-gold-400 break-all">{{ totpInfo.secret }}</p>
          </div>
          <p class="text-[10px] text-steel-500 mb-1">URI (可生成二维码):</p>
          <p class="text-[10px] font-mono text-steel-600 break-all mb-3">{{ totpInfo.uri }}</p>
          <p class="text-[10px] text-yellow-400">设置环境变量 WEB_TOTP_SECRET 和 WEB_TOTP_ENABLED=true 以启用</p>
        </div>
        <button @click="loadTotp" class="btn-ghost text-[9px] mt-2">获取 TOTP 设置</button>
      </div>

      <!-- IP 白名单 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">IP 白名单</span>
        <p class="text-[11px] text-steel-500 mt-2 mb-4">设置环境变量 WEB_IP_WHITELIST (逗号分隔)</p>
        <div v-if="user?.ip_whitelist?.length">
          <div class="flex flex-wrap gap-2">
            <span v-for="ip in user.ip_whitelist" :key="ip" class="px-2.5 py-1 rounded-lg text-[11px] font-mono" style="background: rgba(255,255,255,0.04); border: 1px solid #1e2740;">{{ ip }}</span>
          </div>
        </div>
        <p v-else class="text-[11px] text-steel-500">未设置 (允许所有IP)</p>
      </div>

      <!-- 活跃会话 -->
      <div class="card p-0">
        <div class="p-4" style="border-bottom: 1px solid #1e2740;">
          <span class="text-label text-steel-500">活跃会话</span>
        </div>
        <div class="divide-y" style="border-color: rgba(30,39,64,0.4);">
          <div v-for="s in sessions" :key="s.session_id" class="flex items-center justify-between px-4 py-3">
            <div>
              <p class="text-data font-medium text-steel-100">{{ s.username }}</p>
              <p class="text-[10px] font-mono text-steel-500 mt-0.5">创建: {{ fmtTime(s.created_at) }} · 活跃: {{ fmtTime(s.last_active) }}</p>
            </div>
            <button @click="revokeSession(s.session_id)" class="text-[10px] text-loss hover:text-red-300">撤销</button>
          </div>
          <div v-if="sessions.length===0" class="py-10 text-center text-steel-500">无活跃会话</div>
        </div>
      </div>

      <!-- 修改密码 -->
      <div class="card p-5">
        <span class="text-label text-steel-500">修改密码</span>
        <p class="text-[11px] text-steel-500 mt-2">通过环境变量 WEB_ADMIN_PASSWORD_HASH 设置密码哈希。</p>
        <p class="text-[10px] font-mono text-steel-600 mt-1">python -c "from web.auth import hash_password; print(hash_password('新密码'))"</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores'
import { authApi } from '@/api'

const authStore = useAuthStore()
const user = computed(() => authStore.user)
const sessions = ref<any[]>([])
const totpInfo = ref<any>(null)

function fmtTime(ts: string) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })
}

async function loadSessions() {
  const res: any = await authApi.sessions()
  sessions.value = res.sessions || []
}

async function revokeSession(id: string) {
  await authApi.revokeSession(id)
  loadSessions()
}

async function loadTotp() {
  totpInfo.value = await authApi.totpSetup()
}

onMounted(() => { authStore.fetchMe(); loadSessions() })
</script>