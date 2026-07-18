import request from '@/utils/request'

export function listAgentRuns(query) {
  return request({
    url: '/ai/agent/run/list',
    method: 'get',
    params: query
  })
}

export function agentRunDetail(id) {
  return request({
    url: '/ai/agent/run/detail/' + id,
    method: 'get'
  })
}

export function agentRunSteps(runId) {
  return request({
    url: '/ai/agent/run/steps/' + runId,
    method: 'get'
  })
}

export function agentRunState(runId) {
  return request({
    url: '/ai/agent/run/state/' + runId,
    method: 'get'
  })
}

export function agentRunCompare(query) {
  return request({
    url: '/ai/agent/run/compare',
    method: 'get',
    params: query
  })
}

export function agentRunReplayPreview(runId) {
  return request({
    url: '/ai/agent/run/replay-preview/' + runId,
    method: 'get'
  })
}

export function agentRunReplay(runId) {
  return request({
    url: '/ai/agent/run/replay/' + runId,
    method: 'post'
  })
}

export function agentRunReplayCompare(runId) {
  return request({
    url: '/ai/agent/run/replay-compare/' + runId,
    method: 'get'
  })
}

export function createAgentFeedback(data) {
  return request({
    url: '/ai/agent/feedback/create',
    method: 'post',
    data
  })
}

export function listAgentFeedback(query) {
  return request({
    url: '/ai/agent/feedback/list',
    method: 'get',
    params: query
  })
}

export function agentEvalSummary() {
  return request({
    url: '/ai/agent/eval/summary',
    method: 'get'
  })
}

export function agentEvalTrend() {
  return request({
    url: '/ai/agent/eval/trend',
    method: 'get'
  })
}

export function agentToolStats() {
  return request({
    url: '/ai/agent/eval/tool-stats',
    method: 'get'
  })
}

export function agentFeedbackStats() {
  return request({
    url: '/ai/agent/eval/feedback-stats',
    method: 'get'
  })
}

export function agentQualitySummary() {
  return request({
    url: '/ai/agent/quality/summary',
    method: 'get'
  })
}

export function agentDiagnosticsSummary() {
  return request({
    url: '/ai/agent/diagnostics/summary',
    method: 'get'
  })
}

export function agentDiagnosticsRecentFailures() {
  return request({
    url: '/ai/agent/diagnostics/recent-failures',
    method: 'get'
  })
}

export function agentDiagnosticsFailureGroups() {
  return request({
    url: '/ai/agent/diagnostics/failure-groups',
    method: 'get'
  })
}

export function agentDiagnosticsHealth() {
  return request({
    url: '/ai/agent/diagnostics/health',
    method: 'get'
  })
}

export function agentFrameworkStatus() {
  return request({
    url: '/ai/agent/framework/status',
    method: 'get'
  })
}
