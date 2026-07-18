<template>
  <div class="ai-workbench-page ai-aggregate-page ai-governance-flow-page">
    <ai-page-header
      title="评论治理流程"
      subtitle="把真实评价、智能体巡检、风险任务和运营处理放在同一条业务路径中，便于现场从左到右完成一次评论治理演示。"
      module="主业务路径"
      boundary="本页聚合已有页面能力，不删除原商品评论、巡检、风险中心或运营中心接口。"
    >
      <template slot="actions">
        <el-button icon="el-icon-house" @click="$router.push('/ai-workbench/home')">返回首页</el-button>
      </template>
    </ai-page-header>

    <div class="ai-card">
      <ai-flow-steps :steps="steps" :active="activeIndex" @select="selectStep" />
    </div>

    <el-tabs v-model="activeTab" type="border-card" @tab-click="syncQuery">
      <el-tab-pane label="真实评价" name="reviews">
        <p class="ai-section-note">从 H5 用户端提交的真实商品评价会进入这里，运营人员也可以在商品评论列表中手动触发 AI 分析。</p>
        <div class="ai-embedded-panel"><goods-comment v-if="activeTab === 'reviews'" /></div>
      </el-tab-pane>
      <el-tab-pane label="智能体巡检" name="patrol">
        <p class="ai-section-note">巡检会扫描待分析评论，调用本地 AI 服务，生成分析结果并在高风险时创建风险任务。</p>
        <div class="ai-embedded-panel"><ai-patrol v-if="activeTab === 'patrol'" /></div>
      </el-tab-pane>
      <el-tab-pane label="风险任务" name="risk">
        <p class="ai-section-note">风险任务集中展示负向、低置信度、图文冲突和售后风险评论，可跳转到运营处理。</p>
        <div class="ai-quick-actions"><el-button size="mini" type="primary" @click="activeTab = 'operation'; syncQuery()">进入运营处理</el-button></div>
        <div class="ai-embedded-panel"><ai-risk v-if="activeTab === 'risk'" /></div>
      </el-tab-pane>
      <el-tab-pane label="运营处理" name="operation">
        <p class="ai-section-note">运营人员在这里采纳建议、转交售后、关闭或标记误报；处理完成后可到“运行观测与评估”查看反馈影响。</p>
        <div class="ai-quick-actions"><el-button size="mini" @click="$router.push({ path: '/ai-workbench/observability', query: { tab: 'eval' }})">查看质量反馈</el-button></div>
        <div class="ai-embedded-panel"><ai-operation v-if="activeTab === 'operation'" /></div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script>
import AiFlowSteps from '@/components/AiFlowSteps'
import AiPageHeader from '@/components/AiPageHeader'
import GoodsComment from '@/views/goods/comment'
import AiPatrol from '@/views/ai-patrol/index'
import AiRisk from '@/views/ai-risk/index'
import AiOperation from '@/views/ai-operation/index'

export default {
  name: 'AiGovernanceFlow',
  components: { AiFlowSteps, AiPageHeader, GoodsComment, AiPatrol, AiRisk, AiOperation },
  data() {
    return {
      activeTab: this.$route.query.tab || 'reviews',
      steps: [
        { title: '真实评价', description: '查看用户端真实商品评价。', tab: 'reviews' },
        { title: '智能体巡检', description: '扫描未分析评价并生成结果。', tab: 'patrol' },
        { title: '风险任务', description: '识别需要运营跟进的风险。', tab: 'risk' },
        { title: '运营处理', description: '人工确认并完成闭环处理。', tab: 'operation' },
        { title: '人工反馈', description: '处理结果回写评估体系。', tab: 'operation' }
      ]
    }
  },
  computed: {
    activeIndex() {
      const index = this.steps.findIndex(item => item.tab === this.activeTab)
      return index >= 0 ? index : 0
    }
  },
  watch: {
    '$route.query.tab'(value) {
      if (value && value !== this.activeTab) {
        this.activeTab = value
      }
    }
  },
  methods: {
    selectStep(step) {
      this.activeTab = step.tab
      this.syncQuery()
    },
    syncQuery() {
      this.$router.replace({ path: this.$route.path, query: { tab: this.activeTab }})
    }
  }
}
</script>
