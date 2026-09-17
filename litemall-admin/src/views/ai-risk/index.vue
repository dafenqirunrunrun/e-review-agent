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

    <div class="ai-card quality-card">
      <div class="ai-card-header">
        <div><h2 class="ai-card-title">治理质量观察</h2><p class="ai-card-desc">过去 24 小时的脱敏治理事件。高风险仍须由人工确认。</p></div>
      </div>
      <div class="quality-rates">
        <div v-for="item in qualityCards" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
      </div>
      <div v-if="qualityAlerts.length" class="quality-alerts"><el-alert v-for="item in qualityAlerts" :key="item.code" :title="item.message" type="warning" :closable="false" show-icon /></div>
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
            <el-option v-for="item in riskTypes" :key="item" :label="riskTypeText(item)" :value="item" />
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
        <el-table-column label="风险类型" width="160">
          <template slot-scope="scope">{{ riskTypeText(scope.row.riskType) }}</template>
        </el-table-column>
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
          <strong>{{ riskTypeText(currentTask.riskType) }}</strong>
          <el-button size="mini" type="primary" icon="el-icon-s-operation" @click="openOperationCenter">进入运营处理中心</el-button>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="商品">{{ currentTask.productName }}</el-descriptions-item>
          <el-descriptions-item label="评论">{{ currentTask.reviewText }}</el-descriptions-item>
          <el-descriptions-item label="情感">{{ sentimentText(currentTask.sentimentLabel) }}</el-descriptions-item>
          <el-descriptions-item label="置信度">{{ percent(currentTask.confidence) }}</el-descriptions-item>
          <el-descriptions-item label="处理状态">{{ statusText(currentTask.status) }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="currentGovernanceScenario" class="governance-review-panel">
          <div class="governance-review-head">
            <div>
              <h3>{{ currentGovernanceScenario.decision }}</h3>
              <p>{{ currentGovernanceScenario.reason }}</p>
            </div>
            <div :class="['evidence-state', currentGovernanceScenario.evidenceStatus]">
              <strong>{{ currentGovernanceScenario.evidenceStatusText }}</strong>
              <span>{{ currentGovernanceScenario.requiresHumanReview ? '需要人工复核' : '可按建议处理' }}</span>
            </div>
          </div>
          <el-alert
            :title="currentGovernanceScenario.reflectionReason"
            :type="currentGovernanceScenario.requiresHumanReview ? 'warning' : 'success'"
            :closable="false"
            show-icon
          />
          <el-alert
            v-if="currentGovernanceScenario.history"
            :title="currentGovernanceScenario.history.message"
            :type="currentGovernanceScenario.history.type"
            :closable="false"
            show-icon
          />
          <div v-if="currentGovernanceScenario.riskCoverage.length" class="risk-coverage-list">
            <h3>风险支持状态</h3>
            <div v-for="item in currentGovernanceScenario.riskCoverage" :key="item.riskType" class="risk-coverage-item">
              <div>
                <strong>{{ item.label }}</strong>
                <p>{{ item.description }}</p>
              </div>
              <el-tag :type="item.status === 'supported' ? 'success' : 'warning'" size="mini">{{ item.statusText }}</el-tag>
            </div>
          </div>
          <div class="policy-evidence-list">
            <h3>政策依据</h3>
            <el-collapse v-if="currentGovernanceScenario.showPolicyEvidence && currentGovernanceScenario.evidence.length" accordion>
              <el-collapse-item v-for="item in currentGovernanceScenario.evidence" :key="item.id" :name="item.id">
                <template slot="title">
                  <span class="evidence-title">{{ item.id }} · {{ item.title }}</span>
                </template>
                <div class="evidence-card">
                  <div class="evidence-meta">
                    <el-tag size="mini" type="success">{{ item.sourceType }}</el-tag>
                    <el-tag size="mini" type="info">{{ item.path }}</el-tag>
                  </div>
                  <p>{{ item.snippet }}</p>
                  <small>命中风险：{{ item.riskTypes }}</small>
                  <small>{{ item.supports }}</small>
                  <el-button v-if="item.sourceUrl" size="mini" type="text" icon="el-icon-link" @click="openEvidenceSource(item.sourceUrl)">
                    查看原始政策
                  </el-button>
                  <el-collapse v-if="item.technicalDetails.length" class="technical-collapse">
                    <el-collapse-item title="技术详情" :name="item.id + '-tech'">
                      <div v-for="detail in item.technicalDetails" :key="detail" class="technical-line">{{ detail }}</div>
                    </el-collapse-item>
                  </el-collapse>
                </div>
              </el-collapse-item>
            </el-collapse>
            <div v-else-if="currentGovernanceScenario.showPolicyEvidence" class="policy-empty">当前缺少可验证政策依据，请结合订单、图片和售后记录人工确认。</div>
          </div>
        </div>

        <div v-else-if="currentAnalysis" class="analysis-json">
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
              <p>{{ readableEvidence(item.evidence) }}</p>
              <small>{{ riskTypeListText(item.riskTypes) }} · {{ statusText(item.operationResult) }}</small>
            </div>
          </div>
          <div v-else class="ai-empty-state compact-empty">
            <i class="el-icon-collection" />
            <span>暂无相似案例，Agent 将继续使用规则与当前证据判断。</span>
          </div>
        </div>

        <div v-if="isResolvedTask" class="resolved-panel">
          <h3>人工复核结果</h3>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="最终状态">{{ statusText(currentTask.status) }}</el-descriptions-item>
            <el-descriptions-item label="审核人">{{ currentTask.handler || '-' }}</el-descriptions-item>
            <el-descriptions-item label="处理说明">{{ readableHandleNote(currentTask.handleNote) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <el-form v-else label-position="top" class="handle-form">
          <el-form-item label="人工决定">
            <el-radio-group v-model="handleForm.humanDecision">
              <el-radio-button label="accept_ai_suggestion">接受 AI 建议</el-radio-button>
              <el-radio-button label="override">人工改判</el-radio-button>
              <el-radio-button label="no_action">无需处置</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="处理人">
            <el-input v-model="handleForm.handler" />
          </el-form-item>
          <el-form-item v-if="handleForm.humanDecision !== 'accept_ai_suggestion'" label="改判原因">
            <el-select v-model="handleForm.reasonCode" placeholder="请选择原因" style="width: 100%;">
              <el-option v-for="item in feedbackReasons" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="复核备注">
            <el-input v-model="handleForm.handleNote" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" />
          </el-form-item>
          <el-alert
            class="human-review-note"
            :title="humanReviewHint"
            :closable="false"
            show-icon
            type="info"
          />
          <el-button type="primary" :loading="updating" @click="saveHumanReview">提交人工复核</el-button>
        </el-form>
      </div>
    </el-drawer>
  </div>
</template>

<script>
import { retrieveAiCases } from '@/api/aiCase'
import { closeRiskTask, governanceQualityMetrics, humanReviewRiskTask, listRiskTasks, riskDetail, riskSummary } from '@/api/aiRisk'
import { displayValue, evidenceStatusMap, humanDecisionMap, riskLevelMap, riskTypeLabel, sentimentMap, statusMap } from '@/utils/aiDisplayMap'
import { normalizeReviewGovernance } from '@/utils/reviewGovernanceAdapter'

export default {
  name: 'AiRisk',
  data() {
    return {
      loading: false,
      updating: false,
      detailVisible: false,
      riskList: [],
      summary: {},
      quality: {},
      currentTask: null,
      currentAnalysis: null,
      currentGovernanceScenario: null,
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
        humanDecision: 'accept_ai_suggestion',
        handler: 'admin',
        handleNote: '',
        reasonCode: 'OTHER'
      },
      feedbackReasons: [
        { value: 'FALSE_POSITIVE', label: '误报' }, { value: 'WRONG_RISK_TYPE', label: '风险类型不正确' },
        { value: 'EVIDENCE_INSUFFICIENT', label: '政策依据不足' }, { value: 'EVIDENCE_MISMATCH', label: '政策依据不匹配' },
        { value: 'CONTEXT_MISSING', label: '缺少业务上下文' }, { value: 'POLICY_NOT_APPLICABLE', label: '政策不适用' },
        { value: 'BUSINESS_EXCEPTION', label: '业务例外' }, { value: 'OTHER', label: '其他' }
      ],
      riskTypes: ['fake_review', 'rating_manipulation', 'paid_review', 'review_suppression', 'after_sales_risk', 'safety_or_fraud_risk', 'privacy_risk', 'harassment_or_abuse', 'negative_review', 'modality_conflict', 'low_confidence', 'rating_conflict', 'fake_review_suspected', 'other'],
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
    qualityCards() {
      const rates = this.quality.rates || {}
      return [
        { label: '严格路径率', value: this.percent(rates.strictPathRate) }, { label: '人工复核率', value: this.percent(rates.humanReviewRate) },
        { label: '采纳 AI 建议', value: this.percent(rates.aiAcceptanceRate) }, { label: '人工改判率', value: this.percent(rates.overrideRate) },
        { label: 'BM25 降级率', value: this.percent(rates.bm25FallbackRate) }
      ]
    },
    qualityAlerts() { return this.quality.alerts || [] },
    riskLevelOptions() {
      return ['high', 'medium', 'low'].map(value => ({ value, label: this.riskText(value) }))
    },
    statusOptions() {
      return this.statuses.map(value => ({ value, label: this.statusText(value) }))
    },
    isResolvedTask() {
      return this.currentTask && ['closed', 'ignored', 'replied', 'transferred', 'processed'].indexOf(this.currentTask.status) >= 0
    },
    humanReviewHint() {
      if (!this.currentGovernanceScenario) {
        return '请结合评论内容、订单信息和现有 AI 分析完成最终判断。'
      }
      if (this.currentGovernanceScenario.evidenceStatus === 'mismatch') {
        return '当前 AI 风险判断与政策依据不完全匹配，提交前请确认是否需要人工改判。'
      }
      if (this.currentGovernanceScenario.evidenceStatus === 'insufficient') {
        return '当前缺少可验证政策依据，提交前请补充业务判断说明。'
      }
      return '政策依据支持当前风险判断，可接受 AI 建议或按业务事实调整。'
    }
  },
  created() {
    this.loadData()
  },
  methods: {
    loadData() {
      this.loading = true
      Promise.all([listRiskTasks(this.query), riskSummary(), governanceQualityMetrics()]).then(([listRes, summaryRes, qualityRes]) => {
        this.riskList = listRes.data.data.list || []
        this.summary = summaryRes.data.data || {}
        this.quality = qualityRes.data.data || {}
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
        this.currentGovernanceScenario = this.normalizeGovernance(response.data.data.reviewGovernance, this.currentTask)
        this.handleForm = {
          id: row.id,
          humanDecision: 'accept_ai_suggestion',
          handler: row.handler || 'admin',
          handleNote: row.handleNote || '',
          reasonCode: 'OTHER'
        }
        this.detailVisible = true
        this.loadSimilarCases(this.currentTask)
      }).catch(response => {
        this.$notify.error({
          title: '详情加载失败',
          message: this.safeErrorMessage(response, '暂时无法读取风险详情，可刷新后重试或直接在列表中处理。')
        })
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
    saveHumanReview() {
      if (this.handleForm.humanDecision !== 'accept_ai_suggestion' && !this.handleForm.reasonCode) {
        this.$message.warning('请选择人工改判原因')
        return
      }
      this.updating = true
      humanReviewRiskTask(this.handleForm).then(response => {
        const data = response.data.data || {}
        this.updating = false
        if (data.alreadyResolved) {
          this.$message.warning('该任务已处理，已刷新为最终状态。')
        } else {
          this.$message.success('人工复核已保存')
        }
        this.currentTask = data.task || this.currentTask
        this.loadData()
      }).catch(response => {
        this.updating = false
        this.$notify.error({
          title: '人工复核保存失败',
          message: this.safeErrorMessage(response, '处理结果暂未保存，请确认服务和数据库状态后重试。')
        })
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
    normalizeGovernance(governance, task) {
      if (!governance || !task) {
        return null
      }
      return normalizeReviewGovernance({ review_governance: governance }, {
        key: task.id,
        product: task.productName,
        orderNo: '任务 #' + task.id,
        rating: '-',
        reviewText: task.reviewText,
        actions: []
      })
    },
    openEvidenceSource(url) {
      window.open(url, '_blank', 'noopener')
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
    readableEvidence(value) {
      if (!value) return '暂无证据摘要'
      if (Array.isArray(value)) {
        return value.join('、')
      }
      try {
        const parsed = JSON.parse(value)
        if (Array.isArray(parsed)) {
          return parsed.join('、')
        }
      } catch (e) {
        // Keep plain historical text renderable when it is not JSON.
      }
      return value
    },
    safeErrorMessage(response, fallback) {
      const message = response && response.data ? response.data.errmsg || response.data.message : ''
      if (!message) return fallback
      if (/timeout|ECONN|500|POLICY_|FAISS|QWEN|Exception|Traceback/i.test(message)) {
        return fallback
      }
      return message
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
    riskTypeText(type) {
      return riskTypeLabel(type)
    },
    riskTypeListText(value) {
      if (!value) return '-'
      const parts = Array.isArray(value) ? value : String(value).split(',')
      return parts.map(item => this.riskTypeText(String(item).trim())).filter(Boolean).join('、') || '-'
    },
    readableHandleNote(note) {
      if (!note) return '-'
      let text = String(note)
      const replacements = {
        manual_review: '需人工复核',
        suggest_action: '建议处理',
        auto_pass: '自动通过',
        mismatch: evidenceStatusMap.mismatch,
        insufficient: evidenceStatusMap.insufficient,
        supported: evidenceStatusMap.supported
      }
      Object.keys(humanDecisionMap).forEach(key => {
        replacements[key] = humanDecisionMap[key]
      })
      Object.keys(replacements).forEach(key => {
        text = text.replace(new RegExp(key, 'g'), replacements[key])
      })
      this.riskTypes.forEach(key => {
        text = text.replace(new RegExp(key, 'g'), this.riskTypeText(key))
      })
      return text.replace(/,/g, '、')
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

  .resolved-panel {
    margin-top: 18px;
    padding: 14px;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;

    h3 {
      margin: 0 0 10px;
      font-size: 14px;
    }
  }

  .human-review-note {
    margin-bottom: 12px;
  }

  .governance-review-panel {
    margin-top: 18px;
    padding: 14px;
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }

  .governance-review-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    margin-bottom: 12px;

    h3 {
      margin: 0 0 8px;
      color: #111827;
      font-size: 16px;
    }

    p {
      margin: 0;
      color: #526174;
      line-height: 1.7;
    }
  }

  .evidence-state {
    flex: 0 0 126px;
    padding: 10px;
    color: #065f46;
    text-align: center;
    background: #d1fae5;
    border: 1px solid #a7f3d0;
    border-radius: 8px;

    strong,
    span {
      display: block;
    }

    span {
      margin-top: 5px;
      font-size: 12px;
    }

    &.insufficient {
      color: #92400e;
      background: #fef3c7;
      border-color: #fcd34d;
    }

    &.mismatch {
      color: #991b1b;
      background: #fee2e2;
      border-color: #fecaca;
    }
  }

  .policy-evidence-list {
    margin-top: 14px;

    h3 {
      margin: 0 0 10px;
      color: #1f2937;
      font-size: 15px;
    }
  }

  .risk-coverage-list {
    margin-top: 14px;

    h3 {
      margin: 0 0 10px;
      color: #1f2937;
      font-size: 15px;
    }
  }

  .risk-coverage-item {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
    padding: 10px 12px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 6px;

    strong {
      color: #111827;
    }

    p {
      margin: 4px 0 0;
      color: #64748b;
      font-size: 12px;
      line-height: 1.6;
    }
  }

  .evidence-title {
    color: #111827;
    font-weight: 700;
  }

  .evidence-card {
    p {
      margin: 10px 0;
      color: #334155;
      line-height: 1.7;
    }

    small {
      display: block;
      margin-top: 5px;
      color: #64748b;
    }
  }

  .evidence-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .technical-collapse {
    margin-top: 8px;

    ::v-deep .el-collapse-item__header {
      height: 32px;
      color: #64748b;
      font-size: 12px;
      line-height: 32px;
      background: transparent;
    }
  }

  .technical-line {
    color: #64748b;
    font-size: 12px;
    line-height: 1.8;
  }

  .policy-empty {
    padding: 14px;
    color: #92400e;
    background: #fffbeb;
    border: 1px dashed #fcd34d;
    border-radius: 6px;
    line-height: 1.6;
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

  .quality-card {
    margin-bottom: 16px;
  }

  .quality-rates {
    display: flex;
    flex-wrap: wrap;
    gap: 24px;

    > div {
      display: flex;
      flex-direction: column;
      min-width: 118px;
      gap: 6px;
      color: #637083;
      font-size: 13px;
    }

    strong {
      color: #1b2738;
      font-size: 21px;
    }
  }

  .quality-alerts {
    display: grid;
    gap: 8px;
    margin-top: 14px;
  }
}
</style>
