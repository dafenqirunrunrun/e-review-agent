<template>
  <div class="app-container agent-rag-runtime">
    <div class="page-header">
      <div>
        <h2>Agent-RAG 运行观测</h2>
        <p>只读查看 AI Runtime、Provider、Index、熔断器与本地运行指标。</p>
      </div>
      <div class="toolbar">
        <el-select v-model="refreshInterval" size="small" style="width: 128px" @change="resetTimer">
          <el-option label="暂停刷新" :value="0" />
          <el-option label="15 秒刷新" :value="15000" />
          <el-option label="30 秒刷新" :value="30000" />
          <el-option label="60 秒刷新" :value="60000" />
        </el-select>
        <el-button :loading="loading" type="primary" icon="el-icon-refresh" @click="loadRuntime">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon class="section-gap" />

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-label">整体状态</div>
          <div class="metric-value">
            <el-tag :type="overallTag">{{ overallStatus }}</el-tag>
          </div>
          <div class="metric-foot">最后刷新：{{ lastUpdated || '--' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-label">请求总量</div>
          <div class="metric-value">{{ metrics.requestsTotal || 0 }}</div>
          <div class="metric-foot">成功 {{ metrics.successTotal || 0 }} / 失败 {{ metrics.failureTotal || 0 }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-label">P95 延迟</div>
          <div class="metric-value">{{ latency.p95Ms || 0 }} ms</div>
          <div class="metric-foot">样本 {{ latency.count || 0 }} 次</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="6">
        <el-card shadow="never" class="metric-card">
          <div class="metric-label">降级次数</div>
          <div class="metric-value">{{ metrics.fallbackTotal || 0 }}</div>
          <div class="metric-foot">幂等命中 {{ metrics.idempotencyHitTotal || 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="runtime-card">
          <div slot="header" class="card-header">
            <span>AI Runtime</span>
            <el-tag :type="runtime.status === 'ready' ? 'success' : 'warning'">{{ runtime.status || '--' }}</el-tag>
          </div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="Target Mode">{{ runtime.targetMode || '--' }}</el-descriptions-item>
            <el-descriptions-item label="Retrieval Mode">{{ formatRetrievalMode(runtime.defaultRetrievalMode || runtime.effectiveRetrievalMode) }}</el-descriptions-item>
            <el-descriptions-item label="Fallback">{{ runtime.fallbackUsed ? '已发生' : '未发生' }}</el-descriptions-item>
            <el-descriptions-item label="Reason">{{ formatFallbackReason(runtime.fallbackReason || runtime.reason) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="runtime-card">
          <div slot="header">Provider</div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="请求 Provider">{{ formatProvider(runtime.requestedProviderImpl || runtime.requestedProvider) }}</el-descriptions-item>
            <el-descriptions-item label="实际 Provider">
              <el-tag :type="getProviderTagType(runtime.effectiveProviderImpl)" size="mini">{{ formatProvider(runtime.effectiveProviderImpl) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="实现合规">{{ runtime.providerConformance || '--' }}</el-descriptions-item>
            <el-descriptions-item label="设备">{{ runtime.device || '--' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="runtime-card">
          <div slot="header">Index</div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="Active Version">{{ runtime.activeIndexVersion || runtime.indexVersion || '--' }}</el-descriptions-item>
            <el-descriptions-item label="Loaded">{{ runtime.indexLoaded ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="Compatible">{{ runtime.indexCompatible === false ? '否' : '是' }}</el-descriptions-item>
            <el-descriptions-item label="Dimension">{{ runtime.embeddingDimension || '--' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="section-gap">
      <div slot="header" class="card-header">
        <span>GPU Residency</span>
        <el-tag :type="residency.activeRequests > 0 ? 'warning' : 'success'" size="mini">
          {{ residency.residentModel || 'idle' }}
        </el-tag>
      </div>
      <el-row :gutter="16">
        <el-col :xs="24" :md="6">
          <div class="mini-metric">
            <span>Active / Queue</span>
            <strong>{{ residency.activeRequests || 0 }} / {{ residency.queueDepth || 0 }}</strong>
          </div>
        </el-col>
        <el-col :xs="24" :md="6">
          <div class="mini-metric">
            <span>Model Switches</span>
            <strong>{{ residency.modelSwitchCount || 0 }}</strong>
          </div>
        </el-col>
        <el-col :xs="24" :md="6">
          <div class="mini-metric">
            <span>CUDA Alloc / Reserved</span>
            <strong>{{ residency.cudaAllocatedMb || 0 }} / {{ residency.cudaReservedMb || 0 }} MB</strong>
          </div>
        </el-col>
        <el-col :xs="24" :md="6">
          <div class="mini-metric">
            <span>CUDA Free / Peak</span>
            <strong>{{ residency.cudaFreeMb || 0 }} / {{ residency.cudaPeakMb || 0 }} MB</strong>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header" class="card-header">
            <span>Circuit Breaker</span>
            <el-tag :type="circuitTag">{{ circuit.state || '--' }}</el-tag>
          </div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="State">{{ circuit.state || '--' }}</el-descriptions-item>
            <el-descriptions-item label="Failure Count">{{ circuit.failureCount || 0 }}</el-descriptions-item>
            <el-descriptions-item label="Opened At">{{ formatTimestamp(circuit.openedAt) }}</el-descriptions-item>
            <el-descriptions-item label="Next Probe At">{{ formatTimestamp(circuit.nextProbeAt) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header">运行摘要</div>
          <pre class="bounded-snippet">{{ rawSummary }}</pre>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { getAgentRagRuntimeHealth, getAgentRagRuntimeMetrics } from '@/api/agentRag'
import { formatProvider, formatRetrievalMode, formatFallbackReason, formatTimestamp, getProviderTagType } from '@/utils/agent-rag'

export default {
  name: 'AgentRagRuntime',
  data() {
    return {
      loading: false,
      loadError: '',
      refreshInterval: 0,
      timer: null,
      lastUpdated: '',
      runtime: {},
      circuit: {},
      metrics: {}
    }
  },
  computed: {
    latency() {
      return this.metrics.latency || {}
    },
    residency() {
      return this.runtime.residency || this.runtime.modelResidency || {}
    },
    providerDegraded() {
      return this.runtime.requestedProviderImpl && this.runtime.effectiveProviderImpl && this.runtime.requestedProviderImpl !== this.runtime.effectiveProviderImpl
    },
    overallStatus() {
      if (this.runtime.status === 'ready' && this.runtime.indexCompatible !== false && this.circuit.state !== 'OPEN' && !this.providerDegraded) return 'Ready'
      if (this.runtime.status || this.circuit.state) return 'Degraded'
      return 'Not Ready'
    },
    overallTag() {
      if (this.overallStatus === 'Ready') return 'success'
      if (this.overallStatus === 'Degraded') return 'warning'
      return 'danger'
    },
    circuitTag() {
      if (this.circuit.state === 'CLOSED') return 'success'
      if (this.circuit.state === 'HALF_OPEN') return 'warning'
      if (this.circuit.state === 'OPEN') return 'danger'
      return 'info'
    },
    rawSummary() {
      return JSON.stringify({
        runtimeStatus: this.runtime.status,
        targetMode: this.runtime.targetMode,
        requestedProviderImpl: this.runtime.requestedProviderImpl,
        effectiveProviderImpl: this.runtime.effectiveProviderImpl,
        activeIndexVersion: this.runtime.activeIndexVersion || this.runtime.indexVersion,
        indexCompatible: this.runtime.indexCompatible,
        circuitState: this.circuit.state,
        requestsTotal: this.metrics.requestsTotal || 0,
        p95LatencyMs: this.latency.p95Ms || 0
      }, null, 2)
    }
  },
  created() {
    this.loadRuntime()
    document.addEventListener('visibilitychange', this.handleVisibility)
  },
  beforeDestroy() {
    this.clearTimer()
    document.removeEventListener('visibilitychange', this.handleVisibility)
  },
  methods: {
    formatProvider,
    formatRetrievalMode,
    formatFallbackReason,
    formatTimestamp,
    getProviderTagType,
    async loadRuntime() {
      this.loading = true
      this.loadError = ''
      try {
        const [healthResponse, metricsResponse] = await Promise.all([
          getAgentRagRuntimeHealth(),
          getAgentRagRuntimeMetrics()
        ])
        const health = healthResponse.data.data || {}
        this.runtime = health.runtime || {}
        this.circuit = health.circuitBreaker || {}
        this.metrics = metricsResponse.data.data || health.metrics || {}
        this.lastUpdated = formatTimestamp(new Date().toISOString())
      } catch (e) {
        this.loadError = '运行观测加载失败，请确认 AI Runtime 与 admin-api 可访问。'
      } finally {
        this.loading = false
      }
    },
    resetTimer() {
      this.clearTimer()
      if (this.refreshInterval > 0 && !document.hidden) {
        this.timer = window.setInterval(() => this.loadRuntime(), this.refreshInterval)
      }
    },
    handleVisibility() {
      if (document.hidden) {
        this.clearTimer()
      } else {
        this.resetTimer()
      }
    },
    clearTimer() {
      if (this.timer) {
        window.clearInterval(this.timer)
        this.timer = null
      }
    }
  }
}
</script>

<style scoped>
.page-header,
.card-header,
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toolbar {
  gap: 8px;
}
.page-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
}
.page-header p,
.metric-foot {
  margin: 0;
  color: #909399;
}
.section-gap {
  margin-top: 16px;
}
.metric-card {
  min-height: 128px;
}
.metric-label {
  color: #606266;
  font-size: 13px;
}
.metric-value {
  margin-top: 12px;
  font-size: 26px;
  font-weight: 600;
  color: #303133;
}
.metric-foot {
  margin-top: 10px;
  font-size: 12px;
}
.runtime-card {
  min-height: 270px;
}
.mini-metric {
  min-height: 72px;
  padding: 10px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background: #fafafa;
}
.mini-metric span,
.mini-metric strong {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mini-metric span {
  color: #909399;
  font-size: 12px;
}
.mini-metric strong {
  margin-top: 8px;
  color: #303133;
  font-size: 18px;
}
.bounded-snippet {
  min-height: 206px;
  margin: 0;
  padding: 12px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
