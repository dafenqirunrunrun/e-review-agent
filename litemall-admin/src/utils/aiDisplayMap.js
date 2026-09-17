export const statusMap = {
  pending: '待处理',
  viewed: '已查看',
  replied: '已回复',
  transferred: '已转交',
  ignored: '已忽略',
  closed: '已关闭',
  processed: '已处理',
  running: '运行中',
  success: '成功',
  failed: '失败',
  partial_success: '部分成功',
  completed: '已完成',
  blocked: '已阻断',
  approved: '已批准',
  rejected: '已拒绝',
  executed: '已执行',
  reviewed: '已复核',
  expired: '已过期',
  enabled: '已启用',
  disabled: '已停用',
  active: '生效中',
  inactive: '未生效',
  healthy: '健康',
  watch: '需关注',
  ok: '正常',
  unavailable: '不可用',
  unknown: '未知'
}

export const riskLevelMap = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '严重风险'
}

export const toolRiskLevelMap = riskLevelMap

export const riskTypeRegistry = {
  fake_review: {
    label: '虚假评价',
    description: '评论可能并非真实消费体验，或存在编造、组织化发布等迹象。'
  },
  rating_manipulation: {
    label: '评分操纵',
    description: '通过返现、截图、集中打分等方式影响评分真实性。'
  },
  paid_review: {
    label: '有偿评价',
    description: '评论可能受到现金、返利、赠品或其他利益驱动。'
  },
  review_suppression: {
    label: '压制差评',
    description: '存在删除、屏蔽、威胁或干预用户负面评价展示的风险。'
  },
  after_sales_risk: {
    label: '售后争议',
    description: '评论集中在退款、退货、破损、质量问题或售后处理争议。'
  },
  safety_or_fraud_risk: {
    label: '安全或欺诈',
    description: '评论涉及人身安全、商品安全、假货、欺诈或重大误导。'
  },
  privacy_risk: {
    label: '隐私风险',
    description: '评论包含个人信息、隐私泄露或敏感身份信息。'
  },
  harassment_or_abuse: {
    label: '骚扰威胁',
    description: '评论或上下文包含威胁、辱骂、骚扰或攻击性表达。'
  },
  negative_review: {
    label: '负向体验',
    description: '评论表达不满，但未必构成需要政策依据支撑的治理风险。'
  },
  normal_review: {
    label: '普通评价',
    description: '未发现需要严格治理的风险信号。'
  },
  rating_conflict: {
    label: '评分与内容不一致',
    description: '星级与评论文本情绪不一致，需要人工确认。'
  },
  low_confidence: {
    label: '低置信度',
    description: '当前信息不足，系统无法形成稳定判断。'
  },
  modality_conflict: {
    label: '图文信息冲突',
    description: '图片、文本、评分之间存在明显不一致。'
  },
  fake_review_suspected: {
    label: '疑似虚假评价',
    description: '存在虚假评价迹象，但证据强度不足。'
  },
  other: {
    label: '其他风险',
    description: '系统识别到需要运营关注的其他风险。'
  }
}

export const riskTypeMap = Object.keys(riskTypeRegistry).reduce((map, key) => {
  map[key] = riskTypeRegistry[key].label
  return map
}, {})

export const evidenceTagMap = {
  fake_engagement: '虚假参与',
  fake_review: '虚假评价',
  incentivized_review: '利益诱导评价',
  paid_review: '有偿评价',
  rating_manipulation: '评分操纵',
  review_suppression: '压制差评',
  after_sales: '售后争议',
  after_sales_risk: '售后争议',
  consumer_rights: '消费者权益',
  privacy: '隐私信息',
  personal_information: '个人信息',
  harassment_or_abuse: '骚扰威胁',
  safety_or_fraud: '安全或欺诈',
  safety_or_fraud_risk: '安全或欺诈',
  rating_conflict: '评分冲突',
  modality_conflict: '图文冲突',
  low_confidence: '低置信度'
}

export const evidenceStatusMap = {
  supported: '证据充分',
  insufficient: '证据不足',
  mismatch: '证据不匹配'
}

export const decisionCodeMap = {
  auto_pass: '自动通过',
  suggest_action: '建议处理',
  manual_review: '需人工复核'
}

export const humanDecisionMap = {
  accept_ai_suggestion: '接受 AI 建议',
  override: '人工改判',
  no_action: '无需处置'
}

export const sentimentMap = {
  positive: '正向',
  neutral: '中性',
  negative: '负向'
}

export const feedbackTypeMap = {
  accept: '采纳建议',
  false_positive: '误报',
  risk_level_too_high: '风险等级偏高',
  risk_level_too_low: '风险等级偏低',
  suggestion_bad: '建议不适用',
  transferred_after_sales: '已转售后处理',
  closed_without_action: '无需处理并关闭',
  human_accept_ai_suggestion: '人工接受 AI 建议',
  human_override: '人工改判',
  human_no_action: '人工判定无需处置'
}

export const approvalStatusMap = {
  pending: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
  executed: '已执行',
  reviewed: '已复核',
  expired: '已过期',
  required: '需要审批',
  not_required: '无需审批'
}

export const agentRoleMap = {
  'Review Analyst Agent': '评论分析智能体',
  'Risk Auditor Agent': '风险审查智能体',
  'Case Retriever Agent': '案例检索智能体',
  'Operation Advisor Agent': '运营建议智能体',
  review_analyst: '评论分析智能体',
  risk_auditor: '风险审查智能体',
  case_retriever: '案例检索智能体',
  operation_advisor: '运营建议智能体'
}

export const sourceTypeMap = {
  demo_review: '后台演示评论',
  litemall_comment: '用户端真实评价',
  manual_input: '手工输入'
}

export const triggerTypeMap = {
  manual_run_once: '手动巡检',
  scheduled_patrol: '定时巡检',
  manual_analysis: '手动分析',
  customer_comment: '顾客评价触发',
  replay: '重放运行',
  diagnostic: '诊断检查'
}

export const guardrailActionMap = {
  allow: '放行',
  warn: '警告',
  block: '阻断'
}

export const guardrailSeverityMap = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '严重'
}

export const fallbackMap = {
  true: '已触发回退',
  false: '未触发回退'
}

export const healthStatusMap = {
  ok: '正常',
  fail: '异常',
  failed: '异常',
  unknown: '未知'
}

export function displayValue(map, value, emptyText = '-') {
  if (value === undefined || value === null || value === '') {
    return emptyText
  }
  const key = String(value)
  return map[key] || key
}

export function yesNoText(value) {
  return value ? '是' : '否'
}

export function riskTypeLabel(value) {
  return displayValue(riskTypeMap, value)
}

export function riskTypeDescription(value) {
  const item = riskTypeRegistry[String(value)]
  return item ? item.description : '未登记的风险类型，请结合审核上下文确认。'
}

export function evidenceTagLabel(value) {
  return displayValue(evidenceTagMap, value)
}
