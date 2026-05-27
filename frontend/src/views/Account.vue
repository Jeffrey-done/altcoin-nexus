<template>
  <div class="p-6 space-y-6">
    <h2 class="text-xl font-bold">账号安全</h2>

    <!-- 当前账号信息 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-3">账号信息</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div>
          <span class="text-gray-400">用户名:</span>
          <span class="ml-2 font-mono">{{ user?.username || 'admin' }}</span>
        </div>
        <div>
          <span class="text-gray-400">2FA 状态:</span>
          <span class="ml-2" :class="user?.totp_enabled ? 'text-emerald-400' : 'text-yellow-400'">
            {{ user?.totp_enabled ? '已启用' : '未启用' }}
          </span>
        </div>
      </div>
    </div>

    <!-- 2FA 设置 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-3">双因素认证 (TOTP)</h3>
      <p class="text-xs text-gray-500 mb-3">使用 Google Authenticator / Authy 等应用扫码绑定</p>
      <div v-if="totpInfo">
        <div class="bg-gray-700 rounded-lg p-4 mb-3">
          <p class="text-xs text-gray-400 mb-1">TOTP 密钥 (手动输入):</p>
          <p class="font-mono text-sm text-sky-400 break-all">{{ totpInfo.secret }}</p>
        </div>
        <p class="text-xs text-gray-400 mb-1">URI (可生成二维码):</p>
        <p class="text-xs font-mono text-gray-500 break-all mb-3">{{ totpInfo.uri }}</p>
        <p class="text-xs text-yellow-400">设置环境变量 WEB_TOTP_SECRET 和 WEB_TOTP_ENABLED=true 以启用</p>
      </div>
      <button @click="loadTotp" class="btn-ghost text-xs mt-2">获取 TOTP 设置</button>
    </div>

    <!-- IP 白名单 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-3">IP 白名单</h3>
      <p class="text-xs text-gray-500 mb-3">设置环境变量 WEB_IP_WHITELIST (逗号分隔)</p>
      <div v-if="user?.ip_whitelist?.length">
        <div class="flex flex-wrap gap-2">
          <span v-for="ip in user.ip_whitelist" :key="ip" class="px-2 py-1 bg-gray-700 rounded text-xs font-mono">{{ ip }}</span>
        </div>
      </div>
      <p v-else class="text-xs text-gray-500">未设置 (允许所有IP)</p>
    </div>

    <!-- 活跃会话 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-3">活跃会话</h3>
      <div class="space-y-2">
        <div v-for="s in sessions" :key="s.session_id" class="flex items-center justify-between p-3 bg-gray-700/50 rounded-lg">
          <div>
            <p class="text-sm font-medium">{{ s.username }}</p>
            <p class="text-xs text-gray-500">创建: {{ fmtTime(s.created_at) }} | 活跃: {{ fmtTime(s.last_active) }}</p>
          </div>
          <button @click="revokeSession(s.session_id)" class="text-xs text-red-400 hover:text-red-300">撤销</button>
        </div>
        <div v-if="sessions.length===0" class="text-center py-4 text-gray-500 text-sm">无活跃会话</div>
      </div>
    </div>

    <!-- 修改密码提示 -->
    <div class="card">
      <h3 class="text-sm font-medium text-gray-400 mb-3">修改密码</h3>
      <p class="text-xs text-gray-500">通过环境变量 WEB_ADMIN_PASSWORD_HASH 设置密码哈希。</p>
      <p class="text-xs text-gray-500 mt-1">可使用 python -c "from web.auth import hash_password; print(hash_password('新密码'))" 生成。</p>
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
