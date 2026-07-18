<template>
  <div class="ai-workbench-page ai-home-page">
    <ai-page-header
      title="电商图文评论智能治理工作台"
      subtitle="本系统将 H5 用户端真实评价接入后台智能体治理流程，支持自动巡检、风险识别、运营处理、执行追踪、质量评估和平台化治理。"
      module="智能治理首页"
      boundary="本页聚焦评论治理业务主路径；答辩前服务检查、数据库备份和交付包生成保留在脚本与文档中。"
    >
      <template slot="actions">
        <el-button icon="el-icon-refresh" :loading="loading" @click="loadData">刷新首页</el-button>
        <el-button type="primary" icon="el-icon-video-play" @click="startDemo">开始 5 分钟演示</el-button>
      </template>
    </ai-page-header>

    <div class="ai-card">
      <div class="ai-card-header">
        <div>
          <h2 class="ai-card-title">快速了解系统</h2>
          <p class="ai-card-desc">沿着下面 5 步走，老师可以在 5 分钟内看懂“真实评价进入智能体治理闭环”的价值。</p>
        </div>
        <div class="ai-quick-actions">
          <ai-status-tag status="demo" :label="demoModeText" />
          <ai-status-tag :status="aiServiceOk ? 'success' : 'failed'" :label="aiServiceText" />
        </div>
      </div>
      <ai-flow-steps :steps="flowSteps" :active="activeGuideStep" @select="handleFlowStep" />
    </div>

    <div class="ai-metric-grid dashboard-summary">
      <ai-metric-card v-for="item in metrics" :key="item.label" v-bind="item" />
    </div>

    <el-row :gutter="18" class="home-main-row">
      <el-col :xs="24" :lg="14">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">推荐演示路径</h2>
              <p class="ai-card-desc">从前台真实评价开始，到后台智能体巡检、风险任务和运营处理结束。</p>
            </div>
          </div>
          <div class="demo-path">
            <span v-for="item in demoPath" :key="item">{{ item }}</span>
          </div>
          <div class="ai-advice-note">
            建议答辩时先打开 H5 用户端提交一条带图片 URL 的负向评价，再回到后台点击“执行一次巡检”，最后查看风险中心、运营处理和执行追踪。
          </div>
        </div>

        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">最近智能体运行</h2>
              <p class="ai-card-desc">用于说明每次巡检和评价分析都有可追踪的执行记录。</p>
            </div>
            <el-button size="mini" @click="go('/ai-workbench/observability', 'trace')">查看执行追踪</el-button>
          </div>
          <el-table :data="recentRuns" border fit empty-text="暂无智能体运行记录，请先执行一次巡检。">
            <el-table-column prop="runNo" label="运行编号" min-width="170" show-overflow-tooltip />
            <el-table-column prop="triggerType" label="触发方式" width="150" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template slot-scope="scope">
                <ai-status-tag :status="scope.row.status === 'success' ? 'success' : (scope.row.status === 'failed' ? 'failed' : 'pending')" :label="statusText(scope.row.status)" />
              </template>
            </el-table-column>
            <el-table-column prop="durationMs" label="耗时(ms)" width="110" />
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">最近风险任务</h2>
              <p class="ai-card-desc">展示当前最适合进入运营处理的风险评论。</p>
            </div>
            <el-button size="mini" @click="go('/ai-workbench/governance-flow', 'risk')">查看风险任务</el-button>
          </div>
          <el-table :data="recentRisks" border fit empty-text="暂无风险任务。">
            <el-table-column prop="productName" label="商品" min-width="130" show-overflow-tooltip />
            <el-table-column prop="riskLevel" label="风险" width="90">
              <template slot-scope="scope">
                <ai-status-tag :status="scope.row.riskLevel || 'medium'" :label="riskText(scope.row.riskLevel)" />
              </template>
            </el-table-column>
            <el-table-column prop="status" label="处理" width="96">
              <template slot-scope="scope">{{ riskStatusText(scope.row.status) }}</template>
            </el-table-column>
          </el-table>
          <ai-empty-state
            v-if="!recentRisks.length && !loading"
            title="当前没有风险任务"
            description="可以先提交 H5 真实评价，再执行智能体巡检。"
            action-text="执行一次巡检"
            @action="runOnce"
          />
        </div>

        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">高级能力入口</h2>
              <p class="ai-card-desc">高级平台能力被折叠在下方，不干扰主流程。</p>
            </div>
          </div>
          <div class="ai-advanced-grid">
            <div v-for="item in advancedEntries" :key="item.title" class="ai-advanced-card">
              <strong>{{ item.title }}</strong>
              <span>{{ item.desc }}</span>
              <el-button size="mini" @click="go(item.path, item.tab)">进入</el-button>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import AiEmptyState from '@/components/AiEmptyState'
import AiFlowSteps from '@/components/AiFlowSteps'
import AiMetricCard from '@/components/AiMetricCard'
import AiPageHeader from '@/components/AiPageHeader'
import AiStatusTag from '@/components/AiStatusTag'
import { dashboardSummary, demoStatus } from '@/api/aiDashboard'
import { runPatrolOnce } from '@/api/aiPatrol'
import { listRiskTasks } from '@/api/aiRisk'
import { listAgentRuns } from '@/api/aiAgent'

export default {
  name: 'AiWorkbenchHome',
  components: { AiEmptyState, AiFlowSteps, AiMetricCard, AiPageHeader, AiStatusTag },
  data() {
    return {
      loading: false,
      runLoading: false,
      summary: {},
      demoStatusData: {},
      recentRisks: [],
      recentRuns: [],
      activeGuideStep: 0
    }
  },
  computed: {
    metrics() {
      return [
        { label: '今日新增评价', value: this.safeNumber(this.summary.analysesToday), hint: '今日进入治理链路的评价分析量', status: 'positive' },
        { label: '待分析评价', value: this.safeNumber(this.summary.pendingDemoReviews), hint: '等待智能体巡检分析', status: 'medium' },
        { label: '待处理风险', value: this.safeNumber(this.summary.openRiskTasks), hint: '风险中心仍未关闭的任务', status: 'high' },
        { label: '已处理任务', value: this.safeNumber(this.summary.handledOperationLogs), hint: '运营侧已记录处理动作', status: 'positive' },
        { label: '智能体运行次数', value: this.safeNumber(this.summary.totalAgentRuns || this.summary.totalAnalyses), hint: '分析、巡检与重放形成的运行记录', status: 'neutral' },
        { label: '演示模式状态', value: this.demoModeText, hint: '演示支付和演示发货不调用真实外部服务', status: 'medium' },
        { label: 'AI 服务状态', value: this.aiServiceText, hint: '本地 AI 服务用于评论分析', status: this.aiServiceOk ? 'positive' : 'danger' },
        { label: '数据库状态', value: '本地可用', hint: 'AI 分析、风险任务和运营日志均已落库', status: 'positive' }
      ]
    },
    flowSteps() {
      return [
        { title: '提交用户评价', description: '打开 H5 用户端，发布真实商品图文评价。', action: () => window.open('http://localhost:6255', '_blank') },
        { title: '执行智能体巡检', description: '扫描待分析评价并生成 AI 分析结果。', action: this.runOnce },
        { title: '查看风险任务', description: '进入风险评论中心查看需处理任务。', action: () => this.go('/ai-workbench/governance-flow', 'risk') },
        { title: '运营处理', description: '采纳建议、转交售后或关闭风险任务。', action: () => this.go('/ai-workbench/governance-flow', 'operation') },
        { title: '查看追踪与评估', description: '复盘智能体执行过程和质量指标。', action: () => this.go('/ai-workbench/observability', 'trace') }
      ]
    },
    demoPath() {
      return ['H5 用户端', '发布评价', '智能体巡检', '风险任务', '运营处理', '执行追踪', '质量评估']
    },
    advancedEntries() {
      return [
        { title: '工具注册', desc: '查看本地工具协议、结构校验和审批策略。', path: '/ai-workbench/platform-governance', tab: 'tools' },
        { title: 'RAG 质量', desc: '查看本地案例检索增强的命中率和证据覆盖。', path: '/ai-workbench/knowledge-quality', tab: 'rag' },
        { title: '智能体运维', desc: '查看运行趋势、失败分布和本地回退情况。', path: '/ai-workbench/observability', tab: 'agentops' },
        { title: '安全护栏', desc: '查看输入输出和工具调用的本地安全边界。', path: '/ai-workbench/platform-governance', tab: 'guardrails' }
      ]
    },
    demoModeText() {
      return this.demoStatusData.demoModeEnabled === false ? '未启用' : '演示模式'
    },
    aiServiceOk() {
      return this.demoStatusData.aiServiceStatus === 'ok' || this.demoStatusData.aiServiceAvailable === true || this.demoStatusData.aiServiceBaseUrl
    },
    aiServiceText() {
      return this.aiServiceOk ? '服务正常' : '待检查'
    }
  },
  created() {
    this.loadData()
  },
  methods: {
    loadData() {
      this.loading = true
      Promise.all([
        dashboardSummary(),
        demoStatus(),
        listRiskTasks({ page: 1, limit: 5 }),
        listAgentRuns({ page: 1, limit: 5 })
      ]).then(([summaryRes, demoRes, riskRes, runRes]) => {
        this.summary = summaryRes.data.data || {}
        this.demoStatusData = demoRes.data.data || {}
        this.recentRisks = (riskRes.data.data || {}).list || []
        this.recentRuns = (runRes.data.data || {}).list || []
      }).catch(response => {
        this.$notify.error({
          title: '首页数据加载失败',
          message: response && response.data ? response.data.errmsg : '请检查后台 AI 接口和本地 AI 服务。'
        })
      }).finally(() => {
        this.loading = false
      })
    },
    handleFlowStep(step, index) {
      this.activeGuideStep = index
      if (step && step.action) {
        step.action()
      }
    },
    startDemo() {
      this.activeGuideStep = 0
      window.localStorage.setItem('e_review_ai_guide_started', 'true')
      this.$message.success('已进入 5 分钟演示路径，请先从 H5 用户端提交一条评价。')
      window.open('http://localhost:6255', '_blank')
    },
    runOnce() {
      this.runLoading = true
      runPatrolOnce().then(() => {
        this.$message.success('巡检已完成，请查看风险任务。')
        this.loadData()
      }).catch(response => {
        this.$notify.error({
          title: '巡检失败',
          message: response && response.data ? response.data.errmsg : '请检查 AI 服务状态。'
        })
      }).finally(() => {
        this.runLoading = false
      })
    },
    go(path, tab) {
      this.$router.push({ path, query: tab ? { tab } : {}})
    },
    safeNumber(value) {
      if (value === undefined || value === null || value === '') {
        return 0
      }
      return Number.isFinite(Number(value)) ? Number(value) : 0
    },
    statusText(status) {
      const map = { success: '成功', failed: '失败', running: '运行中', pending: '待处理' }
      return map[status] || status || '未知'
    },
    riskText(level) {
      const map = { low: '低风险', medium: '中风险', high: '高风险', critical: '严重风险' }
      return map[level] || '中风险'
    },
    riskStatusText(status) {
      const map = { pending: '待处理', viewed: '已查看', processed: '已处理', closed: '已关闭', ignored: '已忽略' }
      return map[status] || '待处理'
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-home-page {
  .dashboard-summary,
  .home-main-row {
    margin-bottom: 18px;
  }

  .demo-path {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;

    span {
      position: relative;
      padding: 8px 12px;
      color: #1e40af;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 700;
    }
  }
}
</style>
