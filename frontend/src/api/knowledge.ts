import api from './index'

export interface DocumentInfo {
  name: string
  size: number
  chunks: number
}

/** 获取文档列表 */
export async function getDocuments(): Promise<DocumentInfo[]> {
  const { data } = await api.get('/knowledge/documents')
  return data
}

/** 上传文档 */
export async function uploadDocument(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/** 删除文档 */
export async function deleteDocument(name: string) {
  const { data } = await api.delete(`/knowledge/documents/${encodeURIComponent(name)}`)
  return data
}

/** 重建索引 */
export async function rebuildIndex(): Promise<{ documents: number; chunks: number }> {
  const { data } = await api.post('/knowledge/rebuild')
  return data
}
