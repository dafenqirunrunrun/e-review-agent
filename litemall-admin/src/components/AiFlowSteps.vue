<template>
  <div class="ai-flow-steps">
    <button
      v-for="(step, index) in steps"
      :key="step.title"
      :class="['ai-flow-step', { active: index === active }]"
      type="button"
      @click="$emit('select', step, index)"
    >
      <span class="ai-flow-index">{{ index + 1 }}</span>
      <strong>{{ step.title }}</strong>
      <em>{{ step.description }}</em>
    </button>
  </div>
</template>

<script>
export default {
  name: 'AiFlowSteps',
  props: {
    steps: { type: Array, default: () => [] },
    active: { type: Number, default: 0 }
  }
}
</script>
