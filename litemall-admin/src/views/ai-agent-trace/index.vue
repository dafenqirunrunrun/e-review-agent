<template>
  <div class="ai-workbench-page ai-agent-trace-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">智能体执行追踪（Agent Trace）</p>
        <h1 class="ai-page-title">智能体执行追踪中心</h1>
        <p class="ai-page-subtitle">
          追踪每一次评论治理运行，展示重放、状态快照、角色步骤、输入输出摘要和失败原因，便于答辩演示和问题复盘。
        </p>
      </div>
      <div class="ai-toolbar">
        <el-select v-model="query.status" clearable placeholder="运行状态" style="width: 140px;" @change="reloadRuns">
          <el-option v-for="item in statuses" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="query.sourceType" clearable placeholder="来源类型" style="width: 170px;" @change="reloadRuns">
          <el-option v-for="item in sourceTypes" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="query.triggerType" clearable placeholder="触发方式" style="width: 180px;" @change="reloadRuns">
          <el-option v-for="item in triggerTypes" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button icon="el-icon-refresh" :loading="loading" @click="loadRuns">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="12">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">智能体运行记录</h2>
              <p class="ai-card-desc">每次巡检、手动分析、顾客评价触发或重放都会形成可审计的运行记录。</p>
            </div>
          </div>
          <el-table
            v-loading="loading"
            :data="runs"
            border
            fit
            highlight-current-row
            empty-text="暂无智能体运行记录，请先执行巡检或评论分析。"
            @row-click="selectRun"
          >
            <el-table-column prop="runNo" label="运行编号" min-width="170" show-overflow-tooltip />
            <el-table-column prop="sourceType" label="来源" width="145" show-overflow-tooltip>
              <template slot-scope="scope">{{ sourceText(scope.row.sourceType) }}</template>
            </el-table-column>
            <el-table-column prop="sourceId" label="来源ID" width="95" />
            <el-table-column prop="triggerType" label="触发方式" width="150" show-overflow-tooltip>
              <template slot-scope="scope">{{ triggerText(scope.row.triggerType) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template slot-scope="scope">
                <el-tag :type="statusTagType(scope.row.status)" size="mini">{{ statusText(scope.row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="durationMs" label="耗时(ms)" width="115" />
            <el-table-column prop="startTime" label="开始时间" width="170" show-overflow-tooltip />
            <el-table-column prop="finalResult" label="最终结果" min-width="180" show-overflow-tooltip />
          </el-table>
          <pagination
            v-show="total > 0"
            :total="total"
            :page.sync="query.page"
            :limit.sync="query.limit"
            @pagination="loadRuns"
          />
        </div>
      </el-col>

      <el-col :xs="24" :lg="12">
        <div v-if="!currentRun" class="ai-card">
          <div class="ai-empty-state">
            <i class="el-icon-share" />
            <span>请选择一条运行记录，查看智能体状态和执行步骤。</span>
          </div>
        </div>

        <template v-else>
          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">{{ currentRun.runNo || '智能体运行' }}</h2>
                <p class="ai-card-desc">{{ currentRun.inputSummary || '暂无输入摘要。' }}</p>
              </div>
              <div class="run-actions">
                <el-tag v-if="currentRun.isReplay" type="warning">重放运行</el-tag>
                <el-tag v-else type="success">原始运行</el-tag>
                <el-tag :type="statusTagType(currentRun.status)">{{ statusText(currentRun.status) }}</el-tag>
                <el-button size="mini" icon="el-icon-document" @click="openSource">查看来源评论</el-button>
                <el-button size="mini" icon="el-icon-warning-outline" @click="openRiskCenter">查看风险任务</el-button>
                <el-button size="mini" type="primary" icon="el-icon-refresh-right" :loading="replayLoading" @click="openReplayPreview">重放运行</el-button>
              </div>
            </div>
            <el-row :gutter="12">
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>来源</label><strong>{{ sourceText(currentRun.sourceType) }} #{{ currentRun.sourceId || '-' }}</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>触发方式</label><strong>{{ triggerText(currentRun.triggerType) }}</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>运行耗时</label><strong>{{ currentRun.durationMs || 0 }} ms</strong></div>
              </el-col>
            </el-row>
            <el-row v-if="currentRun.ragEnabled" :gutter="12">
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>检索策略</label><strong>{{ currentRun.ragStrategy || '-' }}</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>命中 / Top 分数</label><strong>{{ currentRun.retrievalHitCount || 0 }} / {{ currentRun.retrievalTopScore || 0 }}</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>检索耗时</label><strong>{{ currentRun.retrievalLatencyMs || 0 }} ms</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>Embedding</label><strong>{{ currentRun.embeddingProvider || '-' }}</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>重排器</label><strong>{{ currentRun.rerankerProvider || '-' }}</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>路由结果</label><strong>{{ currentRun.routeDecision || '-' }}</strong></div>
              </el-col>
            </el-row>
            <el-row :gutter="12">
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>框架模式</label><strong>{{ currentRun.frameworkMode || '-' }}</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>回退机制</label><strong>{{ fallbackText(currentRun.fallbackUsed) }}</strong></div>
              </el-col>
              <el-col :xs="24" :sm="8">
                <div class="mini-info"><label>步骤统计</label><strong>{{ currentRun.stepCount || steps.length || 0 }} / 失败 {{ currentRun.failedStepCount || 0 }}</strong></div>
              </el-col>
            </el-row>
            <div class="final-result">
              <label>最终结果</label>
              <span>{{ currentRun.finalResult || '暂无最终结果。' }}</span>
            </div>
            <div v-if="currentRun.hasHumanFeedback" class="human-feedback-note">
              本次运行已有人工运营反馈，并已回写到评估中心。
            </div>
            <div v-if="replayCompares.length" class="replay-compare-panel">
              <label>重放历史</label>
              <div v-for="item in replayCompares" :key="item.id" class="replay-compare-item">
                <strong>原始 #{{ item.originalRunId }} -> 重放 #{{ item.replayRunId }}</strong>
                <span>情感变化：{{ yesNo(item.sentimentChanged) }}</span>
                <span>风险变化：{{ yesNo(item.riskChanged) }}</span>
                <span>置信度差异：{{ item.confidenceDelta || 0 }}</span>
              </div>
            </div>
            <div v-if="runCompare" class="replay-compare-panel">
              <label>当前重放对比</label>
              <div class="replay-compare-item">
                <strong>#{{ runCompare.leftRun && runCompare.leftRun.id }} vs #{{ runCompare.rightRun && runCompare.rightRun.id }}</strong>
                <span>情感变化：{{ yesNo(runCompare.sentimentChanged) }}</span>
                <span>置信度差异：{{ runCompare.confidenceDelta || 0 }}</span>
                <span>回退变化：{{ yesNo(runCompare.fallbackChanged) }}</span>
                <span>相似案例变化：{{ yesNo(runCompare.similarCasesChanged) }}</span>
              </div>
            </div>
          </div>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">智能体状态快照</h2>
                <p class="ai-card-desc">展示可重放的运行状态、角色摘要、分析证据和失败上下文。</p>
              </div>
            </div>
            <div v-if="runState && runState.stepsByRole && runState.stepsByRole.length" class="role-grid">
              <div v-for="role in runState.stepsByRole" :key="role.agentRole">
                <label class="agent-role-link" @click="openAgentRegistry(role.agentRole)">{{ agentRoleText(role.agentRole) }}</label>
                <strong>{{ role.stepCount || 0 }} 个步骤</strong>
                <span>失败 {{ role.failedStepCount || 0 }}，平均 {{ role.avgDurationMs || 0 }} ms</span>
              </div>
            </div>
            <el-collapse v-if="runState">
              <el-collapse-item title="状态快照原始数据">
                <section class="json-block">
                  <pre>{{ formatJson(runState.snapshot || {}) }}</pre>
                </section>
              </el-collapse-item>
              <el-collapse-item title="分析证据">
                <section class="json-block">
                  <pre>{{ formatJson(runState.analysis || {}) }}</pre>
                </section>
              </el-collapse-item>
            </el-collapse>
            <div v-else class="ai-empty-state compact-empty">
              <i class="el-icon-data-analysis" />
              <span>本次运行暂无状态快照。</span>
            </div>
          </div>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">执行步骤时间线</h2>
                <p class="ai-card-desc">展示步骤顺序、智能体角色、工具调用、状态、耗时、输入输出和错误摘要。</p>
              </div>
            </div>
            <el-timeline v-if="steps.length">
              <el-timeline-item
                v-for="step in steps"
                :key="step.id"
                :type="timelineType(step.status)"
                :timestamp="step.createdTime || step.startTime || '-'"
              >
                <div class="step-title">
                  <strong>{{ step.stepOrder || '-' }}. {{ step.stepName || '未命名步骤' }}</strong>
                  <el-tag size="mini" effect="plain">{{ step.toolName || '未调用工具' }}</el-tag>
                  <el-tag class="agent-role-link" size="mini" type="info" effect="plain" @click.native.stop="openAgentRegistry(step.agentRole)">{{ agentRoleText(step.agentRole) }}</el-tag>
                  <el-tag :type="statusTagType(step.status)" size="mini">{{ statusText(step.status) }}</el-tag>
                  <em>{{ step.durationMs || 0 }} ms</em>
                </div>
                <p v-if="step.agentGoal" class="step-goal">{{ step.agentGoal }}</p>
                <el-collapse>
                  <el-collapse-item title="输入 / 输出 / 错误">
                    <section class="json-block">
                      <label>输入数据</label>
                      <pre>{{ formatJson(step.inputJson) }}</pre>
                    </section>
                    <section class="json-block">
                      <label>输出数据</label>
                      <pre>{{ formatJson(step.outputJson) }}</pre>
                    </section>
                    <section v-if="step.errorMessage" class="json-block error-block">
                      <label>错误摘要</label>
                      <pre>{{ step.errorMessage }}</pre>
                    </section>
                  </el-collapse-item>
                </el-collapse>
              </el-timeline-item>
            </el-timeline>
            <div v-else class="ai-empty-state compact-empty">
              <i class="el-icon-document" />
              <span>本次运行暂无步骤记录。</span>
            </div>
          </div>
        </template>
      </el-col>
    </el-row>

    <el-dialog title="智能体运行重放预览" :visible.sync="replayDialogVisible" width="640px">
      <div v-if="replayPreview">
        <el-alert
          :title="replayPreview.canReplay ? '本次运行可以重放。' : '本次运行暂时不能重放。'"
          :type="replayPreview.canReplay ? 'success' : 'warning'"
          :closable="false"
          show-icon
        />
        <div class="replay-preview-block">
          <label>输入摘要</label>
          <p>{{ replayPreview.inputSummary || '-' }}</p>
          <label>历史结果</label>
          <p>{{ replayPreview.finalResult || '-' }}</p>
          <label>原因</label>
          <p>{{ replayPreview.reason || '-' }}</p>
        </div>
      </div>
      <span slot="footer" class="dialog-footer">
        <el-button @click="replayDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!replayPreview || !replayPreview.canReplay" :loading="replayLoading" @click="executeReplay">确认重放</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import Pagination from '@/components/Pagination'
import { agentRunCompare, agentRunDetail, agentRunReplay, agentRunReplayCompare, agentRunReplayPreview, agentRunState, agentRunSteps, listAgentRuns } from '@/api/aiAgent'
import { agentRoleMap, displayValue, fallbackMap, sourceTypeMap, statusMap, triggerTypeMap, yesNoText } from '@/utils/aiDisplayMap'

export default {
  name: 'AiAgentTrace',
  components: { Pagination },
  data() {
    return {
      loading: false,
      runs: [],
      steps: [],
      total: 0,
      currentRun: null,
      runState: null,
      runCompare: null,
      replayDialogVisible: false,
      replayLoading: false,
      replayPreview: null,
      replayCompares: [],
      statuses: [
        { label: '成功', value: 'success' },
        { label: '失败', value: 'failed' },
        { label: '运行中', value: 'running' },
        { label: '部分成功', value: 'partial_success' }
      ],
      sourceTypes: [
        { label: '后台演示评论', value: 'demo_review' },
        { label: '用户端真实评价', value: 'litemall_comment' },
        { label: '手工输入', value: 'manual_input' }
      ],
      triggerTypes: [
        { label: '手动巡检', value: 'manual_run_once' },
        { label: '定时巡检', value: 'scheduled_patrol' },
        { label: '手动分析', value: 'manual_analysis' },
        { label: '顾客评价触发', value: 'customer_comment' },
        { label: '重放运行', value: 'replay' }
      ],
      query: {
        page: 1,
        limit: 10,
        status: undefined,
        sourceType: undefined,
        triggerType: undefined
      }
    }
  },
  created() {
    this.loadRuns()
  },
  methods: {
    reloadRuns() {
      this.query.page = 1
      this.currentRun = null
      this.steps = []
      this.runState = null
      this.runCompare = null
      this.loadRuns()
    },
    loadRuns() {
      this.loading = true
      listAgentRuns(this.query).then(response => {
        const data = response.data.data || {}
        this.runs = data.list || []
        this.total = data.total || 0
        if (!this.currentRun && this.runs.length) {
          this.selectRun(this.runs[0])
        }
      }).catch(() => {
        this.runs = []
        this.total = 0
      }).finally(() => {
        this.loading = false
      })
    },
    selectRun(row) {
      if (!row || !row.id) return
      this.runState = null
      this.runCompare = null
      agentRunDetail(row.id).then(response => {
        this.currentRun = response.data.data || row
      }).catch(() => {
        this.currentRun = row
      })
      agentRunSteps(row.id).then(response => {
        this.steps = response.data.data || []
      }).catch(() => {
        this.steps = []
      })
      agentRunState(row.id).then(response => {
        this.runState = response.data.data || null
      }).catch(() => {
        this.runState = null
      })
      this.loadReplayCompare(row.id)
    },
    loadReplayCompare(runId) {
      agentRunReplayCompare(runId).then(response => {
        const data = response.data.data || {}
        this.replayCompares = data.list || []
      }).catch(() => {
        this.replayCompares = []
      })
    },
    openReplayPreview() {
      if (!this.currentRun || !this.currentRun.id) return
      this.replayLoading = true
      agentRunReplayPreview(this.currentRun.id).then(response => {
        this.replayPreview = response.data.data || {}
        this.replayDialogVisible = true
      }).finally(() => {
        this.replayLoading = false
      })
    },
    executeReplay() {
      if (!this.currentRun || !this.currentRun.id) return
      const originalRunId = this.currentRun.id
      this.replayLoading = true
      agentRunReplay(originalRunId).then(response => {
        const data = response.data.data || {}
        if (data.success) {
          this.$message.success('已生成重放运行 #' + data.replayRunId)
          this.replayDialogVisible = false
          agentRunCompare({ leftRunId: originalRunId, rightRunId: data.replayRunId }).then(compareResponse => {
            this.runCompare = compareResponse.data.data || null
          }).catch(() => {
            this.runCompare = data.compare || null
          })
          this.loadRuns()
          this.loadReplayCompare(originalRunId)
        } else {
          this.$message.warning(data.reason || '重放未执行')
        }
      }).finally(() => {
        this.replayLoading = false
      })
    },
    openSource() {
      if (!this.currentRun) return
      if (this.currentRun.sourceType === 'litemall_comment') {
        this.$router.push({ path: '/goods/comment', query: { sourceId: this.currentRun.sourceId }})
      } else if (this.currentRun.sourceType === 'demo_review') {
        this.$router.push({ path: '/ai-demo-review/create' })
      } else {
        this.$router.push({ path: '/ai-workbench/review' })
      }
    },
    openRiskCenter() {
      if (!this.currentRun) return
      this.$router.push({ path: '/ai-workbench/risk', query: { sourceType: this.currentRun.sourceType, sourceId: this.currentRun.sourceId }})
    },
    openAgentRegistry(agentRole) {
      this.$router.push({ path: '/ai-workbench/agent-registry', query: { agentRole: agentRole || '' }})
    },
    statusText(value) {
      return displayValue(statusMap, value, '未知')
    },
    sourceText(value) {
      return displayValue(sourceTypeMap, value, '-')
    },
    triggerText(value) {
      return displayValue(triggerTypeMap, value, '-')
    },
    agentRoleText(value) {
      return displayValue(agentRoleMap, value, value || '未知智能体')
    },
    fallbackText(value) {
      return displayValue(fallbackMap, String(Boolean(value)))
    },
    yesNo(value) {
      return yesNoText(value)
    },
    statusTagType(status) {
      if (status === 'success') return 'success'
      if (status === 'failed') return 'danger'
      if (status === 'running') return 'primary'
      if (status === 'partial_success') return 'warning'
      return 'info'
    },
    timelineType(status) {
      if (status === 'failed') return 'danger'
      if (status === 'success') return 'success'
      if (status === 'partial_success') return 'warning'
      return 'primary'
    },
    formatJson(value) {
      if (!value) return '-'
      if (typeof value === 'object') {
        return JSON.stringify(value, null, 2)
      }
      try {
        return JSON.stringify(JSON.parse(value), null, 2)
      } catch (e) {
        return String(value)
      }
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-agent-trace-page {
  .compact-empty {
    min-height: 180px;
  }

  .mini-info,
  .final-result {
    padding: 14px;
    margin-bottom: 12px;
    background: #f8fafc;
    border: 1px solid #e5e7eb;
    border-radius: 8px;

    label {
      display: block;
      margin-bottom: 6px;
      color: #64748b;
      font-size: 12px;
    }
  }

  .run-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .human-feedback-note,
  .replay-compare-panel {
    margin-top: 12px;
    padding: 12px;
    background: #f8fafc;
    border: 1px solid #dbeafe;
    border-radius: 8px;
  }

  .human-feedback-note {
    color: #047857;
    border-color: #a7f3d0;
    background: #ecfdf5;
  }

  .replay-compare-panel label {
    display: block;
    margin-bottom: 8px;
    color: #2563eb;
    font-weight: 700;
  }

  .replay-compare-item {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    color: #475569;
    font-size: 12px;
  }

  .role-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
    margin-bottom: 12px;

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
      margin: 5px 0;
      color: #111827;
      font-size: 18px;
    }
  }

  .agent-role-link {
    color: #2563eb;
    cursor: pointer;
    font-weight: 700;
  }

  .agent-role-link:hover {
    text-decoration: underline;
  }

  .replay-preview-block {
    margin-top: 14px;

    label {
      display: block;
      margin: 12px 0 6px;
      color: #64748b;
      font-size: 12px;
      font-weight: 700;
    }

    p {
      margin: 0;
      padding: 10px;
      color: #374151;
      background: #f8fafc;
      border-radius: 6px;
      line-height: 1.6;
    }
  }

  .step-title {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;

    em {
      color: #64748b;
      font-style: normal;
    }
  }

  .step-goal {
    margin: 8px 0;
    color: #475569;
    line-height: 1.5;
  }

  .json-block {
    margin-bottom: 12px;

    label {
      display: block;
      margin-bottom: 6px;
      color: #64748b;
      font-size: 12px;
      font-weight: 600;
    }
  }

  pre {
    max-height: 240px;
    overflow: auto;
    padding: 10px;
    margin: 0;
    background: #0f172a;
    color: #dbeafe;
    border-radius: 6px;
    white-space: pre-wrap;
  }

  .error-block pre {
    background: #450a0a;
    color: #fecaca;
  }
}
</style>
