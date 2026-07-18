<template>
  <div class="ai-workbench-page ai-agent-eval-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">智能体评估（Agent Eval）</p>
        <h1 class="ai-page-title">智能体评估中心</h1>
        <p class="ai-page-subtitle">
          从运行稳定性、工具调用、案例检索、人工反馈、诊断信息和质量指标评估评论治理智能体，辅助答辩展示和系统验收。
        </p>
      </div>
      <div class="ai-toolbar">
        <el-button icon="el-icon-refresh" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <div class="ai-card framework-status-card">
      <div class="ai-card-header">
        <div>
          <h2 class="ai-card-title">智能体框架状态</h2>
          <p class="ai-card-desc">展示专业框架开关与本地规则工作流回退机制，便于说明当前演示环境的稳定边界。</p>
        </div>
        <span :class="['ai-status-tag', frameworkStatus.available === false ? 'ai-status-negative' : 'ai-status-positive']">
          {{ frameworkMode }}
        </span>
      </div>
      <div class="framework-status-grid">
        <div>
          <label>当前模式</label>
          <strong>{{ modeText(frameworkStatus.currentMode || frameworkStatus.current_mode) }}</strong>
        </div>
        <div>
          <label>LangGraph</label>
          <strong>{{ yesNo(frameworkStatus.langgraphAvailable || frameworkStatus.langgraph_available) }}</strong>
        </div>
        <div>
          <label>外部模型密钥</label>
          <strong>{{ yesNo(frameworkStatus.openaiApiKeyAvailable || frameworkStatus.openai_api_key_available) }}</strong>
        </div>
        <div>
          <label>Java 开关</label>
          <strong>{{ yesNo(frameworkStatus.javaConfigEnabled) }}</strong>
        </div>
      </div>
      <p v-if="frameworkStatus.lastError || frameworkStatus.last_error" class="framework-error">
        {{ frameworkStatus.lastError || frameworkStatus.last_error }}
      </p>
    </div>

    <div class="ai-metric-grid">
      <el-tooltip v-for="item in metrics" :key="item.label" :content="item.description" placement="top">
        <div class="ai-metric-card">
          <div class="ai-metric-label">{{ item.label }}</div>
          <div class="ai-metric-value">{{ item.value }}</div>
          <div class="ai-metric-hint">{{ item.hint }}</div>
        </div>
      </el-tooltip>
    </div>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="14">
        <div class="ai-card quality-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">质量评估摘要</h2>
              <p class="ai-card-desc">基于黄金样本和实时运行证据汇总质量指标，用于答辩中的可解释展示。低于 70% 的指标会提示关注，但不作为硬阻断。</p>
            </div>
            <el-tag :type="qualitySummary.warning ? 'warning' : 'success'">
              {{ qualitySummary.warning ? '需要关注' : '演示就绪' }}
            </el-tag>
          </div>
          <div class="quality-grid">
            <div v-for="item in qualityCards" :key="item.label">
              <label>{{ item.label }}</label>
              <strong>{{ item.value }}</strong>
              <span>{{ item.hint }}</span>
            </div>
          </div>
          <div class="ai-advice-note">AI 输出仅供运营辅助参考，最终风险处理必须由人工确认。</div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="ai-card diagnostics-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">诊断中心</h2>
              <p class="ai-card-desc">汇总服务健康、失败运行、失败步骤、回退信号、巡检失败和修复建议，便于快速排障。</p>
            </div>
            <el-tag :type="diagnosticsSummary.aiServiceStatus === 'ok' ? 'success' : 'danger'">
              {{ healthText(diagnosticsSummary.aiServiceStatus) }}
            </el-tag>
          </div>
          <div class="diagnostics-list">
            <div><span>框架模式</span><strong>{{ modeText(diagnosticsSummary.frameworkMode) }}</strong></div>
            <div><span>失败步骤</span><strong>{{ diagnosticsSummary.failedSteps || 0 }}</strong></div>
            <div><span>回退步骤</span><strong>{{ diagnosticsSummary.fallbackSteps || 0 }}</strong></div>
            <div><span>巡检失败</span><strong>{{ diagnosticsSummary.patrolFailures || 0 }}</strong></div>
          </div>
          <p class="diagnostics-suggestion">{{ diagnosticsSummary.suggestion || '暂无诊断建议。' }}</p>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="12">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">服务健康状态</h2>
              <p class="ai-card-desc">检查顾客端到后台闭环所需的本地演示服务。</p>
            </div>
          </div>
          <div class="health-grid">
            <div v-for="item in healthCards" :key="item.name">
              <label>{{ item.name }}</label>
              <el-tag :type="item.status === 'ok' ? 'success' : 'danger'" size="mini">{{ healthText(item.status) }}</el-tag>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" :lg="12">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">失败分组</h2>
              <p class="ai-card-desc">按常见错误类型聚合，并给出演示排练时可执行的修复建议。</p>
            </div>
          </div>
          <div v-if="failureGroups.length" class="failure-group-list">
            <div v-for="item in failureGroups" :key="item.name">
              <span>{{ item.name }}</span>
              <strong>{{ item.count || 0 }}</strong>
              <em>{{ item.suggestion }}</em>
            </div>
          </div>
          <div v-else class="ai-empty-state compact-empty">
            <i class="el-icon-circle-check" />
            <span>暂无失败分组。</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="14">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">工具调用统计</h2>
              <p class="ai-card-desc">展示工具名称、调用次数、成功次数、失败次数和平均耗时。</p>
            </div>
          </div>
          <el-table v-loading="loading" :data="toolStats" border fit highlight-current-row empty-text="暂无工具调用数据。">
            <el-table-column prop="toolName" label="工具名称" min-width="190" show-overflow-tooltip />
            <el-table-column prop="callCount" label="调用次数" width="110" align="center" />
            <el-table-column prop="successCount" label="成功次数" width="130" align="center" />
            <el-table-column prop="failedCount" label="失败次数" width="120" align="center" />
            <el-table-column prop="avgDurationMs" label="平均耗时(ms)" width="150" align="center" />
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">人工反馈分布</h2>
              <p class="ai-card-desc">展示人工参与闭环后回写到评估中心的反馈类型。</p>
            </div>
          </div>
          <div v-if="normalizedFeedbackStats.length" class="feedback-list">
            <div v-for="item in normalizedFeedbackStats" :key="item.name" class="feedback-item">
              <span>{{ item.name }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
          <div v-else class="ai-empty-state compact-empty">
            <i class="el-icon-chat-line-square" />
            <span>暂无人工反馈。</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="ai-card">
      <div class="ai-card-header">
        <div>
          <h2 class="ai-card-title">最近诊断事件</h2>
          <p class="ai-card-desc">仅展示清洗后的错误摘要，本地路径、堆栈和疑似密钥信息不会直接暴露。</p>
        </div>
      </div>
      <el-table v-loading="loading" :data="diagnosticsFailures" border fit highlight-current-row empty-text="暂无最近诊断失败。">
        <el-table-column prop="itemType" label="类型" width="100" />
        <el-table-column prop="itemNo" label="编号" min-width="170" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template slot-scope="scope">{{ statusText(scope.row.status) }}</template>
        </el-table-column>
        <el-table-column prop="errorMessage" label="错误摘要" min-width="260" show-overflow-tooltip />
        <el-table-column prop="createdTime" label="创建时间" width="180" show-overflow-tooltip />
      </el-table>
    </div>

    <div class="ai-card">
      <div class="ai-card-header">
        <div>
          <h2 class="ai-card-title">最近失败运行</h2>
          <p class="ai-card-desc">如果这里为空，表示当前数据集中暂未发现失败运行。</p>
        </div>
      </div>
      <el-table v-loading="loading" :data="summary.recentFailedRuns || []" border fit highlight-current-row empty-text="暂无失败运行。">
        <el-table-column prop="runNo" label="运行编号" min-width="180" show-overflow-tooltip />
        <el-table-column prop="sourceType" label="来源" width="150">
          <template slot-scope="scope">{{ sourceText(scope.row.sourceType) }}</template>
        </el-table-column>
        <el-table-column prop="sourceId" label="来源ID" width="100" />
        <el-table-column prop="errorMessage" label="错误摘要" min-width="240" show-overflow-tooltip />
        <el-table-column prop="createdTime" label="创建时间" width="180" />
      </el-table>
    </div>
  </div>
</template>

<script>
import { aiCaseStats } from '@/api/aiCase'
import {
  agentDiagnosticsFailureGroups,
  agentDiagnosticsHealth,
  agentDiagnosticsRecentFailures,
  agentDiagnosticsSummary,
  agentEvalSummary,
  agentFeedbackStats,
  agentFrameworkStatus,
  agentQualitySummary,
  agentToolStats
} from '@/api/aiAgent'
import { displayValue, feedbackTypeMap, healthStatusMap, sourceTypeMap, statusMap, yesNoText } from '@/utils/aiDisplayMap'

const FEEDBACK_TYPES = [
  'accept',
  'false_positive',
  'risk_level_too_high',
  'risk_level_too_low',
  'suggestion_bad',
  'transferred_after_sales',
  'closed_without_action'
]

export default {
  name: 'AiAgentEval',
  data() {
    return {
      loading: false,
      summary: {},
      toolStats: [],
      feedbackStats: [],
      frameworkStatus: {},
      caseStats: {},
      qualitySummary: {},
      diagnosticsSummary: {},
      diagnosticsFailures: [],
      failureGroups: [],
      health: {}
    }
  },
  computed: {
    metrics() {
      const total = Number(this.summary.totalRuns || 0)
      const success = Number(this.summary.successRuns || 0)
      const feedback = Number(this.summary.feedbackCount || 0)
      const accepted = Number(this.summary.acceptedFeedback || 0)
      const falsePositive = Number(this.summary.falsePositiveFeedback || 0)
      const retrieval = this.caseStats.retrieval || {}
      return [
        { label: '运行总数', value: total, hint: '智能体运行记录', description: '已记录的智能体工作流运行次数。' },
        { label: '成功率', value: total ? Math.round(success * 100 / total) + '%' : '0%', hint: '成功 / 总数', description: '智能体工作流运行稳定性。' },
        { label: '平均耗时', value: (this.summary.avgDurationMs || 0) + ' ms', hint: '端到端耗时', description: '智能体端到端平均运行耗时。' },
        { label: '工具失败', value: this.summary.toolFailures || 0, hint: '失败步骤', description: '工具调用失败次数。' },
        { label: '人工反馈', value: feedback, hint: '闭环回写', description: '运营处理后回写的人工反馈数量。' },
        { label: '采纳率', value: feedback ? Math.round(accepted * 100 / feedback) + '%' : '0%', hint: '采纳 / 反馈', description: '智能体建议被采纳的比例。' },
        { label: '误报数量', value: falsePositive, hint: '人工标记误报', description: '运营人员标记为误报的案例数。' },
        { label: '重复来源组', value: this.summary.duplicateAnalysisGroups || 0, hint: '来源去重', description: '按来源统计的重复分析组。' },
        { label: '案例数量', value: this.caseStats.caseCount || 0, hint: '案例知识库', description: '可用于检索的历史案例数量。' },
        { label: '检索次数', value: retrieval.retrievalCount || 0, hint: this.modeText(this.caseStats.retrievalMode || 'local_keyword'), description: '检索增强调用次数。' },
        { label: '空检索次数', value: retrieval.emptyRetrievalCount || 0, hint: '无相似案例', description: '未找到相似案例的检索次数。' },
        { label: '检索耗时', value: (retrieval.avgDurationMs || 0) + ' ms', hint: '本地检索', description: '平均本地检索耗时。' }
      ]
    },
    healthCards() {
      return [
        { name: 'admin-api', status: this.health.adminApi },
        { name: 'MySQL', status: this.health.mysql },
        { name: 'AI 服务', status: this.health.aiService },
        { name: 'wx-api', status: this.health.wxApi },
        { name: 'H5 用户端', status: this.health.h5 },
        { name: '后台前端', status: this.health.adminFrontend }
      ]
    },
    normalizedFeedbackStats() {
      const rows = this.feedbackStats || []
      const map = {}
      rows.forEach(item => {
        map[item.name || item.feedbackType] = item.value || item.count || 0
      })
      return FEEDBACK_TYPES.map(name => ({ name: displayValue(feedbackTypeMap, name), value: map[name] || 0 }))
    },
    qualityCards() {
      return [
        { label: '黄金样本数', value: this.qualitySummary.goldenSampleCount || 0, hint: '30 个场景样本' },
        { label: '情感识别准确率', value: this.percentValue(this.qualitySummary.sentimentAccuracy), hint: '情感识别' },
        { label: '风险类型命中率', value: this.percentValue(this.qualitySummary.riskTypeHitRate), hint: '风险类型' },
        { label: '风险等级准确率', value: this.percentValue(this.qualitySummary.riskLevelAccuracy), hint: '风险等级' },
        { label: '图文冲突识别', value: this.percentValue(this.qualitySummary.conflictDetectionAccuracy), hint: '图文一致性' },
        { label: '主模态判断', value: this.percentValue(this.qualitySummary.dominantModalityAccuracy), hint: '图文主次' },
        { label: '证据覆盖率', value: this.percentValue(this.qualitySummary.evidenceCoverageRate), hint: '追踪证据' },
        { label: '运营建议命中率', value: this.percentValue(this.qualitySummary.suggestionActionHitRate), hint: '处理建议' },
        { label: '案例检索非空率', value: this.percentValue(this.qualitySummary.caseRetrievalNonEmptyRate), hint: '检索增强' },
        { label: '回退率', value: this.percentValue(this.qualitySummary.fallbackRate), hint: '越低越好' },
        { label: '平均耗时', value: (this.qualitySummary.averageLatencyMs || 0) + ' ms', hint: '质量评估耗时' }
      ]
    },
    frameworkMode() {
      if (this.frameworkStatus.available === false) {
        return '不可用'
      }
      return this.modeText(this.frameworkStatus.currentMode || this.frameworkStatus.current_mode || 'legacy_rule_agent')
    }
  },
  created() {
    this.loadData()
  },
  methods: {
    loadData() {
      this.loading = true
      Promise.all([
        agentEvalSummary(),
        agentToolStats(),
        agentFeedbackStats(),
        agentFrameworkStatus(),
        aiCaseStats(),
        agentQualitySummary(),
        agentDiagnosticsSummary(),
        agentDiagnosticsRecentFailures(),
        agentDiagnosticsFailureGroups(),
        agentDiagnosticsHealth()
      ]).then(([summaryRes, toolRes, feedbackRes, frameworkRes, caseStatsRes, qualityRes, diagnosticsRes, failuresRes, groupsRes, healthRes]) => {
        this.summary = summaryRes.data.data || {}
        this.toolStats = toolRes.data.data || []
        this.feedbackStats = feedbackRes.data.data || []
        this.frameworkStatus = frameworkRes.data.data || {}
        this.caseStats = caseStatsRes.data.data || {}
        this.qualitySummary = qualityRes.data.data || {}
        this.diagnosticsSummary = diagnosticsRes.data.data || {}
        this.diagnosticsFailures = failuresRes.data.data || []
        this.failureGroups = groupsRes.data.data || []
        this.health = healthRes.data.data || {}
      }).catch(() => {
        this.summary = {}
        this.toolStats = []
        this.feedbackStats = []
        this.frameworkStatus = {}
        this.caseStats = {}
        this.qualitySummary = {}
        this.diagnosticsSummary = {}
        this.diagnosticsFailures = []
        this.failureGroups = []
        this.health = {}
      }).finally(() => {
        this.loading = false
      })
    },
    percentValue(value) {
      if (value === undefined || value === null || value === '') {
        return '0%'
      }
      return String(value).indexOf('%') > -1 ? String(value) : value + '%'
    },
    yesNo(value) {
      return yesNoText(value)
    },
    statusText(value) {
      return displayValue(statusMap, value)
    },
    healthText(value) {
      return displayValue(healthStatusMap, value || 'unknown')
    },
    sourceText(value) {
      return displayValue(sourceTypeMap, value)
    },
    modeText(value) {
      const map = {
        legacy_rule_agent: '本地规则智能体',
        professional_agent: '专业框架智能体',
        local_keyword: '本地关键词检索',
        vector_rag: '向量检索增强'
      }
      return displayValue(map, value)
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-agent-eval-page {
  .ai-metric-grid {
    margin-bottom: 18px;
  }

  .framework-status-card {
    margin-bottom: 18px;
  }

  .quality-card,
  .diagnostics-card {
    min-height: 310px;
    margin-bottom: 18px;
  }

  .quality-grid,
  .health-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 10px;

    div {
      padding: 12px;
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
    }

    label,
    span {
      display: block;
      color: #64748b;
      font-size: 12px;
    }

    strong {
      display: block;
      margin: 6px 0 4px;
      color: #111827;
      font-size: 20px;
    }
  }

  .health-grid div {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .diagnostics-list {
    display: grid;
    gap: 10px;

    div {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 11px 12px;
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
    }

    span {
      color: #64748b;
    }

    strong {
      color: #111827;
    }
  }

  .diagnostics-suggestion {
    margin: 12px 0 0;
    padding: 12px;
    color: #1d4ed8;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    line-height: 1.6;
  }

  .framework-status-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;

    div {
      padding: 12px 14px;
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
    }

    label {
      display: block;
      margin-bottom: 6px;
      color: #64748b;
      font-size: 12px;
    }

    strong {
      color: #111827;
      font-size: 15px;
    }
  }

  .framework-error {
    margin: 12px 0 0;
    color: #dc2626;
  }

  .feedback-list,
  .failure-group-list {
    display: grid;
    gap: 10px;
  }

  .feedback-item,
  .failure-group-list div {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 12px 14px;
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
  }

  .failure-group-list em {
    flex: 1;
    color: #64748b;
    font-size: 12px;
    font-style: normal;
  }

  .compact-empty {
    min-height: 180px;
  }
}
</style>
