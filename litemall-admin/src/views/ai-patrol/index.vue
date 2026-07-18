<template>
  <div class="ai-workbench-page ai-patrol-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">智能体巡检</p>
        <h1 class="ai-page-title">智能体巡检中心</h1>
        <p class="ai-page-subtitle">
          自动扫描待分析演示评论，调用 FastAPI AI 服务生成分析结果，并记录巡检批次日志。
        </p>
      </div>
      <div class="ai-toolbar">
        <el-button icon="el-icon-refresh" :loading="loading" @click="loadStatus">刷新</el-button>
        <el-button type="success" icon="el-icon-video-play" :loading="actionLoading" @click="handleEnable">启用巡检</el-button>
        <el-button type="warning" icon="el-icon-video-pause" :loading="actionLoading" @click="handleDisable">暂停巡检</el-button>
        <el-button type="primary" icon="el-icon-cpu" :loading="runLoading" @click="handleRunOnce">立即巡检</el-button>
      </div>
    </div>

    <div class="ai-metric-grid status-strip">
      <div class="ai-metric-card">
        <div class="ai-metric-label">智能体状态</div>
        <div class="ai-metric-value">{{ status.running ? '运行中' : '待命' }}</div>
        <div class="ai-metric-hint">
          <span :class="['ai-status-tag', status.enabled ? 'ai-status-positive' : 'ai-status-negative']">
            {{ status.enabled ? '自动巡检已启用' : '自动巡检已暂停' }}
          </span>
        </div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">巡检频率</div>
        <div class="ai-metric-value">{{ delayText }}</div>
        <div class="ai-metric-hint">application-admin.yml 配置</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">单批数量</div>
        <div class="ai-metric-value">{{ status.batchSize || 0 }}</div>
        <div class="ai-metric-hint">每次最多处理评论数</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">待分析评论</div>
        <div class="ai-metric-value">{{ status.pendingCount || 0 }}</div>
        <div class="ai-metric-hint">等待智能体巡检分析</div>
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="9">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">智能体工作流</h2>
              <p class="ai-card-desc">巡检任务当前处理演示评论池，后续阶段将联动风险任务。</p>
            </div>
          </div>
          <el-steps direction="vertical" :active="4" finish-status="success">
            <el-step title="扫描待分析评论" description="读取待分析评论池中的记录" />
            <el-step title="锁定分析状态" description="更新为 analyzing，避免重复处理" />
            <el-step title="调用 AI 服务" description="复用 AiReviewService 调 FastAPI" />
            <el-step title="结果落库" description="写入 litemall_review_ai_analysis" />
            <el-step title="记录巡检日志" description="写入 litemall_ai_patrol_log" />
          </el-steps>
        </div>
      </el-col>

      <el-col :xs="24" :lg="15">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">最近巡检日志</h2>
              <p class="ai-card-desc">用于确认自动巡检是否执行、成功数量和失败数量。</p>
            </div>
          </div>
          <el-table v-loading="loading" :data="logs" border fit highlight-current-row>
            <el-table-column prop="taskBatchNo" label="批次号" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="100" align="center">
              <template slot-scope="scope">
                <span :class="['ai-status-tag', logStatusClass(scope.row.status)]">{{ logStatusText(scope.row.status) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="scanCount" label="扫描" width="80" align="center" />
            <el-table-column prop="successCount" label="成功" width="80" align="center" />
            <el-table-column prop="failedCount" label="失败" width="80" align="center" />
            <el-table-column prop="highRiskCount" label="高风险" width="90" align="center" />
            <el-table-column prop="startTime" label="开始时间" width="170" align="center" />
            <el-table-column prop="endTime" label="结束时间" width="170" align="center" />
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { disablePatrol, enablePatrol, patrolStatus, runPatrolOnce } from '@/api/aiPatrol'
import { displayValue, statusMap } from '@/utils/aiDisplayMap'

export default {
  name: 'AiPatrol',
  data() {
    return {
      loading: false,
      actionLoading: false,
      runLoading: false,
      status: {},
      logs: []
    }
  },
  computed: {
    delayText() {
      const delay = Number(this.status.fixedDelay || 0)
      return delay ? Math.round(delay / 1000) + 's' : '--'
    }
  },
  created() {
    this.loadStatus()
  },
  methods: {
    loadStatus() {
      this.loading = true
      patrolStatus().then(response => {
        this.status = response.data.data || {}
        this.logs = this.status.logs || []
        this.loading = false
      }).catch(response => {
        this.loading = false
        this.$notify.error({
          title: '巡检状态加载失败',
          message: response && response.data ? response.data.errmsg : '请检查后端接口'
        })
      })
    },
    handleEnable() {
      this.actionLoading = true
      enablePatrol().then(response => {
        this.status = response.data.data || {}
        this.logs = this.status.logs || []
        this.actionLoading = false
      }).catch(() => {
        this.actionLoading = false
      })
    },
    handleDisable() {
      this.actionLoading = true
      disablePatrol().then(response => {
        this.status = response.data.data || {}
        this.logs = this.status.logs || []
        this.actionLoading = false
      }).catch(() => {
        this.actionLoading = false
      })
    },
    handleRunOnce() {
      this.runLoading = true
      runPatrolOnce().then(response => {
        this.runLoading = false
        this.$notify.success({
          title: '巡检完成',
          message: '扫描 ' + response.data.data.scanCount + ' 条，成功 ' + response.data.data.successCount + ' 条'
        })
        this.loadStatus()
      }).catch(response => {
        this.runLoading = false
        this.$notify.error({
          title: '巡检失败',
          message: response && response.data ? response.data.errmsg : '请检查 AI 服务'
        })
      })
    },
    logStatusClass(status) {
      if (status === 'success') {
        return 'ai-status-positive'
      }
      if (status === 'failed') {
        return 'ai-status-negative'
      }
      return 'ai-status-low'
    },
    logStatusText(status) {
      return displayValue(statusMap, status)
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-patrol-page {
  .status-strip {
    margin-bottom: 18px;
  }
}
</style>
