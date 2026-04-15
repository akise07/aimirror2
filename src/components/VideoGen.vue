<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAppStore } from '../store/app'
import { createVideoTask, getVideoState, getMakeupResultUrl } from '../services/api'

const store = useAppStore()

// 选择的图片
const selectedImage = ref<string | null>(null)
const promptText = ref('以微小角度偏差，展示多角度妆容，视角看向镜头，神色灵动')

// 任务状态
const isCreating = ref(false)
const isPolling = ref(false)
const taskId = ref<string | null>(null)
const status = ref<'idle' | 'creating' | 'running' | 'finish' | 'error'>('idle')
const resultVideoUrl = ref<string | null>(null)
const errorMsg = ref('')

// 轮询取消控制器
let pollingAbortController: AbortController | null = null

// 可选图片列表：妆容生成结果
const availableImages = computed(() => {
  return store.makeupResults.map(r => ({
    label: `💄 妆容结果 (${new Date(r.timestamp).toLocaleTimeString()})`,
    url: r.imageUrl,
    taskId: r.taskId,
  }))
})

const canCreate = computed(() => {
  return selectedImage.value && promptText.value.trim() && !isCreating.value && !isPolling.value
})

function selectImage(url: string) {
  selectedImage.value = url
}

async function startVideoGen() {
  if (!canCreate.value) return

  isCreating.value = true
  status.value = 'creating'
  errorMsg.value = ''
  resultVideoUrl.value = null

  try {
    // 使用本地后端路径作为 image_url
    const imageUrl = selectedImage.value!
    const res = await createVideoTask(imageUrl, promptText.value)
    if (res.code !== 200 || !res.task_id) {
      throw new Error(res.msg || '创建任务失败')
    }

    taskId.value = res.task_id
    isCreating.value = false
    isPolling.value = true
    status.value = 'running'

    await pollVideoState(res.task_id)
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    errorMsg.value = e.message || '操作失败'
    status.value = 'error'
    isCreating.value = false
    isPolling.value = false
  }
}

async function pollVideoState(tid: string) {
  // 创建新的 AbortController
  pollingAbortController = new AbortController()
  const signal = pollingAbortController.signal

  while (!signal.aborted) {
    try {
      const res = await getVideoState(tid)
      if (signal.aborted) return

      if (res.status === 'finish') {
        resultVideoUrl.value = res.fileUrl
        status.value = 'finish'
        isPolling.value = false
        return
      } else if (res.status === 'error') {
        errorMsg.value = res.msg || '生成失败'
        status.value = 'error'
        isPolling.value = false
        return
      }
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
  resultVideoUrl.value = null
  errorMsg.value = ''
  isCreating.value = false
  isPolling.value = false
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
  <div class="video-gen">
    <div class="section-card">
      <h2 class="section-title">🎬 视频生成</h2>
      <p class="section-desc">选择一张妆容图片，AI 为你生成灵动妆容视频</p>

      <!-- 图片选择 -->
      <div class="form-group">
        <label class="form-label">🖼️ 选择图片</label>
        <div v-if="availableImages.length === 0" class="empty-hint">
          <span>📋 暂无妆容生成结果，请先在「💄 妆容生成」中生成妆容</span>
        </div>
        <div v-else class="image-list">
          <div
            v-for="img in availableImages"
            :key="img.taskId"
            class="image-option"
            :class="{ selected: selectedImage === img.url }"
            @click="selectImage(img.url)"
          >
            <img :src="img.url" :alt="img.label" class="option-thumb" />
            <span class="option-label">{{ img.label }}</span>
            <div v-if="selectedImage === img.url" class="check-mark">✓</div>
          </div>
        </div>
      </div>

      <!-- 提示词输入 -->
      <div class="form-group">
        <label class="form-label">💬 提示词</label>
        <textarea
          v-model="promptText"
          class="input textarea"
          rows="3"
          placeholder="输入视频生成提示词..."
        ></textarea>
      </div>

      <!-- 操作按钮 -->
      <div class="action-bar">
        <button class="btn btn-primary" :disabled="!canCreate" @click="startVideoGen">
          <span v-if="isCreating">⏳ 创建任务中...</span>
          <span v-else-if="isPolling">🔄 正在处理中</span>
          <span v-else>🎬 开始生成视频</span>
        </button>
        <button v-if="status !== 'idle'" class="btn btn-secondary" @click="resetTask">
          🔄 重置
        </button>
      </div>

      <!-- 状态展示 -->
      <div v-if="status === 'creating'" class="status-box pulse">
        <div class="loading-spinner"></div>
        <span>⏳ 正在创建视频生成任务...</span>
      </div>

      <div v-if="status === 'running'" class="status-box pulse">
        <div class="loading-spinner"></div>
        <span>🔄 正在处理中，请稍候...</span>
      </div>

      <div v-if="status === 'error'" class="status-box error-box">
        <span>❌ {{ errorMsg }}</span>
      </div>

      <!-- 结果展示 -->
      <div v-if="resultVideoUrl" class="result-section">
        <h3 class="result-title">🎉 视频生成完成</h3>
        <div class="video-wrapper">
          <video :src="resultVideoUrl" controls class="result-video" autoplay loop />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.video-gen {
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

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.empty-hint {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
  background: var(--bg-secondary);
  border-radius: 14px;
}

.image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.image-option {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 14px;
  border: 2px solid var(--border);
  cursor: pointer;
  transition: all 0.25s ease;
  background: var(--input-bg);
}

.image-option:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
}

.image-option.selected {
  border-color: var(--accent);
  background: var(--accent-light);
  box-shadow: 0 4px 15px var(--shadow);
}

.option-thumb {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  object-fit: cover;
}

.option-label {
  font-size: 13px;
  color: var(--text-primary);
}

.check-mark {
  width: 20px;
  height: 20px;
  background: var(--accent);
  border-radius: 50%;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  margin-left: auto;
}

.textarea {
  resize: vertical;
  min-height: 80px;
  font-family: inherit;
  line-height: 1.6;
}

.action-bar {
  display: flex;
  gap: 12px;
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

.video-wrapper {
  display: flex;
  justify-content: center;
}

.result-video {
  max-width: 512px;
  max-height: 512px;
  border-radius: 16px;
  box-shadow: 0 8px 30px var(--shadow-strong);
  border: 2px solid var(--border);
}
</style>
