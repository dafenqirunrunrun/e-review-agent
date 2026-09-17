export function formatRiskLevel(value) {
  const map = {
    high: '高风险',
    medium: '需关注',
    low: '低风险',
    critical: '严重风险',
    none: '无风险'
  }
  return map[value] || '未知'
}

export function formatRunStatus(value) {
  const map = {
    PENDING: '待执行',
    RUNNING: '分析中',
    SUCCESS: '已完成',
    RULE_FALLBACK: '规则降级',
    FAILED: '执行失败',
    REVIEW_REQUIRED: '待人工复核',
    OVERRIDDEN: '已人工复核',
    REPLAYED: '已发起回放'
  }
  return map[value] || value || '未知'
}

export function formatProvider(value) {
  const map = {
    flagembedding: 'Official BGE-M3',
    cls: 'Legacy CLS',
    hash: 'Hash Dense',
    sparse: 'Sparse Only'
  }
  return map[value] || value || '未知'
}

export function formatRetrievalMode(value) {
  const map = {
    'bm25-first-semantic-hybrid': 'BM25-first Hybrid',
    'dense-first-hybrid': 'Dense-first Hybrid',
    'sparse-only': 'Sparse Only'
  }
  return map[value] || value || '未知'
}

export function formatFallbackReason(value) {
  const map = {
    MODEL_UNAVAILABLE: '模型不可用',
    MODEL_OUTPUT_SCHEMA_INVALID: '模型输出结构异常',
    RULE_FALLBACK_DISABLED: '规则降级关闭',
    EXPLICIT_FAILURE: '显式失败'
  }
  return map[value] || value || '无'
}

export function formatDuration(value) {
  if (value === undefined || value === null || value === '') {
    return '--'
  }
  const number = Number(value)
  if (Number.isNaN(number)) {
    return '--'
  }
  return number >= 1000 ? `${(number / 1000).toFixed(2)}s` : `${number}ms`
}

export function formatConfidence(value) {
  if (value === undefined || value === null || value === '') {
    return '--'
  }
  const number = Number(value)
  if (Number.isNaN(number)) {
    return '--'
  }
  return `${Math.round(number * 100)}%`
}

export function formatTimestamp(value) {
  if (!value) {
    return '--'
  }
  return String(value).replace('T', ' ').substring(0, 19)
}

export function shortFingerprint(value) {
  if (!value) {
    return '--'
  }
  const text = String(value)
  return text.length <= 16 ? text : `${text.substring(0, 8)}...${text.substring(text.length - 6)}`
}

export function getRiskTagType(value) {
  if (value === 'high' || value === 'critical') return 'danger'
  if (value === 'medium') return 'warning'
  if (value === 'low' || value === 'none') return 'success'
  return 'info'
}

export function getStatusTagType(value) {
  if (value === 'FAILED') return 'danger'
  if (value === 'RULE_FALLBACK' || value === 'REVIEW_REQUIRED') return 'warning'
  if (value === 'SUCCESS') return 'success'
  if (value === 'RUNNING') return ''
  return 'info'
}

export function getProviderTagType(value) {
  if (value === 'flagembedding') return 'success'
  if (value === 'hash' || value === 'cls') return 'warning'
  return 'info'
}

export function isReplayable(run) {
  return run && run.status !== 'RUNNING' && run.id
}

export function isOverridable(run) {
  return run && run.status !== 'RUNNING' && run.id && run.originalRiskLevel !== undefined
}

export function parseEvidenceBundle(value) {
  if (!value) return {}
  try {
    return JSON.parse(value)
  } catch (e) {
    return { parseError: true, payloadPrefix: String(value).substring(0, 1000) }
  }
}
