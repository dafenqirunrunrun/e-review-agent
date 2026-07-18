import request from '@/utils/request'

export function createDemoReview(data) {
  return request({
    url: '/ai/demo-review/create',
    method: 'post',
    data
  })
}

export function listDemoReview(query) {
  return request({
    url: '/ai/demo-review/list',
    method: 'get',
    params: query
  })
}

export function pendingDemoReview(query) {
  return request({
    url: '/ai/demo-review/pending',
    method: 'get',
    params: query
  })
}
