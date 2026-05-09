from flask import Flask, request, jsonify

app = Flask(__name__)

# 定义路由，只允许 POST 请求访问
@app.route('/api/user_ask', methods=['POST'])
def user_ask():
    data = request.get_json()
    
    # print(data)
    # {'message': '我这里没有调光页面的控制功能，不过我可以帮你调节扬声器的音量，需要吗？'}

    # 5. 返回 JSON 响应
    return jsonify({
        "code": 200,
        "message": "请求成功",
    })

@app.route('/api/ai_answer', methods=['POST'])
def answer():
    data = request.get_json()
    
    # print(data)
    # {'message': '我这里没有调光页面的控制功能，不过我可以帮你调节扬声器的音量，需要吗？'}

    # 5. 返回 JSON 响应
    return jsonify({
        "code": 200,
        "message": "请求成功",
    })


@app.route('/')
def root():
    return jsonify({
        "code": 200,
        "message": "你好！",
    })

if __name__ == '__main__':
    # 启动服务，默认运行在 http://127.0.0.1:5000
    app.run(host='0.0.0.0', port=5466, debug=True)
