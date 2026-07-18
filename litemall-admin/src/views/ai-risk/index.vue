<template>
  <div class="ai-workbench-page ai-risk-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">风险治理中心</p>
        <h1 class="ai-page-title">风险评论中心</h1>
        <p class="ai-page-subtitle">集中管理负向、低置信度、评分冲突和售后风险评论，形成运营处理闭环的任务入口。</p>
      </div>
      <div class="ai-toolbar">
        <el-button icon="el-icon-refresh" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <div class="ai-metric-grid risk-summary">
      <div v-for="item in summaryCards" :key="item.label" class="ai-metric-card">
        <div class="ai-metric-label">{{ item.label }}</div>
        <div class="ai-metric-value">{{ item.value }}</div>
        <div class="ai-metric-hint">{{ item.hint }}</div>
      </div>
    </div>

    <div class="ai-card">
      <div class="ai-card-header">
        <div>
          <h2 class="ai-card-title">风险任务列表</h2>
          <p class="ai-card-desc">列表打开时会从历史 AI 分析记录自动回填风险任务。</p>
        </div>
        <div class="filter-bar">
          <el-select v-model="query.riskLevel" clearable placeholder="风险等级" style="width: 130px;">
            <el-option v-for="item in riskLevelOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="query.riskType" clearable placeholder="风险类型" style="width: 170px;">
            <el-option v-for="item in riskTypes" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="query.status" clearable placeholder="处理状态" style="width: 130px;">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-button type="primary" icon="el-icon-search" @click="handleFilter">筛选</el-button>
        </div>
      </div>

      <el-table v-loading="loading" :data="riskList" border fit highlight-current-row>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column label="等级" width="100" align="center">
          <template slot-scope="scope">
            <span :class="['ai-status-tag', levelClass(scope.row.riskLevel)]">{{ riskText(scope.row.riskLevel) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="riskType" label="风险类型" width="160" />
        <el-table-column prop="productName" label="商品" min-width="150" show-overflow-tooltip />
        <el-table-column prop="reviewText" label="评论内容" min-width="260" show-overflow-tooltip />
        <el-table-column label="情感" width="100" align="center">
          <template slot-scope="scope">
            <span :class="['ai-status-tag', sentimentClass(scope.row.sentimentLabel)]">{{ sentimentText(scope.row.sentimentLabel) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="100" align="center">
          <template slot-scope="scope">{{ percent(scope.row.confidence) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template slot-scope="scope">
            <span :class="['ai-status-tag', statusClass(scope.row.status)]">{{ statusText(scope.row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="创建时间" width="170" align="center" />
        <el-table-column label="操作" width="170" align="center">
          <template slot-scope="scope">
            <el-button type="primary" size="mini" @click="openDetail(scope.row)">详情</el-button>
            <el-button type="success" size="mini" @click="quickClose(scope.row)">关闭</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer :visible.sync="detailVisible" title="风险任务详情" size="42%">
      <div v-if="currentTask" class="risk-detail">
        <div class="risk-detail-head">
          <span :class="['ai-status-tag', levelClass(currentTask.riskLevel)]">{{ riskText(currentTask.riskLevel) }}</span>
          <strong>{{ currentTask.riskType }}</strong>
          <el-button size="mini" type="primary" icon="el-icon-s-operation" @click="openOperationCenter">进入运营处理中心</el-button>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="商品">{{ currentTask.productName }}</el-descriptions-item>
          <el-descriptions-item label="评论">{{ currentTask.reviewText }}</el-descriptions-item>
          <el-descriptions-item label="情感">{{ sentimentText(currentTask.sentimentLabel) }}</el-descriptions-item>
          <el-descriptions-item label="置信度">{{ percent(currentTask.confidence) }}</el-descriptions-item>
          <el-descriptions-item label="处理状态">{{ statusText(currentTask.status) }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="currentAnalysis" class="analysis-json">
          <h3>AI 判断证据</h3>
          <p>{{ currentAnalysis.evidenceJson || '暂无证据' }}</p>
          <h3>Agent 建议</h3>
          <p>{{ currentAnalysis.agentSuggestionJson || '暂无建议' }}</p>
          <div class="ai-advice-note">AI 建议仅供参考，风险关闭或转交前建议结合订单、图片证据和售后记录复核。</div>
        </div>

        <div class="similar-case-panel">
          <h3>相似案例</h3>
          <div v-if="similarCases.length">
            <div v-for="item in similarCases" :key="item.caseId" class="similar-case-item">
              <div class="similar-case-head">
                <strong>{{ item.caseTitle || ('案例 #' + item.caseId) }}</strong>
                <el-tag size="mini" :type="levelTag(item.riskLevel)">{{ riskText(item.riskLevel) }}</el-tag>
                <span>{{ scoreText(item.matchScore) }}</span>
              </div>
              <p>{{ item.evidence || '暂无证据摘要' }}</p>
              <small>{{ item.riskTypes || '-' }} · {{ item.operationResult || '暂无历史处理方式' }}</small>
            </div>
          </div>
          <div v-else class="ai-empty-state compact-empty">
            <i class="el-icon-collection" />
            <span>暂无相似案例，Agent 将继续使用规则与当前证据判断。</span>
          </div>
        </div>

        <el-form label-position="top" class="handle-form">
          <el-form-item label="处理状态">
            <el-select v-model="handleForm.status" style="width: 100%;">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="处理人">
            <el-input v-model="handleForm.handler" />
          </el-form-item>
          <el-form-item label="处理备注">
            <el-input v-model="handleForm.handleNote" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" />
          </el-form-item>
          <el-button type="primary" :loading="updating" @click="saveStatus">保存处理状态</el-button>
        </el-form>
      </div>
    </el-drawer>
  </div>
</template>

<script>
import { retrieveAiCases } from '@/api/aiCase'
import { closeRiskTask, listRiskTasks, riskDetail, riskSummary, updateRiskStatus } from '@/api/aiRisk'
import { displayValue, riskLevelMap, sentimentMap, statusMap } from '@/utils/aiDisplayMap'

export default {
  name: 'AiRisk',
  data() {
    return {
      loading: false,
      updating: false,
      detailVisible: false,
      riskList: [],
      summary: {},
      currentTask: null,
      currentAnalysis: null,
      similarCases: [],
      query: {
        page: 1,
        limit: 20,
        riskLevel: undefined,
        riskType: undefined,
        status: undefined
      },
      handleForm: {
        id: undefined,
        status: 'viewed',
        handler: 'admin',
        handleNote: ''
      },
      riskTypes: ['negative_review', 'modality_conflict', 'low_confidence', 'rating_conflict', 'after_sales_risk', 'fake_review_suspected', 'other'],
      statuses: ['pending', 'viewed', 'replied', 'transferred', 'ignored', 'closed']
    }
  },
  computed: {
    summaryCards() {
      const statusRows = this.summary.status || []
      const levelRows = this.summary.level || []
      return [
        { label: '待处理', value: this.findValue(statusRows, 'pending'), hint: '等待运营跟进' },
        { label: '已查看', value: this.findValue(statusRows, 'viewed'), hint: '已进入人工复核' },
        { label: '已关闭', value: this.findValue(statusRows, 'closed'), hint: '处理闭环完成' },
        { label: '高风险', value: this.findValue(levelRows, 'high'), hint: '需要优先处理' }
      ]
    },
    riskLevelOptions() {
      return ['high', 'medium', 'low'].map(value => ({ value, label: this.riskText(value) }))
    },
    statusOptions() {
      return this.statuses.map(value => ({ value, label: this.statusText(value) }))
    }
  },
  created() {
    this.loadData()
  },
  methods: {
    loadData() {
      this.loading = true
      Promise.all([listRiskTasks(this.query), riskSummary()]).then(([listRes, summaryRes]) => {
        this.riskList = listRes.data.data.list || []
        this.summary = summaryRes.data.data || {}
        this.loading = false
      }).catch(response => {
        this.loading = false
        this.$notify.error({
          title: '风险任务加载失败',
          message: response && response.data ? response.data.errmsg : '请检查后端接口'
        })
      })
    },
    handleFilter() {
      this.query.page = 1
      this.loadData()
    },
    openDetail(row) {
      riskDetail(row.id).then(response => {
        this.currentTask = response.data.data.task
        this.currentAnalysis = response.data.data.analysis
        this.handleForm = {
          id: row.id,
          status: row.status === 'pending' ? 'viewed' : row.status,
          handler: row.handler || 'admin',
          handleNote: row.handleNote || ''
        }
        this.detailVisible = true
        this.loadSimilarCases(this.currentTask)
      })
    },
    loadSimilarCases(task) {
      if (!task) {
        this.similarCases = []
        return
      }
      retrieveAiCases({
        queryText: task.reviewText,
        productId: task.productId,
        riskTypes: task.riskType,
        sentimentLabel: task.sentimentLabel,
        topK: 3,
        sourceType: task.sourceType,
        sourceId: task.sourceId
      }).then(response => {
        this.similarCases = response.data.data || []
      }).catch(() => {
        this.similarCases = []
      })
    },
    saveStatus() {
      this.updating = true
      updateRiskStatus(this.handleForm).then(() => {
        this.updating = false
        this.detailVisible = false
        this.loadData()
      }).catch(() => {
        this.updating = false
      })
    },
    quickClose(row) {
      closeRiskTask({ id: row.id, handler: 'admin', handleNote: '运营确认关闭' }).then(() => {
        this.loadData()
      })
    },
    openOperationCenter() {
      if (!this.currentTask || !this.currentTask.id) return
      this.$router.push({ path: '/ai-workbench/operation', query: { riskTaskId: this.currentTask.id }})
    },
    findValue(rows, name) {
      const item = rows.find(row => row.name === name)
      return item ? item.value : 0
    },
    percent(value) {
      if (value === undefined || value === null) {
        return '0%'
      }
      return Math.round(Number(value) * 100) + '%'
    },
    levelClass(level) {
      if (level === 'high') {
        return 'ai-status-high'
      }
      if (level === 'medium') {
        return 'ai-status-medium'
      }
      return 'ai-status-low'
    },
    statusClass(status) {
      if (status === 'closed' || status === 'replied') {
        return 'ai-status-positive'
      }
      if (status === 'transferred') {
        return 'ai-status-medium'
      }
      return 'ai-status-low'
    },
    levelTag(level) {
      if (level === 'high') return 'danger'
      if (level === 'medium') return 'warning'
      return 'info'
    },
    scoreText(value) {
      if (value === undefined || value === null) return '匹配度 -'
      return '匹配度 ' + Math.round(Number(value) * 100) + '%'
    },
    sentimentClass(label) {
      if (label === 'negative') {
        return 'ai-status-negative'
      }
      if (label === 'positive') {
        return 'ai-status-positive'
      }
      return 'ai-status-neutral'
    },
    sentimentText(label) {
      return displayValue(sentimentMap, label)
    },
    riskText(level) {
      return displayValue(riskLevelMap, level)
    },
    statusText(status) {
      return displayValue(statusMap, status)
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-risk-page {
  .risk-summary {
    margin-bottom: 18px;
  }

  .filter-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: flex-end;
  }

  .risk-detail {
    padding: 0 24px 24px;
  }

  .risk-detail-head {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 18px;

    strong {
      color: #111827;
      font-size: 18px;
    }
  }

  .analysis-json {
    margin-top: 18px;
    padding: 14px;
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 8px;

    h3 {
      margin: 0 0 8px;
      font-size: 14px;
    }

    p {
      margin: 0 0 12px;
      color: #4b5563;
      line-height: 1.7;
      word-break: break-all;
    }
  }

  .similar-case-panel {
    margin-top: 18px;

    h3 {
      margin: 0 0 10px;
      color: #1f2937;
      font-size: 15px;
    }
  }

  .similar-case-item {
    margin-bottom: 10px;
    padding: 12px;
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 8px;

    p {
      margin: 8px 0;
      color: #374151;
      font-size: 13px;
      line-height: 1.6;
    }

    small {
      color: #64748b;
    }
  }

  .similar-case-head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;

    strong {
      color: #111827;
    }

    span {
      color: #2563eb;
      font-size: 12px;
      font-weight: 700;
    }
  }

  .handle-form {
    margin-top: 18px;
  }
}
</style>
