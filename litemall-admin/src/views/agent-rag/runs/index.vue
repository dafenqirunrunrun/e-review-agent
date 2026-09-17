<template>
  <div class="app-container agent-rag-page">
    <div class="page-header">
      <div>
        <h2>Agent-RAG 分析记录</h2>
        <p>按运行状态、风险等级、Provider、Fallback 与时间窗口查询治理记录。</p>
      </div>
      <el-button :loading="listLoading" type="primary" icon="el-icon-refresh" @click="getList">刷新</el-button>
    </div>

    <el-card shadow="never" class="section-gap">
      <div class="quick-filters">
        <el-button-group>
          <el-button :type="quickFilter === 'all' ? 'primary' : 'default'" size="mini" @click="applyQuickFilter('all')">全部</el-button>
          <el-button :type="quickFilter === 'high' ? 'primary' : 'default'" size="mini" @click="applyQuickFilter('high')">高风险</el-button>
          <el-button :type="quickFilter === 'review' ? 'primary' : 'default'" size="mini" @click="applyQuickFilter('review')">待复核</el-button>
          <el-button :type="quickFilter === 'fallback' ? 'primary' : 'default'" size="mini" @click="applyQuickFilter('fallback')">Fallback</el-button>
          <el-button :type="quickFilter === 'failed' ? 'primary' : 'default'" size="mini" @click="applyQuickFilter('failed')">失败</el-button>
          <el-button :type="quickFilter === 'today' ? 'primary' : 'default'" size="mini" @click="applyQuickFilter('today')">今日</el-button>
        </el-button-group>
      </div>

      <el-form :inline="true" :model="listQuery" size="small" class="filter-form">
        <el-form-item label="Subject 类型">
          <el-input v-model="listQuery.subjectType" clearable placeholder="review/comment" />
        </el-form-item>
        <el-form-item label="Subject ID">
          <el-input v-model="listQuery.subjectId" clearable placeholder="局部匹配" />
        </el-form-item>
        <el-form-item label="Request ID">
          <el-input v-model="listQuery.requestId" clearable placeholder="局部匹配" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="listQuery.status" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="item in statusOptions" :key="item" :label="formatRunStatus(item)" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险">
          <el-select v-model="listQuery.riskLevel" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="item in riskOptions" :key="item" :label="formatRiskLevel(item)" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="Provider">
          <el-select v-model="listQuery.providerImpl" clearable placeholder="全部" style="width: 150px">
            <el-option value="flagembedding" label="Official BGE-M3" />
            <el-option value="cls" label="Legacy CLS" />
            <el-option value="hash" label="Hash Dense" />
            <el-option value="sparse" label="Sparse Only" />
          </el-select>
        </el-form-item>
        <el-form-item label="Fallback">
          <el-select v-model="listQuery.fallbackUsed" clearable placeholder="全部" style="width: 110px">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="人工复核">
          <el-select v-model="listQuery.requiresHumanReview" clearable placeholder="全部" style="width: 120px">
            <el-option label="需要" :value="true" />
            <el-option label="不需要" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            value-format="yyyy-MM-dd HH:mm:ss"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            style="width: 360px"
          />
        </el-form-item>
        <el-form-item>
          <el-button v-permission="['GET /admin/agent-rag/runs']" type="primary" icon="el-icon-search" @click="handleFilter">查询</el-button>
          <el-button icon="el-icon-delete" @click="resetFilter">清空</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      show-icon
      class="section-gap"
    />

    <el-table v-loading="listLoading" :data="list" class="section-gap" border fit highlight-current-row empty-text="暂无 Agent-RAG 运行记录。">
      <el-table-column label="时间" width="160">
        <template slot-scope="{ row }">{{ formatTimestamp(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="Subject" min-width="170" show-overflow-tooltip>
        <template slot-scope="{ row }">
          <div>{{ row.subjectType || '--' }}</div>
          <small class="muted">{{ row.subjectId || '--' }}</small>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template slot-scope="{ row }">
          <el-tag :type="getStatusTagType(row.status)" size="mini">{{ formatRunStatus(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="原始风险" width="105">
        <template slot-scope="{ row }">
          <el-tag :type="getRiskTagType(row.originalRiskLevel)" size="mini">{{ formatRiskLevel(row.originalRiskLevel) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="有效风险" width="105">
        <template slot-scope="{ row }">
          <el-tag :type="getRiskTagType(row.effectiveRiskLevel)" size="mini">
            {{ formatRiskLevel(row.effectiveRiskLevel) }}
          </el-tag>
          <span v-if="row.overrideCount > 0" class="override-dot">人工</span>
        </template>
      </el-table-column>
      <el-table-column prop="effectiveAction" label="Action" width="120" show-overflow-tooltip />
      <el-table-column label="Confidence" width="110">
        <template slot-scope="{ row }">{{ formatConfidence(row.confidence) }}</template>
      </el-table-column>
      <el-table-column label="Provider" min-width="150" show-overflow-tooltip>
        <template slot-scope="{ row }">
          <el-tag :type="getProviderTagType(row.effectiveProviderImpl)" size="mini">{{ formatProvider(row.effectiveProviderImpl) }}</el-tag>
          <div v-if="row.requestedProviderImpl && row.requestedProviderImpl !== row.effectiveProviderImpl" class="muted">已降级</div>
        </template>
      </el-table-column>
      <el-table-column label="Retrieval" min-width="150" show-overflow-tooltip>
        <template slot-scope="{ row }">{{ formatRetrievalMode(row.effectiveRetrievalMode) }}</template>
      </el-table-column>
      <el-table-column label="Index" min-width="120" show-overflow-tooltip>
        <template slot-scope="{ row }">{{ row.indexVersion || '--' }}</template>
      </el-table-column>
      <el-table-column label="Fallback" width="120" show-overflow-tooltip>
        <template slot-scope="{ row }">
          <el-tag :type="row.fallbackUsed ? 'warning' : 'success'" size="mini">{{ row.fallbackUsed ? '是' : '否' }}</el-tag>
          <div v-if="row.fallbackUsed" class="muted">{{ formatFallbackReason(row.fallbackReason) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="90">
        <template slot-scope="{ row }">{{ formatDuration(row.durationMs) }}</template>
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="230">
        <template slot-scope="{ row }">
          <el-button type="text" size="mini" @click="viewDetail(row)">详情</el-button>
          <el-button
            v-permission="['POST /admin/agent-rag/override']"
            type="text"
            size="mini"
            :disabled="!isOverridable(row)"
            @click="openOverride(row)"
          >人工复核</el-button>
          <el-button
            v-permission="['POST /admin/agent-rag/runs/replay']"
            type="text"
            size="mini"
            :loading="replayingId === row.id"
            :disabled="!isReplayable(row)"
            @click="handleReplay(row)"
          >Replay</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total > 0" :total="total" :page.sync="listQuery.page" :limit.sync="listQuery.limit" @pagination="getList" />

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
import Pagination from '@/components/Pagination'
import { getAgentRagRuns, overrideAgentRagRun, replayAgentRagRun } from '@/api/agentRag'
import { formatRiskLevel, formatRunStatus, formatProvider, formatRetrievalMode, formatFallbackReason, formatDuration, formatConfidence, formatTimestamp, getRiskTagType, getStatusTagType, getProviderTagType, isReplayable, isOverridable } from '@/utils/agent-rag'

export default {
  name: 'AgentRagRuns',
  components: { Pagination },
  data() {
    return {
      list: [],
      total: 0,
      listLoading: false,
      loadError: '',
      quickFilter: 'all',
      dateRange: [],
      replayingId: null,
      overrideDialogVisible: false,
      submittingOverride: false,
      selectedRun: null,
      listQuery: {
        page: 1,
        limit: 20,
        subjectType: '',
        subjectId: '',
        requestId: '',
        status: '',
        riskLevel: '',
        providerImpl: '',
        fallbackUsed: '',
        requiresHumanReview: ''
      },
      statusOptions: ['PENDING', 'RUNNING', 'SUCCESS', 'RULE_FALLBACK', 'FAILED', 'REVIEW_REQUIRED', 'OVERRIDDEN', 'REPLAYED'],
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
  created() {
    this.getList()
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
    getRiskTagType,
    getStatusTagType,
    getProviderTagType,
    isReplayable,
    isOverridable,
    cleanParams() {
      const params = {}
      Object.keys(this.listQuery).forEach(key => {
        const value = this.listQuery[key]
        if (value !== '' && value !== null && value !== undefined) {
          params[key] = value
        }
      })
      if (this.dateRange && this.dateRange.length === 2) {
        params.createdFrom = this.dateRange[0]
        params.createdTo = this.dateRange[1]
      }
      return params
    },
    async getList() {
      this.listLoading = true
      this.loadError = ''
      try {
        const response = await getAgentRagRuns(this.cleanParams())
        const data = response.data.data || {}
        this.list = data.items || []
        this.total = data.total || 0
      } catch (e) {
        this.loadError = '分析记录加载失败，请检查权限、admin-api 与数据库状态。'
        this.list = []
        this.total = 0
      } finally {
        this.listLoading = false
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    resetFilter() {
      this.quickFilter = 'all'
      this.dateRange = []
      Object.assign(this.listQuery, {
        page: 1,
        limit: this.listQuery.limit,
        subjectType: '',
        subjectId: '',
        requestId: '',
        status: '',
        riskLevel: '',
        providerImpl: '',
        fallbackUsed: '',
        requiresHumanReview: ''
      })
      this.getList()
    },
    applyQuickFilter(type) {
      this.quickFilter = type
      this.dateRange = []
      Object.assign(this.listQuery, {
        page: 1,
        status: '',
        riskLevel: '',
        fallbackUsed: '',
        requiresHumanReview: ''
      })
      if (type === 'high') this.listQuery.riskLevel = 'high'
      if (type === 'review') this.listQuery.requiresHumanReview = true
      if (type === 'fallback') this.listQuery.fallbackUsed = true
      if (type === 'failed') this.listQuery.status = 'FAILED'
      if (type === 'today') {
        const now = new Date()
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0)
        this.dateRange = [this.formatDate(start), this.formatDate(now)]
      }
      this.getList()
    },
    formatDate(date) {
      const pad = value => String(value).padStart(2, '0')
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    },
    viewDetail(row) {
      this.$router.push(`/agent-rag/runs/${row.id}`)
    },
    openOverride(row) {
      this.selectedRun = row
      this.overrideForm = {
        newRiskLevel: row.effectiveRiskLevel || row.originalRiskLevel || 'medium',
        newAction: row.effectiveAction || row.originalAction || 'manual_review',
        reason: ''
      }
      this.overrideDialogVisible = true
    },
    submitOverride() {
      this.$refs.overrideForm.validate(async valid => {
        if (!valid || !this.selectedRun) return
        this.submittingOverride = true
        try {
          await overrideAgentRagRun(this.selectedRun.id, this.overrideForm)
          this.$message.success('人工复核已追加保存，原始 AI 结果已保留。')
          this.overrideDialogVisible = false
          this.getList()
        } catch (e) {
          this.$message.error('人工复核提交失败，请检查权限或运行状态。')
        } finally {
          this.submittingOverride = false
        }
      })
    },
    async handleReplay(row) {
      try {
        await this.$confirm('Replay 会创建新的运行记录，原记录不会被覆盖。是否继续？', '确认 Replay', { type: 'warning' })
      } catch (e) {
        return
      }
      this.replayingId = row.id
      try {
        const response = await replayAgentRagRun(row.id)
        const replayRun = response.data.data && response.data.data.run
        this.$message.success('Replay 已创建新的运行记录。')
        if (replayRun && replayRun.id) {
          this.$router.push(`/agent-rag/runs/${replayRun.id}?compareTo=${row.id}`)
        } else {
          this.getList()
        }
      } catch (e) {
        this.$message.error('Replay 失败，请确认 AI Runtime 与熔断状态。')
      } finally {
        this.replayingId = null
      }
    }
  }
}
</script>

<style scoped>
.page-header {
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
.quick-filters {
  margin-bottom: 14px;
}
.filter-form .el-input {
  width: 160px;
}
.override-dot {
  display: inline-block;
  margin-left: 4px;
  color: #e6a23c;
  font-size: 12px;
}
</style>
