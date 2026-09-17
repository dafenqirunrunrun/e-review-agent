import request from '@/utils/request'

export const listDocuments = params => request({ url: '/ai/documents', params })
export const documentDetail = id => request({ url: `/ai/documents/${id}` })
export const retryDocument = id => request({ url: `/ai/documents/${id}/retry`, method: 'post' })
export const removeDocument = id => request({ url: `/ai/documents/${id}`, method: 'delete' })
export const documentIndexStatus = () => request({ url: '/ai/documents/index/status' })
export const buildDocumentIndex = () => request({ url: '/ai/documents/index/build', method: 'post', timeout: 120000 })
export const publishDocumentIndex = id => request({ url: `/ai/documents/index/${id}/publish`, method: 'post', timeout: 30000 })
export const rollbackDocumentIndex = id => request({ url: `/ai/documents/index/${id}/rollback`, method: 'post', timeout: 30000 })
export const restoreBaseDocumentIndex = () => request({ url: '/ai/documents/index/base/restore', method: 'post', timeout: 30000 })
export function uploadDocument(file, metadata) {
  const data = new FormData()
  data.append('file', file)
  Object.keys(metadata).forEach(key => data.append(key, metadata[key]))
  return request({ url: '/ai/documents', method: 'post', data, timeout: 120000 })
}
