<template>
  <div class="app-container goods-comment-page">
    <div class="filter-container">
      <el-input v-model="listQuery.userId" clearable class="filter-item" style="width: 200px;" :placeholder="$t('goods_comment.placeholder.filter_user_id')" />
      <el-input v-model="listQuery.valueId" clearable class="filter-item" style="width: 200px;" :placeholder="$t('goods_comment.placeholder.filter_value_id')" />
      <el-button class="filter-item" type="primary" icon="el-icon-search" @click="handleFilter">{{ $t('app.button.search') }}</el-button>
      <el-button :loading="downloadLoading" class="filter-item" type="primary" icon="el-icon-download" @click="handleDownload">{{ $t('app.button.download') }}</el-button>
      <el-button :loading="batchAiLoading" :disabled="selectedComments.length === 0" class="filter-item" type="warning" icon="el-icon-cpu" @click="handleBatchAiAnalyze">
        批量 AI 分析
      </el-button>
    </div>

    <el-table
      v-loading="listLoading"
      :data="list"
      :element-loading-text="$t('app.message.list_loading')"
      border
      fit
      highlight-current-row
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="45" align="center" />
      <el-table-column align="center" :label="$t('goods_comment.table.user_id')" prop="userId" />
      <el-table-column align="center" :label="$t('goods_comment.table.value_id')" prop="valueId" />
      <el-table-column align="center" :label="$t('goods_comment.table.star')" prop="star" />
      <el-table-column align="center" :label="$t('goods_comment.table.content')" prop="content" />
      <el-table-column align="center" :label="$t('goods_comment.table.pic_urls')" prop="picUrls">
        <template slot-scope="scope">
          <el-image v-for="item in normalizePicUrls(scope.row.picUrls)" :key="item" :src="item" :preview-src-list="normalizePicUrls(scope.row.picUrls)" :lazy="true" style="width: 40px; height: 40px; margin-right: 5px;" />
        </template>
      </el-table-column>
      <el-table-column align="center" :label="$t('goods_comment.table.add_time')" prop="addTime" />
      <el-table-column align="center" label="AI 状态" width="120">
        <template slot-scope="scope">
          <el-tag v-if="aiResultMap[scope.row.id]" :type="sentimentType(aiResultMap[scope.row.id].sentiment_label)" size="mini">
            {{ sentimentLabel(aiResultMap[scope.row.id].sentiment_label) }}
          </el-tag>
          <el-tag v-else type="info" size="mini">未分析</el-tag>
        </template>
      </el-table-column>
      <el-table-column align="center" :label="$t('goods_comment.table.actions')" width="320" class-name="small-padding fixed-width">
        <template slot-scope="scope">
          <el-button :loading="aiLoadingMap[scope.row.id]" type="warning" size="mini" @click="handleAiAnalyze(scope.row)">AI分析</el-button>
          <el-button type="success" size="mini" @click="handleViewAi(scope.row)">查看结果</el-button>
          <el-button type="primary" size="mini" @click="handleReply(scope.row)">{{ $t('app.button.reply') }}</el-button>
          <el-button type="danger" size="mini" @click="handleDelete(scope.row)">{{ $t('app.button.delete') }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total>0" :total="total" :page.sync="listQuery.page" :limit.sync="listQuery.limit" @pagination="getList" />

    <el-dialog :visible.sync="replyFormVisible" :title="$t('goods_comment.dialog.reply')">
      <el-form ref="replyForm" :model="replyForm" status-icon label-position="left" label-width="100px" style="width: 400px; margin-left:50px;">
        <el-form-item :label="$t('goods_comment.form.content')" prop="content">
          <el-input v-model="replyForm.content" :autosize="{ minRows: 4, maxRows: 8}" type="textarea" />
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <el-button @click="replyFormVisible = false">{{ $t('app.button.cancel') }}</el-button>
        <el-button type="primary" @click="reply">{{ $t('app.button.confirm') }}</el-button>
      </div>
    </el-dialog>

    <el-dialog :visible.sync="aiDialogVisible" title="评论审核详情" width="960px">
      <div v-if="currentAiResult" class="comment-ai-result">
        <section v-if="governanceScenario" class="governance-detail">
          <div class="governance-head">
            <div>
              <el-tag :type="governanceTagType(governanceScenario.status)" effect="dark">
                {{ governanceScenario.statusText }}
              </el-tag>
              <h3>{{ governanceScenario.decision }}</h3>
              <p>{{ governanceScenario.reason }}</p>
            </div>
            <div :class="['evidence-state', governanceScenario.evidenceStatus]">
              <strong>{{ governanceScenario.evidenceStatusText }}</strong>
              <span>{{ governanceScenario.requiresHumanReview ? '需要人工复核' : '可按建议处理' }}</span>
            </div>
          </div>

          <el-descriptions :column="3" border size="small" class="governance-status">
            <el-descriptions-item label="命中风险">{{ signalValue('命中风险') }}</el-descriptions-item>
            <el-descriptions-item label="处理优先级">{{ signalValue('处理优先级') }}</el-descriptions-item>
            <el-descriptions-item label="引用依据">{{ signalValue('引用依据') }}</el-descriptions-item>
            <el-descriptions-item label="Reflection">{{ governanceScenario.evidenceStatusText }}</el-descriptions-item>
            <el-descriptions-item label="人工复核">{{ governanceScenario.requiresHumanReview ? '需要' : '无需' }}</el-descriptions-item>
            <el-descriptions-item label="来源">{{ governanceScenario.source === 'api' ? '真实接口' : '本地示例' }}</el-descriptions-item>
          </el-descriptions>

          <el-alert
            class="reflection-note"
            :title="governanceScenario.reflectionReason || governanceScenario.actionHint"
            :type="governanceScenario.requiresHumanReview ? 'warning' : 'success'"
            :closable="false"
            show-icon
          />
          <el-alert
            v-if="governanceScenario.history"
            class="reflection-note"
            :title="governanceScenario.history.message"
            :type="governanceScenario.history.type"
            :closable="false"
            show-icon
          />
          <div v-if="governanceScenario.riskCoverage.length" class="risk-coverage-list">
            <h4>风险支持状态</h4>
            <div v-for="item in governanceScenario.riskCoverage" :key="item.riskType" class="risk-coverage-item">
              <div>
                <strong>{{ item.label }}</strong>
                <p>{{ item.description }}</p>
              </div>
              <el-tag :type="item.status === 'supported' ? 'success' : 'warning'" size="mini">{{ item.statusText }}</el-tag>
            </div>
          </div>

          <div v-if="governanceScenario.showPolicyEvidence" class="policy-evidence-section">
            <div class="policy-section-title">
              <h4>政策依据</h4>
              <span>{{ governanceScenario.evidence.length }} 条</span>
            </div>
            <el-collapse v-if="governanceScenario.evidence.length" accordion>
              <el-collapse-item v-for="item in governanceScenario.evidence" :key="item.id" :name="item.id">
                <template slot="title">
                  <span class="evidence-title">{{ item.id }} · {{ item.title }}</span>
                </template>
                <div class="evidence-card">
                  <div class="evidence-meta">
                    <el-tag size="mini" type="success">{{ item.sourceType }}</el-tag>
                    <el-tag size="mini" type="info">{{ item.path }}</el-tag>
                  </div>
                  <p>{{ item.snippet }}</p>
                  <small>命中风险：{{ item.riskTypes }}</small>
                  <small>{{ item.supports }}</small>
                  <el-button v-if="item.sourceUrl" size="mini" type="text" icon="el-icon-link" @click="openEvidenceSource(item.sourceUrl)">
                    查看原始政策
                  </el-button>
                  <el-collapse v-if="item.technicalDetails.length" class="technical-collapse">
                    <el-collapse-item title="技术详情" :name="item.id + '-tech'">
                      <div v-for="detail in item.technicalDetails" :key="detail" class="technical-line">{{ detail }}</div>
                    </el-collapse-item>
                  </el-collapse>
                </div>
              </el-collapse-item>
            </el-collapse>
            <div v-else class="policy-empty">
              当前没有可验证政策依据。若系统判定为证据不足或不匹配，请进入人工复核。
            </div>
          </div>
        </section>

        <div class="ai-result-head">
          <el-tag :type="sentimentType(currentAiResult.sentiment_label)" effect="dark">
            {{ sentimentLabel(currentAiResult.sentiment_label) }}
          </el-tag>
          <strong>置信度 {{ percent(currentAiResult.confidence) }}</strong>
          <span>风险等级：{{ riskLabel(currentAiResult.risk_level) }}</span>
        </div>
        <el-row :gutter="12" class="ai-score-row">
          <el-col :span="8">
            <div class="ai-score-box">
              <label>正向分</label>
              <strong>{{ percent(scoreValue(currentAiResult, 'positive')) }}</strong>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="ai-score-box">
              <label>中性分</label>
              <strong>{{ percent(scoreValue(currentAiResult, 'neutral')) }}</strong>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="ai-score-box">
              <label>负向分</label>
              <strong>{{ percent(scoreValue(currentAiResult, 'negative')) }}</strong>
            </div>
          </el-col>
        </el-row>
        <el-alert :title="suggestionSummary" type="info" :closable="false" show-icon />
        <el-alert
          v-if="currentAiResult.need_human_review || (governanceScenario && governanceScenario.requiresHumanReview)"
          class="comment-ai-note"
          title="AI 分析结果仅供运营参考，请结合订单、图片和售后记录进行最终判断。"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-collapse class="comment-technical-status">
          <el-collapse-item title="技术详情" name="technical-status">
            <el-descriptions :column="3" border size="small" class="comment-llm-status">
              <el-descriptions-item label="Provider">{{ currentAiResult.llm_provider || 'local_rule_fallback' }}</el-descriptions-item>
              <el-descriptions-item label="Schema">{{ currentAiResult.schema_valid === false ? '失败' : '通过' }}</el-descriptions-item>
              <el-descriptions-item label="人工复核">{{ currentAiResult.need_human_review ? '需要' : '无需' }}</el-descriptions-item>
              <el-descriptions-item label="Repair">{{ currentAiResult.repair_used ? '是' : '否' }}</el-descriptions-item>
              <el-descriptions-item label="Fallback">{{ currentAiResult.fallback_used ? '是' : '否' }}</el-descriptions-item>
              <el-descriptions-item label="模型">{{ currentAiResult.model_name || '-' }}</el-descriptions-item>
            </el-descriptions>
          </el-collapse-item>
        </el-collapse>
        <h4>基础判断证据</h4>
        <el-timeline>
          <el-timeline-item v-for="item in currentEvidence" :key="item" type="primary">
            {{ item }}
          </el-timeline-item>
        </el-timeline>
      </div>
      <div v-else class="comment-ai-empty">
        暂无 AI 分析结果，请先点击“AI分析”。
      </div>
      <div slot="footer" class="dialog-footer">
        <el-button @click="aiDialogVisible = false">关闭</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { listComment, deleteComment } from '@/api/comment'
import { replyComment } from '@/api/order'
import { analyzeReview } from '@/api/aiReview'
import { normalizeReviewGovernance } from '@/utils/reviewGovernanceAdapter'
import Pagination from '@/components/Pagination'

export default {
  name: 'Comment',
  components: { Pagination },
  data() {
    return {
      list: [],
      total: 0,
      listLoading: true,
      listQuery: {
        page: 1,
        limit: 20,
        userId: undefined,
        valueId: undefined,
        sort: 'add_time',
        order: 'desc'
      },
      downloadLoading: false,
      batchAiLoading: false,
      selectedComments: [],
      aiLoadingMap: {},
      aiResultMap: {},
      governanceMap: {},
      aiDialogVisible: false,
      currentAiResult: null,
      currentGovernanceScenario: null,
      replyForm: {
        commentId: 0,
        content: ''
      },
      replyFormVisible: false
    }
  },
  computed: {
    currentEvidence() {
      if (!this.currentAiResult) {
        return []
      }
      return []
        .concat(this.currentAiResult.evidence || [])
        .concat(this.currentAiResult.text_evidence || [])
        .concat(this.currentAiResult.image_evidence || [])
        .filter((item, index, arr) => item && arr.indexOf(item) === index)
    },
    suggestionSummary() {
      const suggestion = this.currentAiResult && this.currentAiResult.agent_suggestion ? this.currentAiResult.agent_suggestion : {}
      return suggestion.summary || suggestion.operation_advice || 'AI 已生成评论处理建议'
    },
    governanceScenario() {
      return this.currentGovernanceScenario
    }
  },
  created() {
    this.getList()
  },
  methods: {
    getList() {
      this.listLoading = true
      listComment(this.listQuery).then(response => {
        this.list = response.data.data.list
        this.total = response.data.data.total
        this.listLoading = false
      }).catch(() => {
        this.list = []
        this.total = 0
        this.listLoading = false
      })
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleSelectionChange(selection) {
      this.selectedComments = selection
    },
    handleReply(row) {
      this.replyForm = { commentId: row.id, content: '' }
      this.replyFormVisible = true
    },
    reply() {
      replyComment(this.replyForm).then(() => {
        this.replyFormVisible = false
        this.$notify.success({
          title: '成功',
          message: '回复成功'
        })
      }).catch(response => {
        this.$notify.error({
          title: '失败',
          message: response.data.errmsg
        })
      })
    },
    handleDelete(row) {
      deleteComment(row).then(() => {
        this.$notify({
          title: '成功',
          message: '删除成功',
          type: 'success',
          duration: 2000
        })
        this.getList()
      })
    },
    handleAiAnalyze(row) {
      this.loadAiGovernance(row, true)
    },
    loadAiGovernance(row, notifyDone) {
      if (this.aiResultMap[row.id]) {
        this.currentAiResult = this.aiResultMap[row.id]
        this.currentGovernanceScenario = this.governanceMap[row.id] || this.normalizeGovernance(this.currentAiResult, row)
        this.aiDialogVisible = true
        return
      }
      this.$set(this.aiLoadingMap, row.id, true)
      analyzeReview(this.buildAiPayload(row)).then(response => {
        const result = response.data.data.result
        this.$set(this.aiResultMap, row.id, result)
        this.$set(this.governanceMap, row.id, this.normalizeGovernance(result, row))
        this.currentAiResult = result
        this.currentGovernanceScenario = this.governanceMap[row.id]
        this.aiDialogVisible = true
        this.$set(this.aiLoadingMap, row.id, false)
        if (notifyDone) {
          this.$notify.success({
            title: 'AI 分析完成',
            message: '评论已生成风险判断、政策依据和复核建议'
          })
        }
      }).catch(response => {
        this.$set(this.aiLoadingMap, row.id, false)
        this.currentAiResult = this.offlineAiResult(row)
        this.currentGovernanceScenario = this.normalizeGovernance(this.currentAiResult, row)
        this.aiDialogVisible = true
        this.$notify.error({
          title: 'AI 服务暂时不可用',
          message: this.safeErrorMessage(response, '可继续人工审核，AI 分析恢复后再补充政策依据。')
        })
      })
    },
    handleBatchAiAnalyze() {
      if (this.selectedComments.length === 0) {
        return
      }
      this.batchAiLoading = true
      const tasks = this.selectedComments.map(row => {
        this.$set(this.aiLoadingMap, row.id, true)
        return analyzeReview(this.buildAiPayload(row)).then(response => {
          this.$set(this.aiResultMap, row.id, response.data.data.result)
          this.$set(this.governanceMap, row.id, this.normalizeGovernance(response.data.data.result, row))
          this.$set(this.aiLoadingMap, row.id, false)
          return true
        }).catch(() => {
          this.$set(this.aiLoadingMap, row.id, false)
          return false
        })
      })
      Promise.all(tasks).then(results => {
        const successCount = results.filter(Boolean).length
        this.batchAiLoading = false
        this.$notify.success({
          title: '批量 AI 分析完成',
          message: '成功分析 ' + successCount + ' 条评论'
        })
      })
    },
    handleViewAi(row) {
      this.loadAiGovernance(row, false)
    },
    buildAiPayload(row) {
      const ratingSource = row.ratingSource === 'USER_PROVIDED' ? 'USER_PROVIDED' : 'UNKNOWN'
      return {
        reviewId: 'comment-' + row.id,
        productId: row.valueId,
        productName: '商品 ' + row.valueId,
        rating: ratingSource === 'USER_PROVIDED' ? row.star : null,
        ratingSource,
        reviewText: row.content || '用户未填写文字评价',
        imageUrls: this.normalizePicUrls(row.picUrls)
      }
    },
    normalizePicUrls(picUrls) {
      if (!picUrls) {
        return []
      }
      if (Array.isArray(picUrls)) {
        return picUrls
      }
      try {
        const parsed = JSON.parse(picUrls)
        return Array.isArray(parsed) ? parsed : []
      } catch (e) {
        return String(picUrls).split(',').map(item => item.trim()).filter(item => item)
      }
    },
    normalizeGovernance(result, row) {
      return normalizeReviewGovernance(result, {
        key: row.id,
        product: '商品 ' + row.valueId,
        orderNo: '评论 #' + row.id,
        rating: row.ratingSource === 'USER_PROVIDED' && row.star != null ? row.star + ' 星' : '评分未知',
        reviewText: row.content || '用户未填写文字评价',
        actions: []
      })
    },
    offlineAiResult(row) {
      return {
        review_id: 'comment-' + row.id,
        product_id: String(row.valueId || ''),
        sentiment_label: 'neutral',
        confidence: 0,
        scores: {},
        evidence: [],
        text_evidence: [],
        image_evidence: [],
        risk_level: 'medium',
        need_human_review: true,
        agent_suggestion: {
          summary: 'AI 服务暂时不可用，可继续人工审核。',
          operation_advice: '请先根据评论内容、订单信息和售后记录进行人工处理。'
        },
        review_governance: {
          reviewId: 'comment-' + row.id,
          productId: String(row.valueId || ''),
          decision: {
            code: 'manual_review',
            label: '需人工复核',
            riskLevel: 'medium',
            confidence: 0,
            needHumanReview: true,
            status: '待人工复核'
          },
          summary: {
            title: 'AI 服务暂时不可用',
            reason: '当前无法自动生成风险判断，可继续人工审核。',
            explanation: '服务恢复后可重新运行 AI 分析。'
          },
          riskTypes: ['other'],
          evidenceStatus: 'insufficient',
          reflectionReason: '当前缺少可验证政策依据，建议人工复核。',
          reflectionReasonCode: 'RETRIEVAL_FAILED',
          failureReasons: [{ code: 'RETRIEVAL_FAILED', message: 'AI 服务暂时不可用，可继续人工审核。' }],
          riskCoverage: [],
          requiresHumanReview: true,
          evidenceCitations: [],
          humanReview: { required: true, reason: 'AI 服务暂时不可用，可继续人工审核。' },
          recommendedActions: []
        }
      }
    },
    safeErrorMessage(response, fallback) {
      const message = response && response.data ? response.data.errmsg || response.data.message : ''
      if (!message) return fallback
      if (/timeout|ECONN|500|POLICY_|FAISS|QWEN|Exception|Traceback/i.test(message)) {
        return fallback
      }
      return message
    },
    parseJsonArray(value) {
      if (!value) {
        return []
      }
      try {
        const parsed = JSON.parse(value)
        return Array.isArray(parsed) ? parsed : []
      } catch (e) {
        return []
      }
    },
    parseJsonObject(value) {
      if (!value) {
        return {}
      }
      try {
        return JSON.parse(value)
      } catch (e) {
        return {}
      }
    },
    handleDownload() {
      this.downloadLoading = true
      import('@/vendor/Export2Excel').then(excel => {
        const tHeader = ['评论ID', '用户ID', '商品ID', '评论', '评论图片列表', '评论时间']
        const filterVal = ['id', 'userId', 'valueId', 'content', 'picUrls', 'addTime']
        excel.export_json_to_excel2(tHeader, this.list, filterVal, '商品评论信息')
        this.downloadLoading = false
      })
    },
    scoreValue(result, name) {
      if (!result || !result.scores || result.scores[name] === undefined) {
        return 0
      }
      return result.scores[name]
    },
    percent(value) {
      if (value === undefined || value === null) {
        return '0%'
      }
      return Math.round(Number(value) * 100) + '%'
    },
    sentimentType(label) {
      if (label === 'positive') {
        return 'success'
      }
      if (label === 'negative') {
        return 'danger'
      }
      return 'warning'
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
    },
    signalValue(label) {
      const scenario = this.governanceScenario || {}
      const found = (scenario.signals || []).find(item => item.label === label)
      return found ? found.value : '-'
    },
    governanceTagType(status) {
      if (status === 'danger') return 'danger'
      if (status === 'warn') return 'warning'
      return 'success'
    },
    openEvidenceSource(url) {
      window.open(url, '_blank', 'noopener')
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.goods-comment-page {
  .comment-ai-result {
    .governance-detail {
      margin-bottom: 18px;
      padding: 16px;
      background: #f8fafc;
      border: 1px solid #dce3ea;
      border-radius: 8px;
    }

    .governance-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;

      h3 {
        margin: 10px 0 6px;
        color: #111827;
        font-size: 18px;
      }

      p {
        margin: 0;
        color: #526174;
        line-height: 1.65;
      }
    }

    .evidence-state {
      flex: 0 0 132px;
      padding: 10px;
      color: #065f46;
      text-align: center;
      background: #d1fae5;
      border: 1px solid #a7f3d0;
      border-radius: 8px;

      strong,
      span {
        display: block;
      }

      span {
        margin-top: 5px;
        font-size: 12px;
      }

      &.insufficient {
        color: #92400e;
        background: #fef3c7;
        border-color: #fcd34d;
      }

      &.mismatch {
        color: #991b1b;
        background: #fee2e2;
        border-color: #fecaca;
      }
    }

    .governance-status,
    .reflection-note {
      margin-top: 12px;
    }

    .policy-evidence-section {
      margin-top: 16px;
    }

    .risk-coverage-list {
      margin-top: 14px;

      h4 {
        margin: 0 0 10px;
      }
    }

    .risk-coverage-item {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 8px;
      padding: 10px 12px;
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 6px;

      strong {
        color: #111827;
      }

      p {
        margin: 4px 0 0;
        color: #64748b;
        font-size: 12px;
        line-height: 1.6;
      }
    }

    .policy-section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;

      h4 {
        margin: 0;
      }

      span {
        color: #64748b;
        font-size: 12px;
      }
    }

    .evidence-title {
      color: #111827;
      font-weight: 700;
    }

    .evidence-card {
      p {
        margin: 10px 0;
        color: #334155;
        line-height: 1.7;
      }

      small {
        display: block;
        margin-top: 5px;
        color: #64748b;
      }
    }

    .evidence-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .technical-collapse,
    .comment-technical-status {
      margin-top: 8px;

      ::v-deep .el-collapse-item__header {
        height: 32px;
        color: #64748b;
        font-size: 12px;
        line-height: 32px;
        background: transparent;
      }
    }

    .technical-line {
      color: #64748b;
      font-size: 12px;
      line-height: 1.8;
    }

    .policy-empty {
      padding: 14px;
      color: #92400e;
      background: #fffbeb;
      border: 1px dashed #fcd34d;
      border-radius: 6px;
      line-height: 1.6;
    }

    .ai-result-head {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      color: #606266;
    }

    .ai-score-row {
      margin-bottom: 16px;
    }

    .comment-ai-note {
      margin-top: 10px;
    }

    .comment-llm-status {
      margin-top: 12px;
    }

    .ai-score-box {
      padding: 12px;
      background: #f8fafc;
      border: 1px solid #ebeef5;
      border-radius: 4px;

      label {
        display: block;
        margin-bottom: 6px;
        color: #909399;
      }

      strong {
        color: #303133;
        font-size: 20px;
      }
    }

    h4 {
      margin: 18px 0 12px;
    }
  }

  .comment-ai-empty {
    min-height: 160px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #909399;
    border: 1px dashed #dcdfe6;
    border-radius: 4px;
  }
}
</style>
