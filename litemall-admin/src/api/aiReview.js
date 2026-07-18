import request from '@/utils/request'

export function analyzeReview(data) {
  return request({
    url: '/ai/review/analyze',
    method: 'post',
    data
  })
}

export function listReviewAnalysis(query) {
  return request({
    url: '/ai/review/list',
    method: 'get',
    params: query
  })
}
