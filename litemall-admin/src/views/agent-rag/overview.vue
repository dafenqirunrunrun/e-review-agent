<template>
  <div class="app-container agent-rag-page">
    <div class="page-header">
      <div>
        <h2>Agent-RAG 运行概览</h2>
        <p>查看今日治理运行、风险、Fallback 与待复核情况。</p>
      </div>
      <el-button :loading="loading" type="primary" icon="el-icon-refresh" @click="loadData">刷新</el-button>
    </div>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      show-icon
      class="section-gap"
    />

    <el-card class="section-gap" shadow="never">
      <div slot="header" class="card-header">
        <span>运行状态</span>
        <el-tag :type="runtimeTag">{{ runtimeLabel }}</el-tag>
      </div>
      <el-row :gutter="16">
        <el-col :xs="24" :sm="12" :md="6">
          <div class="status-item">
            <span>Target Mode</span>
            <strong>{{ runtime.raw && runtime.raw.targetMode || '--' }}</strong>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="status-item">
            <span>Provider</span>
            <strong>{{ formatProvider(runtime.effectiveProviderImpl) }}</strong>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="status-item">
            <span>Index</span>
            <strong>{{ runtime.activeIndexVersion || '--' }}</strong>
          </div>
        </el-col>
        <el-col :xs="24" :sm="12" :md="6">
          <div class="status-item">
            <span>Circuit</span>
            <strong>{{ circuit.state || '--' }}</strong>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16" class="metric-grid">
      <el-col v-for="item in metrics" :key="item.key" :xs="12" :sm="8" :md="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-label">{{ item.label }}</div>
          <div class="metric-value">{{ displayMetric(item.value, item.duration) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header">状态分布</div>
          <distribution-list :items="summary.statusDistribution" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header">风险分布</div>
          <distribution-list :items="summary.riskDistribution" risk />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header">最近异常运行</div>
          <el-table :data="summary.recentFailures || []" size="mini" border empty-text="暂无异常运行。">
            <el-table-column prop="createdAt" label="时间" width="160">
              <template slot-scope="{ row }">{{ formatTimestamp(row.createdAt) }}</template>
            </el-table-column>
            <el-table-column prop="subjectId" label="Subject" min-width="150" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="110">
              <template slot-scope="{ row }">
                <el-tag :type="getStatusTagType(row.status)" size="mini">{{ formatRunStatus(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="errorCode" label="错误码" min-width="150" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header">最近待复核</div>
          <el-table :data="summary.pendingReviews || []" size="mini" border empty-text="暂无待复核运行。">
            <el-table-column prop="createdAt" label="时间" width="160">
              <template slot-scope="{ row }">{{ formatTimestamp(row.createdAt) }}</template>
            </el-table-column>
            <el-table-column prop="subjectId" label="Subject" min-width="150" show-overflow-tooltip />
            <el-table-column prop="effectiveRiskLevel" label="有效风险" width="100">
              <template slot-scope="{ row }">
                <el-tag :type="getRiskTagType(row.effectiveRiskLevel)" size="mini">{{ formatRiskLevel(row.effectiveRiskLevel) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90">
              <template slot-scope="{ row }">
                <router-link :to="`/agent-rag/runs/${row.id}`">详情</router-link>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { getAgentRagOverview, getAgentRagRuntimeHealth } from '@/api/agentRag'
import { formatProvider, formatRunStatus, formatRiskLevel, formatDuration, formatTimestamp, getRiskTagType, getStatusTagType } from '@/utils/agent-rag'

const DistributionList = {
  props: {
    items: { type: Array, default: () => [] },
    risk: { type: Boolean, default: false }
  },
  methods: { formatRiskLevel, getRiskTagType },
  template: `
    <div>
      <div v-if="!items || items.length === 0" class="empty-inline">暂无数据</div>
      <div v-for="item in items" :key="item.name" class="distribution-row">
        <span>{{ risk ? formatRiskLevel(item.name) : item.name }}</span>
        <el-progress :percentage="Math.min(100, Number(item.value || 0))" :show-text="false" />
        <strong>{{ item.value }}</strong>
      </div>
    </div>
  `
}

export default {
  name: 'AgentRagOverview',
  components: { DistributionList },
  data() {
    return {
      loading: false,
      loadError: '',
      summary: {},
      runtime: {},
      circuit: {}
    }
  },
  computed: {
    runtimeLabel() {
      if (this.runtime.status === 'ready' && this.runtime.indexCompatible && !this.runtime.fallbackUsed) return 'Ready'
      if (this.runtime.status) return 'Degraded'
      return 'Not Ready'
    },
    runtimeTag() {
      if (this.runtimeLabel === 'Ready') return 'success'
      if (this.runtimeLabel === 'Degraded') return 'warning'
      return 'danger'
    },
    metrics() {
      return [
        { key: 'todayRunCount', label: '今日分析', value: this.summary.todayRunCount },
        { key: 'todayHighRiskCount', label: '今日高风险', value: this.summary.todayHighRiskCount },
        { key: 'todayReviewRequiredCount', label: '待人工复核', value: this.summary.todayReviewRequiredCount },
        { key: 'todayFallbackCount', label: '规则/Fallback', value: this.summary.todayFallbackCount },
        { key: 'todayFailureCount', label: '执行失败', value: this.summary.todayFailureCount },
        { key: 'averageDurationMs', label: '平均耗时', value: this.summary.averageDurationMs, duration: true },
        { key: 'p95DurationMs', label: 'P95 耗时', value: this.summary.p95DurationMs, duration: true },
        { key: 'overrideCount', label: '人工复核', value: this.summary.overrideCount }
      ]
    }
  },
  created() {
    this.loadData()
  },
  methods: {
    formatProvider,
    formatRunStatus,
    formatRiskLevel,
    formatTimestamp,
    getRiskTagType,
    getStatusTagType,
    displayMetric(value, duration) {
      if (this.loadError) return '--'
      if (duration) return formatDuration(value)
      return value === undefined || value === null ? '--' : value
    },
    async loadData() {
      this.loading = true
      this.loadError = ''
      try {
        const overview = await getAgentRagOverview()
        const health = await getAgentRagRuntimeHealth()
        this.summary = overview.data.data || {}
        const healthData = health.data.data || {}
        this.runtime = healthData.runtime || {}
        this.circuit = healthData.circuitBreaker || {}
      } catch (e) {
        this.loadError = 'Agent-RAG 概览加载失败，请确认 AI runtime、admin-api 与数据库已启动。'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.agent-rag-page .page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
}
.page-header p {
  margin: 0;
  color: #606266;
}
.section-gap {
  margin-top: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.status-item {
  min-height: 58px;
  padding: 8px 0;
}
.status-item span,
.metric-label {
  display: block;
  color: #909399;
  font-size: 13px;
}
.status-item strong {
  display: block;
  margin-top: 8px;
  color: #303133;
  word-break: break-all;
}
.metric-grid {
  margin-top: 16px;
}
.metric-card {
  margin-bottom: 16px;
}
.metric-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
.distribution-row {
  display: grid;
  grid-template-columns: 120px 1fr 48px;
  gap: 12px;
  align-items: center;
  min-height: 34px;
}
.empty-inline {
  color: #909399;
  line-height: 40px;
}
</style>
