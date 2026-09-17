/* eslint-env jest */
import { documentStatuses, documentError, runBoundedUploads } from '@/utils/documentLibrary'
import DocumentLibrary from '@/views/ai-agentic-demo/document-library.vue'
import { buildDocumentIndex, documentDetail, documentIndexStatus, listDocuments, removeDocument, restoreBaseDocumentIndex, uploadDocument } from '@/api/documentLibrary'

jest.mock('@/api/documentLibrary', () => ({
  listDocuments: jest.fn(),
  documentDetail: jest.fn(),
  uploadDocument: jest.fn(),
  retryDocument: jest.fn(),
  removeDocument: jest.fn(),
  documentIndexStatus: jest.fn(),
  buildDocumentIndex: jest.fn(),
  publishDocumentIndex: jest.fn(),
  rollbackDocumentIndex: jest.fn(),
  restoreBaseDocumentIndex: jest.fn()
}))

afterEach(() => {
  jest.useRealTimers()
  jest.clearAllMocks()
})

function context() {
  const vm = { ...DocumentLibrary.data(), $message: { success: jest.fn() }, $refs: {}}
  Object.keys(DocumentLibrary.methods).forEach(name => { vm[name] = DocumentLibrary.methods[name].bind(vm) })
  Object.keys(DocumentLibrary.computed).forEach(name => Object.defineProperty(vm, name, { get: DocumentLibrary.computed[name].bind(vm) }))
  return vm
}

test('parsed is not published; error codes have readable explanations', () => {
  expect(documentStatuses.parsed.label).toContain('未发布')
  expect(documentError('DOCUMENT_PARSE_EXHAUSTED')).toContain('解析器')
  expect(documentError('unknown')).not.toContain('unknown')
  expect(documentStatuses.removed.label).toContain('下版移除')
})

test('list is backed by API and queue state schedules refresh', async() => {
  jest.useFakeTimers()
  listDocuments.mockResolvedValue({ data: { data: { list: [{ id: 'real-id', status: 'queued' }], total: 1 }}})
  documentIndexStatus.mockResolvedValue({ data: { data: { active: null, candidate: null, releases: [], parsedPolicyCandidates: 1 }}})
  const vm = context()
  await vm.load()
  expect(vm.items[0].id).toBe('real-id')
  expect(vm.timer).not.toBeNull()
  DocumentLibrary.beforeDestroy.call(vm)
})

test('detail failure clears previous document and stays usable', async() => {
  documentDetail.mockRejectedValue(new Error('offline'))
  const vm = context()
  vm.selected = { id: 'old' }
  await vm.open({ id: 'new' })
  expect(vm.selected).toBeNull()
  expect(vm.detailError).toContain('加载失败')
  expect(vm.detailLoading).toBe(false)
})

test('index status failure does not hide the document list', async() => {
  listDocuments.mockResolvedValue({ data: { data: { list: [{ id: 'still-visible', status: 'parsed' }], total: 1 }}})
  documentIndexStatus.mockRejectedValue(new Error('index offline'))
  const vm = context()
  await vm.load()
  expect(vm.items[0].id).toBe('still-visible')
  expect(vm.indexError).toContain('索引状态')
  expect(vm.error).toBe('')
})

test('candidate build is submitted once and refreshes status', async() => {
  buildDocumentIndex.mockResolvedValue({ data: { data: { noOp: false }}})
  const vm = context()
  vm.indexState.parsedPolicyCandidates = 1
  vm.load = jest.fn().mockResolvedValue()
  await vm.buildIndex()
  expect(buildDocumentIndex).toHaveBeenCalledTimes(1)
  expect(vm.load).toHaveBeenCalledTimes(1)
  expect(vm.indexAction).toBe('')
})

test('index state exposes unpublished lifecycle changes', () => {
  const vm = context()
  vm.indexState.hasUnpublishedChanges = true
  expect(vm.indexState.hasUnpublishedChanges).toBe(true)
})

test('runtime state distinguishes effective, switching and failed index versions', () => {
  const vm = context()
  vm.indexState.runtime = { desiredIndexVersion: 'policy-v2', loadedIndexVersion: 'policy-v2', reloadStatus: 'ready', loadedChunkCount: 951 }
  expect(vm.runtimeState.label).toContain('已生效')
  expect(vm.runtimeState.detail).toContain('951')

  vm.indexState.runtime = { desiredIndexVersion: 'policy-v3', loadedIndexVersion: 'policy-v2', reloadStatus: 'loading' }
  expect(vm.runtimeState.label).toContain('正在切换')

  vm.indexState.runtime = { desiredIndexVersion: 'policy-v3', loadedIndexVersion: 'policy-v2', reloadStatus: 'failed' }
  expect(vm.runtimeState.label).toContain('上一版本')
  expect(vm.runtimeState.detail).toContain('policy-v2')
})

test('active managed index can be restored to the system base library', async() => {
  restoreBaseDocumentIndex.mockResolvedValue({ data: { data: { restoredBase: true }}})
  const vm = context()
  vm.indexState.activeRelease = { version: 'policy-v1' }
  vm.$confirm = jest.fn().mockResolvedValue()
  vm.load = jest.fn().mockResolvedValue()

  await vm.restoreBaseIndex()

  expect(restoreBaseDocumentIndex).toHaveBeenCalledTimes(1)
  expect(vm.$confirm.mock.calls[0][0]).toContain('基础政策库')
  expect(vm.load).toHaveBeenCalledTimes(1)
  expect(vm.indexAction).toBe('')
})

test('release evaluation is summarized for operators without exposing raw risk codes', () => {
  const vm = context()
  vm.indexState.candidateRelease = {
    releaseEvaluation: {
      decision: 'review_required',
      decisionLabel: '建议抽查后发布',
      reasonCodes: ['OVERALL_EVIDENCE_COVERAGE_LOW'],
      candidate: { metrics: { caseCount: 12, passedCaseCount: 11 }, cases: [{ caseId: 'c1', query: '删除差评', passed: false, unsupportedRiskTypes: ['review_suppression'] }] },
      comparison: { available: true, regressionCount: 1 }
    }
  }
  expect(vm.candidateEvaluation.decisionLabel).toBe('建议抽查后发布')
  expect(vm.failedReleaseCases).toHaveLength(1)
  expect(vm.riskLabels(vm.failedReleaseCases[0].unsupportedRiskTypes)).toBe('压制差评')
  expect(vm.releaseReason('OVERALL_EVIDENCE_COVERAGE_LOW')).toContain('整体业务风险覆盖')
  expect(vm.indexStatus(vm.candidateRelease).label).toBe('待抽查')
})

test('explicit release roles separate a legacy row from the verified comparison version', () => {
  const vm = context()
  vm.indexState.candidate = { version: 'legacy-ready', status: 'ready' }
  vm.indexState.candidateRelease = null
  vm.indexState.comparableRelease = { version: 'verified-history', status: 'superseded' }
  vm.indexState.historyReleases = [{ version: 'verified-history', status: 'superseded' }]

  expect(vm.candidateRelease).toBeNull()
  expect(vm.comparableRelease.version).toBe('verified-history')
  expect(vm.historyReleases).toHaveLength(1)
})

test('document removal is confirmed and only marks the next release', async() => {
  removeDocument.mockResolvedValue({ data: { data: { status: 'removed' }}})
  const vm = context()
  vm.$confirm = jest.fn().mockResolvedValue()
  vm.load = jest.fn().mockResolvedValue()
  await vm.remove({ id: 'policy-1' })
  expect(removeDocument).toHaveBeenCalledWith('policy-1')
  expect(vm.$confirm.mock.calls[0][0]).toContain('下一候选索引')
  expect(vm.load).toHaveBeenCalledTimes(1)
})

test('invalid size never submits upload', async() => {
  const vm = context()
  vm.chooseFile({ target: { files: [{ name: 'large.pdf', size: 21 * 1024 * 1024 }], value: 'large.pdf' }})
  expect(uploadDocument).not.toHaveBeenCalled()
  expect(vm.uploadError).toContain('20 MB')
})

test('more than 100 files is rejected before upload', () => {
  const vm = context()
  vm.chooseFile({ target: { files: Array.from({ length: 101 }, (_, index) => ({ name: `${index}.txt`, size: 1 })), value: 'many' }})
  expect(vm.files).toHaveLength(0)
  expect(vm.uploadError).toContain('100')
})

test('bounded uploader keeps at most three requests active and preserves failures', async() => {
  let active = 0
  let maximum = 0
  const files = Array.from({ length: 12 }, (_, index) => ({ index }))
  const result = await runBoundedUploads(files, async file => {
    active++
    maximum = Math.max(maximum, active)
    await new Promise(resolve => setTimeout(resolve, 2))
    active--
    if (file.index === 7) throw new Error('failed')
    return file.index
  }, 3)
  expect(maximum).toBe(3)
  expect(result.succeeded).toHaveLength(11)
  expect(result.failed.map(item => item.index)).toEqual([7])
})

test('unsafe source cannot become clickable link', () => {
  expect(context().safeUrl('javascript:alert(1)')).toBe('')
})
