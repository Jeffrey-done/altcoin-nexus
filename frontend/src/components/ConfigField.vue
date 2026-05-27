<template>
  <div>
    <label class="label">{{ label }}</label>
    <div class="flex gap-2">
      <template v-if="type === 'bool'">
        <button @click="toggle" class="input text-left" :class="localVal ? 'border-emerald-500' : 'border-gray-600'">
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
      <button @click="save" class="btn-primary text-xs px-3">保存</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  label: string
  section: string
  field: string
  value: any
  type: string
  options?: string[]
}>()

const emit = defineEmits<{ save: [section: string, key: string, value: any] }>()

const localVal = ref(props.value)
watch(() => props.value, (v) => { localVal.value = v })

function toggle() { localVal.value = !localVal.value; save() }
function save() {
  let v = localVal.value
  if (props.type === 'number') v = Number(v)
  emit('save', props.section, props.field, v)
}
</script>
