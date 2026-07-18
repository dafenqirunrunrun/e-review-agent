<template>
  <div class="ai-workbench-page ai-dashboard-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">E-Review Agent</p>
        <h1 class="ai-page-title">智能评论治理总览看板</h1>
        <p class="ai-page-subtitle">
          汇总 AI 分析、Agent 巡检、风险任务和运营处理状态，帮助运营团队判断评论治理优先级。
        </p>
      </div>
      <div class="ai-toolbar">
        <el-button icon="el-icon-refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
      </div>
    </div>

    <div class="ai-metric-grid dashboard-summary">
      <div v-for="item in metrics" :key="item.label" class="ai-metric-card">
        <div class="ai-metric-label">{{ item.label }}</div>
        <div class="ai-metric-value">{{ item.value }}</div>
        <div class="ai-metric-hint">{{ item.hint }}</div>
      </div>
    </div>

    <el-alert
      class="customer-loop-alert"
      title="H5 用户端真实评价入口已接入：顾客在 6255 端完成演示支付、演示发货、确认收货并发布评价后，Agent 巡检会扫描 litemall_comment 并联动风险中心、运营中心和本看板。"
      type="info"
      show-icon
      :closable="false"
    />

    <el-alert
      class="demo-mode-alert"
      :title="demoModeTitle"
      type="warning"
      show-icon
      :closable="false"
    >
      <div class="demo-mode-content">
        <span>主演示商品：{{ demoStatusData.mainProductId || '--' }}</span>
        <span>AI 服务：{{ demoStatusData.aiServiceBaseUrl || 'http://127.0.0.1:8008' }}</span>
        <span>数据库：{{ demoStatusData.database || 'litemall' }}</span>
      </div>
    </el-alert>

    <el-row :gutter="18" class="dashboard-flow">
      <el-col :xs="24" :lg="14">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">系统链路状态</h2>
              <p class="ai-card-desc">从评论提交、Agent 巡检、风险识别到运营处理的当前闭环状态。</p>
            </div>
          </div>
          <div class="flow-steps">
            <div v-for="item in flowSteps" :key="item.label" class="flow-step">
              <span :class="['flow-dot', item.type]" />
              <div>
                <strong>{{ item.value }}</strong>
                <p>{{ item.label }}</p>
              </div>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">运营处理进度</h2>
              <p class="ai-card-desc">风险中心任务在运营侧的状态分布。</p>
            </div>
          </div>
          <div class="status-bars">
            <div v-for="item in operationStatusCards" :key="item.name" class="status-bar">
              <div>
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
              <el-progress :percentage="item.percent" :show-text="false" />
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="12">
        <div class="ai-card chart-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">情感分布</h2>
              <p class="ai-card-desc">按 positive / neutral / negative 聚合当前分析记录。</p>
            </div>
          </div>
          <ve-pie v-if="sentimentChart.rows.length" :data="sentimentChart" :settings="pieSettings" height="320px" />
          <div v-else class="mini-empty">暂无情感数据</div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="12">
        <div class="ai-card chart-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">近 7 天风险趋势</h2>
              <p class="ai-card-desc">展示分析量、负向评论和高风险评论走势。</p>
            </div>
          </div>
          <ve-line v-if="trendChart.rows.length" :data="trendChart" :settings="lineSettings" height="320px" />
          <div v-else class="mini-empty">暂无趋势数据</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="10">
        <div class="ai-card chart-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">风险类型分布</h2>
              <p class="ai-card-desc">按负向、低置信度、售后风险等规则聚合。</p>
            </div>
          </div>
          <ve-histogram v-if="riskTypeChart.rows.length" :data="riskTypeChart" height="300px" />
          <div v-else class="mini-empty">暂无风险类型数据</div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="14">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">风险商品 Top 5</h2>
              <p class="ai-card-desc">优先关注负向、高负向分或低置信度较多的商品。</p>
            </div>
          </div>
          <el-table :data="topProducts" border fit highlight-current-row>
            <el-table-column align="center" prop="productId" label="商品 ID" width="110" />
            <el-table-column prop="productName" label="商品名称" min-width="180" />
            <el-table-column align="center" prop="riskCount" label="风险数" width="100" />
            <el-table-column align="center" label="平均置信度" width="130">
              <template slot-scope="scope">
                {{ percent(scope.row.avgConfidence) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import VeHistogram from 'v-charts/lib/histogram'
import VeLine from 'v-charts/lib/line'
import VePie from 'v-charts/lib/pie'
import {
  dashboardSummary,
  demoStatus,
  operationOverview,
  patrolSummary,
  riskTrend,
  riskTypeDistribution,
  sentimentDistribution,
  topRiskProducts
} from '@/api/aiDashboard'

export default {
  name: 'AiDashboard',
  components: { VeHistogram, VeLine, VePie },
  data() {
    return {
      loading: false,
      summary: {},
      demoStatusData: {},
      patrol: {},
      operationOverviewData: {},
      sentimentChart: {
        columns: ['name', 'value'],
        rows: []
      },
      trendChart: {
        columns: ['day', 'analyses', 'negativeReviews', 'highRiskReviews'],
        rows: []
      },
      riskTypeChart: {
        columns: ['name', 'value'],
        rows: []
      },
      topProducts: [],
      pieSettings: {
        roseType: 'radius',
        labelMap: {
          positive: '正向',
          neutral: '中性',
          negative: '负向'
        }
      },
      lineSettings: {
        labelMap: {
          analyses: '分析量',
          negativeReviews: '负向评论',
          highRiskReviews: '高风险'
        }
      }
    }
  },
  computed: {
    metrics() {
      return [
        { label: '累计 AI 分析', value: this.numberText(this.summary.totalAnalyses), hint: '已落库分析记录' },
        { label: '今日 AI 分析', value: this.numberText(this.summary.analysesToday), hint: '今日新增分析量' },
        { label: '负向评论', value: this.numberText(this.summary.negativeReviews), hint: '识别为负向情感' },
        { label: '高风险评论', value: this.numberText(this.summary.highRiskReviews), hint: '负向或高负向分' },
        { label: '待分析样本', value: this.numberText(this.summary.pendingDemoReviews), hint: '等待智能体巡检' },
        { label: '开放风险任务', value: this.numberText(this.summary.openRiskTasks), hint: '未关闭或未忽略的任务' },
        { label: 'Agent 状态', value: this.agentStatusText, hint: '自动巡检配置状态' },
        { label: '最近巡检', value: this.summary.lastPatrolTime || this.summary.lastAnalysisTime || '--', hint: 'Agent 最近一次执行' },
        { label: '运营日志', value: this.numberText(this.summary.handledOperationLogs), hint: '已记录的处理动作' },
        { label: '平均置信度', value: this.percent(this.summary.avgConfidence), hint: '当前分析均值' }
      ]
    },
    agentStatusText() {
      if (this.summary.agentStatus === 'running') {
        return '运行中'
      }
      if (this.summary.agentStatus === 'standby') {
        return '待命'
      }
      return '未配置'
    },
    flowSteps() {
      return [
        { label: '待分析评论', value: this.numberText(this.summary.pendingDemoReviews), type: 'pending' },
        { label: 'Agent 巡检', value: this.agentStatusText, type: this.summary.patrolEnabled ? 'running' : 'standby' },
        { label: '开放风险任务', value: this.numberText(this.summary.openRiskTasks), type: 'risk' },
        { label: '运营处理动作', value: this.numberText(this.summary.handledOperationLogs), type: 'done' }
      ]
    },
    operationStatusCards() {
      const rows = this.operationOverviewData.riskTaskStatus || []
      const total = rows.reduce((sum, row) => sum + Number(row.value || 0), 0)
      const labels = {
        pending: '待处理',
        viewed: '已查看',
        replied: '已回复',
        transferred: '已转售后',
        ignored: '已忽略',
        closed: '已关闭'
      }
      return ['pending', 'viewed', 'replied', 'transferred', 'ignored', 'closed'].map(name => {
        const value = Number(this.findStatValue(rows, name))
        return {
          name,
          label: labels[name],
          value,
          percent: total === 0 ? 0 : Math.round(value * 100 / total)
        }
      })
    },
    demoModeTitle() {
      if (this.demoStatusData.demoModeEnabled === false) {
        return '当前未开启答辩演示模式：演示支付和演示发货入口应隐藏或不可用。'
      }
      return '当前为答辩演示模式：演示支付不调用真实支付，演示发货不调用真实物流。'
    }
  },
  created() {
    this.loadDashboard()
  },
  methods: {
    loadDashboard() {
      this.loading = true
      Promise.all([
        dashboardSummary(),
        demoStatus(),
        patrolSummary(),
        operationOverview(),
        sentimentDistribution(),
        riskTrend(),
        riskTypeDistribution(),
        topRiskProducts()
      ]).then(([summaryRes, demoStatusRes, patrolRes, operationRes, sentimentRes, trendRes, riskTypeRes, topRes]) => {
        this.summary = summaryRes.data.data || {}
        this.demoStatusData = demoStatusRes.data.data || {}
        this.patrol = patrolRes.data.data || {}
        this.operationOverviewData = operationRes.data.data || {}
        this.sentimentChart.rows = sentimentRes.data.data || []
        this.trendChart.rows = trendRes.data.data || []
        this.riskTypeChart.rows = this.formatRiskTypes(riskTypeRes.data.data || [])
        this.topProducts = topRes.data.data || []
        this.loading = false
      }).catch(response => {
        this.loading = false
        this.$notify.error({
          title: '看板加载失败',
          message: response && response.data ? response.data.errmsg : '请检查后端 AI 看板接口'
        })
      })
    },
    formatRiskTypes(rows) {
      const labels = {
        negative_sentiment: '负向评论',
        negative_review: '负向评论',
        low_confidence: '低置信度',
        high_negative_score: '高负向分',
        after_sales_risk: '售后风险',
        rating_conflict: '评分冲突'
      }
      return rows.map(item => {
        return {
          name: labels[item.name] || item.name,
          value: item.value
        }
      })
    },
    numberText(value) {
      if (value === undefined || value === null) {
        return '0'
      }
      return String(value)
    },
    findStatValue(rows, name) {
      const item = rows.find(row => row.name === name)
      return item ? item.value : 0
    },
    percent(value) {
      if (value === undefined || value === null) {
        return '0%'
      }
      return Math.round(Number(value) * 100) + '%'
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-dashboard-page {
  .dashboard-summary,
  .dashboard-flow {
    margin-bottom: 18px;
  }

  .customer-loop-alert {
    margin-bottom: 18px;
  }

  .demo-mode-alert {
    margin-bottom: 18px;
  }

  .demo-mode-content {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin-top: 6px;
    color: #92400e;
    font-size: 13px;
  }

  .chart-card {
    min-height: 408px;
  }

  .flow-steps {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }

  .flow-step {
    display: flex;
    gap: 10px;
    align-items: center;
    min-height: 82px;
    padding: 14px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #f8fafc;

    strong {
      display: block;
      color: #111827;
      font-size: 22px;
      line-height: 1.2;
    }

    p {
      margin: 4px 0 0;
      color: #64748b;
    }
  }

  .flow-dot {
    width: 10px;
    height: 34px;
    border-radius: 10px;
    background: #94a3b8;
    flex: 0 0 auto;

    &.running,
    &.done {
      background: #16a34a;
    }

    &.risk {
      background: #dc2626;
    }

    &.pending,
    &.standby {
      background: #f59e0b;
    }
  }

  .status-bars {
    display: grid;
    gap: 12px;
  }

  .status-bar {
    div {
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;
      color: #475569;
    }
  }

  .mini-empty {
    height: 280px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #6b7280;
    border: 1px dashed #cbd5e1;
    border-radius: 8px;
    background: #f8fafc;
  }
}

@media (max-width: 900px) {
  .ai-dashboard-page {
    .flow-steps {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
}

@media (max-width: 560px) {
  .ai-dashboard-page {
    .flow-steps {
      grid-template-columns: 1fr;
    }
  }
}
</style>
