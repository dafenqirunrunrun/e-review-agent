<template>
  <div class="ai-workbench-page review-console-page">
    <div class="console-header">
      <div>
        <p class="console-kicker">评论治理中心</p>
        <h1>审核工作台</h1>
        <p>系统先自动判断评论是否需要处理；审核员只看结论、理由、依据和下一步动作。</p>
      </div>
      <div class="header-actions">
        <el-radio-group v-model="scenarioKey" size="small">
          <el-radio-button label="cashback">建议处理</el-radio-button>
          <el-radio-button label="suppression">需人工复核</el-radio-button>
          <el-radio-button label="normal">自动通过</el-radio-button>
        </el-radio-group>
        <el-button size="small" icon="el-icon-refresh" :loading="loading" @click="loadScenario">刷新真实审核</el-button>
      </div>
    </div>

    <div class="console-layout">
      <aside class="queue-panel">
        <div class="panel-title">
          <span>审核队列</span>
          <strong>{{ queue.length }}</strong>
        </div>
        <button
          v-for="item in queue"
          :key="item.key"
          :class="['queue-item', { active: scenarioKey === item.key }]"
          type="button"
          @click="scenarioKey = item.key"
        >
          <span :class="['status-line', item.status]" />
          <strong>{{ item.product }}</strong>
          <em>{{ item.summary }}</em>
          <small>{{ item.statusText }} / {{ item.enteredAt }}</small>
        </button>
      </aside>

      <main v-loading="loading" class="review-panel">
        <section class="review-subject">
          <div class="subject-meta">
            <span>{{ scenario.product }}</span>
            <span>{{ scenario.orderNo }}</span>
            <span>{{ scenario.rating }}</span>
            <span :class="['source-chip', scenario.source === 'api' ? 'live' : 'demo']">
              {{ scenario.source === 'api' ? '接口返回' : '备用示例' }}
            </span>
          </div>
          <blockquote>{{ scenario.reviewText }}</blockquote>
          <el-alert
            v-if="loadError"
            class="load-note"
            :title="loadError"
            type="warning"
            :closable="false"
            show-icon
          />
        </section>

        <section class="decision-panel">
          <div class="decision-head">
            <div>
              <span :class="['decision-pill', scenario.status]">{{ scenario.statusText }}</span>
              <h2>{{ scenario.decision }}</h2>
              <p>{{ scenario.reason }}</p>
            </div>
            <div class="confidence-mark">
              <span>可信度</span>
              <strong>{{ scenario.confidence }}</strong>
            </div>
          </div>

          <div class="signal-grid">
            <div v-for="signal in scenario.signals" :key="signal.label" class="signal-item">
              <span>{{ signal.label }}</span>
              <strong>{{ signal.value }}</strong>
            </div>
          </div>
        </section>

        <section class="process-panel">
          <div class="section-head">
            <h2>自动审核过程</h2>
            <p>用业务语言保留关键路径，方便复盘系统为什么给出当前结论。</p>
          </div>
          <div class="process-steps">
            <div v-for="step in scenario.process" :key="step.name" class="process-step">
              <i :class="step.done ? 'el-icon-check' : 'el-icon-more'" />
              <span>{{ step.name }}</span>
              <em>{{ step.text }}</em>
            </div>
          </div>
        </section>
      </main>

      <aside class="evidence-panel">
        <section class="reflection-panel">
          <div class="section-head compact">
            <h2>证据核验</h2>
            <p>系统只在政策依据支持风险类型时给出自动处理建议。</p>
          </div>
          <div :class="['reflection-status', scenario.evidenceStatus]">
            <strong>{{ scenario.evidenceStatusText }}</strong>
            <span>{{ scenario.requiresHumanReview ? '需要人工复核' : '可进入自动建议' }}</span>
          </div>
          <p class="reflection-reason">{{ scenario.reflectionReason }}</p>
        </section>

        <section class="basis-panel">
          <div class="section-head compact">
            <h2>判定依据</h2>
            <p>每条依据都能追溯到来源和条款路径。</p>
          </div>

          <div v-if="scenario.evidence.length" class="basis-list">
            <button
              v-for="item in scenario.evidence"
              :key="item.id"
              :class="['basis-card', { active: selectedEvidenceId === item.id }]"
              type="button"
              @click="selectedEvidenceId = item.id"
            >
              <span class="basis-id">依据 {{ item.id }}</span>
              <strong>{{ item.title }}</strong>
              <em>{{ item.path }}</em>
              <p>{{ item.snippet }}</p>
              <small>命中风险：{{ item.riskTypes }}</small>
              <small>{{ item.supports }}</small>
              <small>检索：{{ item.retrieval }}</small>
              <span v-if="item.sourceUrl" class="source-link" @click.stop="openEvidenceSource(item.sourceUrl)">
                查看原文
              </span>
            </button>
          </div>
          <div v-else class="empty-basis">
            <i class="el-icon-circle-check" />
            <strong>无须外部依据</strong>
            <p>这条评论没有命中治理风险，系统仅记录自动通过原因。</p>
          </div>
        </section>

        <section class="action-panel">
          <div class="section-head compact">
            <h2>建议动作</h2>
            <p>{{ scenario.actionHint }}</p>
          </div>
          <div class="action-stack">
            <el-button
              v-for="action in scenario.actions"
              :key="action.label"
              :type="action.primary ? 'primary' : 'default'"
              :icon="action.icon"
              @click="showAction(action.label)"
            >
              {{ action.label }}
            </el-button>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script>
import { analyzeReview } from '@/api/aiReview'
import { normalizeReviewGovernance } from '@/utils/reviewGovernanceAdapter'

export default {
  name: 'AiAgenticDemo',
  data() {
    return {
      scenarioKey: 'cashback',
      selectedEvidenceId: '1',
      loading: false,
      loadError: '',
      liveScenarios: {}
    }
  },
  computed: {
    queue() {
      return Object.keys(this.scenarios).map(key => {
        const item = this.displayScenario(key)
        return {
          key,
          product: item.product,
          summary: item.summary,
          status: item.status,
          statusText: item.statusText,
          enteredAt: item.enteredAt
        }
      })
    },
    scenario() {
      return this.displayScenario(this.scenarioKey)
    },
    scenarios() {
      return {
        cashback: {
          key: 'cashback',
          product: '便携榨汁杯',
          orderNo: '订单 202609060018',
          rating: '5 星',
          enteredAt: '2 分钟前',
          summary: '五星截图返现，不要提质量问题',
          reviewText: '客服说晒五星截图可以返 10 元，但让我不要写杯盖漏水的问题。东西一般，先按要求好评。',
          status: 'warn',
          statusText: '建议处理',
          decision: '疑似好评返现与评分诱导',
          reason: '评论中同时出现返现、五星截图和隐藏质量问题，系统建议拦截并转运营确认。',
          confidence: '高',
          evidenceStatus: 'supported',
          evidenceStatusText: '证据充分',
          reflectionReason: '政策依据同时支持好评返现与评分操纵风险，可以形成运营处理建议。',
          requiresHumanReview: false,
          actionHint: '建议先隐藏该评论，联系运营核查返现活动。',
          payload: {
            reviewId: 'demo-agentic-cashback',
            productId: '1006001',
            productName: '便携榨汁杯',
            reviewText: '客服说晒五星截图可以返 10 元，但让我不要写杯盖漏水的问题。东西一般，先按要求好评。',
            imageUrls: [],
            rating: 5
          },
          signals: [
            { label: '命中风险', value: '好评返现' },
            { label: '处理优先级', value: '高' },
            { label: '引用依据', value: '2 条' },
            { label: '下一步', value: '运营处理' }
          ],
          evidence: [
            {
              id: '1',
              title: 'FTC 16 CFR Part 465',
              path: 'A 类 / Part 465 / 465.4',
              snippet: '购买正向或负向消费者评价，可能构成评价操纵。',
              riskTypes: '评分操纵',
              supports: '支持：好评返现、评分操纵',
              retrieval: 'Hybrid / 0.0317',
              sourceUrl: 'https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-465'
            }
          ],
          actions: [
            { label: '采纳建议', icon: 'el-icon-check', primary: true },
            { label: '转运营核查', icon: 'el-icon-position' },
            { label: '标记误判', icon: 'el-icon-edit-outline' }
          ],
          process: [
            { name: '识别是否需要严格审核', text: '进入严格审核', done: true },
            { name: '查找可引用依据', text: '命中公开政策依据', done: true },
            { name: '核验证据是否支持结论', text: '校验通过', done: true }
          ],
          source: 'demo'
        },
        suppression: {
          key: 'suppression',
          product: '羊毛被',
          orderNo: '订单 202609060026',
          rating: '2 星',
          enteredAt: '8 分钟前',
          summary: '商家要求删除差评再退款',
          reviewText: '商家说我把差评删掉才给退款，不然售后一直拖着。被子有异味，沟通好多次没解决。',
          status: 'danger',
          statusText: '需人工复核',
          decision: '疑似压制差评，证据需要人工确认',
          reason: '评论命中删除差评和售后拖延，系统已转人工复核。',
          confidence: '中',
          evidenceStatus: 'insufficient',
          evidenceStatusText: '证据不足',
          reflectionReason: '评论命中压制差评和售后争议，但当前仍需要结合订单沟通记录确认。',
          requiresHumanReview: true,
          actionHint: '请审核员查看订单沟通记录，再决定是否升级投诉处理。',
          payload: {
            reviewId: 'demo-agentic-suppression',
            productId: '1006002',
            productName: '羊毛被',
            reviewText: '商家说我把差评删掉才给退款，不然售后一直拖着。被子有异味，沟通好多次没解决。',
            imageUrls: [],
            rating: 2
          },
          signals: [
            { label: '命中风险', value: '压制差评' },
            { label: '处理优先级', value: '高' },
            { label: '引用依据', value: '1 条' },
            { label: '下一步', value: '人工复核' }
          ],
          evidence: [],
          actions: [
            { label: '进入人工复核', icon: 'el-icon-user', primary: true },
            { label: '要求补充证据', icon: 'el-icon-document-add' },
            { label: '转售后跟进', icon: 'el-icon-service' }
          ],
          process: [
            { name: '识别是否需要严格审核', text: '进入严格审核', done: true },
            { name: '确认最终处理方式', text: '转人工复核', done: false }
          ],
          source: 'demo'
        },
        normal: {
          key: 'normal',
          product: '旅行收纳包',
          orderNo: '订单 202609060033',
          rating: '4 星',
          enteredAt: '14 分钟前',
          summary: '物流稍慢，商品整体可以',
          reviewText: '物流比预计慢了一天，不过收纳包质量还可以，颜色也和页面差不多。',
          status: 'ok',
          statusText: '自动通过',
          decision: '普通体验反馈，无须处理',
          reason: '评论只包含物流体验和一般商品反馈，没有命中治理风险。',
          confidence: '高',
          evidenceStatus: 'supported',
          evidenceStatusText: '证据充分',
          reflectionReason: '未命中治理风险，轻路径自动审核通过。',
          requiresHumanReview: false,
          actionHint: '无须人工处理，系统记录为普通评论。',
          payload: {
            reviewId: 'demo-agentic-normal',
            productId: '1006003',
            productName: '旅行收纳包',
            reviewText: '物流比预计慢了一天，不过收纳包质量还可以，颜色也和页面差不多。',
            imageUrls: [],
            rating: 4
          },
          signals: [
            { label: '命中风险', value: '无' },
            { label: '处理优先级', value: '低' },
            { label: '引用依据', value: '无须依据' },
            { label: '下一步', value: '自动通过' }
          ],
          evidence: [],
          actions: [
            { label: '确认通过', icon: 'el-icon-check', primary: true },
            { label: '加入观察', icon: 'el-icon-view' },
            { label: '重新审核', icon: 'el-icon-refresh' }
          ],
          process: [
            { name: '识别是否需要严格审核', text: '轻路径', done: true },
            { name: '快速完成普通评价审核', text: '无须严格依据', done: true }
          ],
          source: 'demo'
        }
      }
    }
  },
  watch: {
    scenarioKey() {
      this.selectedEvidenceId = this.scenario.evidence[0] ? this.scenario.evidence[0].id : ''
      this.loadScenario()
    }
  },
  created() {
    this.loadScenario()
  },
  methods: {
    displayScenario(key) {
      return this.liveScenarios[key] || this.scenarios[key]
    },
    loadScenario() {
      const fallback = this.scenarios[this.scenarioKey]
      this.loading = true
      this.loadError = ''
      analyzeReview(fallback.payload).then(response => {
        const result = response.data.data.result
        const normalized = normalizeReviewGovernance(result, fallback)
        this.$set(this.liveScenarios, this.scenarioKey, normalized)
        this.selectedEvidenceId = normalized.evidence[0] ? normalized.evidence[0].id : ''
        this.loading = false
      }).catch(() => {
        this.loadError = '暂时无法连接真实审核接口，当前展示备用示例。'
        this.$set(this.liveScenarios, this.scenarioKey, fallback)
        this.selectedEvidenceId = fallback.evidence[0] ? fallback.evidence[0].id : ''
        this.loading = false
      })
    },
    showAction(label) {
      this.$message.success('已选择：' + label)
    },
    openEvidenceSource(url) {
      window.open(url, '_blank', 'noopener')
    }
  }
}
</script>

<style rel="stylesheet/scss" lang="scss" scoped>
.review-console-page {
  background: #f3f5f7;
  color: #172033;

  .console-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 16px;
    padding: 18px 20px;
    background: #ffffff;
    border: 1px solid #dce3ea;
    border-radius: 8px;
    box-shadow: 0 12px 28px rgba(20, 31, 45, 0.05);

    h1 {
      margin: 0;
      font-size: 26px;
      line-height: 1.25;
    }

    p {
      max-width: 820px;
      margin: 7px 0 0;
      color: #5e6d7f;
      font-size: 14px;
      line-height: 1.7;
    }
  }

  .console-kicker {
    margin: 0 0 7px;
    color: #0f766e;
    font-size: 13px;
    font-weight: 800;
  }

  .header-actions {
    display: flex;
    flex: 0 0 auto;
    gap: 10px;
    align-items: center;
  }

  .console-layout {
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr) 360px;
    gap: 14px;
    align-items: start;
  }

  .queue-panel,
  .review-subject,
  .decision-panel,
  .process-panel,
  .reflection-panel,
  .basis-panel,
  .action-panel {
    background: #ffffff;
    border: 1px solid #dce3ea;
    border-radius: 8px;
    box-shadow: 0 12px 28px rgba(20, 31, 45, 0.045);
  }

  .queue-panel,
  .reflection-panel,
  .basis-panel,
  .action-panel {
    padding: 14px;
  }

  .review-panel,
  .evidence-panel {
    display: grid;
    gap: 14px;
  }

  .panel-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;

    span {
      color: #111827;
      font-weight: 800;
    }

    strong {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 26px;
      height: 26px;
      color: #ffffff;
      background: #172033;
      border-radius: 6px;
      font-size: 12px;
    }
  }

  .queue-item {
    position: relative;
    display: block;
    width: 100%;
    min-height: 116px;
    margin-bottom: 10px;
    padding: 13px 12px 13px 18px;
    text-align: left;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    cursor: pointer;
    transition: border-color .18s ease, background .18s ease, transform .18s ease;

    &:hover,
    &.active {
      background: #ffffff;
      border-color: #0f766e;
      transform: translateY(-1px);
    }

    strong,
    em,
    small {
      display: block;
    }

    strong {
      color: #111827;
      font-size: 14px;
      line-height: 1.35;
    }

    em {
      margin-top: 8px;
      color: #475569;
      font-size: 13px;
      font-style: normal;
      line-height: 1.5;
    }

    small {
      margin-top: 10px;
      color: #64748b;
      font-size: 12px;
    }
  }

  .status-line {
    position: absolute;
    top: 12px;
    bottom: 12px;
    left: 0;
    width: 4px;
    background: #22c55e;
    border-radius: 0 4px 4px 0;

    &.warn {
      background: #f59e0b;
    }

    &.danger {
      background: #ef4444;
    }
  }

  .review-subject {
    padding: 18px 20px;

    blockquote {
      margin: 14px 0 0;
      padding: 18px;
      color: #111827;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-left: 5px solid #0f766e;
      border-radius: 8px;
      font-size: 18px;
      font-weight: 700;
      line-height: 1.65;
    }
  }

  .subject-meta {
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

  .source-chip.live {
    color: #065f46;
    background: #d1fae5;
    border-color: #a7f3d0;
  }

  .source-chip.demo {
    color: #92400e;
    background: #fef3c7;
    border-color: #fcd34d;
  }

  .load-note {
    margin-top: 12px;
  }

  .decision-panel {
    padding: 20px;
  }

  .decision-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;

    h2 {
      margin: 12px 0 0;
      color: #111827;
      font-size: 22px;
      line-height: 1.35;
    }

    p {
      max-width: 720px;
      margin: 8px 0 0;
      color: #526174;
      font-size: 14px;
      line-height: 1.75;
    }
  }

  .decision-pill {
    display: inline-flex;
    align-items: center;
    min-height: 28px;
    padding: 5px 11px;
    color: #166534;
    background: #dcfce7;
    border: 1px solid #86efac;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 800;

    &.warn {
      color: #92400e;
      background: #fef3c7;
      border-color: #fcd34d;
    }

    &.danger {
      color: #991b1b;
      background: #fee2e2;
      border-color: #fecaca;
    }
  }

  .confidence-mark {
    flex: 0 0 92px;
    min-height: 82px;
    padding: 12px;
    text-align: center;
    background: #172033;
    border-radius: 8px;

    span,
    strong {
      display: block;
    }

    span {
      color: #cbd5e1;
      font-size: 12px;
    }

    strong {
      margin-top: 10px;
      color: #ffffff;
      font-size: 28px;
      line-height: 1;
    }
  }

  .signal-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-top: 18px;
  }

  .signal-item {
    min-height: 72px;
    padding: 12px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;

    span,
    strong {
      display: block;
    }

    span {
      color: #64748b;
      font-size: 12px;
    }

    strong {
      margin-top: 9px;
      color: #111827;
      font-size: 15px;
      line-height: 1.35;
    }
  }

  .process-panel {
    padding: 18px;
  }

  .section-head {
    margin-bottom: 12px;

    h2 {
      margin: 0;
      color: #111827;
      font-size: 16px;
      line-height: 1.35;
    }

    p {
      margin: 5px 0 0;
      color: #64748b;
      font-size: 13px;
      line-height: 1.6;
    }

    &.compact {
      margin-bottom: 10px;
    }
  }

  .process-steps {
    display: grid;
    gap: 8px;
  }

  .process-step {
    display: grid;
    grid-template-columns: 28px minmax(120px, 180px) minmax(0, 1fr);
    gap: 8px;
    align-items: center;
    min-height: 40px;
    padding: 9px 10px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 7px;

    i {
      color: #0f766e;
      font-size: 16px;
      font-weight: 800;
    }

    span {
      color: #111827;
      font-size: 13px;
      font-weight: 800;
    }

    em {
      color: #64748b;
      font-size: 13px;
      font-style: normal;
      line-height: 1.45;
    }
  }

  .basis-list {
    display: grid;
    gap: 10px;
  }

  .reflection-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    min-height: 48px;
    padding: 10px 12px;
    color: #065f46;
    background: #d1fae5;
    border: 1px solid #a7f3d0;
    border-radius: 8px;

    strong,
    span {
      display: block;
    }

    strong {
      font-size: 15px;
    }

    span {
      color: #047857;
      font-size: 12px;
      font-weight: 800;
    }

    &.insufficient {
      color: #92400e;
      background: #fef3c7;
      border-color: #fcd34d;

      span {
        color: #92400e;
      }
    }

    &.mismatch {
      color: #991b1b;
      background: #fee2e2;
      border-color: #fecaca;

      span {
        color: #991b1b;
      }
    }
  }

  .reflection-reason {
    margin: 10px 0 0;
    color: #475569;
    font-size: 13px;
    line-height: 1.65;
  }

  .basis-card {
    width: 100%;
    min-height: 164px;
    padding: 13px;
    text-align: left;
    background: #f8fafc;
    border: 1px solid #dbe4ee;
    border-radius: 8px;
    cursor: pointer;
    transition: border-color .18s ease, background .18s ease;

    &:hover,
    &.active {
      background: #ffffff;
      border-color: #0f766e;
    }

    strong,
    em,
    p,
    small {
      display: block;
    }

    strong {
      margin-top: 8px;
      color: #111827;
      font-size: 15px;
      line-height: 1.35;
    }

    em {
      margin-top: 5px;
      color: #2563eb;
      font-size: 12px;
      font-style: normal;
      font-weight: 800;
      line-height: 1.45;
    }

    p {
      margin: 10px 0 0;
      color: #334155;
      font-size: 13px;
      line-height: 1.6;
    }

    small {
      margin-top: 10px;
      color: #64748b;
      font-size: 12px;
      line-height: 1.45;
    }
  }

  .source-link {
    display: inline-flex;
    margin-top: 10px;
    color: #0f766e;
    font-size: 12px;
    font-weight: 800;
  }

  .basis-id {
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    padding: 4px 8px;
    color: #ffffff;
    background: #0f766e;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 800;
  }

  .empty-basis {
    min-height: 160px;
    padding: 18px;
    text-align: center;
    color: #64748b;
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    border-radius: 8px;

    i {
      color: #16a34a;
      font-size: 30px;
    }

    strong {
      display: block;
      margin-top: 10px;
      color: #111827;
    }

    p {
      margin: 8px 0 0;
      font-size: 13px;
      line-height: 1.6;
    }
  }

  .action-stack {
    display: grid;
    gap: 9px;

    .el-button {
      width: 100%;
      margin-left: 0;
    }
  }
}

@media (max-width: 1240px) {
  .review-console-page {
    .console-layout {
      grid-template-columns: 260px minmax(0, 1fr);
    }

    .evidence-panel {
      grid-column: 1 / -1;
      grid-template-columns: minmax(0, 1fr) 300px;
    }
  }
}

@media (max-width: 860px) {
  .review-console-page {
    .console-header,
    .decision-head,
    .header-actions {
      display: block;
    }

    .header-actions .el-button,
    .confidence-mark {
      margin-top: 14px;
    }

    .console-layout,
    .evidence-panel,
    .signal-grid {
      grid-template-columns: 1fr;
    }

    .process-step {
      grid-template-columns: 28px 1fr;

      em {
        grid-column: 2;
      }
    }
  }
}
</style>
