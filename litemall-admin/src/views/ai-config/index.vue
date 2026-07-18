<template>
  <div class="ai-workbench-page ai-config-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">配置中心</p>
        <h1 class="ai-page-title">智能体配置中心</h1>
        <p class="ai-page-subtitle">
          展示当前 AI 服务、专业 Agent 框架开关和回退策略。本页只读展示，不直接修改运行配置，避免答辩演示时误操作。
        </p>
      </div>
      <div class="ai-toolbar">
        <el-button icon="el-icon-refresh" :loading="loading" @click="loadStatus">刷新状态</el-button>
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="12">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">运行模式</h2>
              <p class="ai-card-desc">默认保持 legacy_rule_agent，专业框架可通过环境变量启用。</p>
            </div>
            <span :class="['ai-status-tag', status.available === false ? 'ai-status-negative' : 'ai-status-positive']">
              {{ modeText(status.currentMode || status.current_mode || 'legacy_rule_agent') }}
            </span>
          </div>
          <div class="config-grid">
            <div>
              <label>FastAPI 服务</label>
              <strong>http://127.0.0.1:8008</strong>
            </div>
            <div>
              <label>Java 框架开关</label>
              <strong>{{ yesNo(status.javaConfigEnabled) }}</strong>
            </div>
            <div>
              <label>回退策略</label>
              <strong>{{ yesNo(status.fallbackEnabled || status.fallback_enabled || status.javaFallbackToLegacy) }}</strong>
            </div>
            <div>
              <label>外部模型密钥</label>
              <strong>{{ yesNo(status.openaiApiKeyAvailable || status.openai_api_key_available) }}</strong>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :lg="12">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">专业框架能力</h2>
              <p class="ai-card-desc">当前以 LangGraph 为主框架，OpenAI Agents SDK 保留扩展位置。</p>
            </div>
          </div>
          <div class="config-grid">
            <div>
              <label>LangGraph 包</label>
              <strong>{{ yesNo(status.langgraphAvailable || status.langgraph_available) }}</strong>
            </div>
            <div>
              <label>OpenAI Agents SDK</label>
              <strong>{{ yesNo(status.openaiAgentsAvailable || status.openai_agents_available) }}</strong>
            </div>
            <div>
              <label>图文冲突检测</label>
              <strong>已接入</strong>
            </div>
            <div>
              <label>主模态判定</label>
              <strong>已接入</strong>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="ai-card">
      <div class="ai-card-header">
        <div>
          <h2 class="ai-card-title">Agentic RAG 状态</h2>
          <p class="ai-card-desc">展示轻量案例库、检索模式和向量库扩展状态。当前默认不强依赖 Qdrant。</p>
        </div>
        <span :class="['ai-status-tag', caseStats.ragEnabled ? 'ai-status-positive' : 'ai-status-neutral']">
          {{ caseStats.ragEnabled ? '检索增强已启用' : '检索增强待命' }}
        </span>
      </div>
      <div class="config-grid">
        <div>
          <label>检索模式</label>
          <strong>{{ modeText(caseStats.retrievalMode || 'local_keyword') }}</strong>
        </div>
        <div>
          <label>案例数量</label>
          <strong>{{ caseStats.caseCount || 0 }}</strong>
        </div>
        <div>
          <label>向量嵌入可用</label>
          <strong>{{ yesNo(caseStats.embeddingAvailable) }}</strong>
        </div>
        <div>
          <label>向量库提供方</label>
          <strong>{{ providerText(caseStats.vectorStoreProvider) }}</strong>
        </div>
        <div>
          <label>回退机制</label>
          <strong>{{ yesNo(caseStats.fallbackEnabled) }}</strong>
        </div>
      </div>
    </div>

    <div class="ai-card">
      <div class="ai-card-header">
        <div>
          <h2 class="ai-card-title">启用说明</h2>
          <p class="ai-card-desc">答辩演示建议保持默认关闭，展示专业框架时可临时启用 FastAPI 环境变量。</p>
        </div>
      </div>
      <el-alert
        title="AI 生成内容仅供运营辅助参考，最终处理动作仍需人工确认。"
        type="warning"
        :closable="false"
        show-icon
      />
      <pre class="config-code">AGENT_FRAMEWORK_ENABLED=true
AGENT_FRAMEWORK_FALLBACK_ENABLED=true
AGENT_FRAMEWORK_REQUIRE_API_KEY=false</pre>
      <p v-if="status.lastError || status.last_error" class="config-error">
        {{ status.lastError || status.last_error }}
      </p>
    </div>
  </div>
</template>

<script>
import { aiCaseStats } from '@/api/aiCase'
import { agentFrameworkStatus } from '@/api/aiAgent'
import { yesNoText } from '@/utils/aiDisplayMap'

export default {
  name: 'AiConfig',
  data() {
    return {
      loading: false,
      status: {},
      caseStats: {}
    }
  },
  created() {
    this.loadStatus()
  },
  methods: {
    loadStatus() {
      this.loading = true
      Promise.all([agentFrameworkStatus(), aiCaseStats()]).then(([statusRes, caseStatsRes]) => {
        this.status = statusRes.data.data || {}
        this.caseStats = caseStatsRes.data.data || {}
      }).catch(() => {
        this.status = {
          available: false,
          currentMode: 'unavailable'
        }
        this.caseStats = {}
      }).finally(() => {
        this.loading = false
      })
    },
    yesNo(value) {
      return yesNoText(value)
    },
    modeText(value) {
      const map = {
        legacy_rule_agent: '本地规则智能体',
        langgraph: 'LangGraph 工作流',
        local_keyword: '本地关键词检索',
        unavailable: '不可用'
      }
      return map[value] || value || '-'
    },
    providerText(value) {
      if (!value || value === 'none') {
        return '未接入外部向量库'
      }
      return value
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-config-page {
  .config-grid {
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
      color: #64748b;
      font-size: 12px;
    }

    strong {
      color: #111827;
      font-size: 15px;
    }
  }

  .config-code {
    margin: 16px 0 0;
    padding: 14px;
    overflow-x: auto;
    color: #e5e7eb;
    background: #111827;
    border-radius: 8px;
    line-height: 1.7;
  }

  .config-error {
    margin: 12px 0 0;
    color: #dc2626;
  }
}
</style>
