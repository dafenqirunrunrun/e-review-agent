<template>
  <div class="app-container agent-rag-detail">
    <div class="page-header">
      <div>
        <h2>Agent-RAG 运行详情 #{{ run.id || runId }}</h2>
        <p>查看原始决策、有效决策、证据链、Provider/Fallback、人工复核与 Replay 对比。</p>
      </div>
      <div>
        <el-button icon="el-icon-back" @click="$router.push('/agent-rag/runs')">返回列表</el-button>
        <el-button :loading="loading" type="primary" icon="el-icon-refresh" @click="loadDetail">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon class="section-gap" />

    <el-card v-loading="loading" shadow="never" class="section-gap">
      <el-row :gutter="16">
        <el-col :xs="24" :md="12">
          <h3>运行摘要</h3>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="Request ID">{{ run.requestId || '--' }}</el-descriptions-item>
            <el-descriptions-item label="Subject">{{ run.subjectType || '--' }} / {{ run.subjectId || '--' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusTagType(run.status)" size="mini">{{ formatRunStatus(run.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTimestamp(run.createdAt) }}</el-descriptions-item>
            <el-descriptions-item label="耗时">{{ formatDuration(run.durationMs) }}</el-descriptions-item>
            <el-descriptions-item label="Schema / Analyzer">{{ run.schemaVersion || '--' }} / {{ run.analyzerVersion || '--' }}</el-descriptions-item>
            <el-descriptions-item label="错误摘要">
              <span>{{ safeError(run.errorCode, run.errorMessage) }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-col>
        <el-col :xs="24" :md="12">
          <h3>运行环境</h3>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="Target Mode">{{ run.targetMode || '--' }}</el-descriptions-item>
            <el-descriptions-item label="请求 Provider">{{ formatProvider(run.requestedProviderImpl) }}</el-descriptions-item>
            <el-descriptions-item label="实际 Provider">
              <el-tag :type="getProviderTagType(run.effectiveProviderImpl)" size="mini">{{ formatProvider(run.effectiveProviderImpl) }}</el-tag>
              <span v-if="providerDegraded" class="warn-text">已降级</span>
            </el-descriptions-item>
            <el-descriptions-item label="Retrieval">{{ formatRetrievalMode(run.effectiveRetrievalMode) }}</el-descriptions-item>
            <el-descriptions-item label="Index Version">{{ run.indexVersion || '--' }}</el-descriptions-item>
            <el-descriptions-item label="Fallback">
              <el-tag :type="run.fallbackUsed ? 'warning' : 'success'" size="mini">{{ run.fallbackUsed ? '是' : '否' }}</el-tag>
              <span class="muted">{{ formatFallbackReason(run.fallbackReason) }}</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header">原始 AI 决策</div>
          <decision-card :decision="originalDecision" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header" class="card-header">
            <span>有效决策</span>
            <el-tag v-if="effectiveDecision.overridden" type="warning" size="mini">人工复核</el-tag>
          </div>
          <decision-card :decision="effectiveDecision" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="section-gap">
      <div slot="header" class="card-header">
        <span>证据链时间线</span>
        <span class="muted">Bundle Hash: {{ shortFingerprint(evidence.bundleHash) }}</span>
      </div>
      <div class="model-evidence-inline">
        <div>
          <strong>Retrieval</strong>
          <span>{{ formatRetrievalMode(realModelEvidence.effectiveRetrievalMode) }}</span>
          <span>{{ realModelEvidence.denseProvider || '--' }}</span>
          <span>{{ realModelEvidence.faissIndexType || '--' }}</span>
        </div>
        <div>
          <strong>Rerank</strong>
          <span>{{ realModelEvidence.effectiveRerankerType || '--' }}</span>
          <span>{{ realModelEvidence.rerankerModelId || '--' }}</span>
          <span>{{ shortFingerprint(realModelEvidence.rerankerFingerprint) }}</span>
          <span>{{ formatDuration(realModelEvidence.rerankerDurationMs) }}</span>
        </div>
        <div>
          <strong>LLM</strong>
          <span>{{ formatProvider(realModelEvidence.effectiveAnalysisProvider) }}</span>
          <span>{{ realModelEvidence.llmModelId || '--' }}</span>
          <span>{{ realModelEvidence.groundingStatus || '--' }}</span>
          <span>{{ realModelEvidence.llmInputTokens || 0 }} / {{ realModelEvidence.llmOutputTokens || 0 }}</span>
        </div>
      </div>
      <p class="model-evidence-note">Sanitized metadata only. Model paths, full prompts and raw model outputs are intentionally hidden.</p>
      <el-timeline v-if="evidenceTimeline.length > 0">
        <el-timeline-item v-for="item in evidenceTimeline" :key="item.title" :timestamp="item.timestamp" placement="top">
          <h4>{{ item.title }}</h4>
          <pre class="bounded-snippet">{{ item.content }}</pre>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无可展示的脱敏证据片段。" />
      <div class="evidence-meta">
        <span>Evidence ID: {{ evidence.evidenceId || '--' }}</span>
        <span>引用数: {{ evidence.citationCount || 0 }}</span>
        <span>大小: {{ evidence.payloadSizeBytes || 0 }} bytes</span>
      </div>
    </el-card>

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header" class="card-header">
            <span>人工复核历史</span>
            <el-button
              v-permission="['POST /admin/agent-rag/override']"
              type="primary"
              size="mini"
              :disabled="!isOverridable(run)"
              @click="openOverride"
            >新增复核</el-button>
          </div>
          <el-table :data="overrideHistory" size="mini" border empty-text="暂无人工复核记录。">
            <el-table-column label="时间" width="155">
              <template slot-scope="{ row }">{{ formatTimestamp(row.createdAt) }}</template>
            </el-table-column>
            <el-table-column label="风险变化" width="150">
              <template slot-scope="{ row }">{{ formatRiskLevel(row.previousRiskLevel) }} -> {{ formatRiskLevel(row.newRiskLevel) }}</template>
            </el-table-column>
            <el-table-column prop="newAction" label="新动作" width="120" />
            <el-table-column prop="reason" label="理由" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header" class="card-header">
            <span>Replay 与对比</span>
            <el-button
              v-permission="['POST /admin/agent-rag/runs/replay']"
              :loading="submittingReplay"
              :disabled="!isReplayable(run)"
              type="primary"
              size="mini"
              @click="handleReplay"
            >发起 Replay</el-button>
          </div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="Parent Run">{{ run.parentRunId || '--' }}</el-descriptions-item>
            <el-descriptions-item label="Replay Of">{{ run.replayOfRunId || '--' }}</el-descriptions-item>
            <el-descriptions-item label="当前对比">{{ compareTargetId || '--' }}</el-descriptions-item>
          </el-descriptions>
          <el-divider />
          <div v-if="comparison">
            <div v-for="(value, key) in comparison.changes" :key="key" class="compare-row">
              <span>{{ key }}</span>
              <strong>{{ value }}</strong>
            </div>
          </div>
          <el-empty v-else description="尚未加载 Replay 对比结果。" />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog title="人工复核 Agent-RAG 结果" :visible.sync="overrideDialogVisible" width="520px">
      <el-form ref="overrideForm" :model="overrideForm" :rules="overrideRules" label-width="110px">
        <el-form-item label="新风险等级" prop="newRiskLevel">
          <el-select v-model="overrideForm.newRiskLevel" placeholder="请选择">
            <el-option v-for="item in riskOptions" :key="item" :label="formatRiskLevel(item)" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="新动作" prop="newAction">
          <el-select v-model="overrideForm.newAction" placeholder="请选择">
            <el-option v-for="item in actionOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="复核理由" prop="reason">
          <el-input v-model="overrideForm.reason" type="textarea" :rows="4" maxlength="500" show-word-limit placeholder="请说明人工复核依据，至少 8 个字符。" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button @click="overrideDialogVisible = false">取消</el-button>
        <el-button :loading="submittingOverride" type="primary" @click="submitOverride">提交复核</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getAgentRagRunDetail, getAgentRagEvidence, overrideAgentRagRun, replayAgentRagRun, compareAgentRagRuns } from '@/api/agentRag'
import { formatRiskLevel, formatRunStatus, formatProvider, formatRetrievalMode, formatFallbackReason, formatDuration, formatConfidence, formatTimestamp, shortFingerprint, getRiskTagType, getStatusTagType, getProviderTagType, isReplayable, isOverridable, parseEvidenceBundle } from '@/utils/agent-rag'

const DecisionCard = {
  props: {
    decision: { type: Object, default: () => ({}) }
  },
  methods: {
    formatRiskLevel,
    formatConfidence,
    getRiskTagType
  },
  template: `
    <div class="decision-card">
      <div class="decision-row">
        <span>风险等级</span>
        <el-tag :type="getRiskTagType(decision.riskLevel)" size="mini">{{ formatRiskLevel(decision.riskLevel) }}</el-tag>
      </div>
      <div class="decision-row">
        <span>建议动作</span>
        <strong>{{ decision.action || '--' }}</strong>
      </div>
      <div class="decision-row">
        <span>置信度</span>
        <strong>{{ formatConfidence(decision.confidence) }}</strong>
      </div>
      <div class="decision-row">
        <span>人工复核</span>
        <strong>{{ decision.requiresHumanReview ? '需要' : '不需要' }}</strong>
      </div>
    </div>
  `
}

export default {
  name: 'AgentRagRunDetail',
  components: { DecisionCard },
  data() {
    return {
      loading: false,
      loadError: '',
      run: {},
      evidence: {},
      evidenceBundle: {},
      originalDecision: {},
      effectiveDecision: {},
      overrideHistory: [],
      comparison: null,
      compareTargetId: '',
      overrideDialogVisible: false,
      submittingOverride: false,
      submittingReplay: false,
      riskOptions: ['none', 'low', 'medium', 'high', 'critical'],
      actionOptions: ['none', 'monitor', 'reply', 'hide', 'escalate', 'refund_review', 'manual_review'],
      overrideForm: {
        newRiskLevel: '',
        newAction: '',
        reason: ''
      },
      overrideRules: {
        newRiskLevel: [{ required: true, message: '请选择新风险等级', trigger: 'change' }],
        newAction: [{ required: true, message: '请选择新动作', trigger: 'change' }],
        reason: [
          { required: true, message: '请输入复核理由', trigger: 'blur' },
          { min: 8, message: '复核理由至少 8 个字符', trigger: 'blur' }
        ]
      }
    }
  },
  computed: {
    runId() {
      return this.$route.params.id
    },
    providerDegraded() {
      return this.run.requestedProviderImpl && this.run.effectiveProviderImpl && this.run.requestedProviderImpl !== this.run.effectiveProviderImpl
    },
    evidenceTimeline() {
      const bundle = this.evidenceBundle || {}
      const items = []
      if (bundle.truncated) {
        items.push({ title: '证据已限长', timestamp: this.formatTimestamp(this.evidence.createdAt), content: JSON.stringify({ originalBytes: bundle.originalBytes, originalSha256: shortFingerprint(bundle.originalSha256), payloadPrefix: bundle.payloadPrefix }, null, 2) })
        return items
      }
      items.push({ title: '请求上下文', timestamp: this.formatTimestamp(this.evidence.createdAt), content: JSON.stringify({ requestId: bundle.requestId, subjectType: bundle.subjectType, subjectId: bundle.subjectId }, null, 2) })
      if (bundle.retrieval) items.push({ title: '检索与引用', timestamp: this.formatTimestamp(this.evidence.createdAt), content: JSON.stringify(bundle.retrieval, null, 2) })
      if (bundle.analysis) items.push({ title: '分析摘要', timestamp: this.formatTimestamp(this.evidence.createdAt), content: JSON.stringify(bundle.analysis, null, 2) })
      if (bundle.runtime) items.push({ title: '运行时信息', timestamp: this.formatTimestamp(this.evidence.createdAt), content: JSON.stringify(bundle.runtime, null, 2) })
      if (bundle.audit) items.push({ title: '审计轨迹', timestamp: this.formatTimestamp(this.evidence.createdAt), content: JSON.stringify(bundle.audit, null, 2) })
      return items
    },
    realModelEvidence() {
      const bundle = this.evidenceBundle || {}
      const retrieval = bundle.retrieval || {}
      const runtime = bundle.runtime || {}
      return Object.assign({}, retrieval, runtime, {
        effectiveRetrievalMode: retrieval.effectiveRetrievalMode || runtime.effectiveRetrievalMode || this.run.effectiveRetrievalMode,
        effectiveAnalysisProvider: runtime.effectiveAnalysisProvider || runtime.effectiveLlmProvider || this.run.effectiveProviderImpl,
        fallbackUsed: Boolean(runtime.fallbackUsed || runtime.llmFallbackUsed || retrieval.denseFallbackUsed || retrieval.rerankerFallbackUsed || this.run.fallbackUsed)
      })
    }
  },
  created() {
    this.compareTargetId = this.$route.query.compareTo || ''
    this.loadDetail()
  },
  methods: {
    formatRiskLevel,
    formatRunStatus,
    formatProvider,
    formatRetrievalMode,
    formatFallbackReason,
    formatDuration,
    formatConfidence,
    formatTimestamp,
    shortFingerprint,
    getRiskTagType,
    getStatusTagType,
    getProviderTagType,
    isReplayable,
    isOverridable,
    safeError(code, message) {
      if (!code && !message) return '--'
      return [code, message].filter(Boolean).join(': ').substring(0, 240)
    },
    async loadDetail() {
      this.loading = true
      this.loadError = ''
      try {
        const detail = await getAgentRagRunDetail(this.runId)
        const data = detail.data.data || {}
        this.run = data.run || {}
        this.evidence = data.evidence || {}
        this.originalDecision = data.originalDecision || {}
        this.effectiveDecision = data.effectiveDecision || {}
        this.overrideHistory = data.overrideHistory || []
        if (!this.evidence.boundedJson) {
          const evidenceResponse = await getAgentRagEvidence(this.runId)
          this.evidence = evidenceResponse.data.data || {}
        }
        this.evidenceBundle = parseEvidenceBundle(this.evidence.boundedJson)
        if (this.compareTargetId) {
          await this.loadComparison(this.compareTargetId, this.run.id)
        }
      } catch (e) {
        this.loadError = '运行详情加载失败，请检查记录是否存在以及当前账号权限。'
      } finally {
        this.loading = false
      }
    },
    async loadComparison(baseId, compareId) {
      try {
        const response = await compareAgentRagRuns(baseId, compareId)
        this.comparison = response.data.data
      } catch (e) {
        this.comparison = null
      }
    },
    openOverride() {
      this.overrideForm = {
        newRiskLevel: this.effectiveDecision.riskLevel || this.originalDecision.riskLevel || 'medium',
        newAction: this.effectiveDecision.action || this.originalDecision.action || 'manual_review',
        reason: ''
      }
      this.overrideDialogVisible = true
    },
    submitOverride() {
      this.$refs.overrideForm.validate(async valid => {
        if (!valid) return
        this.submittingOverride = true
        try {
          await overrideAgentRagRun(this.run.id, this.overrideForm)
          this.$message.success('人工复核已追加保存，原始 AI 结果已保留。')
          this.overrideDialogVisible = false
          this.loadDetail()
        } catch (e) {
          this.$message.error('人工复核提交失败，请检查权限或输入。')
        } finally {
          this.submittingOverride = false
        }
      })
    },
    async handleReplay() {
      try {
        await this.$confirm('Replay 会创建新的运行记录，原记录不会被覆盖。是否继续？', '确认 Replay', { type: 'warning' })
      } catch (e) {
        return
      }
      this.submittingReplay = true
      try {
        const response = await replayAgentRagRun(this.run.id)
        const replayRun = response.data.data && response.data.data.run
        this.$message.success('Replay 已创建新的运行记录。')
        if (replayRun && replayRun.id) {
          this.$router.push(`/agent-rag/runs/${replayRun.id}?compareTo=${this.run.id}`)
        }
      } catch (e) {
        this.$message.error('Replay 失败，请确认 AI Runtime 与熔断状态。')
      } finally {
        this.submittingReplay = false
      }
    }
  }
}
</script>

<style scoped>
.page-header,
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
}
.page-header p,
.muted {
  margin: 0;
  color: #909399;
}
.section-gap {
  margin-top: 16px;
}
h3 {
  margin: 0 0 12px;
}
.decision-row,
.compare-row,
.evidence-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 34px;
  gap: 16px;
}
.bounded-snippet {
  max-height: 220px;
  overflow: auto;
  padding: 12px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}
.evidence-meta {
  justify-content: flex-start;
  margin-top: 12px;
  color: #909399;
}
.warn-text {
  margin-left: 8px;
  color: #e6a23c;
}
.model-evidence-inline {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.model-evidence-inline > div {
  min-height: 88px;
  padding: 10px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background: #fafafa;
}
.model-evidence-inline strong,
.model-evidence-inline span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-evidence-inline strong {
  margin-bottom: 6px;
  color: #303133;
}
.model-evidence-inline span {
  color: #606266;
  line-height: 20px;
}
.model-evidence-note {
  margin: 0 0 12px;
  color: #909399;
  font-size: 12px;
}
@media (max-width: 900px) {
  .model-evidence-inline {
    grid-template-columns: 1fr;
  }
}
</style>
