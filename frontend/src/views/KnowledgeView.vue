<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Refresh, Delete } from '@element-plus/icons-vue'
import {
  getDocuments,
  uploadDocument,
  deleteDocument,
  rebuildIndex,
} from '../api/knowledge'
import type { DocumentInfo } from '../api/knowledge'

const router = useRouter()
const documents = ref<DocumentInfo[]>([])
const loading = ref(false)
const rebuilding = ref(false)
const uploading = ref(false)
const uploadRef = ref()

async function loadDocuments() {
  loading.value = true
  try {
    documents.value = await getDocuments()
  } catch {
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

async function handleUpload(file: File) {
  uploading.value = true
  try {
    const res = await uploadDocument(file)
    ElMessage.success(res.message)
    await loadDocuments()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

function onFileChange(uploadFile: any) {
  handleUpload(uploadFile.raw)
}

async function handleDelete(name: string) {
  try {
    await ElMessageBox.confirm(`确认删除「${name}」？删除后需重建索引。`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const res = await deleteDocument(name)
    ElMessage.success(res.message)
    await loadDocuments()
  } catch {
    // 用户取消
  }
}

async function handleRebuild() {
  rebuilding.value = true
  try {
    const res = await rebuildIndex()
    ElMessage.success(`索引重建完成：${res.documents} 个文档，${res.chunks} 个分块`)
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '重建索引失败')
  } finally {
    rebuilding.value = false
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

loadDocuments()
</script>

<template>
  <div class="knowledge-page">
    <nav class="page-nav">
      <button class="nav-back" @click="router.push('/')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        返回对话
      </button>
      <span class="nav-title">知识库管理</span>
    </nav>

    <div class="container">
      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <span>文档列表（{{ documents.length }} 份）</span>
            <div class="actions">
              <el-upload
                ref="uploadRef"
                :auto-upload="false"
                :show-file-list="false"
                accept=".md"
                :on-change="onFileChange"
              >
                <el-button type="primary" :loading="uploading">
                  <el-icon><Upload /></el-icon>
                  上传文档
                </el-button>
              </el-upload>
              <el-button :loading="rebuilding" @click="handleRebuild">
                <el-icon><Refresh /></el-icon>
                重建索引
              </el-button>
            </div>
          </div>
        </template>

        <el-table :data="documents" v-loading="loading" stripe>
          <el-table-column prop="name" label="文档名称" min-width="240" />
          <el-table-column label="大小" width="100" align="center">
            <template #default="{ row }">
              {{ formatSize(row.size) }}
            </template>
          </el-table-column>
          <el-table-column prop="chunks" label="预估分块" width="100" align="center" />
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button
                type="danger"
                text
                size="small"
                :icon="Delete"
                @click="handleDelete(row.name)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!loading && documents.length === 0" description="暂无文档，请上传 .md 文件" />
      </el-card>

      <el-card shadow="hover" class="tip-card">
        <el-icon><InfoFilled /></el-icon>
        <span>上传 Markdown 文件后，需点击「重建索引」才能生效。文档存放在 <code>docs/rag/</code> 目录。</span>
      </el-card>
    </div>
  </div>
</template>

<script lang="ts">
import { InfoFilled } from '@element-plus/icons-vue'
export default { components: { InfoFilled } }
</script>

<style scoped>
.knowledge-page {
  min-height: 100vh;
  background: #f0f2f5;
}

.container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 28px 24px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.actions {
  display: flex;
  gap: 8px;
}

.tip-card {
  margin-top: 16px;
}

.tip-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
}

.tip-card code {
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: #e94560;
}
</style>
