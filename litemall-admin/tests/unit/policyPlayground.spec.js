/* eslint-env jest */
import EvidencePlayground from '@/views/ai-agentic-demo/evidence-playground.vue'
import { queryPolicyEvidence } from '@/api/policyPlayground'
import { documentIndexStatus } from '@/api/documentLibrary'
import { evidenceTone, safePolicyUrl, shortHash } from '@/utils/policyPlayground'

jest.mock('@/api/policyPlayground', () => ({ queryPolicyEvidence: jest.fn() }))
jest.mock('@/api/documentLibrary', () => ({ documentIndexStatus: jest.fn() }))

function context() {
  const vm = { ...EvidencePlayground.data(), $refs: {}, $nextTick: callback => callback && callback() }
  Object.keys(EvidencePlayground.methods).forEach(name => { vm[name] = EvidencePlayground.methods[name].bind(vm) })
  Object.keys(EvidencePlayground.computed || {}).forEach(name => Object.defineProperty(vm, name, { get: EvidencePlayground.computed[name].bind(vm) }))
  return vm
}

afterEach(() => jest.clearAllMocks())

test('unsafe citations never become clickable', () => {
  expect(safePolicyUrl('javascript:alert(1)')).toBe('')
  expect(safePolicyUrl('https://example.org/policy')).toContain('https://')
})

test('business statuses have stable tones and hashes stay compact', () => {
  expect(evidenceTone('supported')).toBe('success')
  expect(evidenceTone('mismatch')).toBe('danger')
  expect(shortHash('1234567890abcdef')).toBe('1234567890ab')
})

test('query result is appended without creating a business task', async() => {
  queryPolicyEvidence.mockResolvedValue({ data: { data: {
    isolated: true,
    decision: { label: '建议人工确认', tone: 'warning' },
    risks: [],
    evidence: [],
    evidenceStatus: 'insufficient',
    evidenceStatusLabel: '证据不足',
    reflectionReason: '需要人工确认。',
    technical: { actualMode: 'bm25_fallback', candidateCount: 2, displayCount: 0, retrievalMs: 3, indexVersion: '' }
  }}})
  const vm = context()
  vm.query = '客服要求删除差评后才退款'
  await vm.submit()
  expect(queryPolicyEvidence).toHaveBeenCalledWith(expect.objectContaining({ topK: 3 }))
  expect(vm.turns[0].result.isolated).toBe(true)
  expect(vm.loading).toBe(false)
})

test('failed request remains readable and can be retried', async() => {
  queryPolicyEvidence.mockRejectedValue(new Error('offline'))
  const vm = context()
  vm.query = '五星截图返现'
  await vm.submit()
  expect(vm.turns[0].error).toContain('暂时不可用')
  expect(vm.loading).toBe(false)
})

test('short greeting can reach the guidance fallback', async() => {
  queryPolicyEvidence.mockResolvedValue({ data: { data: {
    isolated: true,
    decision: { code: 'input_guidance', label: '请描述需要核对的问题', tone: 'info' },
    risks: [],
    evidence: [],
    evidenceStatus: 'not_required',
    evidenceStatusLabel: '尚未检索',
    reflectionReason: '请输入评论原文或具体治理问题。',
    technical: { actualMode: 'not_executed', candidateCount: 0, displayCount: 0, retrievalMs: 0, indexVersion: '' }
  }}})
  const vm = context()
  vm.query = '你好'

  await vm.submit()

  expect(queryPolicyEvidence).toHaveBeenCalledWith(expect.objectContaining({ query: '你好' }))
  expect(vm.turns[0].result.decision.code).toBe('input_guidance')
  expect(vm.cleanResultTitle(vm.turns[0].result)).toBe('请补充评论或治理问题')
})

test('compare mode queries current and verified candidate without writing business state', async() => {
  documentIndexStatus.mockResolvedValue({ data: { data: {
    active: null,
    candidate: { status: 'ready', evaluationAvailable: true, version: 'policy-20260916T213237-0963c90a' }
  }}})
  const result = {
    isolated: true,
    decision: { code: 'evidence_ready', label: '已找到依据', tone: 'success' },
    riskTypes: ['rating_manipulation'],
    risks: [],
    evidence: [{ sourceName: '评价规则' }],
    evidenceStatus: 'supported',
    evidenceStatusLabel: '证据充分',
    reflectionReason: '有依据。',
    technical: { actualMode: 'hybrid', candidateCount: 3, displayCount: 1, retrievalMs: 3, indexVersion: 'v1' }
  }
  queryPolicyEvidence.mockResolvedValue({ data: { data: result }})
  const vm = context()
  await vm.loadIndexState()
  vm.indexTarget = 'compare'
  vm.query = '五星截图返现'

  await vm.submit()

  expect(queryPolicyEvidence).toHaveBeenCalledTimes(2)
  expect(queryPolicyEvidence).toHaveBeenCalledWith(expect.objectContaining({ indexTarget: 'current' }))
  expect(queryPolicyEvidence).toHaveBeenCalledWith(expect.objectContaining({ indexTarget: 'candidate', candidateVersion: 'policy-20260916T213237-0963c90a' }))
  expect(vm.turns[0].baseline).not.toBeNull()
  expect(vm.comparisonVerdict(vm.turns[0]).tag).toBe('无明显退化')
})

test('latest verified historical release is used when the ready candidate lacks evaluation', async() => {
  documentIndexStatus.mockResolvedValue({ data: { data: {
    active: null,
    candidate: { status: 'ready', evaluationAvailable: false, version: 'policy-old' },
    releases: [
      { status: 'superseded', evaluationAvailable: true, version: 'policy-20260916T213237-0963c90a', releaseEvaluation: { gatePassed: true }},
      { status: 'ready', evaluationAvailable: false, version: 'policy-legacy' }
    ]
  }}})
  const vm = context()

  await vm.loadIndexState()

  expect(vm.candidateAvailable).toBe(true)
  expect(vm.candidateVersion).toBe('policy-20260916T213237-0963c90a')
  expect(vm.indexHint).toContain('对比版本')
})

test('backend comparable release role is preferred over legacy candidate guessing', async() => {
  documentIndexStatus.mockResolvedValue({ data: { data: {
    candidate: { status: 'ready', evaluationAvailable: false, version: 'policy-legacy' },
    candidateRelease: null,
    comparableRelease: { status: 'superseded', evaluationAvailable: true, version: 'policy-verified' },
    historyReleases: []
  }}})
  const vm = context()

  await vm.loadIndexState()

  expect(vm.candidateVersion).toBe('policy-verified')
  expect(vm.candidateAvailable).toBe(true)
})
