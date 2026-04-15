<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAppStore } from '../store/app'
import { createMakeupTask, getMakeupState, getRefImages, getMakeupResultUrl } from '../services/api'

const store = useAppStore()

// 参考图片列表
const refImages = getRefImages()

// 选中的图片
const selectedIdImage = ref<string | null>(null)   // 身份图片路径
const useCachedPhoto = ref(false)                   // 是否使用缓存的拍照图片
const selectedRefImage = ref<string | null>(null)   // 参考妆容图片路径

// 任务状态
const isCreating = ref(false)
const isPolling = ref(false)
const taskId = ref<string | null>(null)
const status = ref<'idle' | 'creating' | 'running' | 'finish' | 'error'>('idle')
const resultImageUrl = ref<string | null>(null)
const errorMsg = ref('')

const canCreate = computed(() => {
  const hasIdImage = useCachedPhoto.value ? !!store.cachedPhoto : !!selectedIdImage.value
  return hasIdImage && selectedRefImage.value && !isCreating.value && !isPolling.value
})

function selectIdImage(img: string) {
  selectedIdImage.value = img
  useCachedPhoto.value = false
}

function selectRefImage(img: string) {
  selectedRefImage.value = img
}

function toggleCachedPhoto() {
  useCachedPhoto.value = !useCachedPhoto.value
  if (useCachedPhoto.value) {
    selectedIdImage.value = null
  }
}

async function startMakeup() {
  if (!canCreate.value) return

  isCreating.value = true
  status.value = 'creating'
  errorMsg.value = ''
  resultImageUrl.value = null

  try {
    // 获取身份图片 File
    let idFile: File
    if (useCachedPhoto.value && store.cachedPhoto) {
      idFile = await base64ToFile(store.cachedPhoto, 'identity.jpg')
    } else if (selectedIdImage.value) {
      idFile = await urlToFile(selectedIdImage.value, 'identity.jpg')
    } else {
      throw new Error('未选择身份图片')
    }

    // 获取参考妆容图片 File
    if (!selectedRefImage.value) throw new Error('未选择参考妆容图片')
    const refFile = await urlToFile(selectedRefImage.value, 'reference.jpg')

    // 创建任务
    const res = await createMakeupTask(idFile, refFile)
    if (res.code !== 200 || !res.task_id) {
      throw new Error(res.msg || '创建任务失败')
    }

    taskId.value = res.task_id
    isCreating.value = false
    isPolling.value = true
    status.value = 'running'

    // 轮询状态
    await pollMakeupState(res.task_id)
  } catch (e: any) {
    errorMsg.value = e.message || '操作失败'
    status.value = 'error'
    isCreating.value = false
    isPolling.value = false
  }
}

async function pollMakeupState(tid: string) {
  while (true) {
    try {
      const res = await getMakeupState(tid)
      if (res.status === 'finish') {
        resultImageUrl.value = getMakeupResultUrl(tid)
        status.value = 'finish'
        isPolling.value = false
        store.addMakeupResult({ taskId: tid, imageUrl: resultImageUrl.value!, timestamp: Date.now() })
        return
      } else if (res.status === 'error') {
        errorMsg.value = res.msg || '生成失败'
        status.value = 'error'
        isPolling.value = false
        return
      }
      // running - 继续轮询
    } catch {
      errorMsg.value = '网络错误，请重试'
      status.value = 'error'
      isPolling.value = false
      return
    }
    await sleep(1000)
  }
}

function resetTask() {
  taskId.value = null
  status.value = 'idle'
  resultImageUrl.value = null
  errorMsg.value = ''
  isCreating.value = false
  isPolling.value = false
}

// 工具函数
async function base64ToFile(base64: string, filename: string): Promise<File> {
  const res = await fetch(base64)
  const blob = await res.blob()
  return new File([blob], filename, { type: 'image/jpeg' })
}

async function urlToFile(url: string, filename: string): Promise<File> {
  const res = await fetch(url)
  const blob = await res.blob()
  return new File([blob], filename, { type: 'image/jpeg' })
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
</script>

<template>
  <div class="makeup-gen">
    <div class="section-card">
      <h2 class="section-title">💄 妆容生成</h2>
      <p class="section-desc">选择身份图片和参考妆容图片，AI 为你生成专属妆容</p>

      <div class="makeup-content">
        <!-- 身份图片选择 -->
        <div class="image-section">
          <div class="section-header">
            <span class="section-label">👩 身份图片</span>
            <button
              class="btn btn-secondary btn-sm"
              :class="{ active: useCachedPhoto }"
              @click="toggleCachedPhoto"
              :disabled="!store.cachedPhoto"
            >
              📸 使用拍照缓存
            </button>
          </div>

          <div v-if="useCachedPhoto && store.cachedPhoto" class="cached-preview-large">
            <img :src="store.cachedPhoto" alt="缓存照片" />
            <span class="preview-tag">📸 拍照缓存</span>
          </div>

          <div v-else class="image-grid">
            <div
              v-for="img in refImages"
              :key="'id-' + img"
              class="image-grid-item"
              :class="{ selected: selectedIdImage === img && !useCachedPhoto }"
              @click="selectIdImage(img)"
            >
              <img :src="img" :alt="img" />
              <div v-if="selectedIdImage === img && !useCachedPhoto" class="check-mark">✓</div>
            </div>
          </div>
        </div>

        <!-- 参考妆容图片选择 -->
        <div class="image-section">
          <span class="section-label">🎨 参考妆容图片</span>
          <div class="image-grid">
            <div
              v-for="img in refImages"
              :key="'ref-' + img"
              class="image-grid-item"
              :class="{ selected: selectedRefImage === img }"
              @click="selectRefImage(img)"
            >
              <img :src="img" :alt="img" />
              <div v-if="selectedRefImage === img" class="check-mark">✓</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-bar">
        <button class="btn btn-primary" :disabled="!canCreate" @click="startMakeup">
          <span v-if="isCreating">⏳ 创建任务中...</span>
          <span v-else-if="isPolling">🔄 正在处理中</span>
          <span v-else>✨ 开始生成妆容</span>
        </button>
        <button v-if="status !== 'idle'" class="btn btn-secondary" @click="resetTask">
          🔄 重置
        </button>
      </div>

      <!-- 状态展示 -->
      <div v-if="status === 'creating'" class="status-box pulse">
        <div class="loading-spinner"></div>
        <span>⏳ 正在创建妆容生成任务...</span>
      </div>

      <div v-if="status === 'running'" class="status-box pulse">
        <div class="loading-spinner"></div>
        <span>🔄 正在处理中，请稍候...</span>
      </div>

      <div v-if="status === 'error'" class="status-box error-box">
        <span>❌ {{ errorMsg }}</span>
      </div>

      <!-- 结果展示 -->
      <div v-if="resultImageUrl" class="result-section">
        <h3 class="result-title">🎉 妆容生成完成</h3>
        <div class="result-image-wrapper">
          <img :src="resultImageUrl" alt="妆容结果" class="result-image" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.makeup-gen {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 24px;
}

.section-card {
  background: var(--bg-card);
  border-radius: 20px;
  padding: 28px;
  box-shadow: 0 4px 20px var(--shadow);
  border: 1px solid var(--border);
}

.section-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.section-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 24px;
}

.makeup-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.image-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.btn-sm {
  padding: 6px 14px;
  font-size: 12px;
  border-radius: 10px;
}

.btn-sm.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.cached-preview-large {
  position: relative;
  width: 160px;
  height: 160px;
  border-radius: 16px;
  overflow: hidden;
  border: 2px solid var(--accent);
  box-shadow: 0 4px 15px var(--shadow);
}

.cached-preview-large img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-tag {
  position: absolute;
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  background: var(--accent);
  color: #fff;
  padding: 2px 10px;
  border-radius: 10px;
  white-space: nowrap;
}

.action-bar {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.status-box {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding: 14px 20px;
  border-radius: 14px;
  background: var(--bg-secondary);
  font-size: 14px;
  color: var(--text-secondary);
}

.error-box {
  background: #fff0f0;
  color: var(--error);
}

.result-section {
  margin-top: 24px;
}

.result-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 16px;
}

.result-image-wrapper {
  display: flex;
  justify-content: center;
}

.result-image {
  max-width: 512px;
  max-height: 512px;
  border-radius: 16px;
  box-shadow: 0 8px 30px var(--shadow-strong);
  border: 2px solid var(--border);
}
</style>
