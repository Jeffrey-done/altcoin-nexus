<template>
  <div>
    <label class="label">{{ label }}</label>
    <div class="flex gap-2">
      <template v-if="readonly">
        <div class="input flex-1 flex items-center" style="opacity: 0.7; cursor: default; background: rgba(255,255,255,0.02);">
          <span v-if="type === 'bool'">{{ displayBool }}</span>
          <span v-else>{{ value ?? '-' }}</span>
          <span v-if="type === 'number' && field.includes('pct')" class="ml-0.5 text-steel-500 text-[9px]">%</span>
        </div>
        <div class="flex items-center px-2 text-steel-600 text-[9px]" title="只读 - 由系统管理">
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        </div>
      </template>
      <template v-else>
        <template v-if="type === 'bool'">
          <button @click="toggle" class="input text-left" :style="localVal ? 'border-color: rgba(34,197,94,0.4); color: #22c55e;' : ''">
            {{ localVal ? '启用' : '禁用' }}
          </button>
        </template>
        <template v-else-if="type === 'select'">
          <select v-model="localVal" class="input flex-1">
            <option v-for="o in options" :key="o" :value="o">{{ o }}</option>
          </select>
        </template>
        <template v-else>
          <input v-model="localVal" :type="type === 'number' ? 'number' : 'text'" class="input flex-1" :step="type==='number'?'any':undefined" />
        </template>
        <button @click="save" class="btn-primary text-[9px] px-3">保存</button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{
  label: string
  section: string
  field: string
  value: any
  type: string
  options?: string[]
  readonly?: boolean
}>()

const emit = defineEmits<{ save: [section: string, key: string, value: any] }>()

const localVal = ref(props.value)
watch(() => props.value, (v) => { localVal.value = v })

const displayBool = computed(() => props.value ? '启用' : '禁用')

function toggle() { localVal.value = !localVal.value; save() }
function save() {
  let v = localVal.value
  if (props.type === 'number') v = Number(v)
  emit('save', props.section, props.field, v)
}
</script>
