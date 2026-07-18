import request from '@/utils/request'

export function dashboardSummary() {
  return request({
    url: '/ai/dashboard/summary',
    method: 'get'
  })
}

export function sentimentDistribution() {
  return request({
    url: '/ai/dashboard/sentiment-distribution',
    method: 'get'
  })
}

export function riskTrend() {
  return request({
    url: '/ai/dashboard/risk-trend',
    method: 'get'
  })
}

export function riskTypeDistribution() {
  return request({
    url: '/ai/dashboard/risk-type-distribution',
    method: 'get'
  })
}

export function topRiskProducts() {
  return request({
    url: '/ai/dashboard/top-risk-products',
    method: 'get'
  })
}

export function patrolSummary() {
  return request({
    url: '/ai/dashboard/patrol-summary',
    method: 'get'
  })
}

export function operationOverview() {
  return request({
    url: '/ai/dashboard/operation-overview',
    method: 'get'
  })
}

export function demoStatus() {
  return request({
    url: '/ai/demo/status',
    method: 'get'
  })
}

export function demoReset() {
  return request({
    url: '/ai/demo/reset',
    method: 'post'
  })
}
