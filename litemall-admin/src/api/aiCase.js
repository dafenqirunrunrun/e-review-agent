import request from '@/utils/request'

export function listAiCases(query) {
  return request({
    url: '/ai/case/list',
    method: 'get',
    params: query
  })
}

export function aiCaseDetail(id) {
  return request({
    url: '/ai/case/detail/' + id,
    method: 'get'
  })
}

export function buildAiCasesFromHistory() {
  return request({
    url: '/ai/case/build-from-history',
    method: 'post'
  })
}

export function aiCaseStats() {
  return request({
    url: '/ai/case/stats',
    method: 'get'
  })
}

export function aiCaseRetrievalLogs() {
  return request({
    url: '/ai/case/retrieval/logs',
    method: 'get'
  })
}

export function retrieveAiCases(query) {
  return request({
    url: '/ai/case/retrieve',
    method: 'get',
    params: query
  })
}

export function retrieveAiCasesV2(query) {
  return request({
    url: '/ai/case/retrieve-v2',
    method: 'get',
    params: query
  })
}

export function compareAiCaseRetrieval(query) {
  return request({
    url: '/ai/case/retrieve-compare',
    method: 'get',
    params: query
  })
}

export function aiCaseRetrievalFailures() {
  return request({
    url: '/ai/case/retrieval/failures',
    method: 'get'
  })
}

export function aiCaseRetrievalMetrics() {
  return request({
    url: '/ai/case/retrieval/metrics',
    method: 'get'
  })
}
