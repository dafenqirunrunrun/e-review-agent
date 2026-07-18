<template>
  <div class="ai-workbench-page ai-case-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">案例检索增强</p>
        <h1 class="ai-page-title">案例知识库</h1>
        <p class="ai-page-subtitle">
          沉淀历史风险评论、AI 分析结果、运营处理和人工反馈，为 Agent 提供相似案例召回和证据参考。AI 生成内容仅供运营辅助参考，最终处理动作仍需人工确认。
        </p>
      </div>
      <div class="ai-toolbar">
        <el-input
          v-model="query.keyword"
          clearable
          placeholder="搜索评论、商品、标签"
          style="width: 220px;"
          @keyup.enter.native="reload"
        />
        <el-select v-model="query.riskLevel" clearable placeholder="风险等级" style="width: 130px;" @change="reload">
          <el-option v-for="item in riskLevelOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="query.sentimentLabel" clearable placeholder="情感" style="width: 130px;" @change="reload">
          <el-option v-for="item in sentimentOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button icon="el-icon-search" :loading="loading" @click="reload">查询</el-button>
        <el-button type="primary" icon="el-icon-magic-stick" :loading="building" @click="buildFromHistory">从历史任务构建</el-button>
      </div>
    </div>

    <div class="ai-metric-grid">
      <div class="ai-metric-card">
        <div class="ai-metric-label">案例总数</div>
        <div class="ai-metric-value">{{ stats.caseCount || 0 }}</div>
        <div class="ai-metric-hint">来自历史风险任务与运营处理记录</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">检索模式</div>
        <div class="ai-metric-value compact-value">{{ retrievalModeText(stats.retrievalMode || 'local_keyword') }}</div>
        <div class="ai-metric-hint">轻量关键词、风险、情感、商品综合检索</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">平均检索耗时</div>
        <div class="ai-metric-value">{{ retrieval.avgDurationMs || 0 }}ms</div>
        <div class="ai-metric-hint">最近本地案例召回日志统计</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">向量库状态</div>
        <div class="ai-metric-value compact-value">{{ vectorProviderText(stats.vectorStoreProvider || 'none') }}</div>
        <div class="ai-metric-hint">当前使用本地检索，保留扩展能力</div>
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="15">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">案例列表</h2>
              <p class="ai-card-desc">展示可被智能体检索召回的历史处理案例。</p>
            </div>
            <el-button icon="el-icon-refresh" :loading="loading" @click="loadCases">刷新</el-button>
          </div>

          <el-table
            v-loading="loading"
            :data="cases"
            border
            fit
            highlight-current-row
            empty-text="暂无案例，可点击“从历史任务构建”生成案例知识库。"
            @row-click="selectCase"
          >
            <el-table-column prop="caseTitle" label="案例" min-width="160" show-overflow-tooltip />
            <el-table-column prop="productName" label="商品" min-width="150" show-overflow-tooltip />
            <el-table-column prop="sentimentLabel" label="情感" width="105">
              <template slot-scope="scope">
                <el-tag :type="sentimentTag(scope.row.sentimentLabel)" size="mini">{{ sentimentText(scope.row.sentimentLabel) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="riskLevel" label="风险等级" width="105">
              <template slot-scope="scope">
                <span :class="['ai-status-tag', 'ai-status-' + (scope.row.riskLevel || 'neutral')]">{{ riskText(scope.row.riskLevel) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="riskTypes" label="风险类型" min-width="160" show-overflow-tooltip />
            <el-table-column prop="feedbackType" label="反馈" width="120" show-overflow-tooltip>
              <template slot-scope="scope">{{ feedbackText(scope.row.feedbackType) }}</template>
            </el-table-column>
            <el-table-column prop="updatedTime" label="更新时间" width="165" show-overflow-tooltip />
          </el-table>

          <pagination
            v-show="total > 0"
            :total="total"
            :page.sync="query.page"
            :limit.sync="query.limit"
            @pagination="loadCases"
          />
        </div>
      </el-col>

      <el-col :xs="24" :lg="9">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">案例详情</h2>
              <p class="ai-card-desc">用于说明 AI 建议参考了哪些历史证据和处理方式。</p>
            </div>
          </div>
          <div v-if="!currentCase" class="ai-empty-state compact-empty">
            <i class="el-icon-collection" />
            <span>请选择一条案例查看详情。</span>
          </div>
          <div v-else class="case-detail">
            <h3>{{ currentCase.caseTitle }}</h3>
            <p class="case-meta">{{ sourceText(currentCase.sourceType) }} #{{ currentCase.sourceId || '-' }}</p>
            <section>
              <label>评论内容</label>
              <p>{{ currentCase.commentText || '-' }}</p>
            </section>
            <section>
              <label>证据摘要</label>
              <p>{{ currentCase.evidence || '-' }}</p>
            </section>
            <section>
              <label>历史处理方式</label>
              <p>{{ currentCase.operationResult || '暂无处理记录，建议人工结合当前上下文判断。' }}</p>
            </section>
            <section>
              <label>标签</label>
              <p>{{ currentCase.tags || '-' }}</p>
            </section>
          </div>
        </div>

        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">检索日志</h2>
              <p class="ai-card-desc">记录智能体最近的相似案例召回情况。</p>
            </div>
          </div>
          <el-table :data="logs" size="mini" border empty-text="暂无检索日志。">
            <el-table-column prop="retrievalMode" label="模式" width="120">
              <template slot-scope="scope">{{ retrievalModeText(scope.row.retrievalMode) }}</template>
            </el-table-column>
            <el-table-column prop="retrievedCaseIds" label="召回案例" min-width="120" show-overflow-tooltip />
            <el-table-column prop="durationMs" label="耗时" width="80" />
          </el-table>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import Pagination from '@/components/Pagination'
import { aiCaseDetail, aiCaseRetrievalLogs, aiCaseStats, buildAiCasesFromHistory, listAiCases } from '@/api/aiCase'
import { displayValue, feedbackTypeMap, riskLevelMap, sentimentMap, sourceTypeMap } from '@/utils/aiDisplayMap'

export default {
  name: 'AiCaseKnowledge',
  components: { Pagination },
  data() {
    return {
      loading: false,
      building: false,
      cases: [],
      logs: [],
      total: 0,
      stats: {},
      currentCase: null,
      query: {
        page: 1,
        limit: 10,
        keyword: undefined,
        riskLevel: undefined,
        sentimentLabel: undefined
      }
    }
  },
  computed: {
    retrieval() {
      return this.stats.retrieval || {}
    },
    riskLevelOptions() {
      return ['high', 'medium', 'low'].map(value => ({ value, label: this.riskText(value) }))
    },
    sentimentOptions() {
      return ['positive', 'neutral', 'negative'].map(value => ({ value, label: this.sentimentText(value) }))
    }
  },
  created() {
    this.loadAll()
  },
  methods: {
    loadAll() {
      this.loadStats()
      this.loadLogs()
      this.loadCases()
    },
    reload() {
      this.query.page = 1
      this.loadCases()
    },
    loadCases() {
      this.loading = true
      listAiCases(this.query).then(response => {
        const data = response.data.data || {}
        this.cases = data.list || []
        this.total = data.total || 0
        if (!this.currentCase && this.cases.length) {
          this.selectCase(this.cases[0])
        }
      }).catch(() => {
        this.cases = []
        this.total = 0
      }).finally(() => {
        this.loading = false
      })
    },
    loadStats() {
      aiCaseStats().then(response => {
        this.stats = response.data.data || {}
      }).catch(() => {
        this.stats = {}
      })
    },
    loadLogs() {
      aiCaseRetrievalLogs().then(response => {
        const data = response.data.data || {}
        this.logs = data.list || data || []
      }).catch(() => {
        this.logs = []
      })
    },
    selectCase(row) {
      if (!row || !row.id) return
      aiCaseDetail(row.id).then(response => {
        this.currentCase = response.data.data || row
      }).catch(() => {
        this.currentCase = row
      })
    },
    buildFromHistory() {
      this.building = true
      buildAiCasesFromHistory().then(response => {
        const count = response.data.data || 0
        this.$message.success('已从历史任务构建 ' + count + ' 条案例')
        this.currentCase = null
        this.loadAll()
      }).catch(() => {
        this.$message.error('构建案例失败，请检查后端接口和数据库表。')
      }).finally(() => {
        this.building = false
      })
    },
    sentimentTag(label) {
      if (label === 'positive') return 'success'
      if (label === 'negative') return 'danger'
      return 'info'
    },
    sentimentText(label) {
      return displayValue(sentimentMap, label)
    },
    riskText(level) {
      return displayValue(riskLevelMap, level)
    },
    feedbackText(type) {
      return displayValue(feedbackTypeMap, type)
    },
    sourceText(type) {
      return displayValue(sourceTypeMap, type)
    },
    retrievalModeText(mode) {
      const map = {
        local_keyword: '本地关键词检索',
        vector_rag: '向量检索增强'
      }
      return displayValue(map, mode)
    },
    vectorProviderText(provider) {
      const map = {
        none: '未启用外部向量库',
        local: '本地检索',
        qdrant: '可扩展向量库'
      }
      return displayValue(map, provider)
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-case-page {
  .compact-value {
    font-size: 18px;
  }

  .compact-empty {
    min-height: 220px;
  }

  .case-detail {
    h3 {
      margin: 0;
      color: #111827;
      font-size: 18px;
    }

    .case-meta {
      margin: 6px 0 14px;
      color: #64748b;
      font-size: 12px;
    }

    section {
      margin-bottom: 14px;
      padding-bottom: 12px;
      border-bottom: 1px solid #eef2f7;

      label {
        display: block;
        margin-bottom: 6px;
        color: #2563eb;
        font-size: 12px;
        font-weight: 700;
      }

      p {
        margin: 0;
        color: #374151;
        font-size: 13px;
        line-height: 1.7;
        word-break: break-word;
      }
    }
  }
}
</style>
