<template>
  <div class="ai-workbench-page ai-aggregate-page ai-observability-page">
    <ai-page-header
      title="运行观测与评估"
      subtitle="可观测智能体指的是每一次评论治理运行都能被追踪、重放、评估和诊断，便于解释系统为什么给出某个风险判断。"
      module="智能体运行质量"
      boundary="本页只展示本地演示环境中的运行证据，不声明生产级运维能力。"
    />

    <el-tabs v-model="activeTab" type="border-card" @tab-click="syncQuery">
      <el-tab-pane label="执行追踪" name="trace">
        <p class="ai-section-note">保留状态快照、角色步骤、输入输出摘要和错误摘要，用于说明智能体的可解释执行过程。</p>
        <div class="ai-embedded-panel"><ai-agent-trace v-if="activeTab === 'trace'" /></div>
      </el-tab-pane>
      <el-tab-pane label="重放对比" name="replay">
        <p class="ai-section-note">重放是执行追踪中的子能力，适合对同一条评价重新运行并比较结果变化。</p>
        <div class="ai-embedded-panel"><ai-agent-trace v-if="activeTab === 'replay'" /></div>
      </el-tab-pane>
      <el-tab-pane label="质量评估" name="eval">
        <p class="ai-section-note">汇总质量指标、人工反馈和服务健康信息，避免和 RAG 检索质量混在一起。</p>
        <div class="ai-embedded-panel"><ai-agent-eval v-if="activeTab === 'eval'" /></div>
      </el-tab-pane>
      <el-tab-pane label="运维趋势" name="agentops">
        <p class="ai-section-note">AgentOps 只展示运行趋势、失败分布和本地回退，不抢占首页业务摘要。</p>
        <div class="ai-embedded-panel"><ai-enterprise-platform v-if="activeTab === 'agentops'" mode-override="agentops" /></div>
      </el-tab-pane>
      <el-tab-pane label="失败诊断" name="diagnostics">
        <p class="ai-section-note">诊断信息放在最后，用于排查失败运行、失败步骤和服务健康，不作为答辩主入口。</p>
        <div class="ai-embedded-panel"><ai-agent-eval v-if="activeTab === 'diagnostics'" /></div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script>
import AiPageHeader from '@/components/AiPageHeader'
import AiAgentTrace from '@/views/ai-agent-trace/index'
import AiAgentEval from '@/views/ai-agent-eval/index'
import AiEnterprisePlatform from '@/views/ai-enterprise-platform/index'

export default {
  name: 'AiObservability',
  components: { AiPageHeader, AiAgentTrace, AiAgentEval, AiEnterprisePlatform },
  data() {
    return {
      activeTab: this.$route.query.tab || 'trace'
    }
  },
  watch: {
    '$route.query.tab'(value) {
      if (value && value !== this.activeTab) this.activeTab = value
    }
  },
  methods: {
    syncQuery() {
      this.$router.replace({ path: this.$route.path, query: { tab: this.activeTab }})
    }
  }
}
</script>
