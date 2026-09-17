<template>
  <section class="document-library">
    <div class="index-panel">
      <div class="index-summary">
        <div>
          <h2>知识索引</h2>
          <p v-if="activeRelease">当前版本 {{ activeRelease.version }}，包含 {{ activeRelease.chunkCount }} 个证据片段。</p>
          <p v-else>当前使用系统基础政策库，新版本发布前不会影响审核。</p>
          <p>已有 {{ indexState.parsedPolicyCandidates || 0 }} 份候选政策完成解析。</p>
          <div class="runtime-state" :class="`runtime-state--${runtimeState.tone}`">
            <i :class="runtimeState.icon" aria-hidden="true" />
            <span>{{ runtimeState.label }}</span>
            <small v-if="runtimeState.detail">{{ runtimeState.detail }}</small>
          </div>
        </div>
        <div class="index-actions">
          <el-button v-if="activeRelease" plain icon="el-icon-refresh-left" :loading="indexAction === 'restore-base'" @click="restoreBaseIndex">恢复基础政策库</el-button>
          <el-button type="primary" plain icon="el-icon-cpu" :loading="indexAction === 'build'" :disabled="indexBusy || (!indexState.parsedPolicyCandidates && !activeRelease)" @click="buildIndex">构建候选索引</el-button>
        </div>
      </div>
      <el-alert v-if="indexState.hasUnpublishedChanges" title="文件集合有未发布变更：请先构建候选索引，通过质量检查后再发布。当前审核索引不受影响。" type="info" :closable="false" show-icon />
      <el-alert v-if="indexError" :title="indexError" type="error" :closable="false" show-icon />
      <div v-if="candidateRelease" class="candidate-row">
        <div>
          <el-tag :type="indexStatus(candidateRelease).type" size="small">{{ indexStatus(candidateRelease).label }}</el-tag>
          <strong>{{ candidateRelease.version }}</strong>
          <span>{{ candidateRelease.documentCount }} 份文件 · {{ candidateRelease.chunkCount || 0 }} 个片段</span>
        </div>
        <el-button v-if="candidateRelease.canPublish" type="success" icon="el-icon-check" :loading="indexAction === 'publish'" @click="publishIndex(candidateRelease)">发布此版本</el-button>
      </div>
      <p v-else-if="comparableRelease" class="comparison-line">暂无待发布版本；最近已验收版本 {{ comparableRelease.version }} 可在证据试查台进行双版本对比。</p>
      <el-alert v-if="candidateRelease && candidateRelease.evaluationMissing" title="该候选由旧构建流程生成，缺少发布验收结果。请重新构建，暂不可发布。" type="warning" :closable="false" show-icon />
      <section v-if="candidateEvaluation" class="release-decision" :class="`release-decision--${candidateEvaluation.decision}`">
        <div class="release-decision__heading">
          <div>
            <span class="release-decision__eyebrow">候选索引验收</span>
            <h3>{{ candidateEvaluation.decisionLabel }}</h3>
            <p>{{ releaseSummary(candidateEvaluation) }}</p>
          </div>
          <i :class="releaseDecisionIcon(candidateEvaluation.decision)" aria-hidden="true" />
        </div>
        <div class="release-facts">
          <div><span>业务问题</span><strong>{{ candidateMetrics.passedCaseCount || 0 }} / {{ candidateMetrics.caseCount || 0 }}</strong></div>
          <div><span>关键风险覆盖</span><strong>{{ percentage(candidateMetrics.criticalCoverageAt5) }}</strong></div>
          <div><span>引用完整</span><strong>{{ percentage(candidateMetrics.citationValidRate) }}</strong></div>
          <div><span>相比当前版本退化</span><strong>{{ candidateComparison.regressionCount || 0 }} 条</strong></div>
        </div>
        <p v-if="candidateComparison.available" class="comparison-line">相比当前版本：新增解决 {{ candidateComparison.improvementCount || 0 }} 条，保持 {{ candidateComparison.unchangedCount || 0 }} 条，退化 {{ candidateComparison.regressionCount || 0 }} 条。</p>
        <p v-else class="comparison-line">当前没有可比较的已发布版本，本次结论仅依据固定业务验收集。</p>
        <el-collapse v-if="failedReleaseCases.length || candidateEvaluation.reasonCodes.length" class="release-details">
          <el-collapse-item :title="`查看未通过项（${failedReleaseCases.length}）`" name="failed-cases">
            <div v-for="item in failedReleaseCases" :key="item.caseId" class="failed-case">
              <strong>{{ item.query }}</strong>
              <span>缺少依据：{{ riskLabels(item.unsupportedRiskTypes) }}</span>
            </div>
            <p v-for="code in candidateEvaluation.reasonCodes" :key="code" class="reason-line">{{ releaseReason(code) }}</p>
          </el-collapse-item>
        </el-collapse>
        <el-collapse class="technical-details">
          <el-collapse-item title="技术详情" name="technical">
            <dl>
              <dt>验收集</dt><dd>{{ candidateEvaluation.suite ? candidateEvaluation.suite.name : '-' }}</dd>
              <dt>检索模式</dt><dd>{{ candidateEvaluation.candidate ? candidateEvaluation.candidate.retrievalMode : '-' }}</dd>
              <dt>验收集指纹</dt><dd>{{ shortHash(candidateEvaluation.suite && candidateEvaluation.suite.sha256) }}</dd>
            </dl>
          </el-collapse-item>
        </el-collapse>
      </section>
      <el-alert v-if="candidateRelease && candidateRelease.status === 'failed'" title="候选版本未通过构建或质量检查，当前审核索引没有改变。" type="warning" :closable="false" show-icon />
      <el-collapse v-if="historyReleases.some(item => item.canRollback)">
        <el-collapse-item title="历史可回滚版本" name="history">
          <div v-for="item in historyReleases.filter(row => row.canRollback)" :key="item.id" class="history-row">
            <span>{{ item.version }} · {{ item.chunkCount }} 个片段</span>
            <el-button type="text" :loading="indexAction === item.id" @click="rollbackIndex(item)">回滚到此版本</el-button>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
    <div class="document-toolbar">
      <h2>导入文件</h2>
      <div>
        <el-button icon="el-icon-refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" icon="el-icon-upload2" @click="uploadVisible = true">上传文件</el-button>
      </div>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-table v-loading="loading" :data="items" empty-text="暂无导入文件" row-key="id">
      <el-table-column prop="fileName" label="文件" min-width="230" show-overflow-tooltip />
      <el-table-column label="用途" min-width="120"><template slot-scope="scope">{{ usages[scope.row.usageType] || '参考资料' }}</template></el-table-column>
      <el-table-column label="处理状态" min-width="170"><template slot-scope="scope"><el-tag :type="status(scope.row).type" size="small">{{ status(scope.row).label }}</el-tag></template></el-table-column>
      <el-table-column label="处理方式" min-width="110"><template slot-scope="scope"><el-tag :type="execution(scope.row).type" effect="plain" size="small">{{ execution(scope.row).label }}</el-tag></template></el-table-column>
      <el-table-column prop="sourceName" label="来源名称" min-width="180" show-overflow-tooltip />
      <el-table-column label="操作" width="210">
        <template slot-scope="scope">
          <el-button type="text" icon="el-icon-document" @click="open(scope.row)">详情</el-button>
          <el-button v-if="scope.row.canRetry" type="text" icon="el-icon-refresh-right" :disabled="retrying === scope.row.id" @click="retry(scope.row)">重试</el-button>
          <el-button v-if="scope.row.canRemove" type="text" icon="el-icon-delete" :disabled="removing === scope.row.id" @click="remove(scope.row)">下线</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination :current-page="page" :page-size="20" :total="total" layout="prev, pager, next, total" @current-change="changePage" />

    <el-dialog title="上传文件" :visible.sync="uploadVisible" width="min(560px, 94vw)" :close-on-click-modal="!uploading" :show-close="!uploading" :close-on-press-escape="!uploading">
      <el-form label-position="top" @submit.native.prevent>
        <el-form-item label="文件（最多 100 个，单个不超过 20 MB）">
          <input ref="fileInput" type="file" multiple :disabled="uploading" accept=".pdf,.docx,.pptx,.xlsx,.csv,.md,.markdown,.txt,.html,.htm,.png,.jpg,.jpeg,.tif,.tiff,.webp" @change="chooseFile">
          <p v-if="files.length" class="file-selection">已选择 {{ files.length }} 个文件</p>
        </el-form-item>
        <el-form-item label="来源名称"><el-input v-model="metadata.sourceName" maxlength="255" :disabled="uploading" /></el-form-item>
        <el-form-item label="来源链接（选填）"><el-input v-model="metadata.sourceUrl" maxlength="2048" :disabled="uploading" placeholder="https://" /></el-form-item>
        <el-form-item label="资料用途"><el-select v-model="metadata.usageType" :disabled="uploading"><el-option v-for="(label, value) in usages" :key="value" :label="label" :value="value" /></el-select></el-form-item>
      </el-form>
      <el-progress v-if="uploading" :percentage="uploadPercentage" :status="uploadFailed ? 'exception' : undefined" />
      <el-alert v-if="uploadError" :title="uploadError" type="error" :closable="false" />
      <div slot="footer"><el-button :disabled="uploading" @click="uploadVisible = false">取消</el-button><el-button type="primary" icon="el-icon-upload2" :loading="uploading" :disabled="!files.length" @click="upload">上传 {{ files.length || '' }}</el-button></div>
    </el-dialog>

    <el-dialog title="文件详情" :visible.sync="detailVisible" width="min(880px, 94vw)">
      <div v-loading="detailLoading">
        <el-alert v-if="detailError" :title="detailError" type="error" :closable="false" />
        <template v-if="selected">
          <h3>{{ selected.fileName }}</h3>
          <el-tag :type="status(selected).type">{{ status(selected).label }}</el-tag>
          <dl class="file-facts">
            <dt>来源</dt><dd>{{ selected.sourceName }}</dd>
            <dt>用途</dt><dd>{{ usages[selected.usageType] }}</dd>
            <dt>审核使用状态</dt><dd>{{ selected.published ? `已发布至 ${selected.indexVersion}` : '未发布，不参与当前审核' }}</dd>
            <template v-if="safeUrl(selected.sourceUrl)"><dt>原始来源</dt><dd><a :href="safeUrl(selected.sourceUrl)" target="_blank" rel="noopener noreferrer">查看来源 <i class="el-icon-link" /></a></dd></template>
          </dl>
          <el-alert v-if="selected.errorCode" :title="errorLabel(selected.errorCode)" type="warning" :closable="false" show-icon />
          <el-alert v-if="selected.status === 'removed'" title="该来源已标记下线；发布下一候选索引后才会停止参与审核，当前线上版本保持不变。" type="info" :closable="false" show-icon />
          <p v-if="selected.status === 'failed' && !selected.canRetry">已达到 3 次尝试上限，请检查文件或解析环境。</p>
          <template v-if="selected.status === 'parsed'">
            <h4>正文预览</h4>
            <pre class="document-preview">{{ selected.preview }}</pre>
            <p v-if="selected.previewTruncated">预览已截取，完整解析结果保留在文件任务中。</p>
            <el-collapse><el-collapse-item title="结构与定位" name="structure">
              <el-table :data="selected.outline || []" size="small">
                <el-table-column label="章节路径" min-width="150"><template slot-scope="scope">{{ (scope.row.sectionPath || []).join(' / ') || '正文' }}</template></el-table-column>
                <el-table-column prop="pageNumber" label="页码" width="65" />
                <el-table-column prop="sourceRef" label="原文位置" min-width="160" show-overflow-tooltip />
                <el-table-column prop="text" label="内容" min-width="240" show-overflow-tooltip />
              </el-table>
            </el-collapse-item></el-collapse>
          </template>
        </template>
      </div>
    </el-dialog>
  </section>
</template>

<script>
import { listDocuments, documentDetail, uploadDocument, retryDocument, removeDocument, documentIndexStatus, buildDocumentIndex, publishDocumentIndex, rollbackDocumentIndex, restoreBaseDocumentIndex } from '@/api/documentLibrary'
import { documentStatuses, documentUsages, documentExecutionClasses, documentError, runBoundedUploads } from '@/utils/documentLibrary'
import { riskTypeLabel } from '@/utils/aiDisplayMap'

export default {
  name: 'DocumentLibrary',
  data() {
    return { items: [], total: 0, page: 1, loading: false, error: '', timer: null, disposed: false,
      uploadVisible: false, files: [], uploading: false, uploadTotal: 0, uploadCompleted: 0, uploadFailed: 0, uploadError: '', retrying: '', removing: '', usages: documentUsages,
      metadata: { sourceName: '', sourceUrl: '', usageType: 'reference' },
      selected: null, detailVisible: false, detailLoading: false, detailError: '', detailRequest: 0,
      indexState: { active: null, candidate: null, releases: [], activeRelease: null, candidateRelease: null, comparableRelease: null, historyReleases: [], parsedPolicyCandidates: 0, runtime: null }, indexAction: '', indexError: '' }
  },
  computed: {
    uploadPercentage() { return this.uploadTotal ? Math.round(this.uploadCompleted * 100 / this.uploadTotal) : 0 },
    activeRelease() { return this.indexState.activeRelease !== undefined ? this.indexState.activeRelease : this.indexState.active },
    candidateRelease() { return this.indexState.candidateRelease !== undefined ? this.indexState.candidateRelease : this.indexState.candidate },
    comparableRelease() { return this.indexState.comparableRelease || null },
    historyReleases() { return this.indexState.historyReleases || this.indexState.releases || [] },
    indexBusy() { return Boolean(this.candidateRelease && ['queued', 'building'].includes(this.candidateRelease.status)) },
    candidateEvaluation() { return this.candidateRelease && this.candidateRelease.releaseEvaluation },
    candidateMetrics() { return this.candidateEvaluation && this.candidateEvaluation.candidate ? this.candidateEvaluation.candidate.metrics || {} : {} },
    candidateComparison() { return this.candidateEvaluation ? this.candidateEvaluation.comparison || {} : {} },
    failedReleaseCases() { return this.candidateEvaluation && this.candidateEvaluation.candidate ? (this.candidateEvaluation.candidate.cases || []).filter(item => !item.passed) : [] },
    runtimeState() {
      const runtime = this.indexState.runtime || {}
      const desired = runtime.desiredIndexVersion || ''
      const loaded = runtime.loadedIndexVersion || ''
      if (runtime.reloadStatus === 'failed') return { tone: 'danger', icon: 'el-icon-warning-outline', label: '新版本切换失败，审核仍使用上一版本', detail: loaded ? `当前：${this.runtimeVersionLabel(loaded)}` : '' }
      if (['loading', 'pending'].includes(runtime.reloadStatus) || (desired && loaded && desired !== loaded)) return { tone: 'warning', icon: 'el-icon-loading', label: '审核链路正在切换知识版本', detail: loaded ? `切换前：${this.runtimeVersionLabel(loaded)}` : '' }
      if (runtime.reloadStatus === 'ready' && desired && desired === loaded) return { tone: 'success', icon: 'el-icon-circle-check', label: '已发布且审核链路已生效', detail: `${this.runtimeVersionLabel(loaded)} · ${runtime.loadedChunkCount || 0} 个片段` }
      return { tone: 'muted', icon: 'el-icon-info', label: '暂未取得审核链路运行状态', detail: '' }
    }
  },
  mounted() { this.load() },
  beforeDestroy() { this.disposed = true; clearTimeout(this.timer); this.detailRequest++ },
  methods: {
    indexStatus(row) {
      const labels = { queued: ['等待构建', 'info'], building: ['正在构建', 'warning'], ready: ['质量检查通过', 'success'], failed: ['构建失败', 'danger'], active: ['使用中', 'success'], superseded: ['历史版本', 'info'] }
      if (row.releaseEvaluation && row.releaseEvaluation.decision === 'blocked') return { label: '验收未通过', type: 'danger' }
      if (row.releaseEvaluation && row.releaseEvaluation.decision === 'review_required') return { label: '待抽查', type: 'warning' }
      const value = labels[row.status] || ['待确认', 'info']
      return { label: value[0], type: value[1] }
    },
    percentage(value) { return `${Math.round(Number(value || 0) * 100)}%` },
    shortHash(value) { return value ? `${String(value).slice(0, 10)}…` : '-' },
    runtimeVersionLabel(value) { return value === 'base' ? '系统基础政策库' : value },
    riskLabels(values) { return (values || []).map(riskTypeLabel).join('、') || '无' },
    releaseDecisionIcon(decision) {
      return { recommended: 'el-icon-circle-check', review_required: 'el-icon-warning-outline', blocked: 'el-icon-circle-close' }[decision] || 'el-icon-info'
    },
    releaseSummary(evaluation) {
      const metrics = evaluation.candidate && evaluation.candidate.metrics ? evaluation.candidate.metrics : {}
      if (evaluation.decision === 'recommended') return `固定业务问题通过 ${metrics.passedCaseCount || 0}/${metrics.caseCount || 0}，未发现关键风险依据缺失或版本退化。`
      if (evaluation.decision === 'review_required') return '关键风险依据完整，但存在普通问题未通过或相较当前版本退化，请抽查后决定是否发布。'
      return '候选索引缺少关键业务依据、引用不完整或检索链路异常，禁止进入审核链路。'
    },
    releaseReason(code) {
      const labels = {
        CRITICAL_RISK_EVIDENCE_MISSING: '关键风险缺少可引用的政策依据。',
        OVERALL_EVIDENCE_COVERAGE_LOW: '整体业务风险覆盖未达到发布标准。',
        CITATION_INCOMPLETE: '部分证据缺少来源、条款路径或内容指纹。',
        RETRIEVAL_FAILED: '验收过程中存在检索失败。',
        HYBRID_RETRIEVAL_DEGRADED: '混合检索发生降级，未按候选发布标准运行。',
        CRITICAL_CASE_REGRESSION: '关键业务问题相较当前版本发生退化。',
        DENSE_INDEX_UNAVAILABLE: '稠密索引不可用，候选版本无法完成验收。'
      }
      return labels[code] || '候选版本存在未通过的发布检查。'
    },
    status(row) { return documentStatuses[row.status] || { label: '待确认', type: 'info' } },
    execution(row) { return documentExecutionClasses[row.executionClass] || documentExecutionClasses.heavy },
    errorLabel: documentError,
    safeUrl(value) { return /^https?:\/\//i.test(value || '') ? value : '' },
    async load() {
      if (this.loading || this.disposed) return
      clearTimeout(this.timer)
      this.loading = true
      this.error = ''
      try {
        const [response, indexResponse] = await Promise.all([
          listDocuments({ page: this.page, limit: 20 }),
          documentIndexStatus().catch(() => null)
        ])
        if (this.disposed) return
        this.items = response.data.data.list
        this.total = response.data.data.total
        if (indexResponse) this.indexState = indexResponse.data.data
        else this.indexError = '索引状态暂时不可用，文件列表仍可正常操作。'
        const runtime = this.indexState.runtime || {}
        if (this.items.some(item => ['queued', 'running'].includes(item.status)) || this.indexBusy || ['loading', 'pending'].includes(runtime.reloadStatus) || (runtime.desiredIndexVersion && runtime.loadedIndexVersion && runtime.desiredIndexVersion !== runtime.loadedIndexVersion)) this.timer = setTimeout(() => this.load(), 4000)
      } catch (_) { this.error = '文件列表加载失败，请稍后刷新。' } finally { this.loading = false }
    },
    changePage(value) { this.page = value; this.load() },
    async buildIndex() {
      if (this.indexBusy) return
      this.indexAction = 'build'; this.indexError = ''
      try {
        const response = await buildDocumentIndex()
        await this.load()
        this.$message.success(response.data.data.noOp ? '当前文件集合与已有索引一致，无需重复构建' : '候选索引已进入后台构建队列')
      } catch (_) { this.indexError = '候选索引未能开始，请确认文件状态和索引服务。' } finally { this.indexAction = '' }
    },
    async publishIndex(row) {
      const needsReview = row.releaseEvaluation && row.releaseEvaluation.decision === 'review_required'
      const message = needsReview
        ? '该版本建议抽查后发布。请确认已核对未通过项；发布后会参与后续审核，当前版本仍保留用于回滚。'
        : '发布后，新版本将参与后续审核。当前版本会保留用于回滚。'
      try { await this.$confirm(message, '确认发布', { type: needsReview ? 'warning' : 'info' }) } catch (_) { return }
      this.indexAction = 'publish'; this.indexError = ''
      try { await publishDocumentIndex(row.id); await this.load(); this.$message.success('知识索引已安全切换') } catch (_) { this.indexError = '发布失败，当前审核索引保持不变。' } finally { this.indexAction = '' }
    },
    async rollbackIndex(row) {
      try { await this.$confirm(`确认回滚到 ${row.version}？`, '确认回滚', { type: 'warning' }) } catch (_) { return }
      this.indexAction = row.id; this.indexError = ''
      try { await rollbackDocumentIndex(row.id); await this.load(); this.$message.success('已回滚到所选版本') } catch (_) { this.indexError = '回滚失败，当前审核索引保持不变。' } finally { this.indexAction = '' }
    },
    async restoreBaseIndex() {
      try { await this.$confirm('确认恢复系统基础政策库？当前版本会保留在历史列表中，可随时重新启用。', '确认恢复', { type: 'warning' }) } catch (_) { return }
      this.indexAction = 'restore-base'; this.indexError = ''
      try { await restoreBaseDocumentIndex(); await this.load(); this.$message.success('已恢复系统基础政策库') } catch (_) { this.indexError = '恢复失败，当前审核索引保持不变。' } finally { this.indexAction = '' }
    },
    chooseFile(event) {
      const files = Array.from(event.target.files || [])
      this.uploadError = ''
      if (files.length > 100) {
        this.files = []
        event.target.value = ''
        this.uploadError = '单次最多选择 100 个文件。'
        return
      }
      const invalid = files.find(file => !file.size || file.size > 20 * 1024 * 1024)
      if (invalid) {
        this.files = []
        event.target.value = ''
        this.uploadError = `${invalid.name || '文件'}为空或超过 20 MB。`
        return
      }
      this.files = files
    },
    async upload() {
      if (!this.files.length || this.uploading) return
      if (this.metadata.sourceUrl && !this.safeUrl(this.metadata.sourceUrl)) { this.uploadError = '来源链接需以 http:// 或 https:// 开头。'; return }
      this.uploading = true
      this.uploadTotal = this.files.length
      this.uploadCompleted = 0
      this.uploadFailed = 0
      this.uploadError = ''
      try {
        const result = await runBoundedUploads(this.files, async file => {
          try { return await uploadDocument(file, this.metadata) } catch (error) { this.uploadFailed++; throw error } finally { this.uploadCompleted++ }
        })
        const total = this.files.length
        if (!result.failed.length) this.uploadVisible = false
        this.files = []
        if (this.$refs.fileInput) this.$refs.fileInput.value = ''
        this.page = 1
        await this.load()
        if (result.failed.length) this.uploadError = `${total - result.failed.length} 个文件已进入队列，${result.failed.length} 个上传失败，可重新选择失败文件。`
        else this.$message.success(`${total} 个文件已进入处理队列`)
      } catch (_) { this.uploadError = '上传未完成，请检查文件、来源信息及服务状态。' } finally { this.uploading = false }
    },
    async open(row) {
      const request = ++this.detailRequest
      this.detailVisible = true
      this.detailLoading = true
      this.detailError = ''
      this.selected = null
      try {
        const response = await documentDetail(row.id)
        if (request === this.detailRequest) this.selected = response.data.data
      } catch (_) { if (request === this.detailRequest) this.detailError = '详情加载失败，请关闭后重试。' } finally { if (request === this.detailRequest) this.detailLoading = false }
    },
    async retry(row) {
      if (this.retrying) return
      this.retrying = row.id
      try { await retryDocument(row.id); await this.load() } catch (_) { this.error = '重试未提交，请刷新后确认任务状态。' } finally { this.retrying = '' }
    },
    async remove(row) {
      if (this.removing) return
      try { await this.$confirm('下线将在下一候选索引发布后生效，当前审核索引不会立即改变。', '确认下线', { type: 'warning' }) } catch (_) { return }
      this.removing = row.id
      try {
        await removeDocument(row.id)
        await this.load()
        this.$message.success('已标记下线，请构建并发布候选索引以生效')
      } catch (_) { this.error = '文件下线失败，请确认任务当前未在解析。' } finally { this.removing = '' }
    }
  }
}
</script>

<style scoped>
.document-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.index-panel { margin-bottom: 24px; padding: 16px 0; border-bottom: 1px solid #dcdfe6; }
.index-summary, .candidate-row, .history-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.index-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.index-summary p { margin: 6px 0 0; color: #606266; }
.runtime-state { display: flex; align-items: center; gap: 7px; margin-top: 10px; font-size: 13px; }
.runtime-state small { color: #909399; }
.runtime-state--success { color: #16856b; }
.runtime-state--warning { color: #b26a00; }
.runtime-state--danger { color: #c23b4a; }
.runtime-state--muted { color: #606266; }
.candidate-row { margin-top: 14px; padding: 12px; background: #f5f7fa; border-left: 3px solid #409eff; }
.candidate-row > div { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0; }
.candidate-row strong, .history-row span { overflow-wrap: anywhere; }
.history-row { padding: 8px 0; border-bottom: 1px solid #ebeef5; }
.release-decision { margin: 12px 0; padding: 18px 20px; border: 1px solid #dcdfe6; border-left-width: 4px; background: #fff; }
.release-decision--recommended { border-left-color: #16856b; }
.release-decision--review_required { border-left-color: #c27a0a; }
.release-decision--blocked { border-left-color: #c23b4a; }
.release-decision__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.release-decision__heading h3 { margin: 3px 0 7px; font-size: 22px; }
.release-decision__heading p { margin: 0; color: #606266; line-height: 1.6; }
.release-decision__heading > i { font-size: 30px; color: #606266; }
.release-decision__eyebrow { color: #606266; font-size: 12px; }
.release-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; margin-top: 18px; border-top: 1px solid #ebeef5; border-bottom: 1px solid #ebeef5; }
.release-facts > div { padding: 14px 16px 14px 0; min-width: 0; }
.release-facts span { display: block; margin-bottom: 4px; color: #606266; font-size: 13px; }
.release-facts strong { font-size: 18px; overflow-wrap: anywhere; }
.comparison-line { margin: 14px 0 0; color: #303133; }
.release-details, .technical-details { margin-top: 8px; }
.failed-case { display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-bottom: 1px solid #ebeef5; }
.failed-case span, .reason-line { color: #606266; }
.technical-details dl { display: grid; grid-template-columns: 100px minmax(0, 1fr); gap: 8px 16px; margin: 0; }
.technical-details dt { color: #606266; }
.technical-details dd { margin: 0; overflow-wrap: anywhere; }
h2 { margin: 0; font-size: 18px; }
h3 { overflow-wrap: anywhere; }
.file-facts { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 12px; }
.file-facts dt { color: #606266; }
.file-facts dd { margin: 0; overflow-wrap: anywhere; }
.document-preview { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 360px; overflow: auto; background: #f5f7fa; border: 1px solid #e4e7ed; padding: 16px; font: 14px/1.8 inherit; }
.el-pagination { margin-top: 16px; overflow-x: auto; }
input[type=file] { max-width: 100%; }
.file-selection { margin: 8px 0 0; color: #606266; }
@media (max-width: 900px) {
  .release-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .failed-case { display: block; }
  .failed-case span { display: block; margin-top: 5px; }
}
</style>
