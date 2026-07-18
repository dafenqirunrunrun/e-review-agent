import request from '@/utils/request'

export function listOperationTasks(query) {
  return request({
    url: '/ai/operation/list',
    method: 'get',
    params: query
  })
}

export function operationDetail(id) {
  return request({
    url: '/ai/operation/detail/' + id,
    method: 'get'
  })
}

export function handleOperation(data) {
  return request({
    url: '/ai/operation/handle',
    method: 'post',
    data
  })
}

export function operationLogs(riskTaskId) {
  return request({
    url: '/ai/operation/logs/' + riskTaskId,
    method: 'get'
  })
}

export function operationSummary() {
  return request({
    url: '/ai/operation/summary',
    method: 'get'
  })
}
