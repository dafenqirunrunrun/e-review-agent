<template>
  <section class="evidence-playground">
    <header class="playground-head">
      <div>
        <p class="eyebrow">只读验证环境</p>
        <h2>政策证据试查台</h2>
        <p>输入一段评论或治理问题，查看系统识别的风险、证据覆盖和可追溯政策依据。</p>
      </div>
      <div class="sandbox-mark"><i class="el-icon-lock" /> 不写入正式审核</div>
    </header>

    <div class="playground-shell">
      <aside class="query-bench">
        <div class="bench-section">
          <span class="bench-label">试查方式</span>
          <el-radio-group v-model="mode" size="small" class="mode-switch">
            <el-radio-button label="evidence_search">查政策依据</el-radio-button>
            <el-radio-button label="audit_simulation">模拟审核边界</el-radio-button>
          </el-radio-group>
        </div>

        <div class="bench-section">
          <span class="bench-label">试查索引</span>
          <el-radio-group v-model="indexTarget" size="small" class="mode-switch">
            <el-radio-button label="current">当前版本</el-radio-button>
            <el-radio-button label="candidate" :disabled="!candidateAvailable">可对比版本</el-radio-button>
            <el-radio-button label="compare" :disabled="!candidateAvailable">双版本对比</el-radio-button>
          </el-radio-group>
          <p class="index-hint">{{ indexHint }}</p>
        </div>

        <div class="bench-section sample-section">
          <span class="bench-label">困难与边界样例</span>
          <button
            v-for="sample in examples"
            :key="sample.label"
            type="button"
            class="sample-row"
            @click="useExample(sample.query)"
          >
            <span>{{ sample.label }}</span>
            <i class="el-icon-arrow-right" />
          </button>
        </div>

        <div class="boundary-note">
          <i class="el-icon-info" />
          <span>结果用于验证政策覆盖与审核边界，不会创建风险任务，也不会执行处罚。</span>
        </div>
      </aside>

      <main class="conversation-panel">
        <div ref="conversation" class="conversation-stream" aria-live="polite">
          <div v-if="!turns.length && !loading" class="welcome-state">
            <div class="welcome-symbol"><i class="el-icon-search" /></div>
            <h3>从一条真实问题开始</h3>
            <p>可以输入评论原文，也可以选择左侧样例，系统只返回足够支撑判断的少量证据。</p>
          </div>

          <article v-for="turn in turns" :key="turn.id" class="conversation-turn">
            <div class="query-message">
              <span>你的问题 · {{ turn.targetLabel }}</span>
              <p>{{ turn.query }}</p>
            </div>

            <div v-if="turn.error" class="result-error">
              <i class="el-icon-warning-outline" />
              <div><strong>本次试查未完成</strong><p>{{ turn.error }}</p></div>
            </div>

            <template v-else-if="turn.result">
              <section v-if="turn.baseline" class="comparison-band">
                <div class="comparison-heading">
                  <div><span>版本对比</span><h3>{{ comparisonVerdict(turn).label }}</h3></div>
                  <el-tag :type="comparisonVerdict(turn).type" size="small" effect="plain">{{ comparisonVerdict(turn).tag }}</el-tag>
                </div>
                <div class="comparison-columns">
                  <div><span>当前版本</span><strong>{{ turn.baseline.evidenceStatusLabel }}</strong><p>{{ sourceSummary(turn.baseline) }}</p></div>
                  <div><span>候选版本</span><strong>{{ turn.result.evidenceStatusLabel }}</strong><p>{{ sourceSummary(turn.result) }}</p></div>
                </div>
              </section>
              <section class="decision-band" :class="`is-${turn.result.decision.tone}`">
                <div class="decision-copy">
                  <span>试查结论</span>
                  <h3>{{ turn.result.decision.label }}</h3>
                  <p>{{ turn.result.reflectionReason }}</p>
                </div>
                <div class="status-stamp">
                  <span>证据状态</span>
                  <strong>{{ turn.result.evidenceStatusLabel }}</strong>
                </div>
              </section>

              <section v-if="turn.result.risks.length" class="risk-coverage">
                <div class="section-heading">
                  <div><span>风险覆盖</span><h3>系统认为哪里需要关注</h3></div>
                </div>
                <div class="risk-list">
                  <div v-for="risk in turn.result.risks" :key="risk.code" class="risk-row">
                    <span class="risk-severity">{{ risk.severity }}</span>
                    <div><strong>{{ risk.label }}</strong><p>{{ risk.description }}</p></div>
                    <el-tag :type="tone(risk.evidenceStatus)" size="small" effect="plain">{{ risk.evidenceStatusLabel }}</el-tag>
                  </div>
                </div>
              </section>

              <section v-if="turn.result.evidence.length" class="evidence-section">
                <div class="section-heading">
                  <div><span>引用链</span><h3>支持判断的政策依据</h3></div>
                  <small>仅保留必要且不重复的证据</small>
                </div>
                <ol class="evidence-chain">
                  <li v-for="item in turn.result.evidence" :key="item.evidenceId" class="evidence-item">
                    <div class="evidence-marker">{{ item.evidenceId }}</div>
                    <div class="evidence-body">
                      <div class="evidence-title">
                        <div><strong>{{ item.sourceName }}</strong><span>{{ evidenceLocation(item) }}</span></div>
                        <a v-if="safeUrl(item.sourceUrl)" :href="safeUrl(item.sourceUrl)" target="_blank" rel="noopener noreferrer">查看原文 <i class="el-icon-top-right" /></a>
                      </div>
                      <p class="snippet">{{ item.snippet }}</p>
                      <div class="evidence-support">
                        <span>支持风险</span>
                        <b v-for="label in uniqueLabels(item.riskLabels)" :key="label">{{ label }}</b>
                      </div>
                    </div>
                  </li>
                </ol>
              </section>

              <div v-else-if="turn.result.evidenceStatus === 'not_required'" class="clean-result">
                <i class="el-icon-circle-check" />
                <div><strong>{{ cleanResultTitle(turn.result) }}</strong><p>{{ cleanResultDescription(turn.result) }}</p></div>
              </div>

              <div v-else class="empty-evidence">
                <i class="el-icon-document-delete" />
                <div><strong>当前缺少可验证政策依据</strong><p>系统不会补写或伪造引用，本次结果应交给人工判断。</p></div>
              </div>

              <el-collapse class="technical-fold">
                <el-collapse-item name="technical">
                  <template slot="title"><i class="el-icon-setting" /> 技术详情</template>
                  <dl>
                    <div><dt>检索路径</dt><dd>{{ modeLabel(turn.result.technical.actualMode) }}</dd></div>
                    <div><dt>候选 / 展示</dt><dd>{{ turn.result.technical.candidateCount }} / {{ turn.result.technical.displayCount }}</dd></div>
                    <div><dt>耗时</dt><dd>{{ turn.result.technical.retrievalMs }} ms</dd></div>
                    <div><dt>索引版本</dt><dd>{{ turn.result.technical.indexVersion || '基础政策库' }}</dd></div>
                  </dl>
                  <div v-for="item in turn.result.evidence" :key="`tech-${item.evidenceId}`" class="evidence-tech">
                    {{ item.evidenceId }} · {{ item.retrieval.mode }} · score {{ formatScore(item.retrieval.score) }} · hash {{ shortContentHash(item.contentHash) }}
                  </div>
                </el-collapse-item>
              </el-collapse>
            </template>

            <div v-else class="turn-pending">
              <span /><span /><span />
              <p>正在核对这条输入</p>
            </div>
          </article>

          <div v-if="loading" class="thinking-state">
            <span /><span /><span />
            <p>正在核对风险与政策依据</p>
          </div>
        </div>

        <form class="query-composer" @submit.prevent="submit">
          <el-input
            v-model="query"
            type="textarea"
            :rows="3"
            :maxlength="2000"
            resize="none"
            placeholder="输入评论或审核问题，例如：客服要求删除差评后才退款"
            :disabled="loading"
            @keydown.ctrl.enter.native="submit"
          />
          <div class="composer-foot">
            <span>{{ query.length }}/2000</span>
            <el-button type="primary" icon="el-icon-search" native-type="submit" :loading="loading" :disabled="query.trim().length < 1">核对政策依据</el-button>
          </div>
        </form>
      </main>
    </div>
  </section>
</template>

<script>
import { queryPolicyEvidence } from '@/api/policyPlayground'
import { documentIndexStatus } from '@/api/documentLibrary'
import { evidenceTone, playgroundExamples, safePolicyUrl, shortHash } from '@/utils/policyPlayground'

export default {
  name: 'EvidencePlayground',
  data() {
    return {
      mode: 'evidence_search',
      query: '',
      loading: false,
      sequence: 0,
      turns: [],
      examples: playgroundExamples,
      indexTarget: 'current',
      indexState: { active: null, candidate: null, releases: [], candidateRelease: null, comparableRelease: null },
      indexStateError: ''
    }
  },
  computed: {
    candidateAvailable() {
      return Boolean(this.comparableRelease)
    },
    comparableRelease() {
      const explicitComparable = this.indexState.comparableRelease
      if (explicitComparable) return explicitComparable
      const candidate = this.indexState.candidateRelease !== undefined ? this.indexState.candidateRelease : this.indexState.candidate
      if (candidate && candidate.evaluationAvailable && ['ready', 'failed'].includes(candidate.status)) return candidate
      const releases = this.indexState.historyReleases || this.indexState.releases || []
      return releases.find(item => item.evaluationAvailable && item.releaseEvaluation && item.releaseEvaluation.gatePassed && ['ready', 'superseded'].includes(item.status)) || null
    },
    candidateVersion() {
      return this.comparableRelease ? this.comparableRelease.version : ''
    },
    indexHint() {
      if (this.indexStateError) return '索引状态暂不可用，仅可试查当前版本。'
      if (!this.candidateAvailable) return '暂无可用于对比的已验收版本。'
      return `对比版本 ${this.candidateVersion}`
    }
  },
  mounted() { this.loadIndexState() },
  methods: {
    tone: evidenceTone,
    safeUrl: safePolicyUrl,
    shortContentHash: shortHash,
    async loadIndexState() {
      try {
        const response = await documentIndexStatus()
        this.indexState = response.data.data
        if (!this.candidateAvailable && this.indexTarget !== 'current') this.indexTarget = 'current'
      } catch (_) {
        this.indexStateError = 'INDEX_STATUS_UNAVAILABLE'
        this.indexTarget = 'current'
      }
    },
    useExample(value) {
      this.query = value
      this.$nextTick(() => this.submit())
    },
    async submit() {
      const value = this.query.trim()
      if (this.loading || value.length < 1) return
      this.loading = true
      this.query = ''
      const target = this.indexTarget
      const turn = { id: ++this.sequence, query: value, result: null, baseline: null, error: '', targetLabel: this.targetLabel(target) }
      this.turns.push(turn)
      try {
        const request = { query: value, mode: this.mode, topK: 3 }
        if (target === 'compare') {
          const [current, candidate] = await Promise.all([
            queryPolicyEvidence({ ...request, indexTarget: 'current' }),
            queryPolicyEvidence({ ...request, indexTarget: 'candidate', candidateVersion: this.candidateVersion })
          ])
          turn.baseline = current.data.data
          turn.result = candidate.data.data
        } else {
          const response = await queryPolicyEvidence({
            ...request,
            indexTarget: target,
            candidateVersion: target === 'candidate' ? this.candidateVersion : ''
          })
          turn.result = response.data.data
        }
      } catch (_) {
        turn.error = '证据服务暂时不可用。已保留输入，请确认 AI 服务启动后重试。'
      } finally {
        this.loading = false
        this.trimHistory()
        this.$nextTick(this.scrollToLatest)
      }
    },
    trimHistory() {
      if (this.turns.length > 6) this.turns = this.turns.slice(-6)
    },
    scrollToLatest() {
      const area = this.$refs.conversation
      if (area) area.scrollTop = area.scrollHeight
    },
    evidenceLocation(item) {
      const path = (item.sectionPath || []).join(' / ')
      return [path, item.clauseId].filter(Boolean).join(' · ') || '正文'
    },
    uniqueLabels(values) {
      return Array.from(new Set(values || [])).slice(0, 3)
    },
    modeLabel(value) {
      return { hybrid: '混合检索', dense: '语义检索', bm25_fallback: '关键词降级', unavailable: '未获得结果', not_executed: '未执行' }[value] || value
    },
    cleanResultTitle(result) {
      return result.decision.code === 'input_guidance' ? '请补充评论或治理问题' : '未启动政策检索'
    },
    cleanResultDescription(result) {
      return result.decision.code === 'input_guidance'
        ? '例如：商家要求删除差评后才退款。信息明确后，系统再核对对应政策。'
        : '普通评论保持简洁，不展示无意义的政策卡片。'
    },
    formatScore(value) {
      const number = Number(value)
      return Number.isFinite(number) ? number.toFixed(4) : '-'
    },
    targetLabel(target) {
      return { current: '当前版本', candidate: '可对比版本', compare: '双版本对比' }[target] || '当前版本'
    },
    sourceSummary(result) {
      const sources = Array.from(new Set((result.evidence || []).map(item => item.sourceName))).slice(0, 2)
      return sources.length ? sources.join('、') : '未返回政策证据'
    },
    comparisonVerdict(turn) {
      const baseline = turn.baseline || {}
      const candidate = turn.result || {}
      const sameRisks = JSON.stringify([...(baseline.riskTypes || [])].sort()) === JSON.stringify([...(candidate.riskTypes || [])].sort())
      const sameDecision = baseline.evidenceStatus === candidate.evidenceStatus && baseline.decision && candidate.decision && baseline.decision.code === candidate.decision.code
      if (sameRisks && sameDecision) return { label: '业务判断保持一致', tag: '无明显退化', type: 'success' }
      if (candidate.evidenceStatus === 'supported' && baseline.evidenceStatus !== 'supported') return { label: '候选版本补足了政策依据', tag: '候选改善', type: 'success' }
      return { label: '两个版本结果存在差异', tag: '需要抽查', type: 'warning' }
    }
  }
}
</script>

<style lang="scss" scoped>
$ink: #172033;
$muted: #647084;
$line: #dce3ec;
$canvas: #f4f7fb;
$blue: #3159d9;
$teal: #118577;
$amber: #b66a08;
$red: #c83d4b;

.evidence-playground { color: $ink; background: $canvas; border: 1px solid $line; border-radius: 8px; overflow: hidden; font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; }
.playground-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 22px 24px 18px; background: #fff; border-bottom: 1px solid $line; }
.playground-head h2 { margin: 0; font: 700 24px/1.25 "Arial Narrow", "Segoe UI", sans-serif; letter-spacing: 0; }
.playground-head p:not(.eyebrow) { max-width: 720px; margin: 7px 0 0; color: $muted; font-size: 14px; line-height: 1.65; }
.eyebrow { margin: 0 0 6px; color: $blue; font: 700 12px/1.2 "SFMono-Regular", Consolas, monospace; }
.sandbox-mark { flex: 0 0 auto; padding: 8px 10px; color: #315469; background: #edf7f5; border: 1px solid #bce1da; border-radius: 6px; font-size: 12px; font-weight: 700; }
.playground-shell { display: grid; grid-template-columns: 236px minmax(0, 1fr); min-height: 650px; }
.query-bench { padding: 20px 16px; background: #eef2f7; border-right: 1px solid $line; }
.bench-section + .bench-section { margin-top: 24px; }
.bench-label { display: block; margin-bottom: 9px; color: #526075; font-size: 12px; font-weight: 700; }
.mode-switch { display: grid; }
.mode-switch ::v-deep .el-radio-button__inner { width: 100%; padding: 9px 8px; border-radius: 0; }
.mode-switch ::v-deep .el-radio-button:first-child .el-radio-button__inner { border-radius: 5px 5px 0 0; }
.mode-switch ::v-deep .el-radio-button:last-child .el-radio-button__inner { border-left: 1px solid #dcdfe6; border-radius: 0 0 5px 5px; }
.sample-section { display: grid; gap: 6px; }
.sample-row { display: flex; align-items: center; justify-content: space-between; min-height: 38px; padding: 0 10px; color: #344257; background: transparent; border: 1px solid transparent; border-radius: 5px; cursor: pointer; font: 600 13px/1.3 inherit; text-align: left; transition: background .16s, border-color .16s; }
.sample-row:hover, .sample-row:focus-visible { background: #fff; border-color: #bdc9d8; outline: none; }
.sample-row i { color: #8a96a8; }
.boundary-note { display: flex; gap: 8px; margin-top: 28px; padding-top: 16px; color: $muted; border-top: 1px solid #d3dbe6; font-size: 12px; line-height: 1.6; }
.index-hint { margin: 8px 0 0; color: $muted; font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
.boundary-note i { margin-top: 2px; color: $blue; }
.conversation-panel { display: grid; grid-template-rows: minmax(0, 1fr) auto; min-width: 0; background: #fff; }
.conversation-stream { max-height: 720px; min-height: 510px; padding: 24px clamp(18px, 3vw, 42px); overflow-y: auto; scroll-behavior: smooth; }
.welcome-state { display: grid; place-items: center; align-content: center; min-height: 430px; text-align: center; }
.welcome-symbol { display: grid; place-items: center; width: 56px; height: 56px; color: #fff; background: $blue; border-radius: 8px; box-shadow: 8px 8px 0 #cfd9f5; font-size: 24px; }
.welcome-state h3 { margin: 24px 0 7px; font-size: 19px; }
.welcome-state p { max-width: 450px; margin: 0; color: $muted; font-size: 13px; line-height: 1.7; }
.conversation-turn + .conversation-turn { margin-top: 34px; padding-top: 30px; border-top: 1px solid $line; }
.query-message { max-width: 760px; margin: 0 0 18px auto; padding: 13px 15px; background: #edf2ff; border-right: 3px solid $blue; border-radius: 6px 0 0 6px; }
.query-message span { color: $blue; font-size: 11px; font-weight: 700; }
.query-message p { margin: 5px 0 0; color: #26364e; font-size: 14px; line-height: 1.65; }
.comparison-band { margin-bottom: 14px; padding: 15px 18px; background: #f7fafc; border: 1px solid $line; border-left: 4px solid $teal; border-radius: 6px; }
.comparison-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.comparison-heading span, .comparison-columns span { color: $muted; font-size: 11px; }
.comparison-heading h3 { margin: 4px 0 0; font-size: 16px; }
.comparison-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 0; margin-top: 12px; border-top: 1px solid $line; }
.comparison-columns > div { padding: 12px 16px 0 0; min-width: 0; }
.comparison-columns > div + div { padding-left: 16px; border-left: 1px solid $line; }
.comparison-columns strong { display: block; margin-top: 4px; font-size: 13px; }
.comparison-columns p { margin: 4px 0 0; color: $muted; font-size: 12px; overflow-wrap: anywhere; }
.decision-band { display: flex; align-items: stretch; justify-content: space-between; gap: 20px; padding: 18px 20px; background: #f6f8fb; border: 1px solid $line; border-left: 4px solid $blue; border-radius: 6px; }
.decision-band.is-success { border-left-color: $teal; }
.decision-band.is-warning { border-left-color: $amber; }
.decision-band.is-danger { border-left-color: $red; }
.decision-copy > span, .section-heading span { color: $muted; font: 700 11px/1.2 "SFMono-Regular", Consolas, monospace; }
.decision-copy h3 { margin: 5px 0 6px; font-size: 18px; }
.decision-copy p { margin: 0; color: #536176; font-size: 13px; line-height: 1.65; }
.status-stamp { display: grid; min-width: 118px; place-content: center; padding-left: 18px; border-left: 1px solid $line; text-align: center; }
.status-stamp span { color: $muted; font-size: 11px; }
.status-stamp strong { margin-top: 6px; font-size: 14px; }
.risk-coverage, .evidence-section { margin-top: 24px; }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.section-heading h3 { margin: 4px 0 0; font-size: 16px; }
.section-heading small { color: $muted; font-size: 12px; }
.risk-list { border-top: 1px solid $line; }
.risk-row { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid $line; }
.risk-severity { display: grid; place-items: center; width: 27px; height: 27px; color: #fff; background: $ink; border-radius: 4px; font-size: 11px; font-weight: 700; }
.risk-row strong { font-size: 14px; }
.risk-row p { margin: 3px 0 0; color: $muted; font-size: 12px; line-height: 1.5; }
.evidence-chain { position: relative; margin: 0; padding: 0; list-style: none; }
.evidence-chain::before { position: absolute; top: 16px; bottom: 16px; left: 18px; width: 2px; content: ""; background: #c9d6e8; }
.evidence-item { position: relative; display: grid; grid-template-columns: 38px minmax(0, 1fr); gap: 14px; }
.evidence-item + .evidence-item { margin-top: 12px; }
.evidence-marker { z-index: 1; display: grid; place-items: center; width: 38px; height: 38px; color: #fff; background: $teal; border: 4px solid #fff; border-radius: 50%; font: 700 11px/1 "SFMono-Regular", Consolas, monospace; }
.evidence-body { min-width: 0; padding: 14px 16px; border: 1px solid $line; border-radius: 6px; }
.evidence-title { display: flex; justify-content: space-between; gap: 16px; }
.evidence-title strong, .evidence-title span { display: block; }
.evidence-title strong { font-size: 14px; }
.evidence-title span { margin-top: 4px; color: $muted; font-size: 12px; overflow-wrap: anywhere; }
.evidence-title a { flex: 0 0 auto; color: $blue; font-size: 12px; font-weight: 700; text-decoration: none; }
.snippet { margin: 12px 0; color: #3e4b5f; font-size: 13px; line-height: 1.75; }
.evidence-support { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; }
.evidence-support span { color: $muted; font-size: 11px; }
.evidence-support b { padding: 3px 7px; color: #23695f; background: #e9f6f3; border-radius: 4px; font-size: 11px; }
.clean-result, .empty-evidence, .result-error { display: flex; gap: 12px; margin-top: 18px; padding: 14px 16px; border-radius: 6px; }
.clean-result { color: #28695f; background: #edf8f5; border: 1px solid #bee3dc; }
.empty-evidence, .result-error { color: #8c3b45; background: #fff4f5; border: 1px solid #efc7cc; }
.clean-result i, .empty-evidence i, .result-error i { margin-top: 2px; font-size: 18px; }
.clean-result strong, .empty-evidence strong, .result-error strong { font-size: 13px; }
.clean-result p, .empty-evidence p, .result-error p { margin: 4px 0 0; font-size: 12px; line-height: 1.55; }
.technical-fold { margin-top: 14px; }
.technical-fold ::v-deep .el-collapse-item__header { color: $muted; font-size: 12px; }
.technical-fold dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin: 0 0 10px; }
.technical-fold dl div { padding: 9px; background: #f6f8fb; border-radius: 4px; }
.technical-fold dt { color: $muted; font-size: 10px; }
.technical-fold dd { margin: 4px 0 0; font: 600 11px/1.4 "SFMono-Regular", Consolas, monospace; overflow-wrap: anywhere; }
.evidence-tech { color: $muted; font: 11px/1.7 "SFMono-Regular", Consolas, monospace; overflow-wrap: anywhere; }
.thinking-state { display: flex; align-items: center; gap: 5px; padding: 14px 0; color: $muted; }
.turn-pending { display: flex; align-items: center; gap: 5px; min-height: 54px; padding: 14px 16px; color: $muted; background: #f6f8fb; border: 1px solid $line; border-radius: 6px; }
.thinking-state span, .turn-pending span { width: 7px; height: 7px; background: $blue; border-radius: 50%; animation: pulse 1s ease-in-out infinite; }
.thinking-state span:nth-child(2), .turn-pending span:nth-child(2) { animation-delay: .14s; }.thinking-state span:nth-child(3), .turn-pending span:nth-child(3) { animation-delay: .28s; }
.thinking-state p, .turn-pending p { margin: 0 0 0 7px; font-size: 12px; }
.query-composer { padding: 16px 20px; background: #f8fafc; border-top: 1px solid $line; }
.query-composer ::v-deep textarea { color: $ink; border-color: #bdc8d8; border-radius: 6px; font-family: inherit; line-height: 1.6; }
.query-composer ::v-deep textarea:focus { border-color: $blue; }
.composer-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 9px; }
.composer-foot span { color: #8792a2; font-size: 11px; }
@keyframes pulse { 0%, 100% { opacity: .28; transform: translateY(0); } 50% { opacity: 1; transform: translateY(-2px); } }
@media (prefers-reduced-motion: reduce) { .thinking-state span, .turn-pending span { animation: none; } .conversation-stream { scroll-behavior: auto; } }
@media (max-width: 900px) { .playground-shell { grid-template-columns: 1fr; }.query-bench { border-right: 0; border-bottom: 1px solid $line; }.sample-section { grid-template-columns: repeat(2, minmax(0, 1fr)); }.bench-label { grid-column: 1 / -1; }.boundary-note { margin-top: 18px; }.conversation-stream { min-height: 430px; }.technical-fold dl { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .playground-head, .decision-band, .evidence-title { display: block; }.sandbox-mark { display: inline-block; margin-top: 12px; }.playground-head { padding: 18px 16px; }.conversation-stream { padding: 18px 14px; }.status-stamp { margin-top: 14px; padding: 12px 0 0; border-top: 1px solid $line; border-left: 0; text-align: left; }.risk-row { grid-template-columns: 28px minmax(0, 1fr); }.risk-row .el-tag { grid-column: 2; justify-self: start; }.evidence-title a { display: inline-block; margin-top: 9px; }.technical-fold dl { grid-template-columns: 1fr 1fr; } }
</style>
