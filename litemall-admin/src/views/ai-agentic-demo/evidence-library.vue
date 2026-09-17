<template>
  <div class="ai-workbench-page evidence-library-page">
    <div class="page-head">
      <p>评论治理中心</p>
      <h1>判定依据库</h1>
      <span>这里放审核员能引用的规则来源，不展示底层检索和切片细节。</span>
    </div>

    <div class="source-tabs">
      <button
        v-for="type in sourceTypes"
        :key="type.value"
        :class="{ active: activeType === type.value }"
        type="button"
        @click="selectType(type.value)"
      >
        {{ type.label }}
      </button>
    </div>

    <evidence-playground v-if="activeType === 'playground'" />
    <document-library v-else-if="activeType === 'files'" />
    <div v-else class="evidence-grid">
      <article v-for="item in filteredSources" :key="item.id" class="source-card">
        <div class="source-head">
          <span>{{ item.level }}</span>
          <strong>{{ item.name }}</strong>
        </div>
        <p>{{ item.summary }}</p>
        <dl>
          <div>
            <dt>适用风险</dt>
            <dd>{{ item.risks }}</dd>
          </div>
          <div>
            <dt>条款路径</dt>
            <dd>{{ item.path }}</dd>
          </div>
          <div>
            <dt>来源状态</dt>
            <dd>{{ item.status }}</dd>
          </div>
        </dl>
        <el-button size="mini" icon="el-icon-link" @click="openSource(item.url)">查看来源</el-button>
      </article>
    </div>
  </div>
</template>

<script>
import DocumentLibrary from './document-library'
import EvidencePlayground from './evidence-playground'

export default {
  name: 'EvidenceLibraryDemo',
  components: { DocumentLibrary, EvidencePlayground },
  data() {
    return {
      activeType: ['regulation', 'platform', 'case', 'files', 'playground'].includes(this.$route.query.tab) ? this.$route.query.tab : 'regulation',
      sourceTypes: [
        { label: '证据试查', value: 'playground' },
        { label: '法规依据', value: 'regulation' },
        { label: '平台规范', value: 'platform' },
        { label: '历史案例', value: 'case' },
        { label: '导入文件', value: 'files' }
      ],
      sources: [
        {
          id: 'ftc-465',
          type: 'regulation',
          level: 'A 类',
          name: 'FTC 16 CFR Part 465',
          summary: '用于判断虚假评价、付费好评、评分操纵等风险。',
          risks: '好评返现 / 评分操纵 / 虚假评价',
          path: 'Part 465 / §465.4',
          status: '公开可引用',
          url: 'https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-465'
        },
        {
          id: 'ecommerce-law',
          type: 'regulation',
          level: 'A 类',
          name: '电子商务法',
          summary: '用于判断删除差评、压制消费者评价等风险。',
          risks: '压制差评 / 评价展示治理',
          path: '信用评价制度',
          status: '公开可引用',
          url: 'https://www.mofcom.gov.cn/zhrmghgdzswf/fg/art/2018/art_cc9187dd95cd40158552d78a610e8c29.html'
        },
        {
          id: 'google-ugc',
          type: 'platform',
          level: 'B 类',
          name: 'Google Maps UGC Policy',
          summary: '用于辅助判断虚假参与、利益冲突、评分操纵等风险。',
          risks: '虚假参与 / 利益冲突 / 评分操纵',
          path: 'Fake engagement',
          status: '公开页面引用',
          url: 'https://support.google.com/contributionpolicy/answer/7400114?hl=en'
        },
        {
          id: 'case-after-sale',
          type: 'case',
          level: 'C 类',
          name: '历史售后争议案例',
          summary: '用于辅助识别重复商品问题和售后拖延风险，不单独作为强处置依据。',
          risks: '售后风险 / 重复投诉 / 商品质量',
          path: '本地案例库 / 售后争议',
          status: '内部参考',
          url: ''
        }
      ]
    }
  },
  computed: {
    filteredSources() {
      return this.sources.filter(item => item.type === this.activeType)
    }
  },
  watch: {
    '$route.query.tab'(value) {
      if (this.sourceTypes.some(item => item.value === value)) this.activeType = value
    }
  },
  methods: {
    selectType(value) {
      this.activeType = value
      this.$router.replace({ path: this.$route.path, query: { tab: value }})
    },
    openSource(url) {
      if (url) {
        window.open(url, '_blank')
      } else {
        this.$message.info('历史案例为内部参考，当前 demo 不打开外部来源。')
      }
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.evidence-library-page {
  background: #f3f5f7;

  .page-head,
  .source-card {
    background: #ffffff;
    border: 1px solid #dce3ea;
    border-radius: 8px;
    box-shadow: 0 12px 28px rgba(20, 31, 45, 0.045);
  }

  .page-head {
    margin-bottom: 14px;
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
      margin-top: 8px;
      color: #5e6d7f;
      font-size: 14px;
      line-height: 1.7;
    }
  }

  .source-tabs {
    display: flex;
    flex-wrap: wrap;
    width: fit-content;
    max-width: 100%;
    margin-bottom: 14px;
    padding: 4px;
    background: #ffffff;
    border: 1px solid #dce3ea;
    border-radius: 8px;

    button {
      flex: 1 1 96px;
      min-width: 96px;
      height: 34px;
      color: #475569;
      background: transparent;
      border: 0;
      border-radius: 6px;
      font-weight: 800;
      cursor: pointer;

      &.active {
        color: #ffffff;
        background: #0f766e;
      }
    }
  }

  @media (max-width: 680px) {
    .source-tabs {
      width: 100%;

      button {
        min-width: 104px;
      }
    }
  }

  .evidence-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 14px;
  }

  .source-card {
    padding: 18px;

    p {
      margin: 12px 0;
      color: #475569;
      font-size: 14px;
      line-height: 1.7;
    }

    dl {
      display: grid;
      gap: 8px;
      margin: 0 0 14px;
    }

    div {
      padding: 10px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 7px;
    }

    dt {
      color: #64748b;
      font-size: 12px;
      font-weight: 800;
    }

    dd {
      margin: 6px 0 0;
      color: #111827;
      font-size: 13px;
      line-height: 1.45;
    }
  }

  .source-head {
    display: flex;
    align-items: center;
    gap: 10px;

    span {
      padding: 5px 9px;
      color: #ffffff;
      background: #172033;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 800;
    }

    strong {
      color: #111827;
      font-size: 17px;
      line-height: 1.35;
    }
  }
}
</style>
