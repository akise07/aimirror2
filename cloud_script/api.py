from flask import Flask, request, jsonify, Response
import threading
import time
from recommend import RecommendGenerator
import json

app = Flask(__name__)

recommend_generator = RecommendGenerator()

@app.route("/")
def index():
    return jsonify({"message": "Hello, World!"})

@app.route("/recommend", methods=["POST"])
def api_recommend():
    image_data = request.data  # 原始JPEG数据
    # print(recommend_generator.step_status["step"])
    if recommend_generator.step_status["step"] == 100:
        recommend_generator.step_status["step"] = 0
    if recommend_generator.step_status["step"] == 0:
        thread = threading.Thread(target=recommend_generator.makeup_recommend, args=(image_data,))
        thread.start()
    def recommend():
        last_step = recommend_generator.step_status["step"]
        while True:
            if last_step != recommend_generator.step_status["step"]:
                last_step = recommend_generator.step_status["step"]
                yield (b'--frame\r\n'
                       b'Content-Type: application/json\r\n\r\n' + json.dumps(recommend_generator.step_status).encode('utf-8') + b'\r\n')
            if recommend_generator.step_status["step"] == 100:
                break
            time.sleep(0.3)
    return Response(recommend(), mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3402, debug=True)
