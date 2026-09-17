export const playgroundExamples = [
  { label: '五星返现', query: '商家说五星好评截图发给客服，确认后返现二十元。' },
  { label: '删评退款', query: '客服说先把差评删掉，才给我办理退款。' },
  { label: '模板评价', query: '我没有买过这个商品，店员让我复制统一模板发布评价。' },
  { label: '隐私泄露', query: '商家在评论区公开了我的手机号和家庭住址。' },
  { label: '跨语言', query: 'The merchant will only process my refund after I remove the negative review.' },
  { label: '普通反馈', query: '包装完整，物流速度正常，商品和页面描述基本一致。' }
]

export function safePolicyUrl(value) {
  return /^https?:\/\//i.test(value || '') ? value : ''
}

export function evidenceTone(status) {
  if (status === 'supported') return 'success'
  if (status === 'mismatch') return 'danger'
  if (status === 'not_required') return 'info'
  return 'warning'
}

export function shortHash(value) {
  return value ? String(value).slice(0, 12) : '未提供'
}
