<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../store/app'
import { createMakeupTask, getMakeupState, getIdentityImages, getMakeupRefImages, getMakeupResultUrl } from '../services/api'

const store = useAppStore()
const router = useRouter()

// A类身份图片 + B类参考妆容图片
const identityImages = getIdentityImages()
const makeupRefImages = getMakeupRefImages()

// 选中的图片
const selectedIdImage = ref<string | null>(null)   // 身份图片路径（ref图片或拍照缓存）
const useCachedPhoto = ref(false)                   // 是否使用缓存的拍照图片
const selectedRefImage = ref<string | null>(null)   // 参考妆容图片路径

// 图片预览
const previewImage = ref<string | null>(null)

// 任务状态
const isCreating = ref(false)
const isPolling = ref(false)
const taskId = ref<string | null>(null)
const status = ref<'idle' | 'creating' | 'running' | 'finish' | 'error'>('idle')
const resultImageUrl = ref<string | null>(null)
const errorMsg = ref('')

// 轮询取消控制器
let pollingAbortController: AbortController | null = null

const canCreate = computed(() => {
  const hasIdImage = useCachedPhoto.value ? !!store.cachedPhoto : !!selectedIdImage.value
  return hasIdImage && selectedRefImage.value && !isCreating.value && !isPolling.value
})

function selectIdImage(img: string) {
  // 已勾选的图片再点击 → 放大预览
  if (selectedIdImage.value === img && !useCachedPhoto.value) {
    previewImage.value = img
    return
  }
  selectedIdImage.value = img
  useCachedPhoto.value = false
}

function selectCachedPhoto() {
  if (store.cachedPhoto) {
    // 已选中缓存照片 → 放大预览
    if (useCachedPhoto.value) {
      previewImage.value = store.cachedPhoto
      return
    }
    useCachedPhoto.value = true
    selectedIdImage.value = null
  } else {
    // 没有缓存，跳转到拍照页面
    router.push('/camera')
  }
}

function selectRefImage(img: string) {
  // 已勾选的图片再点击 → 放大预览
  if (selectedRefImage.value === img) {
    previewImage.value = img
    return
  }
  selectedRefImage.value = img
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
    // 如果是取消导致的错误，不更新状态
    if (e?.name === 'AbortError') return
    errorMsg.value = e.message || '操作失败'
    status.value = 'error'
    isCreating.value = false
    isPolling.value = false
  }
}

async function pollMakeupState(tid: string) {
  // 创建新的 AbortController
  pollingAbortController = new AbortController()
  const signal = pollingAbortController.signal

  while (!signal.aborted) {
    try {
      const res = await getMakeupState(tid)
      if (signal.aborted) return  // 检查是否已取消

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
      if (signal.aborted) return
      errorMsg.value = '网络错误，请重试'
      status.value = 'error'
      isPolling.value = false
      return
    }
    await sleep(1000, signal)
  }
}

function resetTask() {
  // 取消正在进行的轮询
  if (pollingAbortController) {
    pollingAbortController.abort()
    pollingAbortController = null
  }
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

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) { reject(new DOMException('Aborted', 'AbortError')); return }
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) }, { once: true })
  })
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
          <span class="section-label">👩 身份图片</span>
          <div class="image-grid">
            <!-- 拍照缓存框 - 固定在第一格 -->
            <div
              class="image-grid-item cached-photo-item"
              :class="{ selected: useCachedPhoto && !!store.cachedPhoto }"
              @click="selectCachedPhoto"
            >
              <template v-if="store.cachedPhoto">
                <img :src="store.cachedPhoto" alt="拍照缓存" />
                <div v-if="useCachedPhoto" class="check-mark">✓</div>
                <span class="cached-badge">📸 缓存</span>
              </template>
              <template v-else>
                <div class="cached-placeholder">
                  <span class="placeholder-icon">📸</span>
                  <span class="placeholder-text">尚未存储拍照缓存</span>
                  <span class="placeholder-hint">前往拍照获取缓存</span>
                </div>
              </template>
            </div>

            <!-- 身份图片列表（A类） -->
            <div
              v-for="img in identityImages"
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
              v-for="img in makeupRefImages"
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

  <!-- 图片预览模态框 -->
  <Teleport to="body">
    <div v-if="previewImage" class="preview-overlay" @click="previewImage = null">
      <img :src="previewImage" class="preview-image" />
    </div>
  </Teleport>
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

.section-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 拍照缓存框样式 */
.cached-photo-item {
  position: relative;
  cursor: pointer;
  background: var(--bg-secondary);
  border: 2px dashed var(--border);
}

.cached-photo-item:hover {
  border-style: solid;
}

.cached-badge {
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
  z-index: 2;
}

.cached-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  gap: 6px;
  padding: 12px;
}

.placeholder-icon {
  font-size: 20px;
  opacity: 0.5;
}

.placeholder-text {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  line-height: 1.4;
}

.placeholder-hint {
  font-size: 12px;
  color: var(--accent);
  text-align: center;
  opacity: 0.8;
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

/* 图片预览模态框 */
.preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  animation: fadeIn 0.2s ease;
}

.preview-image {
  max-width: 90vw;
  max-height: 90vh;
  border-radius: 16px;
  box-shadow: 0 16px 60px rgba(0, 0, 0, 0.5);
  object-fit: contain;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
