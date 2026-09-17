import {
  decisionCodeMap,
  evidenceStatusMap,
  evidenceTagLabel,
  riskTypeDescription,
  riskTypeLabel
} from '@/utils/aiDisplayMap'

const DECISION_STATUS = {
  auto_pass: { className: 'ok', text: '自动通过' },
  suggest_action: { className: 'warn', text: '建议处理' },
  manual_review: { className: 'danger', text: '需人工复核' }
}

export function normalizeReviewGovernance(result, fallbackScenario) {
  const fallback = fallbackScenario || {}
  const contract = result && result.review_governance ? result.review_governance : result
  if (!contract || !contract.decision) {
    return normalizeFallbackScenario(fallback)
  }
  const decision = contract.decision || {}
  const summary = contract.summary || {}
  const humanReview = contract.humanReview || {}
  const status = DECISION_STATUS[decision.code] || DECISION_STATUS.suggest_action
  const riskCoverage = buildRiskCoverage(contract)
  const history = buildHistoryDisplay(contract)
  const evidence = toArray(contract.evidenceCitations).map(item => ({
    id: item.id,
    title: item.sourceName || '未命名依据',
    sourceType: sourceTypeText(item),
    path: formatEvidencePath(item),
    snippet: item.snippet || '该依据未返回片段，建议打开来源查看原文。',
    riskTypes: formatRiskTypes(item.riskTypes),
    supports: formatEvidenceTags(item),
    retrieval: formatRetrieval(item.retrieval),
    shortHash: shortHash(item.contentHash),
    technicalDetails: buildTechnicalDetails(item),
    sourceUrl: item.sourceUrl
  }))
  const actions = toArray(contract.recommendedActions).map(item => ({
    label: item.label,
    icon: actionIcon(item.code),
    primary: item.style === 'primary' || item.style === 'warning',
    code: item.code
  }))

  return {
    key: fallback.key,
    product: fallback.product,
    orderNo: fallback.orderNo,
    rating: fallback.rating,
    reviewText: fallback.reviewText,
    status: status.className,
    statusText: decision.label || decisionCodeMap[decision.code] || status.text,
    decision: summary.title || decision.label || status.text,
    reason: businessReason(summary.reason || summary.explanation, decision.code),
    confidence: formatConfidence(decision.confidence),
    evidenceStatus: contract.evidenceStatus || fallback.evidenceStatus || 'supported',
    evidenceStatusText: evidenceStatusMap[contract.evidenceStatus] || fallback.evidenceStatusText || '证据充分',
    reflectionReason: businessReason(contract.reflectionReason || fallback.reflectionReason || summary.explanation, decision.code),
    reflectionReasonCode: contract.reflectionReasonCode || '',
    governanceSchemaVersion: contract.governanceSchemaVersion || contract.schemaVersion || 'review-governance-v1',
    history,
    failureReasons: formatFailureReasons(contract),
    riskCoverage,
    requiresHumanReview: Boolean(contract.requiresHumanReview || humanReview.required),
    actionHint: humanReview.required ? humanReview.reason : summary.explanation,
    signals: buildSignals(contract),
    evidence,
    showPolicyEvidence: shouldShowPolicyEvidence(contract, evidence),
    actions: actions.length ? actions : toArray(fallback.actions),
    process: toArray(contract.process).map(step => ({
      name: step.name,
      text: step.summary || step.status,
      done: step.status !== '需关注'
    })),
    source: 'api',
    rawResult: result
  }
}

function normalizeFallbackScenario(fallback) {
  return {
    ...fallback,
    status: fallback.status || 'ok',
    statusText: fallback.statusText || '暂无治理结论',
    decision: fallback.decision || '暂无治理结论',
    reason: fallback.reason || '当前记录尚未返回完整治理结果。',
    evidenceStatus: fallback.evidenceStatus || 'insufficient',
    evidenceStatusText: fallback.evidenceStatusText || evidenceStatusMap[fallback.evidenceStatus] || '证据不足',
    reflectionReason: fallback.reflectionReason || '当前缺少可验证政策依据。',
    reflectionReasonCode: fallback.reflectionReasonCode || 'NO_EVIDENCE',
    governanceSchemaVersion: fallback.governanceSchemaVersion || '',
    history: fallback.history || null,
    failureReasons: toArray(fallback.failureReasons),
    riskCoverage: toArray(fallback.riskCoverage),
    requiresHumanReview: Boolean(fallback.requiresHumanReview),
    signals: toArray(fallback.signals),
    evidence: toArray(fallback.evidence),
    showPolicyEvidence: Boolean(fallback.showPolicyEvidence),
    actions: toArray(fallback.actions),
    process: toArray(fallback.process),
    source: fallback.source || 'fallback'
  }
}

function buildHistoryDisplay(contract) {
  const version = contract.governanceSchemaVersion || contract.schemaVersion || 'review-governance-v1'
  const provided = contract.historyDisplay || {}
  const historical = Boolean(provided.isHistorical || version !== 'review-governance-v2' || contract.originalGovernanceSnapshot)
  if (!historical) return null
  if (contract.requiresReevaluation) {
    return { type: 'warning', message: '该记录来自历史治理口径，和当前规则可能存在差异；需显式重新评估后才能更新 AI 结论。' }
  }
  return { type: 'info', message: provided.message || '该记录来自历史治理口径，已适配为当前展示格式；原始判断仍可追溯。' }
}

function toArray(value) {
  return Array.isArray(value) ? value : []
}

export function formatConfidence(value) {
  if (value === undefined || value === null || value === '') {
    return '中'
  }
  const numeric = Number(value)
  if (Number.isNaN(numeric)) {
    return String(value)
  }
  if (numeric >= 0.8) return '高'
  if (numeric >= 0.6) return '中'
  return '低'
}

function buildSignals(contract) {
  const decision = contract.decision || {}
  const risks = contract.riskSignals || []
  const evidence = contract.evidenceCitations || []
  const firstRisk = risks[0] || {}
  return [
    { label: '命中风险', value: firstRisk.label || riskTypeLabel(firstRisk.riskType) || '无' },
    { label: '处理优先级', value: firstRisk.severity || riskLevelLabel(decision.riskLevel) },
    { label: '引用依据', value: evidence.length ? evidence.length + ' 条' : '无须依据' },
    { label: '下一步', value: decision.needHumanReview ? '人工复核' : decision.label || '自动处理' }
  ]
}

function businessReason(value, decisionCode) {
  const text = value ? String(value) : ''
  if (!text) {
    return decisionCode === 'auto_pass' ? '系统已完成自动审核。' : '请结合评论内容和政策依据完成处理。'
  }
  const replacements = [
    ['High-risk review has matching evidence and requires human confirmation.', '该评论风险较高，系统已找到匹配政策依据，需要人工确认后处理。'],
    ['Risk signals are supported by structured evidence; system recommends an operational action.', '风险信号已有政策依据支持，建议运营按提示处理。'],
    ['Governance signal detected; continue evidence-backed action recommendation.', '系统识别到治理风险，已继续查找政策依据并形成处理建议。'],
    ['Reflection unresolved after max iterations.', '证据核验仍未通过，建议进入人工复核。'],
    ['No strong risk signal from intent router.', '未发现明显治理风险，已按轻量路径完成审核。'],
    ['Intent router sent the review directly to human review.', '评论信息不足或风险不确定，已直接进入人工复核。'],
    ['政策依据能够支持当前风险类型，且来源、条款路径和内容哈希可追溯。', '当前政策依据能够支持该风险判断。']
  ]
  const matched = replacements.find(item => text.indexOf(item[0]) >= 0)
  return matched ? matched[1] : text
}

function formatEvidencePath(item) {
  const parts = []
  if (item.sourceLevel) {
    parts.push(item.sourceLevel + ' 类')
  }
  if (item.sectionPath && item.sectionPath.length) {
    parts.push(item.sectionPath.join(' / '))
  }
  if (item.clauseId) {
    parts.push(item.clauseId)
  }
  return parts.join(' / ') || '来源路径待补充'
}

function formatEvidenceTags(item) {
  const tags = item.evidenceTags || []
  if (!tags.length) {
    return '支持：风险判定'
  }
  return '支持：' + tags.map(tag => evidenceTagLabel(tag)).join('、')
}

function formatRiskTypes(riskTypes) {
  const values = riskTypes || []
  return values.length ? values.map(tag => riskTypeLabel(tag)).join('、') : '未标注'
}

function formatRetrieval(retrieval) {
  if (!retrieval) {
    return 'BM25 兜底'
  }
  const mode = retrieval.mode === 'hybrid' ? 'Hybrid' : retrieval.mode === 'dense' ? 'Dense' : 'BM25 兜底'
  const score = typeof retrieval.score === 'number' ? retrieval.score.toFixed(4) : retrieval.score
  return score ? mode + ' / ' + score : mode
}

function buildRiskCoverage(contract) {
  const coverage = toArray(contract.riskCoverage)
  if (coverage.length) {
    return coverage.map(item => ({
      riskType: item.riskType,
      label: item.label || riskTypeLabel(item.riskType),
      description: item.description || riskTypeDescription(item.riskType),
      status: item.status || 'insufficient',
      statusText: item.statusText || (item.status === 'supported' ? '已支持' : '证据不足'),
      supportedBy: toArray(item.supportedBy).join('、') || '-',
      missingEvidenceTags: toArray(item.missingEvidenceTags).join('、') || '-'
    }))
  }
  return toArray(contract.riskTypes).map(code => ({
    riskType: code,
    label: riskTypeLabel(code),
    description: riskTypeDescription(code),
    status: code === 'normal_review' ? 'supported' : contract.evidenceStatus || 'insufficient',
    statusText: code === 'normal_review' || contract.evidenceStatus === 'supported' ? '已支持' : evidenceStatusMap[contract.evidenceStatus] || '待确认',
    supportedBy: '-',
    missingEvidenceTags: '-'
  }))
}

function formatFailureReasons(contract) {
  return toArray(contract.failureReasons).map(item => ({
    code: item.code || 'UNKNOWN',
    message: item.message || '当前结果需要人工确认。'
  }))
}

function shouldShowPolicyEvidence(contract, evidence) {
  const riskTypes = toArray(contract.riskTypes)
  const isNormalOnly = riskTypes.length <= 1 && riskTypes[0] === 'normal_review'
  if (isNormalOnly && (contract.decision || {}).code === 'auto_pass') {
    return false
  }
  return evidence.length > 0 || Boolean(contract.requiresHumanReview || (contract.humanReview || {}).required)
}

function sourceTypeText(item) {
  if (item.sourceLevel) {
    return item.sourceLevel + ' 类来源'
  }
  if (item.sourceType === 'regulation' || item.sourceType === 'law') {
    return '监管规则'
  }
  if (item.sourceType === 'platform_policy') {
    return '平台规范'
  }
  return '政策依据'
}

function buildTechnicalDetails(item) {
  const details = []
  if (item.retrieval) {
    details.push('检索方式：' + formatRetrieval(item.retrieval))
  }
  if (item.contentHash) {
    details.push('证据指纹：' + shortHash(item.contentHash))
  }
  if (item.evidenceTags && item.evidenceTags.length) {
    details.push('内部标签：' + item.evidenceTags.join(', '))
  }
  return details
}

function shortHash(value) {
  if (!value) {
    return '-'
  }
  const text = String(value)
  return text.length > 16 ? text.slice(0, 16) : text
}

function actionIcon(code) {
  const icons = {
    confirm_pass: 'el-icon-check',
    watch: 'el-icon-view',
    open_manual_review: 'el-icon-user',
    request_more_evidence: 'el-icon-document-add',
    override: 'el-icon-edit-outline',
    accept_suggestion: 'el-icon-check',
    manual_check: 'el-icon-position',
    mark_false_positive: 'el-icon-edit-outline'
  }
  return icons[code] || 'el-icon-position'
}

function riskLevelLabel(level) {
  const labels = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return labels[level] || '中'
}
