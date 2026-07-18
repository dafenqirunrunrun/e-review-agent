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

    <el-dialog :visible.sync="aiDialogVisible" title="AI 评论分析结果" width="760px">
      <div v-if="currentAiResult" class="comment-ai-result">
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
          class="comment-ai-note"
          title="AI 分析结果仅供运营参考，请结合订单、图片和售后记录进行最终判断。"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-descriptions :column="3" border size="small" class="comment-llm-status">
          <el-descriptions-item label="Provider">{{ currentAiResult.llm_provider || 'local_rule_fallback' }}</el-descriptions-item>
          <el-descriptions-item label="Schema">{{ currentAiResult.schema_valid === false ? '失败' : '通过' }}</el-descriptions-item>
          <el-descriptions-item label="人工复核">{{ currentAiResult.need_human_review ? '需要' : '无需' }}</el-descriptions-item>
          <el-descriptions-item label="Repair">{{ currentAiResult.repair_used ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="Fallback">{{ currentAiResult.fallback_used ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ currentAiResult.model_name || '-' }}</el-descriptions-item>
        </el-descriptions>
        <h4>判断证据</h4>
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
import { analyzeReview, listReviewAnalysis } from '@/api/aiReview'
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
      aiDialogVisible: false,
      currentAiResult: null,
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
      this.$set(this.aiLoadingMap, row.id, true)
      analyzeReview(this.buildAiPayload(row)).then(response => {
        const result = response.data.data.result
        this.$set(this.aiResultMap, row.id, result)
        this.currentAiResult = result
        this.aiDialogVisible = true
        this.$set(this.aiLoadingMap, row.id, false)
        this.$notify.success({
          title: 'AI 分析完成',
          message: '评论已生成情感判断和运营建议'
        })
      }).catch(response => {
        this.$set(this.aiLoadingMap, row.id, false)
        this.$notify.error({
          title: 'AI 分析失败',
          message: response && response.data ? response.data.errmsg : '请检查 AI 服务状态'
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
      if (this.aiResultMap[row.id]) {
        this.currentAiResult = this.aiResultMap[row.id]
        this.aiDialogVisible = true
        return
      }
      listReviewAnalysis({ productId: row.valueId, page: 1, limit: 1 }).then(response => {
        const list = response.data.data.list || []
        this.currentAiResult = list.length > 0 ? this.convertHistoryResult(list[0]) : null
        this.aiDialogVisible = true
      }).catch(() => {
        this.currentAiResult = null
        this.aiDialogVisible = true
      })
    },
    buildAiPayload(row) {
      return {
        reviewId: 'comment-' + row.id,
        productId: row.valueId,
        productName: '商品 ' + row.valueId,
        rating: row.star,
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
    convertHistoryResult(row) {
      return {
        sentiment_label: row.sentimentLabel,
        confidence: row.confidence,
        risk_level: row.sentimentLabel === 'negative' ? 'high' : 'low',
        scores: {
          positive: row.positiveScore,
          neutral: row.neutralScore,
          negative: row.negativeScore
        },
        evidence: this.parseJsonArray(row.evidenceJson),
        agent_suggestion: this.parseJsonObject(row.agentSuggestionJson)
      }
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
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.goods-comment-page {
  .comment-ai-result {
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
