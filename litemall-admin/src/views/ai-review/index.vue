<template>
  <div class="ai-workbench-page ai-review-workbench">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">E-Review Agent</p>
        <h1 class="ai-page-title">智能图文评论分析工作台</h1>
        <p class="ai-page-subtitle">
          面向电商运营场景，对图文评论进行情感识别、置信度评估、证据提取、相似案例检索和 Agent 处理建议生成。
        </p>
      </div>
      <div class="ai-toolbar">
        <el-button icon="el-icon-refresh" @click="resetForm">重置输入</el-button>
        <el-button type="primary" icon="el-icon-data-analysis" :loading="analyzing" @click="handleAnalyze">
          开始 AI 分析
        </el-button>
      </div>
    </div>

    <div class="ai-metric-grid overview-strip">
      <div class="ai-metric-card">
        <div class="ai-metric-label">当前分析状态</div>
        <div class="ai-metric-value">{{ analyzing ? '分析中' : result ? '已完成' : '待输入' }}</div>
        <div class="ai-metric-hint">FastAPI Agent 服务实时返回</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">最新情感</div>
        <div class="ai-metric-value">{{ result ? sentimentLabel(result.sentiment_label) : '--' }}</div>
        <div class="ai-metric-hint">正向 / 中性 / 负向</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">置信度</div>
        <div class="ai-metric-value">{{ result ? percent(result.confidence) : '--' }}</div>
        <div class="ai-metric-hint">用于低置信度复核</div>
      </div>
      <div class="ai-metric-card">
        <div class="ai-metric-label">风险等级</div>
        <div class="ai-metric-value">{{ result ? riskLabel(result.risk_level) : '--' }}</div>
        <div class="ai-metric-hint">后续进入风险任务中心</div>
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :xs="24" :sm="24" :md="9" :lg="8">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">评论输入</h2>
              <p class="ai-card-desc">支持手工演示输入，后续将从商品评论列表一键带入。</p>
            </div>
          </div>
          <el-form ref="reviewForm" :model="reviewForm" :rules="rules" label-position="top" class="review-form">
            <el-form-item label="商品 ID" prop="productId">
              <el-input-number v-model="reviewForm.productId" :min="1" :step="1" controls-position="right" />
            </el-form-item>
            <el-form-item label="商品名称" prop="productName">
              <el-input v-model="reviewForm.productName" clearable />
            </el-form-item>
            <el-row :gutter="10">
              <el-col :span="12">
                <el-form-item label="商品类目" prop="category">
                  <el-input v-model="reviewForm.category" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="用户评分" prop="rating">
                  <el-rate v-model="reviewForm.rating" :max="5" show-score />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="商品价格" prop="price">
              <el-input-number v-model="reviewForm.price" :min="0" :precision="2" :step="10" controls-position="right" />
            </el-form-item>
            <el-form-item label="评论内容" prop="reviewText">
              <el-input
                v-model="reviewForm.reviewText"
                :autosize="{ minRows: 6, maxRows: 10 }"
                type="textarea"
                placeholder="输入用户真实评论，例如：包装完好，但是用两天后开始发热，希望客服尽快处理。"
              />
            </el-form-item>
            <el-form-item label="图片 URL" prop="imageUrlsText">
              <el-input
                v-model="reviewForm.imageUrlsText"
                :autosize="{ minRows: 2, maxRows: 5 }"
                type="textarea"
                placeholder="多张图片可换行或用英文逗号分隔"
              />
            </el-form-item>
          </el-form>
        </div>

        <div v-if="previewImages.length" class="ai-card image-preview-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">图像预览</h2>
              <p class="ai-card-desc">当前阶段先预览 URL，后续接入图像语义分析。</p>
            </div>
          </div>
          <div class="image-grid">
            <el-image
              v-for="url in previewImages"
              :key="url"
              :src="url"
              :preview-src-list="previewImages"
              fit="cover"
            />
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :sm="24" :md="15" :lg="16">
        <div v-if="!result" class="ai-card">
          <div class="ai-empty-state">
            <i class="el-icon-data-line" />
            <strong>等待评论分析</strong>
            <span>填写左侧评论内容后，点击“开始 AI 分析”生成治理建议。</span>
          </div>
        </div>

        <template v-else>
          <div class="ai-card result-hero-card">
            <div class="result-hero-main">
              <span :class="['ai-status-tag', statusClass(result.sentiment_label)]">{{ sentimentLabel(result.sentiment_label) }}</span>
              <h2>{{ suggestion.summary || 'AI 已完成图文评论综合分析' }}</h2>
              <p>评论 ID：{{ result.review_id || '-' }}，分析 ID：{{ analysisId || '-' }}</p>
            </div>
            <div class="confidence-ring">
              <strong>{{ percent(result.confidence) }}</strong>
              <span>置信度</span>
            </div>
          </div>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">多模态评分</h2>
                <p class="ai-card-desc">文本、图像和融合结果共同决定最终风险等级。</p>
              </div>
              <span :class="['ai-status-tag', riskClass(result.risk_level)]">{{ riskLabel(result.risk_level) }}</span>
            </div>
            <el-row :gutter="14">
              <el-col v-for="item in scoreCards" :key="item.label" :xs="24" :sm="12" :md="8">
                <div class="score-card">
                  <div class="score-card-head">
                    <span>{{ item.label }}</span>
                    <strong>{{ percent(item.value) }}</strong>
                  </div>
                  <el-progress :percentage="progressValue(item.value)" :color="item.color" :show-text="false" />
                </div>
              </el-col>
            </el-row>
          </div>

          <el-row :gutter="18">
            <el-col :span="24">
              <div class="ai-card llm-schema-card">
                <div class="ai-card-header">
                  <div>
                    <h2 class="ai-card-title">结构化输出状态</h2>
                    <p class="ai-card-desc">展示 Provider、Schema 校验与人工复核信号，不替代运营最终判断。</p>
                  </div>
                </div>
                <el-descriptions :column="4" border size="small">
                  <el-descriptions-item label="LLM Provider">{{ result.llm_provider || 'local_rule_fallback' }}</el-descriptions-item>
                  <el-descriptions-item label="Schema">
                    <el-tag :type="result.schema_valid === false ? 'danger' : 'success'" size="mini">
                      {{ result.schema_valid === false ? '校验失败' : '校验通过' }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="修复">{{ result.repair_used ? '已使用' : '未使用' }}</el-descriptions-item>
                  <el-descriptions-item label="Fallback">{{ result.fallback_used ? '已使用' : '未使用' }}</el-descriptions-item>
                  <el-descriptions-item label="置信度">{{ percent(result.confidence) }}</el-descriptions-item>
                  <el-descriptions-item label="人工复核">
                    <el-tag :type="result.need_human_review ? 'warning' : 'success'" size="mini">
                      {{ result.need_human_review ? '需要' : '无需' }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="模型">{{ result.model_name || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="延迟">{{ result.latency_ms == null ? '-' : result.latency_ms + ' ms' }}</el-descriptions-item>
                </el-descriptions>
                <el-alert v-if="result.schema_error" :title="result.schema_error" type="warning" :closable="false" show-icon />
              </div>
            </el-col>
            <el-col :xs="24" :lg="12">
              <div class="ai-card">
                <div class="ai-card-header">
                  <div>
                    <h2 class="ai-card-title">判断证据</h2>
                    <p class="ai-card-desc">用于解释模型判断依据，便于人工复核。</p>
                  </div>
                </div>
                <el-timeline>
                  <el-timeline-item v-for="item in evidenceItems" :key="item" type="primary">
                    {{ item }}
                  </el-timeline-item>
                </el-timeline>
              </div>
            </el-col>
            <el-col :xs="24" :lg="12">
              <div class="ai-card">
                <div class="ai-card-header">
                  <div>
                    <h2 class="ai-card-title">运营建议</h2>
                    <p class="ai-card-desc">面向客服、售后和商品运营的可执行建议。</p>
                  </div>
                </div>
                <div class="suggestion-list">
                  <div>
                    <label>客服回复</label>
                    <p>{{ suggestion.customer_reply || '-' }}</p>
                  </div>
                  <div>
                    <label>运营优化</label>
                    <p>{{ suggestion.operation_advice || '-' }}</p>
                  </div>
                  <div>
                    <label>售后动作</label>
                    <p>{{ suggestion.after_sales_suggestion || '-' }}</p>
                  </div>
                </div>
                <div class="ai-advice-note">AI 生成内容仅供参考，请结合真实订单、商品批次和售后记录进行最终判断。</div>
              </div>
            </el-col>
          </el-row>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">相似案例</h2>
                <p class="ai-card-desc">基于本地案例检索增强返回相似评论，当前不依赖外部向量库。</p>
              </div>
            </div>
            <el-table :data="result.similar_cases || []" border fit size="small">
              <el-table-column prop="case_id" label="案例 ID" width="110" />
              <el-table-column label="标签" width="130">
                <template slot-scope="scope">
                  <span :class="['ai-status-tag', statusClass(scope.row.label || scope.row.sentiment_label)]">
                    {{ sentimentLabel(scope.row.label || scope.row.sentiment_label) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="review_text" label="相似评论" min-width="240" show-overflow-tooltip />
              <el-table-column prop="reason" label="命中原因" min-width="220" show-overflow-tooltip />
            </el-table>
          </div>

          <div class="ai-card">
            <div class="ai-card-header">
              <div>
                <h2 class="ai-card-title">智能体工作流</h2>
                <p class="ai-card-desc">感知、检索、判断、审计、报告五步链路。</p>
              </div>
            </div>
            <el-steps :active="traceActive" finish-status="success" align-center>
              <el-step
                v-for="item in result.workflow_trace"
                :key="item.step || item.node"
                :title="item.agent || item.step || item.node"
                :description="item.output || item.message || item.status"
              />
            </el-steps>
          </div>
        </template>
      </el-col>
    </el-row>

    <div class="ai-card history-card">
      <div class="ai-card-header">
        <div>
          <h2 class="ai-card-title">分析历史</h2>
          <p class="ai-card-desc">当前仍复用第一阶段历史接口，后续拆入独立历史页并增加风险筛选。</p>
        </div>
        <div class="history-toolbar">
          <el-input v-model="historyQuery.productId" clearable class="filter-item" style="width: 160px;" placeholder="商品 ID" />
          <el-select v-model="historyQuery.sentimentLabel" clearable class="filter-item" style="width: 160px;" placeholder="情感标签">
            <el-option label="正向" value="positive" />
            <el-option label="中性" value="neutral" />
            <el-option label="负向" value="negative" />
          </el-select>
          <el-button class="filter-item" type="primary" icon="el-icon-search" @click="handleHistoryFilter">查询</el-button>
        </div>
      </div>

      <el-table v-loading="historyLoading" :data="historyList" border fit highlight-current-row>
        <el-table-column align="center" prop="id" label="分析 ID" width="90" />
        <el-table-column align="center" prop="productId" label="商品 ID" width="110" />
        <el-table-column prop="productName" label="商品名称" min-width="160" />
        <el-table-column prop="reviewText" label="评论内容" min-width="260" show-overflow-tooltip />
        <el-table-column align="center" label="情感" width="130">
          <template slot-scope="scope">
            <span :class="['ai-status-tag', statusClass(scope.row.sentimentLabel)]">{{ sentimentLabel(scope.row.sentimentLabel) }}</span>
          </template>
        </el-table-column>
        <el-table-column align="center" label="置信度" width="130">
          <template slot-scope="scope">
            {{ percent(scope.row.confidence) }}
          </template>
        </el-table-column>
        <el-table-column align="center" prop="addTime" label="分析时间" width="170" />
      </el-table>
    </div>
  </div>
</template>

<script>
import { analyzeReview, listReviewAnalysis } from '@/api/aiReview'

export default {
  name: 'AiReview',
  data() {
    return {
      analyzing: false,
      analysisId: null,
      result: null,
      historyLoading: false,
      historyList: [],
      historyQuery: {
        productId: undefined,
        sentimentLabel: undefined,
        page: 1,
        limit: 10
      },
      reviewForm: {
        productId: 1006002,
        productName: 'E-Review 示例商品',
        category: '数码配件',
        rating: 3,
        price: 99.00,
        reviewText: '物流很快，包装也不错，但是用了两天以后有点发热，希望客服尽快处理。',
        imageUrlsText: ''
      },
      rules: {
        productId: [{ required: true, message: '请输入商品 ID', trigger: 'change' }],
        productName: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
        reviewText: [{ required: true, message: '请输入评论内容', trigger: 'blur' }]
      }
    }
  },
  computed: {
    suggestion() {
      return this.result && this.result.agent_suggestion ? this.result.agent_suggestion : {}
    },
    traceActive() {
      return this.result && this.result.workflow_trace ? this.result.workflow_trace.length : 0
    },
    previewImages() {
      return this.parseImageUrls(this.reviewForm.imageUrlsText)
    },
    evidenceItems() {
      if (!this.result) {
        return []
      }
      return []
        .concat(this.result.evidence || [])
        .concat(this.result.text_evidence || [])
        .concat(this.result.image_evidence || [])
        .filter((item, index, arr) => item && arr.indexOf(item) === index)
    },
    scoreCards() {
      if (!this.result) {
        return []
      }
      return [
        { label: '正向分', value: this.scoreValue('positive'), color: '#16A34A' },
        { label: '中性分', value: this.scoreValue('neutral'), color: '#64748B' },
        { label: '负向分', value: this.scoreValue('negative'), color: '#DC2626' },
        { label: '文本分', value: this.result.text_score, color: '#2563EB' },
        { label: '图像分', value: this.result.image_score, color: '#F59E0B' },
        { label: '冲突分', value: this.result.conflict_score, color: '#DC2626' }
      ]
    }
  },
  created() {
    this.getHistory()
  },
  methods: {
    handleAnalyze() {
      this.$refs.reviewForm.validate(valid => {
        if (!valid) {
          return
        }
        this.analyzing = true
        analyzeReview(this.buildPayload()).then(response => {
          this.analysisId = response.data.data.analysisId
          this.result = response.data.data.result
          this.analyzing = false
          this.getHistory()
          this.$notify.success({
            title: '成功',
            message: 'AI 评价分析完成'
          })
        }).catch(response => {
          this.analyzing = false
          this.$notify.error({
            title: '失败',
            message: response && response.data ? response.data.errmsg : 'AI 评价分析失败'
          })
        })
      })
    },
    buildPayload() {
      return {
        productId: this.reviewForm.productId,
        productName: this.reviewForm.productName,
        category: this.reviewForm.category,
        rating: this.reviewForm.rating,
        price: this.reviewForm.price,
        reviewText: this.reviewForm.reviewText,
        imageUrls: this.parseImageUrls(this.reviewForm.imageUrlsText)
      }
    },
    parseImageUrls(value) {
      if (!value) {
        return []
      }
      return value.split(/\n|,/).map(item => item.trim()).filter(item => item.length > 0)
    },
    resetForm() {
      this.result = null
      this.analysisId = null
      this.$refs.reviewForm.resetFields()
      this.reviewForm.imageUrlsText = ''
    },
    getHistory() {
      this.historyLoading = true
      listReviewAnalysis(this.historyQuery).then(response => {
        this.historyList = response.data.data.list
        this.historyLoading = false
      }).catch(() => {
        this.historyList = []
        this.historyLoading = false
      })
    },
    handleHistoryFilter() {
      this.historyQuery.page = 1
      this.getHistory()
    },
    scoreValue(name) {
      if (!this.result || !this.result.scores || this.result.scores[name] === undefined) {
        return 0
      }
      return this.result.scores[name]
    },
    progressValue(value) {
      if (value === undefined || value === null) {
        return 0
      }
      return Math.max(0, Math.min(100, Math.round(value * 100)))
    },
    percent(value) {
      if (value === undefined || value === null) {
        return '0%'
      }
      return Math.round(Number(value) * 100) + '%'
    },
    statusClass(label) {
      if (label === 'positive') {
        return 'ai-status-positive'
      }
      if (label === 'negative') {
        return 'ai-status-negative'
      }
      return 'ai-status-neutral'
    },
    riskClass(level) {
      if (level === 'high') {
        return 'ai-status-high'
      }
      if (level === 'medium') {
        return 'ai-status-medium'
      }
      return 'ai-status-low'
    },
    sentimentLabel(label) {
      const labels = {
        positive: '正向',
        neutral: '中性',
        negative: '负向'
      }
      return labels[label] || label || '-'
    },
    riskLabel(level) {
      const labels = {
        high: '高风险',
        medium: '中风险',
        low: '低风险'
      }
      return labels[level] || level || '-'
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-review-workbench {
  .overview-strip {
    margin-bottom: 18px;
  }

  .review-form {
    ::v-deep .el-input-number {
      width: 100%;
    }
  }

  .image-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
    gap: 10px;

    ::v-deep .el-image {
      width: 100%;
      height: 96px;
      border-radius: 8px;
      border: 1px solid #e5e7eb;
      overflow: hidden;
      background: #f8fafc;
    }
  }

  .result-hero-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
  }

  .result-hero-main {
    h2 {
      margin: 14px 0 8px;
      color: #111827;
      font-size: 22px;
      line-height: 1.35;
    }

    p {
      margin: 0;
      color: #6b7280;
    }
  }

  .confidence-ring {
    width: 116px;
    height: 116px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    flex: 0 0 116px;
    border-radius: 50%;
    background: #ffffff;
    border: 10px solid #bfdbfe;
    box-shadow: inset 0 0 0 1px #e5e7eb;

    strong {
      color: #2563eb;
      font-size: 26px;
    }

    span {
      margin-top: 4px;
      color: #64748b;
      font-size: 12px;
    }
  }

  .score-card {
    margin-bottom: 12px;
    padding: 14px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #f8fafc;
  }

  .score-card-head {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;
    color: #64748b;

    strong {
      color: #111827;
    }
  }

  .suggestion-list {
    display: grid;
    gap: 12px;

    div {
      padding: 14px;
      background: #f8fafc;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
    }

    label {
      display: block;
      margin-bottom: 6px;
      color: #2563eb;
      font-size: 13px;
      font-weight: 700;
    }

    p {
      margin: 0;
      color: #1f2937;
      line-height: 1.7;
    }
  }

  .history-card {
    margin-top: 2px;
  }

  .history-toolbar {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 8px;
  }

  .llm-schema-card {
    margin-bottom: 18px;

    ::v-deep .el-alert {
      margin-top: 12px;
    }
  }
}

@media (max-width: 768px) {
  .ai-review-workbench {
    .result-hero-card {
      display: block;
    }

    .confidence-ring {
      margin-top: 16px;
    }
  }
}
</style>
