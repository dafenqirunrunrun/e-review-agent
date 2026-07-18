<template>
  <div class="ai-workbench-page ai-aggregate-page ai-knowledge-quality-page">
    <ai-page-header
      title="知识增强与质量"
      subtitle="本页面展示系统如何利用历史案例、检索质量评估和本地记忆辅助评论治理。当前不依赖外部向量数据库，属于本地可运行的检索增强原型。"
      module="知识增强"
      boundary="案例、检索质量和本地记忆均服务于评论治理解释，不接入 Qdrant 或外部向量数据库。"
    />

    <el-tabs v-model="activeTab" type="border-card" @tab-click="syncQuery">
      <el-tab-pane label="案例知识库" name="case">
        <p class="ai-section-note">案例检索用于给运营建议提供历史处理依据，是答辩中解释 AI 建议来源的重点入口。</p>
        <div class="ai-embedded-panel"><ai-case-knowledge v-if="activeTab === 'case'" /></div>
      </el-tab-pane>
      <el-tab-pane label="检索质量" name="rag">
        <p class="ai-section-note">RAG 质量只评价本地案例检索命中、证据覆盖和策略对比，不等同于外部向量数据库。</p>
        <div class="ai-embedded-panel"><ai-enterprise-platform v-if="activeTab === 'rag'" mode-override="rag-quality" /></div>
      </el-tab-pane>
      <el-tab-pane label="本地记忆" name="memory">
        <p class="ai-section-note">本地记忆用于沉淀商品、风险和处理证据，不描述为生产级用户画像。</p>
        <div class="ai-embedded-panel"><ai-enterprise-platform v-if="activeTab === 'memory'" mode-override="memory" /></div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script>
import AiPageHeader from '@/components/AiPageHeader'
import AiCaseKnowledge from '@/views/ai-case-knowledge/index'
import AiEnterprisePlatform from '@/views/ai-enterprise-platform/index'

export default {
  name: 'AiKnowledgeQuality',
  components: { AiPageHeader, AiCaseKnowledge, AiEnterprisePlatform },
  data() {
    return {
      activeTab: this.$route.query.tab || 'case'
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
