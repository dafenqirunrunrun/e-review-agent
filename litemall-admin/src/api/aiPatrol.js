import request from '@/utils/request'

export function patrolStatus() {
  return request({
    url: '/ai/patrol/status',
    method: 'get'
  })
}

export function runPatrolOnce() {
  return request({
    url: '/ai/patrol/run-once',
    method: 'post'
  })
}

export function enablePatrol() {
  return request({
    url: '/ai/patrol/enable',
    method: 'post'
  })
}

export function disablePatrol() {
  return request({
    url: '/ai/patrol/disable',
    method: 'post'
  })
}

export function patrolLogs() {
  return request({
    url: '/ai/patrol/logs',
    method: 'get'
  })
}
