<template>
  <div class="ai-empty-state">
    <i :class="icon" />
    <strong>{{ title }}</strong>
    <span>{{ description }}</span>
    <el-button v-if="actionText" size="mini" type="primary" @click="$emit('action')">
      {{ actionText }}
    </el-button>
  </div>
</template>

<script>
export default {
  name: 'AiEmptyState',
  props: {
    title: { type: String, default: '暂无数据' },
    description: { type: String, default: '完成主流程后这里会出现可展示数据。' },
    actionText: { type: String, default: '' },
    icon: { type: String, default: 'el-icon-data-analysis' }
  }
}
</script>
