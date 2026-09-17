export const documentStatuses = {
  queued: { label: '等待解析', type: 'info' },
  running: { label: '正在解析', type: 'warning' },
  parsed: { label: '已解析 · 未发布', type: 'success' },
  failed: { label: '解析失败', type: 'danger' },
  removed: { label: '待从下版移除', type: 'info' }
}
export const documentUsages = { reference: '参考资料', policy_candidate: '待核验规范', historical_case: '历史案例' }
export const documentExecutionClasses = {
  light: { label: '快速处理', type: 'info' },
  heavy: { label: '深度识别', type: 'warning' }
}

export async function runBoundedUploads(files, upload, concurrency = 3) {
  if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 6) throw new Error('UPLOAD_CONCURRENCY_INVALID')
  let cursor = 0
  const result = { succeeded: [], failed: [] }
  async function worker() {
    while (cursor < files.length) {
      const index = cursor++
      try {
        result.succeeded.push({ index, value: await upload(files[index], index) })
      } catch (error) {
        result.failed.push({ index, error })
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, files.length) }, () => worker()))
  result.succeeded.sort((a, b) => a.index - b.index)
  result.failed.sort((a, b) => a.index - b.index)
  return result
}

export function documentError(code) {
  const errors = {
    WORKER_INTERRUPTED: '处理进程曾中断，任务将重新领取。',
    DOCUMENT_PARSE_TIMEOUT: '解析超时，可重试或拆分较大的文件。',
    DOCUMENT_HASH_MISMATCH: '文件完整性校验失败，请重新上传原文件。',
    DOCUMENT_PARSE_EXHAUSTED: '可用解析器均未完成解析，请检查文件和本地解析环境。',
    DOCUMENT_EMPTY: '未识别到正文，请检查文件是否为空或需要文字识别。',
    FILE_SIZE_INVALID: '文件为空或超过 20 MB。',
    FILE_FORMAT_UNSUPPORTED: '暂不支持此文件格式。'
  }
  return code ? errors[code] || '本次解析未完成，请检查原文件后重试。' : ''
}
