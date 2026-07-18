<template>
  <div class="ai-page-header ai-product-header">
    <div>
      <p v-if="module" class="ai-page-kicker">{{ module }}</p>
      <h1 class="ai-page-title">{{ title }}</h1>
      <p v-if="subtitle" class="ai-page-subtitle">{{ subtitle }}</p>
      <p v-if="boundary" class="ai-boundary-note">{{ boundary }}</p>
    </div>
    <div v-if="$slots.actions" class="ai-toolbar">
      <slot name="actions" />
    </div>
  </div>
</template>

<script>
export default {
  name: 'AiPageHeader',
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    module: { type: String, default: 'E-Review Agent' },
    boundary: { type: String, default: '' }
  }
}
</script>
