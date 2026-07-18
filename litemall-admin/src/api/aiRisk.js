import request from '@/utils/request'

export function listRiskTasks(query) {
  return request({
    url: '/ai/risk/list',
    method: 'get',
    params: query
  })
}

export function riskDetail(id) {
  return request({
    url: '/ai/risk/detail/' + id,
    method: 'get'
  })
}

export function updateRiskStatus(data) {
  return request({
    url: '/ai/risk/update-status',
    method: 'post',
    data
  })
}

export function closeRiskTask(data) {
  return request({
    url: '/ai/risk/close',
    method: 'post',
    data
  })
}

export function riskSummary() {
  return request({
    url: '/ai/risk/summary',
    method: 'get'
  })
}
