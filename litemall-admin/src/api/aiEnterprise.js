import request from '@/utils/request'

export function toolRegistryList() {
  return request({
    url: '/ai/tool/registry/list',
    method: 'get'
  })
}

export function toolRegistryDetail(query) {
  return request({
    url: '/ai/tool/registry/detail',
    method: 'get',
    params: query
  })
}

export function updateToolEnabled(data) {
  return request({
    url: '/ai/tool/registry/update-enabled',
    method: 'post',
    data
  })
}

export function toolManifestLocal() {
  return request({
    url: '/ai/tool/manifest/local',
    method: 'get'
  })
}

export function toolManifestOpenApi() {
  return request({
    url: '/ai/tool/manifest/openapi',
    method: 'get'
  })
}

export function toolManifestMcpLike() {
  return request({
    url: '/ai/tool/manifest/mcp-like',
    method: 'get'
  })
}

export function validateToolSchema() {
  return request({
    url: '/ai/tool/schema/validate',
    method: 'get'
  })
}

export function testToolSchema() {
  return request({
    url: '/ai/tool/schema/test',
    method: 'post'
  })
}

export function toolSchemaReport() {
  return request({
    url: '/ai/tool/schema/report',
    method: 'get'
  })
}

export function toolPolicyList() {
  return request({
    url: '/ai/tool/policy/list',
    method: 'get'
  })
}

export function updateToolPolicy(data) {
  return request({
    url: '/ai/tool/policy/update',
    method: 'post',
    data
  })
}

export function toolExecutionLogs(query) {
  return request({
    url: '/ai/tool/execution/logs',
    method: 'get',
    params: query
  })
}

export function toolExecutionSummary() {
  return request({
    url: '/ai/tool/execution/summary',
    method: 'get'
  })
}

export function unregisteredToolExecutions() {
  return request({
    url: '/ai/tool/execution/unregistered',
    method: 'get'
  })
}

export function pendingToolApprovals() {
  return request({
    url: '/ai/tool/approval/pending',
    method: 'get'
  })
}

export function toolApprovalList(query) {
  return request({
    url: '/ai/tool/approval/list',
    method: 'get',
    params: query
  })
}

export function toolApprovalDetail(query) {
  return request({
    url: '/ai/tool/approval/detail',
    method: 'get',
    params: query
  })
}

export function approveTool(data) {
  return request({
    url: '/ai/tool/approval/approve',
    method: 'post',
    data
  })
}

export function rejectTool(data) {
  return request({
    url: '/ai/tool/approval/reject',
    method: 'post',
    data
  })
}

export function markToolApprovalExecuted(data) {
  return request({
    url: '/ai/tool/approval/mark-executed',
    method: 'post',
    data
  })
}

export function markToolApprovalReviewed(data) {
  return request({
    url: '/ai/tool/approval/mark-reviewed',
    method: 'post',
    data
  })
}

export function toolApprovalTimeline(query) {
  return request({
    url: '/ai/tool/approval/timeline',
    method: 'get',
    params: query
  })
}

export function memoryProfileList(query) {
  return request({
    url: '/ai/memory/profile/list',
    method: 'get',
    params: query
  })
}

export function memoryProfileDetail(query) {
  return request({
    url: '/ai/memory/profile/detail',
    method: 'get',
    params: query
  })
}

export function rebuildMemory() {
  return request({
    url: '/ai/memory/rebuild',
    method: 'post'
  })
}

export function guardrailEvents() {
  return request({
    url: '/ai/guardrail/events',
    method: 'get'
  })
}

export function guardrailSummary() {
  return request({
    url: '/ai/guardrail/summary',
    method: 'get'
  })
}

export function guardrailTest(data) {
  return request({
    url: '/ai/guardrail/test',
    method: 'post',
    data
  })
}

export function agentOpsSummary() {
  return request({
    url: '/ai/agentops/summary',
    method: 'get'
  })
}

export function agentOpsTrends() {
  return request({
    url: '/ai/agentops/trends',
    method: 'get'
  })
}

export function agentOpsRecentRuns(query) {
  return request({
    url: '/ai/agentops/recent-runs',
    method: 'get',
    params: query
  })
}

export function agentOpsFailureTop() {
  return request({
    url: '/ai/agentops/failure-top',
    method: 'get'
  })
}

export function agentOpsToolFailureTop() {
  return request({
    url: '/ai/agentops/tool-failure-top',
    method: 'get'
  })
}

export function agentOpsFallbackDistribution() {
  return request({
    url: '/ai/agentops/fallback-distribution',
    method: 'get'
  })
}

export function agentOpsGuardrailTrend() {
  return request({
    url: '/ai/agentops/guardrail-trend',
    method: 'get'
  })
}

export function agentOpsRagTrend() {
  return request({
    url: '/ai/agentops/rag-trend',
    method: 'get'
  })
}

export function agentOpsQualityTrend() {
  return request({
    url: '/ai/agentops/quality-trend',
    method: 'get'
  })
}

export function agentOpsSlo() {
  return request({
    url: '/ai/agentops/slo',
    method: 'get'
  })
}

export function agentRegistryList() {
  return request({
    url: '/ai/agent/registry/list',
    method: 'get'
  })
}

export function agentRegistryDetail(query) {
  return request({
    url: '/ai/agent/registry/detail',
    method: 'get',
    params: query
  })
}

export function ragQualitySummary() {
  return request({
    url: '/ai/rag/quality/summary',
    method: 'get'
  })
}

export function ragV2Status() {
  return request({
    url: '/ai/rag-v2/status',
    method: 'get'
  })
}

export function ragV2Search(data) {
  return request({
    url: '/ai/rag-v2/search',
    method: 'post',
    data
  })
}

export function ragV2Evaluate(data) {
  return request({
    url: '/ai/rag-v2/evaluate',
    method: 'post',
    data
  })
}
