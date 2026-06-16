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
      <el-card shadow="never" class="main-card">
        <template #header>
          <div class="card-header">
            <div class="header-left">
              <span class="header-title">文档列表</span>
              <span class="header-count">{{ documents.length }} 份</span>
            </div>
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

        <el-table :data="documents" v-loading="loading" class="doc-table">
          <el-table-column prop="name" label="文档名称" min-width="240">
            <template #default="{ row }">
              <span class="doc-name">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="100" align="center">
            <template #default="{ row }">
              <span class="doc-size">{{ formatSize(row.size) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="chunks" label="预估分块" width="100" align="center">
            <template #default="{ row }">
              <span class="doc-chunks">{{ row.chunks }}</span>
            </template>
          </el-table-column>
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

      <div class="tip-card">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>上传 Markdown 文件后，需点击「重建索引」才能生效。文档存放在 <code>docs/rag/</code> 目录。</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-page {
  min-height: 100vh;
  background: var(--bg-page, #f0f2f5);
}

.container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 28px 24px;
}

.main-card {
  background: #fff;
  border: 1px solid #e8e8e8;
}

.main-card :deep(.el-card__header) {
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
}

.main-card :deep(.el-card__body) {
  padding: 0;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}

.header-count {
  font-size: 13px;
  color: #999;
}

.actions {
  display: flex;
  gap: 8px;
}

/* 表格固定白底黑字，不受主题切换影响 */
.doc-table {
  --el-table-bg-color: #fff;
  --el-table-tr-bg-color: #fff;
  --el-table-header-bg-color: #f8f9fa;
  --el-table-row-hover-bg-color: #f0f5ff;
  --el-table-border-color: #e8e8e8;
  --el-table-text-color: #333;
  --el-table-header-text-color: #666;
  --el-table-current-row-bg-color: #e6f0ff;
}

.doc-name {
  font-weight: 500;
  color: #333;
}

.doc-size {
  color: #888;
  font-size: 13px;
}

.doc-chunks {
  color: #888;
  font-variant-numeric: tabular-nums;
}

.tip-card {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-card, #fff);
  border: 1px solid var(--border-default, #e5e7eb);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-secondary, #6b7280);
}

.tip-card svg {
  flex-shrink: 0;
  color: var(--color-primary, #c2703e);
}

.tip-card code {
  background: var(--bg-code, #f3f4f6);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-accent, #e94560);
}

/* 导航栏 */
.page-nav {
  background: var(--bg-sidebar, #1a1a2e);
  padding: 14px 32px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-nav .nav-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-sidebar, #ccd6f6);
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 6px 14px;
  transition: all 0.2s;
}

.page-nav .nav-back:hover {
  color: var(--text-sidebar-active, #fff);
  background: rgba(255, 255, 255, 0.12);
}

.page-nav .nav-title {
  color: var(--text-sidebar-active, #fff);
  font-size: 16px;
  font-weight: 600;
}

@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .actions {
    width: 100%;
  }

  .actions .el-button {
    flex: 1;
  }
}
</style>
