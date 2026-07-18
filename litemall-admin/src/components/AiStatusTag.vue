<template>
  <span :class="['ai-status-tag', statusClass]">{{ text }}</span>
</template>

<script>
const STATUS_TEXT = {
  success: '成功',
  failed: '失败',
  pending: '待处理',
  processed: '已处理',
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  enabled: '已启用',
  disabled: '已停用',
  approved: '已批准',
  rejected: '已拒绝',
  fallback: '本地回退',
  demo: '演示模式',
  neutral: '正常'
}

export default {
  name: 'AiStatusTag',
  props: {
    status: { type: String, default: 'neutral' },
    label: { type: String, default: '' }
  },
  computed: {
    text() {
      return this.label || STATUS_TEXT[this.status] || this.status || '正常'
    },
    statusClass() {
      const map = {
        success: 'ai-status-positive',
        failed: 'ai-status-negative',
        pending: 'ai-status-medium',
        processed: 'ai-status-positive',
        enabled: 'ai-status-positive',
        disabled: 'ai-status-neutral',
        approved: 'ai-status-positive',
        rejected: 'ai-status-negative',
        fallback: 'ai-status-medium',
        demo: 'ai-status-low'
      }
      return map[this.status] || 'ai-status-' + this.status
    }
  }
}
</script>
