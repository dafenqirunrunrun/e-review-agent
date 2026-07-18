<template>
  <div class="ai-workbench-page ai-operation-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">运营闭环</p>
        <h1 class="ai-page-title">运营处理中心</h1>
        <p class="ai-page-subtitle">把 AI 发现的风险任务转化为客服回复、售后跟进、转交和关闭等可追踪运营动作。</p>
      </div>
      <div class="ai-toolbar">
        <el-select v-model="query.status" clearable placeholder="处理状态" style="width: 150px;" @change="loadData">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button icon="el-icon-refresh" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <div class="ai-metric-grid operation-summary">
      <div v-for="item in summaryCards" :key="item.label" class="ai-metric-card">
        <div class="ai-metric-label">{{ item.label }}</div>
        <div class="ai-metric-value">{{ item.value }}</div>
        <div class="ai-metric-hint">{{ item.hint }}</div>
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="9">
        <div class="ai-card task-list-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">待处理任务</h2>
              <p class="ai-card-desc">从风险中心同步而来。</p>
            </div>
          </div>
          <div v-if="taskList.length === 0" class="ai-empty-state compact-empty">
            <i class="el-icon-finished" />
            <span>当前没有运营任务</span>
          </div>
          <div v-else class="task-list">
            <div
              v-for="task in taskList"
              :key="task.id"
              :class="['task-item', currentTask && currentTask.id === task.id ? 'active' : '']"
              @click="selectTask(task)"
            >
              <div class="task-item-head">
                <span :class="['ai-status-tag', levelClass(task.riskLevel)]">{{ riskText(task.riskLevel) }}</span>
                <strong>#{{ task.id }}</strong>
              </div>
              <p>{{ task.reviewText }}</p>
              <div class="task-item-foot">
                <span>{{ task.riskType }}</span>
                <span>{{ statusText(task.status) }}</span>
              </div>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="15">
        <div v-if="!currentTask" class="ai-card">
          <div class="ai-empty-state">
            <i class="el-icon-s-operation" />
            <span>请选择左侧任务查看详情</span>
          </div>
        </div>

        <template v-else>
          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">{{ currentTask.productName }}</h2>
                <p class="ai-card-desc">{{ currentTask.reviewText }}</p>
              </div>
              <span :class="['ai-status-tag', statusClass(currentTask.status)]">{{ statusText(currentTask.status) }}</span>
            </div>

            <el-row :gutter="12">
              <el-col :span="8">
                <div class="mini-info"><label>风险类型</label><strong>{{ currentTask.riskType }}</strong></div>
              </el-col>
              <el-col :span="8">
                <div class="mini-info"><label>情感</label><strong>{{ sentimentText(currentTask.sentimentLabel) }}</strong></div>
              </el-col>
              <el-col :span="8">
                <div class="mini-info"><label>置信度</label><strong>{{ percent(currentTask.confidence) }}</strong></div>
              </el-col>
            </el-row>
          </div>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">AI 建议</h2>
                <p class="ai-card-desc">从分析记录中的智能体建议解析展示。</p>
              </div>
            </div>
            <div class="suggestion-grid">
              <div>
                <label>客服回复建议</label>
                <p>{{ suggestion.customer_reply || '-' }}</p>
              </div>
              <div>
                <label>商品页优化建议</label>
                <p>{{ suggestion.operation_advice || '-' }}</p>
              </div>
              <div>
                <label>售后处理建议</label>
                <p>{{ suggestion.after_sales_suggestion || '-' }}</p>
              </div>
            </div>
            <div class="ai-advice-note">AI 建议仅供运营参考，最终处理动作请结合订单、售后记录和人工判断确认。</div>
          </div>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">参考历史案例</h2>
                <p class="ai-card-desc">相似案例用于辅助判断，不能自动替代人工处理决策。</p>
              </div>
            </div>
            <div v-if="referenceCases.length" class="reference-case-list">
              <div v-for="item in referenceCases" :key="item.caseId" class="reference-case-item">
                <div class="reference-case-head">
                  <strong>{{ item.caseTitle || ('案例 #' + item.caseId) }}</strong>
                  <el-tag size="mini" :type="levelTag(item.riskLevel)">{{ riskText(item.riskLevel) }}</el-tag>
                  <span>{{ scoreText(item.matchScore) }}</span>
                </div>
                <p>{{ item.evidence || '暂无证据摘要' }}</p>
                <small>历史处理：{{ item.operationResult || '暂无历史处理方式' }}</small>
              </div>
            </div>
            <div v-else class="ai-empty-state compact-empty">
              <i class="el-icon-collection" />
              <span>暂无参考历史案例，请结合当前证据人工处理。</span>
            </div>
          </div>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">处理动作</h2>
                <p class="ai-card-desc">保存后会同步风险中心状态并写入处理日志。</p>
              </div>
            </div>
            <el-form label-position="top">
              <el-row :gutter="12">
                <el-col :xs="24" :sm="8">
                  <el-form-item label="动作类型">
                    <el-select v-model="handleForm.actionType" style="width: 100%;">
                      <el-option label="标记已查看" value="mark_viewed" />
                      <el-option label="标记已回复" value="mark_replied" />
                      <el-option label="转交售后" value="transfer_after_sales" />
                      <el-option label="关闭任务" value="close_task" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="新状态">
                    <el-select v-model="handleForm.newStatus" style="width: 100%;">
                      <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="8">
                  <el-form-item label="处理人">
                    <el-input v-model="handleForm.operator" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="处理备注">
                <el-input v-model="handleForm.note" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" />
              </el-form-item>
              <el-row :gutter="12">
                <el-col :xs="24" :sm="10">
                  <el-form-item label="智能体反馈类型">
                    <el-select v-model="handleForm.feedbackType" style="width: 100%;">
                      <el-option v-for="item in feedbackOptions" :key="item.value" :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="14">
                  <el-form-item label="反馈备注">
                    <el-input v-model="handleForm.feedbackNote" placeholder="记录人工对智能体结果的复核意见" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-button type="primary" :loading="handling" @click="saveHandle">保存处理结果</el-button>
            </el-form>
          </div>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">处理日志</h2>
                <p class="ai-card-desc">记录每次运营动作和状态变化。</p>
              </div>
            </div>
            <el-timeline v-if="logs.length">
              <el-timeline-item v-for="log in logs" :key="log.id" type="primary" :timestamp="log.createdTime">
                {{ log.operator || 'admin' }}：{{ actionText(log.actionType) }}，{{ statusText(log.oldStatus) }} -> {{ statusText(log.newStatus) }}，{{ log.note || '-' }}
              </el-timeline-item>
            </el-timeline>
            <div v-else class="ai-empty-state compact-empty">
              <i class="el-icon-time" />
              <span>暂无处理日志</span>
            </div>
          </div>
        </template>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { retrieveAiCases } from '@/api/aiCase'
import { handleOperation, listOperationTasks, operationDetail, operationSummary } from '@/api/aiOperation'
import { displayValue, feedbackTypeMap, riskLevelMap, sentimentMap, statusMap } from '@/utils/aiDisplayMap'

export default {
  name: 'AiOperation',
  data() {
    return {
      loading: false,
      handling: false,
      taskList: [],
      currentTask: null,
      currentAnalysis: null,
      referenceCases: [],
      logs: [],
      summary: {},
      query: {
        page: 1,
        limit: 20,
        status: undefined
      },
      statuses: ['pending', 'viewed', 'replied', 'transferred', 'ignored', 'closed'],
      handleForm: {
        riskTaskId: undefined,
        actionType: 'mark_viewed',
        newStatus: 'viewed',
        operator: 'admin',
        note: '',
        feedbackType: 'accept',
        feedbackNote: ''
      }
    }
  },
  computed: {
    summaryCards() {
      const rows = this.summary.status || []
      return [
        { label: '待处理', value: this.findValue(rows, 'pending'), hint: '等待运营跟进' },
        { label: '已回复', value: this.findValue(rows, 'replied'), hint: '客服已回复' },
        { label: '已转售后', value: this.findValue(rows, 'transferred'), hint: '售后团队处理中' },
        { label: '已关闭', value: this.findValue(rows, 'closed'), hint: '处理闭环完成' }
      ]
    },
    suggestion() {
      if (!this.currentAnalysis || !this.currentAnalysis.agentSuggestionJson) {
        return {}
      }
      try {
        return JSON.parse(this.currentAnalysis.agentSuggestionJson)
      } catch (e) {
        return {}
      }
    },
    statusOptions() {
      return this.statuses.map(value => ({ value, label: this.statusText(value) }))
    },
    feedbackOptions() {
      return Object.keys(feedbackTypeMap).map(value => ({ value, label: displayValue(feedbackTypeMap, value) }))
    }
  },
  created() {
    this.loadData()
  },
  methods: {
    loadData() {
      this.loading = true
      Promise.all([listOperationTasks(this.query), operationSummary()]).then(([listRes, summaryRes]) => {
        this.taskList = listRes.data.data.list || []
        this.summary = summaryRes.data.data || {}
        this.loading = false
        const riskTaskId = this.$route.query.riskTaskId
        if (riskTaskId) {
          this.selectTask({ id: Number(riskTaskId) })
        } else if (!this.currentTask && this.taskList.length > 0) {
          this.selectTask(this.taskList[0])
        }
      }).catch(response => {
        this.loading = false
        this.$notify.error({
          title: '运营任务加载失败',
          message: response && response.data ? response.data.errmsg : '请检查后端接口'
        })
      })
    },
    selectTask(task) {
      operationDetail(task.id).then(response => {
        this.currentTask = response.data.data.task
        this.currentAnalysis = response.data.data.analysis
        this.logs = response.data.data.logs || []
        this.handleForm = {
          riskTaskId: task.id,
          actionType: 'mark_viewed',
          newStatus: this.currentTask.status === 'pending' ? 'viewed' : this.currentTask.status,
          operator: 'admin',
          note: '',
          feedbackType: 'accept',
          feedbackNote: ''
        }
        this.loadReferenceCases(this.currentTask)
      })
    },
    loadReferenceCases(task) {
      if (!task) {
        this.referenceCases = []
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
        this.referenceCases = response.data.data || []
      }).catch(() => {
        this.referenceCases = []
      })
    },
    saveHandle() {
      this.handling = true
      handleOperation(this.handleForm).then(() => {
        this.handling = false
        this.$notify.success({
          title: '处理已保存',
          message: '风险中心状态已同步'
        })
        const id = this.handleForm.riskTaskId
        this.currentTask = null
        this.loadData()
        operationDetail(id).then(response => {
          this.currentTask = response.data.data.task
          this.currentAnalysis = response.data.data.analysis
          this.logs = response.data.data.logs || []
          this.loadReferenceCases(this.currentTask)
        })
      }).catch(() => {
        this.handling = false
      })
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
    levelTag(level) {
      if (level === 'high') return 'danger'
      if (level === 'medium') return 'warning'
      return 'info'
    },
    scoreText(value) {
      if (value === undefined || value === null) return '匹配度 -'
      return '匹配度 ' + Math.round(Number(value) * 100) + '%'
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
    riskText(level) {
      return displayValue(riskLevelMap, level)
    },
    statusText(status) {
      return displayValue(statusMap, status)
    },
    sentimentText(label) {
      return displayValue(sentimentMap, label)
    },
    actionText(actionType) {
      const map = {
        mark_viewed: '标记已查看',
        mark_replied: '标记已回复',
        transfer_after_sales: '转交售后',
        close_task: '关闭任务'
      }
      return displayValue(map, actionType)
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-operation-page {
  .operation-summary {
    margin-bottom: 18px;
  }

  .compact-empty {
    min-height: 180px;
  }

  .task-list {
    display: grid;
    gap: 10px;
  }

  .task-item {
    padding: 14px;
    cursor: pointer;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #f8fafc;

    &.active {
      border-color: #2563eb;
      background: #eff6ff;
    }

    p {
      margin: 10px 0;
      color: #374151;
      line-height: 1.6;
    }
  }

  .task-item-head,
  .task-item-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    color: #64748b;
  }

  .mini-info {
    padding: 14px;
    margin-bottom: 12px;
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 8px;

    label {
      display: block;
      margin-bottom: 6px;
      color: #64748b;
    }
  }

  .suggestion-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;

    div {
      padding: 14px;
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
    }

    label {
      display: block;
      margin-bottom: 8px;
      color: #2563eb;
      font-weight: 700;
    }

    p {
      margin: 0;
      color: #374151;
      line-height: 1.7;
    }
  }

  .reference-case-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 10px;
  }

  .reference-case-item {
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

  .reference-case-head {
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
}
</style>
