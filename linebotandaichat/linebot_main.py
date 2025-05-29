import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent

import requests

from dotenv import load_dotenv

load_dotenv()
# ===== 初始化 Flask =====
app = Flask(__name__)

# ===== LINE 憑證設定 =====
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

# ===== 使用者聊天狀態儲存 =====
user_chat_status = {}

# ===== Hugging Face 設定（留空用作範例） =====
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
HF_API_URL = "https://api-inference.huggingface.co/models/<username>/<modelname>"
headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}


def query_hf(payload):
    try:
        response = requests.post(
            "https://tongling01-sculinebot2025.hf.space/predict",
            json={"text": payload},
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        ai_reply = result["reply"]
        return ai_reply
    except Exception as e:
        print(f"Hugging Face API error: {e}")
        return "抱歉，AI 回應失敗了。"

# ===== Webhook 主入口 =====
@app.route("/", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        app.logger.error(f"Handle error: {e}")
        abort(400)

    return "OK"



# ===== 處理文字訊息 =====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_id = event.source.user_id
    user_input = event.message.text.strip()

    # 檢查聊天開關狀態
    if user_chat_status.get(user_id, False):
        ai_response = query_hf(user_input)
        reply_text = f"🤖 {ai_response}"
    else:
        reply_text = "聊天功能已關閉，請從圖文選單開啟。"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )


# ===== 處理 Postback（開關聊天功能） =====
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data

    if data == "start_chat":
        user_chat_status[user_id] = True
        reply_text = "✅ 已開啟聊天功能！"
    elif data == "stop_chat":
        user_chat_status[user_id] = False
        reply_text = "⛔ 已關閉聊天功能！"
    else:
        reply_text = f"⚠️ 未知指令：{data}"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
