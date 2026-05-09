<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'

/* ---------- 类型 ---------- */
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  image?: string  // 图片路径
}

interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
}

/* ---------- 默认会话数据 ---------- */
const defaultSessions: ChatSession[] = [
  {
    id: '1',
    title: '打开摄像',
    createdAt: Date.now() - 60000,
    messages: [
      { role: 'user', content: '帮我打开摄像页面' },
      { role: 'assistant', content: '好的，已切换到摄像页面' },
      { role: 'user', content: '把黄灯亮度调到100，白灯亮度调到50' },
      { role: 'assistant', content: '好的，已切换' },
    ],
  },
  {
    id: '2',
    title: '妆容自动化',
    createdAt: Date.now(),
    messages: [
      { role: 'user', content: '切换到摄像页面，3秒后给我拍张照，然后根据我的人脸特征选择合适的参考妆容进行美妆' },
      { role: 'assistant', content: '好的，开始创建美妆任务，现在切换到摄像页面' },
      { role: 'assistant', content: '3s后将给你拍摄一张照片' },
      { role: 'assistant', content: '已经获取到照片', image: './ref/sessions/id.png' },
      { role: 'assistant', content: '正在进行妆容推荐' },
      {
        role: 'assistant',
        content:
          '妆容推荐完成，根据返回的结果，我为你总结一下：您的皮肤白调偏粉，这里给你推荐一张参考妆容，这个风格偏向"暗黑甜美，底妆呈现白皙无瑕的哑光质感，唇妆为橘红色调的水光唇釉，眼影以粉色系大面积晕染眼窝，叠加了细闪珠光，营造出微醺的梦幻感，眼线在眼尾拉出上扬线条，同时在下眼睑处勾勒出几何三角形装饰，带有小丑/戏剧感的暗黑元素，内眼角点缀银白色珠光，让眼神更加灵动，并配上能放大双眼浓密卷翘的假睫毛"，您要使用这个风格吗？',
        image: './ref/sessions/b6.jpg',
      },
      { role: 'user', content: '是的' },
      { role: 'assistant', content: '好的，我将为您进行美妆' },
      { role: 'assistant', content: '美妆完成，这是生成的美妆图像', image: './ref/sessions/result.png' },
    ],
  },
]

/* ---------- 响应式状态 ---------- */
const isOpen = ref(false)
const sessions = ref<ChatSession[]>(JSON.parse(JSON.stringify(defaultSessions)))
const activeSessionId = ref('1')
const inputText = ref('')
const chatBodyRef = ref<HTMLElement | null>(null)

/* ---------- 计算属性 ---------- */
const activeSession = computed(() =>
  sessions.value.find((s) => s.id === activeSessionId.value)
)

/* ---------- 方法 ---------- */
function togglePanel() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    nextTick(() => scrollToBottom())
  }
}

function selectSession(id: string) {
  activeSessionId.value = id
  nextTick(() => scrollToBottom())
}

function createSession() {
  const id = String(Date.now())
  const session: ChatSession = {
    id,
    title: '新会话',
    createdAt: Date.now(),
    messages: [],
  }
  sessions.value.unshift(session)
  activeSessionId.value = id
}

function deleteSession(id: string) {
  if (sessions.value.length <= 1) return
  sessions.value = sessions.value.filter((s) => s.id !== id)
  if (activeSessionId.value === id) {
    activeSessionId.value = sessions.value[0]?.id || ''
  }
}

function sendMessage() {
  if (!inputText.value.trim() || !activeSession.value) return
  activeSession.value.messages.push({
    role: 'user',
    content: inputText.value.trim(),
  })
  // 更新会话标题（第一条消息）
  if (activeSession.value.messages.filter((m) => m.role === 'user').length === 1) {
    activeSession.value.title = inputText.value.trim().slice(0, 12)
  }
  inputText.value = ''
  nextTick(() => scrollToBottom())
}

function scrollToBottom() {
  if (chatBodyRef.value) {
    chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
  }
}

watch(
  () => activeSession.value?.messages.length,
  () => nextTick(() => scrollToBottom())
)
</script>

<template>
  <!-- 悬浮按钮 -->
  <div class="voice-fab" :class="{ active: isOpen }" @click="togglePanel">
    <span v-if="!isOpen" class="fab-icon">🎙️</span>
    <span v-else class="fab-icon">✕</span>
  </div>

  <!-- 悬浮面板 -->
  <Transition name="panel">
    <div v-if="isOpen" class="voice-panel">
      <!-- 左侧会话列表 -->
      <div class="panel-sidebar">
        <div class="sidebar-header">
          <span class="sidebar-title">会话</span>
          <button class="btn-new" @click="createSession" title="新建会话">＋</button>
        </div>
        <div class="session-list">
          <div
            v-for="s in sessions"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === activeSessionId }"
            @click="selectSession(s.id)"
          >
            <span class="session-title">{{ s.title }}</span>
            <span class="session-count">{{ s.messages.length }}</span>
            <button
              v-if="sessions.length > 1"
              class="session-del"
              @click.stop="deleteSession(s.id)"
              title="删除会话"
            >
              ✕
            </button>
          </div>
        </div>
      </div>

      <!-- 右侧聊天区域 -->
      <div class="panel-chat">
        <!-- 顶部标题栏 -->
        <div class="chat-header">
          <span class="chat-title">{{ activeSession?.title || '小安' }}</span>
          <span class="chat-avatar">🤖</span>
        </div>

        <!-- 消息列表 -->
        <div ref="chatBodyRef" class="chat-body">
          <template v-if="activeSession?.messages.length">
            <div
              v-for="(msg, idx) in activeSession?.messages"
              :key="idx"
              class="msg-row"
              :class="msg.role"
            >
              <div class="msg-avatar">
                {{ msg.role === 'user' ? '🙋' : '🤖' }}
              </div>
              <div class="msg-bubble" :class="msg.role">
                <p class="msg-text">{{ msg.content }}</p>
                <img
                  v-if="msg.image"
                  :src="msg.image"
                  class="msg-image"
                  alt="图片"
                />
              </div>
            </div>
          </template>
          <div v-else class="chat-empty">
            <span>🎤 开始与小安对话吧</span>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="chat-input-bar">
          <input
            v-model="inputText"
            class="chat-input"
            placeholder="输入消息..."
            @keyup.enter="sendMessage"
          />
          <button class="btn-send" @click="sendMessage">➤</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* ========== 悬浮按钮 ========== */
.voice-fab {
  position: fixed;
  right: 28px;
  bottom: 28px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--accent-gradient);
  box-shadow: 0 6px 24px var(--shadow-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 9999;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.voice-fab:hover {
  transform: scale(1.12);
  box-shadow: 0 8px 32px var(--shadow-strong);
}
.voice-fab.active {
  background: var(--bg-secondary);
  box-shadow: 0 4px 16px var(--shadow);
}
.fab-icon {
  font-size: 24px;
  line-height: 1;
  color: #fff;
}
.voice-fab.active .fab-icon {
  color: var(--text-secondary);
  font-size: 20px;
}

/* ========== 悬浮面板 ========== */
.voice-panel {
  position: fixed;
  right: 24px;
  bottom: 96px;
  width: 520px;
  height: 480px;
  border-radius: 20px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.25);
  display: flex;
  overflow: hidden;
  z-index: 9998;
}

/* ========== 左侧会话列表 ========== */
.panel-sidebar {
  width: 160px;
  min-width: 160px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 12px;
  border-bottom: 1px solid var(--border);
}

.sidebar-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.btn-new {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: 1px dashed var(--border);
  background: transparent;
  color: var(--accent);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.btn-new:hover {
  background: var(--accent-light);
  border-color: var(--accent);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}
.session-item:hover {
  background: var(--accent-light);
}
.session-item.active {
  background: var(--accent);
}
.session-item.active .session-title,
.session-item.active .session-count {
  color: #fff;
}

.session-title {
  flex: 1;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-count {
  font-size: 10px;
  color: var(--text-muted);
  background: var(--bg-card);
  padding: 1px 6px;
  border-radius: 8px;
  flex-shrink: 0;
}
.session-item.active .session-count {
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.session-del {
  display: none;
  width: 16px;
  height: 16px;
  border: none;
  background: transparent;
  color: var(--error);
  font-size: 10px;
  cursor: pointer;
  border-radius: 50%;
  flex-shrink: 0;
}
.session-item:hover .session-del {
  display: flex;
  align-items: center;
  justify-content: center;
}
.session-item.active .session-del {
  color: #fff;
}

/* ========== 右侧聊天区域 ========== */
.panel-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.chat-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}
.chat-avatar {
  font-size: 20px;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 13px;
}

/* 消息行 */
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  max-width: 100%;
}
.msg-row.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
  background: var(--bg-secondary);
}

.msg-bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}
.msg-bubble.user {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.msg-bubble.assistant {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-bottom-left-radius: 4px;
}

.msg-text {
  margin: 0;
}

.msg-image {
  display: block;
  max-width: 200px;
  max-height: 200px;
  border-radius: 10px;
  margin-top: 8px;
  object-fit: cover;
}

/* ========== 输入框 ========== */
.chat-input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--border);
}

.chat-input {
  flex: 1;
  padding: 8px 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--input-bg);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: all 0.2s;
}
.chat-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-light);
}
.chat-input::placeholder {
  color: var(--text-muted);
}

.btn-send {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: var(--accent-gradient);
  color: #fff;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}
.btn-send:hover {
  transform: scale(1.1);
}

/* ========== 面板动画 ========== */
.panel-enter-active {
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
.panel-leave-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.panel-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.95);
}
.panel-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.97);
}
</style>
