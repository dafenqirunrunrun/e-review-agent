import request from '@/utils/request'

export function queryPolicyEvidence(data) {
  return request({
    url: '/ai/review/policy-playground/query',
    method: 'post',
    data,
    timeout: 65000
  })
}
