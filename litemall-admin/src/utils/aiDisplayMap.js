export const statusMap = {
  pending: '待处理',
  viewed: '已查看',
  replied: '已回复',
  transferred: '已转交',
  ignored: '已忽略',
  closed: '已关闭',
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
  closed_without_action: '无需处理并关闭'
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
