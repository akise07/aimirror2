from flask import Flask, request, jsonify, Response, send_from_directory
import threading
import time
import requests
import json
from io import BytesIO
import os
from datetime import datetime

app = Flask(__name__)

# 静态文件：参考图片
REF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ref")

@app.route('/ref/<path:filename>')
def serve_ref_image(filename):
    """提供参考图片"""
    return send_from_directory(REF_DIR, filename)

host = "www.runninghub.cn"
api_key = "740945f3fe064b0b8f64789079174f20"
makeup_workflow_id = "2042647218557030401"
video_workflow_id = "2035008194837225473"

# 存储最新帧
class FrameStore:
    def __init__(self):
        self.frame = None
        self.lock = threading.Lock()
        self.last_update = 0

    def update(self, frame_bytes):
        with self.lock:
            self.frame = frame_bytes
            self.last_update = time.time()

    def get(self):
        with self.lock:
            return self.frame, self.last_update

class TaskStore:
    def __init__(self):
        self.task_id = None
        self.lock = threading.Lock()

    def set(self, task_id):
        with self.lock:
            self.task_id = task_id

class VideoTaskStore:
    def __init__(self):
        self.task_id = None
        self.lock = threading.Lock()

    def set(self, task_id):
        with self.lock:
            self.task_id = task_id

task_store = TaskStore()
video_task_store = VideoTaskStore()

frame_store = FrameStore()

CACHE_DIR = os.path.join("cache", "makeup_img")

# 缓存文件服务
CACHE_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")

@app.route('/cache/<path:filename>')
def serve_cache_file(filename):
    """提供缓存文件"""
    return send_from_directory(CACHE_BASE_DIR, filename)

def download_image(url: str, save_path: str) -> None:
    """下载网络图片并保存"""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)


# 软件接口

@app.route("/recommend", methods=["POST"])
def api_recommend():
    data = request.get_json()
    text_input = data.get("input", "")
    image_path = "cache/input" + text_input
    # 这里可以替换为你的实际处理逻辑
    result = f"收到输入：{image_path}，这里是推荐结果。"
    return jsonify({"result": result})

@app.route("/makeup_image", methods=["POST"])
def api_makeup_image():
    data = request.files
    image_id_input = data.get("image_id", "")
    image_ref_input = data.get("image_ref", "")

    image_id_bytes = image_id_input.read()
    image_ref_bytes = image_ref_input.read()

    url = "https://www.runninghub.cn/openapi/v2/media/upload/binary"

    files = {
    "file": ("image_id.jpg", BytesIO(image_id_bytes), "image/jpeg"),
    }
    headers = {
    'Authorization': f'Bearer {api_key}'
    }
    response_id = requests.request("POST", url, headers=headers, files=files)
    files = {
    "file": ("image_ref.jpg", BytesIO(image_ref_bytes), "image/jpeg"),
    }
    response_ref = requests.request("POST", url, headers=headers, files=files)
    # print(response.json())
    # return response.json()
    result_id = response_id.json()
    result_ref = response_ref.json()
    if result_id.get("code") != 0:
        return jsonify({"code": 400, "status": "error", "msg": "上传妆容图片失败"}), 400
    
    fileName_id = result_id.get("data").get("fileName")
    fileName_ref = result_ref.get("data").get("fileName")

    url = "https://www.runninghub.cn/task/openapi/create"

    payload = json.dumps({
    "apiKey": api_key,
    "workflowId": makeup_workflow_id,
    "nodeInfoList": [
        {
            "nodeId": "3",
            "fieldName": "image",
            "fieldValue": fileName_id
        },
        {
            "nodeId": "4",
            "fieldName": "image",
            "fieldValue": fileName_ref
        }
    ]
    })
    headers = {
    'Host': host,
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    result = response.json()
    task_id = result.get("data").get("taskId")
    # taskStatus = result.get("data").get("taskStatus")
    # task_store.task_id = task_id
    task_store.set(task_id)
    
    if task_id:
        return jsonify({"code": 200, "status": "success", "msg": "创建妆容生成任务成功", "task_id": f"{task_id}"}), 200
    else:
        return jsonify({"code": 400, "status": "error", "msg": "创建妆容生成任务失败"}), 400
    

@app.route("/makeup_state", methods=["POST"])
def api_makeup_state():
    data = request.get_json()
    if data.get("taskId"):
        task_id = data.get("taskId")
    else:
        task_id = task_store.task_id
    
    url = "https://www.runninghub.cn/task/openapi/outputs"

    payload = json.dumps({
    "apiKey": api_key,
    "taskId": task_id
    })
    headers = {
    'Host': host,
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    result = response.json()
    # 804,APIKEY_TASK_IS_RUNNING
    if result.get("code") == 804:
        return jsonify({"code": 200, "status": "running", "msg": "任务运行中", "task_id": f"{task_id}"}), 200
    elif result.get("code") == 0:
        # 下载图片
        image_url = result.get("data")[0].get("fileUrl")
        # 构建保存路径
        filename = f"{task_id}.jpg"
        os.makedirs(CACHE_DIR, exist_ok=True)
        save_path = os.path.join(CACHE_DIR, filename)
        try:
            download_image(image_url, save_path)
        except requests.RequestException as e:
            return jsonify({"error": f"下载失败: {e}"}), 502
        return jsonify({"code": 200, "status": "finish", "task_id": f"{task_id}", "fileUrl": image_url}), 200
    else:
        return jsonify({"code": 400, "status": "error", "msg": "未知错误", "task_id": f"{task_id}"}), 400
    

@app.route("/video_gen", methods=["POST"])
def api_video_gen():
    # data = request.get_json()
    # image_url_input = data.get("image_url", "")
    data = request.files
    image_id_input = data.get("image_id", "")
    text_input = request.form.get("text", "")

    image_id_bytes = image_id_input.read()

    url = "https://www.runninghub.cn/openapi/v2/media/upload/binary"

    files = {
    "file": ("image_id.jpg", BytesIO(image_id_bytes), "image/jpeg"),
    }
    headers = {
    'Authorization': f'Bearer {api_key}'
    }
    response_id = requests.request("POST", url, headers=headers, files=files)

    result_id = response_id.json()
    if result_id.get("code") != 0:
        return jsonify({"code": 400, "status": "error", "msg": "上传妆容图片失败"}), 400

    fileName_id = result_id.get("data").get("fileName")
    
    url = "https://www.runninghub.cn/task/openapi/create"

    payload = json.dumps({
    "apiKey": api_key,
    "workflowId": video_workflow_id,
    "nodeInfoList": [
        {
            "nodeId": "4",
            "fieldName": "image",
            "fieldValue": fileName_id
        },
        {
            "nodeId": "10",
            "fieldName": "text",
            "fieldValue": text_input
        }
    ]
    })
    headers = {
    'Host': host,
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    result = response.json()
    task_id = result.get("data").get("taskId")
    task_store.task_id = task_id
    
    if task_id:
        return jsonify({"code": 200, "status": "success", "msg": "创建视频生成任务成功", "task_id": f"{task_id}"}), 200
    else:
        return jsonify({"code": 400, "status": "error", "msg": "创建视频生成任务失败"}), 400


@app.route("/video_state", methods=["POST"])
def api_video_state():
    data = request.get_json()
    if data.get("taskId"):
        task_id = data.get("taskId")
    else:
        task_id = video_task_store.task_id
    
    url = "https://www.runninghub.cn/task/openapi/outputs"

    payload = json.dumps({
    "apiKey": api_key,
    "taskId": task_id
    })
    headers = {
    'Host': host,
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    result = response.json()
    # 804,APIKEY_TASK_IS_RUNNING
    if result.get("code") == 804:
        return jsonify({"code": 200, "status": "running", "msg": "任务运行中", "task_id": f"{task_id}"}), 200
    elif result.get("code") == 0:
        return jsonify({"code": 200, "status": "finish", "task_id": f"{task_id}", "fileUrl": result.get("data")[0].get("fileUrl")}), 200
    else:
        return jsonify({"code": 400, "status": "error", "msg": "未知错误", "task_id": f"{task_id}"}), 400


@app.route('/frame_upload', methods=['POST'])
def api_upload_frame():
    """接收RDKX5发送的视频帧"""
    try:
        frame_data = request.data  # 原始JPEG数据
        frame_store.update(frame_data)
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/video_feed')
def api_video_feed():
    """MJPEG流，供浏览器显示"""
    def generate():
        while True:
            frame, _ = frame_store.get()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.033)  # ~30fps

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_status')
def api_video_status():
    """检查连接状态"""
    _, last_update = frame_store.get()
    online = (time.time() - last_update) < 2.0
    return jsonify({'online': online, 'last_update': last_update})

# from io import BytesIO
# from PIL import Image
# @app.route('/image_test')
# def api_image_test():
#     image_data = request.data  # 原始JPEG数据
#     image = Image.open(BytesIO(image_data))
#     image_bytes = BytesIO()
#     image.save(image_bytes, format='JPEG')
#     image_bytes.seek(0)
#     return Response(image_bytes,  mimetype='image/jpeg')

# 硬件接口

# import Hobot.GPIO as GPIO

# pwm1_pin = 32
# pwm2_pin = 33

# GPIO.setwarnings(False)

# GPIO.setmode(GPIO.BOARD)

# class LightValueStore:
#     def __init__(self):
#         self.light1_value = 0
#         self.light2_value = 0
#         self.lock = threading.Lock()
#         self.p1 = GPIO.PWM(pwm1_pin, 500)
#         self.p2 = GPIO.PWM(pwm2_pin, 500)
    
#     def set1(self, light1_value):
#         with self.lock:
#             self.light1_value = light1_value
    
#     def set2(self, light2_value):
#         with self.lock:
#             self.light2_value = light2_value

# light_value_store = LightValueStore()
# light_value_store.p1.start(0)
# light_value_store.p2.start(0)

# @app.route("/set_light", methods=["POST"])
# def api_set_light():
#     data = request.get_json()
#     light1_value = int(data.get("light1_value", None))
#     light2_value = int(data.get("light2_value", None))

#     if light1_value is None and light2_value is None:
#         return jsonify({"code": 400, "status": "error", "msg": "缺少亮度值"}), 400
    
#     if light1_value is None:
#         light1_value = light_value_store.light1_value
#     elif light2_value is None:
#         light2_value = light_value_store.light2_value
    
#     if light1_value >= 0 and light1_value <= 100 and light2_value >= 0 and light2_value <= 100:
#         light_value_store.set1(light1_value)
#         light_value_store.set2(light2_value)
        
#         light_value_store.p1.ChangeDutyCycle(light1_value)
#         light_value_store.p2.ChangeDutyCycle(light2_value)
        
#     return jsonify({"code": 200, "msg": "设置灯光成功", "light1_value": light1_value, "light2_value": light2_value})




@app.route("/")
def index():
    return jsonify({"message": "Hello, World!"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3401, debug=True)
