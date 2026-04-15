# AIMakeup 项目记忆

## 项目概况
- Electron + Vue 3 + TypeScript 桌面美妆应用
- 本地后端 Flask (port 3401)：视频流、妆容生成、视频生成、调光
- 云端后端 Flask (port 3402)：妆容推荐（流式输出）
- 使用 RunningHub API 执行 AI 推理任务

## 架构
- 路由：Hash 模式 (createWebHashHistory)，5个页面
  - /camera - 实时视频预览+拍照
  - /makeup - 妆容生成（选身份图片+参考图片）
  - /video - 视频生成（选妆容结果+提示词）
  - /recommend - 妆容推荐（流式进度输出）
  - /settings - 调光+主题切换+关于
- 状态管理：Pinia (useAppStore)，存储主题、缓存照片、妆容结果、灯光值
- 4套主题：白粉(pink)、黑粉(dark-pink，默认)、暖色(warm)、冷色(cool)
- 后端静态文件：/ref/ 参考图片、/cache/ 缓存文件（妆容结果等）

## API 要点
- 妆容生成：POST /makeup_image (FormData: image_id, image_ref) → task_id
- 妆容状态：POST /makeup_state (JSON: taskId) → status: running/finish
- 视频生成：POST /video_gen (JSON: image_url, text) → task_id
- 视频状态：POST /video_state (JSON: taskId) → status + fileUrl
- 调光：POST /set_light (JSON: light1_value, light2_value)
- 视频流：GET /video_feed (MJPEG)
- 妆容推荐：POST /recommend (binary image) → MJPEG 流式 JSON
