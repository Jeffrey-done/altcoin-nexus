<template>
  <div ref="chartRef" class="w-full h-64"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  data: { name: string; value: number }[]
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function initChart() {
  if (!chartRef.value) return
  
  chart = echarts.init(chartRef.value)
  updateChart()
}

function updateChart() {
  if (!chart) return

  const option = {
    backgroundColor: 'transparent',
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#111827',
          borderWidth: 2,
        },
        label: {
          show: true,
          color: '#9CA3AF',
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
          },
        },
        data: props.data.map((d, i) => ({
          ...d,
          itemStyle: {
            color: i === 0 ? '#ef4444' : '#22c55e',
          },
        })),
      },
    ],
    tooltip: {
      trigger: 'item',
      backgroundColor: '#1F2937',
      borderColor: '#374151',
      textStyle: { color: '#F3F4F6' },
    },
  }

  chart.setOption(option)
}

watch(() => props.data, updateChart, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', () => chart?.resize())
})
</script>
