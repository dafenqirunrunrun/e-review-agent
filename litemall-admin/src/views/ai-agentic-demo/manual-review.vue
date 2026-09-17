<template>
  <div class="ai-workbench-page manual-review-page">
    <div class="page-head">
      <p>评论治理中心</p>
      <h1>人工复核</h1>
      <span>只展示系统无法稳妥自动处理的评论，让审核员聚焦冲突点和下一步动作。</span>
    </div>

    <div class="review-list">
      <section v-for="item in cases" :key="item.id" class="review-case">
        <div class="case-main">
          <div class="case-title">
            <strong>{{ item.product }}</strong>
            <em>{{ item.reason }}</em>
          </div>
          <p>{{ item.review }}</p>
          <div class="case-flags">
            <span v-for="flag in item.flags" :key="flag">{{ flag }}</span>
          </div>
        </div>

        <div class="case-check">
          <h2>需要人工看的点</h2>
          <ul>
            <li v-for="point in item.points" :key="point">{{ point }}</li>
          </ul>
        </div>

        <div class="case-actions">
          <el-button type="primary" icon="el-icon-check" @click="choose(item, '采纳系统建议')">采纳系统建议</el-button>
          <el-button icon="el-icon-service" @click="choose(item, '转售后处理')">转售后处理</el-button>
          <el-button icon="el-icon-edit-outline" @click="choose(item, '改判')">改判</el-button>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ManualReviewDemo',
  data() {
    return {
      cases: [
        {
          id: 'MR-001',
          product: '羊毛被',
          reason: '疑似压制差评',
          review: '商家说我把差评删掉才给退款，不然售后一直拖着。',
          flags: ['高优先级', '依据不完全一致', '售后记录待确认'],
          points: ['是否存在要求删除差评的沟通记录', '退款是否被不合理拖延', '是否需要升级投诉处理']
        },
        {
          id: 'MR-002',
          product: '保温杯',
          reason: '证据不足',
          review: '很多人都说五星有礼，我也跟着写了。',
          flags: ['中优先级', '需补充来源', '疑似活动诱导'],
          points: ['是否有商家活动页面或客服话术', '评论是否来自真实购买用户', '是否需要加入观察名单']
        }
      ]
    }
  },
  methods: {
    choose(item, action) {
      this.$message.success(item.id + ' 已选择：' + action)
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.manual-review-page {
  background: #f3f5f7;

  .page-head,
  .review-case {
    background: #ffffff;
    border: 1px solid #dce3ea;
    border-radius: 8px;
    box-shadow: 0 12px 28px rgba(20, 31, 45, 0.045);
  }

  .page-head {
    margin-bottom: 16px;
    padding: 18px 20px;

    p {
      margin: 0 0 7px;
      color: #0f766e;
      font-size: 13px;
      font-weight: 800;
    }

    h1 {
      margin: 0;
      color: #111827;
      font-size: 26px;
      line-height: 1.25;
    }

    span {
      display: block;
      max-width: 760px;
      margin-top: 8px;
      color: #5e6d7f;
      font-size: 14px;
      line-height: 1.7;
    }
  }

  .review-list {
    display: grid;
    gap: 14px;
  }

  .review-case {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(260px, .8fr) 150px;
    gap: 16px;
    padding: 18px;
  }

  .case-title {
    display: flex;
    align-items: center;
    gap: 10px;

    strong {
      color: #111827;
      font-size: 18px;
    }

    em {
      color: #991b1b;
      font-size: 13px;
      font-style: normal;
      font-weight: 800;
    }
  }

  .case-main p {
    margin: 12px 0;
    color: #334155;
    font-size: 15px;
    line-height: 1.7;
  }

  .case-flags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;

    span {
      padding: 5px 9px;
      color: #334155;
      background: #eef3f7;
      border: 1px solid #d8e1ea;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }
  }

  .case-check {
    padding: 13px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;

    h2 {
      margin: 0 0 10px;
      color: #111827;
      font-size: 15px;
    }

    ul {
      margin: 0;
      padding-left: 18px;
      color: #475569;
      font-size: 13px;
      line-height: 1.8;
    }
  }

  .case-actions {
    display: grid;
    align-content: start;
    gap: 9px;

    .el-button {
      width: 100%;
      margin-left: 0;
    }
  }
}

@media (max-width: 1040px) {
  .manual-review-page {
    .review-case {
      grid-template-columns: 1fr;
    }

    .case-actions {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
}

@media (max-width: 720px) {
  .manual-review-page {
    .case-actions {
      grid-template-columns: 1fr;
    }
  }
}
</style>
