<template>
  <div :class="['ai-metric-card', statusClass]">
    <div class="ai-metric-label">{{ label }}</div>
    <div class="ai-metric-value">{{ safeValue }}</div>
    <div v-if="hint" class="ai-metric-hint">{{ hint }}</div>
    <div v-if="trend" class="ai-metric-trend">{{ trend }}</div>
  </div>
</template>

<script>
export default {
  name: 'AiMetricCard',
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number], default: '0' },
    hint: { type: String, default: '' },
    status: { type: String, default: 'neutral' },
    trend: { type: String, default: '' }
  },
  computed: {
    safeValue() {
      if (this.value === undefined || this.value === null || this.value === '') {
        return '0'
      }
      return String(this.value)
    },
    statusClass() {
      return 'ai-metric-' + this.status
    }
  }
}
</script>
