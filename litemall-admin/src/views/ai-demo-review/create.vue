<template>
  <div class="ai-workbench-page ai-demo-review-page">
    <div class="ai-page-header">
      <div>
        <p class="ai-page-kicker">Demo Review Intake</p>
        <h1 class="ai-page-title">模拟用户图文评论提交</h1>
        <p class="ai-page-subtitle">
          构造“用户发布评论 -> 进入待分析池 -> Agent 巡检分析”的业务入口，为后续自动巡检、风险任务和运营处理闭环提供数据源。
        </p>
      </div>
      <div class="ai-toolbar">
        <el-button icon="el-icon-refresh" @click="resetForm">重置</el-button>
        <el-button type="primary" icon="el-icon-upload2" :loading="submitting" @click="submitReview">提交评论</el-button>
      </div>
    </div>

    <el-row :gutter="18">
      <el-col :xs="24" :lg="14">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">评论内容</h2>
              <p class="ai-card-desc">提交后进入待分析池，等待智能体巡检任务自动分析。</p>
            </div>
            <span class="ai-status-tag ai-status-medium">待分析</span>
          </div>

          <el-form ref="reviewForm" :model="reviewForm" :rules="rules" label-position="top">
            <el-row :gutter="12">
              <el-col :xs="24" :sm="8">
                <el-form-item label="商品 ID" prop="productId">
                  <el-input-number v-model="reviewForm.productId" :min="1" controls-position="right" />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item label="商品名称" prop="productName">
                  <el-input v-model="reviewForm.productName" clearable />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="8">
                <el-form-item label="商品类目" prop="categoryName">
                  <el-input v-model="reviewForm.categoryName" clearable />
                </el-form-item>
              </el-col>
            </el-row>

            <el-row :gutter="12">
              <el-col :xs="24" :sm="12">
                <el-form-item label="用户昵称" prop="nickname">
                  <el-input v-model="reviewForm.nickname" clearable />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="用户评分" prop="rating">
                  <el-rate v-model="reviewForm.rating" show-score />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="评论文本" prop="reviewText">
              <el-input
                v-model="reviewForm.reviewText"
                type="textarea"
                :autosize="{ minRows: 6, maxRows: 10 }"
                placeholder="例如：商品外观不错，但是用了两天就发热，想申请售后处理。"
              />
            </el-form-item>

            <el-form-item label="图片 URL" prop="imageUrl">
              <el-input v-model="reviewForm.imageUrl" clearable placeholder="http://localhost:6255/static/demo-review-risk.png" />
            </el-form-item>
          </el-form>
        </div>

        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">最近提交</h2>
              <p class="ai-card-desc">展示演示评论池中的最新记录。</p>
            </div>
            <el-button size="mini" icon="el-icon-refresh" @click="loadList">刷新</el-button>
          </div>
          <el-table v-loading="listLoading" :data="reviewList" border fit highlight-current-row>
            <el-table-column prop="id" label="ID" width="80" align="center" />
            <el-table-column prop="productName" label="商品" min-width="150" show-overflow-tooltip />
            <el-table-column prop="nickname" label="昵称" width="120" />
            <el-table-column prop="rating" label="评分" width="80" align="center" />
            <el-table-column prop="reviewText" label="评论" min-width="220" show-overflow-tooltip />
            <el-table-column label="状态" width="110" align="center">
              <template slot-scope="scope">
                <span :class="['ai-status-tag', statusClass(scope.row.analysisStatus)]">{{ scope.row.analysisStatus }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="createdTime" label="提交时间" width="170" align="center" />
          </el-table>
        </div>
      </el-col>

      <el-col :xs="24" :lg="10">
        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">图片预览</h2>
              <p class="ai-card-desc">用于模拟图文评论的图片信号。</p>
            </div>
          </div>
          <div v-if="reviewForm.imageUrl" class="preview-box">
            <el-image :src="reviewForm.imageUrl" fit="cover" :preview-src-list="[reviewForm.imageUrl]" />
          </div>
          <div v-else class="ai-empty-state compact-empty">
            <i class="el-icon-picture-outline" />
            <span>填写图片 URL 后显示预览</span>
          </div>
        </div>

        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">演示流程</h2>
              <p class="ai-card-desc">阶段 6 负责写入待分析池，阶段 7 将由 Agent 自动消费。</p>
            </div>
          </div>
          <el-steps direction="vertical" :active="1" finish-status="success">
            <el-step title="用户提交图文评论" description="运营后台模拟用户发布评论内容" />
            <el-step title="进入待分析池" description="等待智能体巡检分析" />
            <el-step title="智能体巡检分析" description="阶段 7 定时扫描并调用 AI 服务" />
            <el-step title="风险治理闭环" description="阶段 8/9 进入风险中心和运营处理中心" />
          </el-steps>
        </div>

        <div class="ai-card">
          <div class="ai-card-header">
            <div>
              <h2 class="ai-card-title">提交结果</h2>
              <p class="ai-card-desc">最近一次提交反馈。</p>
            </div>
          </div>
          <div v-if="lastSubmit" class="submit-result">
            <span class="ai-status-tag ai-status-positive">成功</span>
            <strong>{{ lastSubmit.message }}</strong>
            <p>记录 ID：{{ lastSubmit.id }}，当前状态：{{ statusText(lastSubmit.analysisStatus) }}</p>
          </div>
          <div v-else class="ai-empty-state compact-empty">
            <i class="el-icon-document-add" />
            <span>尚未提交演示评论</span>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { createDemoReview, listDemoReview } from '@/api/aiDemoReview'
import { displayValue, statusMap } from '@/utils/aiDisplayMap'

export default {
  name: 'AiDemoReviewCreate',
  data() {
    return {
      submitting: false,
      listLoading: false,
      lastSubmit: null,
      reviewList: [],
      reviewForm: {
        productId: 1006002,
        productName: 'E-Review 示例商品',
        categoryName: '数码配件',
        nickname: '体验用户A',
        rating: 2,
        reviewText: '包装挺好，但是用了两天后开始发热，希望客服尽快处理售后。',
        imageUrl: ''
      },
      rules: {
        productId: [{ required: true, message: '请输入商品 ID', trigger: 'change' }],
        productName: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
        reviewText: [{ required: true, message: '请输入评论文本', trigger: 'blur' }]
      }
    }
  },
  created() {
    this.loadList()
  },
  methods: {
    submitReview() {
      this.$refs.reviewForm.validate(valid => {
        if (!valid) {
          return
        }
        this.submitting = true
        createDemoReview(this.reviewForm).then(response => {
          this.submitting = false
          this.lastSubmit = response.data.data
          this.$notify.success({
            title: '提交成功',
            message: '评论提交成功，等待 Agent 巡检分析'
          })
          this.loadList()
        }).catch(response => {
          this.submitting = false
          this.$notify.error({
            title: '提交失败',
            message: response && response.data ? response.data.errmsg : '请检查后端服务'
          })
        })
      })
    },
    loadList() {
      this.listLoading = true
      listDemoReview({ page: 1, limit: 8 }).then(response => {
        this.reviewList = response.data.data.list || []
        this.listLoading = false
      }).catch(() => {
        this.reviewList = []
        this.listLoading = false
      })
    },
    resetForm() {
      this.$refs.reviewForm.resetFields()
      this.reviewForm.imageUrl = ''
      this.lastSubmit = null
    },
    statusClass(status) {
      if (status === 'analyzed') {
        return 'ai-status-positive'
      }
      if (status === 'failed') {
        return 'ai-status-negative'
      }
      if (status === 'analyzing') {
        return 'ai-status-low'
      }
      return 'ai-status-medium'
    },
    statusText(status) {
      const map = Object.assign({}, statusMap, {
        analyzing: '分析中',
        analyzed: '已分析'
      })
      return displayValue(map, status)
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.ai-demo-review-page {
  ::v-deep .el-input-number {
    width: 100%;
  }

  .preview-box {
    height: 260px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    overflow: hidden;
    background: #f8fafc;

    ::v-deep .el-image {
      width: 100%;
      height: 100%;
    }
  }

  .compact-empty {
    min-height: 180px;
  }

  .submit-result {
    display: grid;
    gap: 10px;

    strong {
      color: #111827;
      font-size: 16px;
    }

    p {
      margin: 0;
      color: #6b7280;
    }
  }
}
</style>
