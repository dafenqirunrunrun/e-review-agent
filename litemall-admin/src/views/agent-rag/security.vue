<template>
  <div class="app-container agent-rag-security">
    <div class="page-header">
      <div>
        <h2>Agent-RAG Security Governance</h2>
        <p>Audit integrity, retention preview, controlled evidence expiry and safe export.</p>
      </div>
      <el-button :loading="loading" type="primary" icon="el-icon-refresh" @click="loadAll">Refresh</el-button>
    </div>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      show-icon
      class="section-gap"
    />

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="metric-card">
          <div class="metric-label">Security policy</div>
          <div class="metric-value">{{ security.securityPolicyVersion || '--' }}</div>
          <div class="metric-foot">Current tenant: {{ security.tenantId || retention.tenantId || '--' }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="metric-card">
          <div class="metric-label">Pending expired evidence</div>
          <div class="metric-value">{{ retention.pendingExpiredEvidenceCount || 0 }}</div>
          <div class="metric-foot">Business rows deleted: 0</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="metric-card">
          <div class="metric-label">Audit chain</div>
          <div class="metric-value">
            <el-tag :type="security.auditChainEnabled ? 'success' : 'warning'">
              {{ security.auditChainEnabled ? 'Enabled' : 'Pending data' }}
            </el-tag>
          </div>
          <div class="metric-foot">Latest hash: {{ shortHash(security.latestAuditHash) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="section-gap">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header" class="card-header">
            <span>Retention control</span>
            <el-tag type="info">dry-run first</el-tag>
          </div>
          <el-form :inline="true" size="small">
            <el-form-item label="Batch limit">
              <el-input-number v-model="retentionLimit" :min="1" :max="100" />
            </el-form-item>
            <el-form-item>
              <el-button
                v-permission="['POST /admin/agent-rag/security/retention/preview']"
                :loading="previewing"
                type="primary"
                plain
                @click="previewRetention"
              >Preview</el-button>
              <el-button
                v-permission="['POST /admin/agent-rag/security/retention/execute']"
                :loading="executing"
                type="danger"
                plain
                @click="confirmExecuteRetention"
              >Expire payloads</el-button>
            </el-form-item>
          </el-form>
          <el-alert
            title="Only expired Agent-RAG evidence payloads are replaced by retention markers. Business tables and audit hashes are preserved."
            type="info"
            show-icon
            :closable="false"
          />
          <pre class="bounded-snippet">{{ retentionPreviewText }}</pre>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <div slot="header" class="card-header">
            <span>Safe export</span>
            <el-tag type="success">no raw evidence</el-tag>
          </div>
          <el-form :inline="true" size="small">
            <el-form-item label="Run ID">
              <el-input v-model="exportRunId" placeholder="Agent-RAG run id" style="width: 180px" />
            </el-form-item>
            <el-form-item>
              <el-button
                v-permission="['POST /admin/agent-rag/runs/export']"
                :loading="exporting"
                type="primary"
                @click="exportRun"
              >Export JSON</el-button>
            </el-form-item>
          </el-form>
          <el-alert
            title="The export response contains run metadata, hashes, lineage and sanitized evidence summary only."
            type="success"
            show-icon
            :closable="false"
          />
          <pre class="bounded-snippet">{{ exportText }}</pre>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import {
  getAgentRagSecurityStatus,
  getAgentRagRetentionStatus,
  previewAgentRagRetention,
  executeAgentRagRetention,
  exportAgentRagRun
} from '@/api/agentRag'

export default {
  name: 'AgentRagSecurity',
  data() {
    return {
      loading: false,
      loadError: '',
      security: {},
      retention: {},
      retentionLimit: 50,
      retentionPreview: {},
      exportRunId: '',
      exportedRun: {},
      previewing: false,
      executing: false,
      exporting: false
    }
  },
  computed: {
    retentionPreviewText() {
      const data = Object.keys(this.retentionPreview).length > 0 ? this.retentionPreview : this.retention
      return JSON.stringify(data || {}, null, 2)
    },
    exportText() {
      return Object.keys(this.exportedRun).length > 0 ? JSON.stringify(this.exportedRun, null, 2) : '{}'
    }
  },
  created() {
    this.loadAll()
  },
  methods: {
    shortHash(value) {
      if (!value) return '--'
      const text = String(value)
      return text.length <= 16 ? text : `${text.substring(0, 8)}...${text.substring(text.length - 6)}`
    },
    async loadAll() {
      this.loading = true
      this.loadError = ''
      try {
        const [security, retention] = await Promise.all([
          getAgentRagSecurityStatus(),
          getAgentRagRetentionStatus()
        ])
        this.security = security.data.data || {}
        this.retention = retention.data.data || {}
      } catch (e) {
        this.loadError = 'Security governance data failed to load. Check admin-api permissions and database migration.'
      } finally {
        this.loading = false
      }
    },
    async previewRetention() {
      this.previewing = true
      try {
        const response = await previewAgentRagRetention({ limit: this.retentionLimit })
        this.retentionPreview = response.data.data || {}
        this.$message.success('Retention preview loaded')
      } catch (e) {
        this.$message.error('Retention preview failed')
      } finally {
        this.previewing = false
      }
    },
    confirmExecuteRetention() {
      this.$confirm('Expired evidence payloads will be replaced by retention markers. Business data is not deleted. Continue?', 'Retention execution', {
        confirmButtonText: 'Execute',
        cancelButtonText: 'Cancel',
        type: 'warning'
      }).then(() => this.executeRetention()).catch(() => {})
    },
    async executeRetention() {
      this.executing = true
      try {
        const response = await executeAgentRagRetention({ limit: this.retentionLimit })
        this.retentionPreview = response.data.data || {}
        this.$message.success('Retention batch completed')
        await this.loadAll()
      } catch (e) {
        this.$message.error('Retention execution failed')
      } finally {
        this.executing = false
      }
    },
    async exportRun() {
      if (!this.exportRunId) {
        this.$message.warning('Please enter a run ID')
        return
      }
      this.exporting = true
      try {
        const response = await exportAgentRagRun(this.exportRunId)
        this.exportedRun = response.data.data || {}
        this.$message.success('Safe export loaded')
      } catch (e) {
        this.$message.error('Safe export failed')
      } finally {
        this.exporting = false
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
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
.metric-foot {
  margin-top: 10px;
  font-size: 12px;
}
.bounded-snippet {
  min-height: 280px;
  max-height: 460px;
  margin: 14px 0 0;
  padding: 12px;
  overflow: auto;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
