import request from '@/utils/request'

export function getAgentRagOverview(params) {
  return request({
    url: '/agent-rag/overview',
    method: 'get',
    params
  })
}

export function getAgentRagRuns(params) {
  return request({
    url: '/agent-rag/runs',
    method: 'get',
    params
  })
}

export function getAgentRagRunDetail(id) {
  return request({
    url: `/agent-rag/runs/${id}`,
    method: 'get'
  })
}

export function getAgentRagEvidence(id) {
  return request({
    url: `/agent-rag/runs/${id}/evidence`,
    method: 'get'
  })
}

export function getAgentRagOverrides(id) {
  return getAgentRagRunDetail(id)
}

export function overrideAgentRagRun(id, data) {
  return request({
    url: '/agent-rag/override',
    method: 'post',
    data: Object.assign({ operatorId: 1 }, data, { runId: id })
  })
}

export function replayAgentRagRun(id, data) {
  return request({
    url: `/agent-rag/runs/${id}/replay`,
    method: 'post',
    data: data || {}
  })
}

export function compareAgentRagRuns(id, otherRunId) {
  return request({
    url: `/agent-rag/runs/${id}/compare/${otherRunId}`,
    method: 'get'
  })
}

export function getAgentRagRuntimeHealth() {
  return request({
    url: '/agent-rag/health',
    method: 'get'
  })
}

export function getAgentRagRuntimeReady() {
  return request({
    url: '/agent-rag/runtime/ready',
    method: 'get'
  })
}

export function getAgentRagRuntimeMetrics() {
  return request({
    url: '/agent-rag/runtime/metrics',
    method: 'get'
  })
}

export function getAgentRagSecurityStatus() {
  return request({
    url: '/agent-rag/security/status',
    method: 'get'
  })
}

export function getAgentRagRetentionStatus() {
  return request({
    url: '/agent-rag/security/retention/status',
    method: 'get'
  })
}

export function previewAgentRagRetention(data) {
  return request({
    url: '/agent-rag/security/retention/preview',
    method: 'post',
    data: data || {}
  })
}

export function executeAgentRagRetention(data) {
  return request({
    url: '/agent-rag/security/retention/execute',
    method: 'post',
    data: data || {}
  })
}

export function exportAgentRagRun(id) {
  return request({
    url: `/agent-rag/runs/${id}/export`,
    method: 'post'
  })
}
