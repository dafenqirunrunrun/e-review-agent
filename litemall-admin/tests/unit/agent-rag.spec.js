import {
  formatRiskLevel,
  formatRunStatus,
  formatProvider,
  formatFallbackReason,
  formatDuration,
  formatConfidence,
  shortFingerprint,
  getRiskTagType,
  isReplayable,
  isOverridable
} from '@/utils/agent-rag'

describe('agent-rag utilities', () => {
  it('formats risk, status, provider and fallback labels', () => {
    expect(formatRiskLevel('high')).toBe('高风险')
    expect(formatRunStatus('REVIEW_REQUIRED')).toBe('待人工复核')
    expect(formatProvider('flagembedding')).toBe('Official BGE-M3')
    expect(formatFallbackReason('MODEL_UNAVAILABLE')).toBe('模型不可用')
  })

  it('formats duration, confidence and fingerprints', () => {
    expect(formatDuration(950)).toBe('950ms')
    expect(formatDuration(1200)).toBe('1.20s')
    expect(formatConfidence(0.876)).toBe('88%')
    expect(shortFingerprint('1234567890abcdef123456')).toBe('12345678...123456')
  })

  it('maps risk tag colors and operation availability', () => {
    expect(getRiskTagType('high')).toBe('danger')
    expect(getRiskTagType('medium')).toBe('warning')
    expect(isReplayable({ id: 1, status: 'SUCCESS' })).toBeTruthy()
    expect(isReplayable({ id: 1, status: 'RUNNING' })).toBeFalsy()
    expect(isOverridable({ id: 2, status: 'SUCCESS', originalRiskLevel: 'medium' })).toBeTruthy()
  })
})
