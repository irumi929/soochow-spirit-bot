import os
from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import TextMessage, ReplyMessageRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv

# 讀取 .env 檔案
load_dotenv()

# 從 .env 檔案取得 Channel Access Token 和 Channel Secret
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')

# Flask App 初始化
app = Flask(__name__)

# LineBot 初始化
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 初始化 line_bot_api
with ApiClient(configuration) as api_client:
    line_bot_api = MessagingApi(api_client)

@app.route("/callback", methods=['POST'])
def callback():
    # 取得簽名
    signature = request.headers['X-Line-Signature']

    # 取得請求內容
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# 收到文字訊息事件時回覆
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_msg = event.message.text.lower()

    if "課程" in user_msg:
        reply_text = "這是課程查詢功能喔 📚（之後會接資料庫）"
    elif "成績" in user_msg:
        reply_text = "這是成績查詢功能 📊（之後會接學生資料）"
    elif "活動" in user_msg:
        reply_text = "這是活動資訊功能 🎉"
    elif "屁眼" in user_msg:
        reply_text = "派對"
    elif "bruh" in user_msg:
        reply_text = "eww"
    elif "poordog" in user_msg:
        reply_text = "that's me🤌🏻"
    elif "校園地圖" in user_msg:
        # 回傳東吳大學地圖圖片
        image_url = "https://drive.google.com/uc?export=download&id=1uYUx4G_3UGhBd4Oj6GBYZzcxCcxPe_Kx" # google drive 的url
        #https://www.dropbox.com/scl/fi/ridqgh04r6j545eo73xbe/.jpg?rlkey=6qlnd92eoxcs0cz65237p94wh&st=lpitrnq1&raw=1 這個為dropbox 的url(備用)
        #無法開啟圖片，之後要放上去要透過huggingface上傳圖片然後取得公開url再放入image_url=這裡面
        reply_messages = [
            ImageMessage(original_content_url=image_url, preview_image_url=image_url),
            TextMessage(text="這是東吳大學外雙溪校區的地圖！")
        ]
    else:
        reply_text = f"你說了: {user_msg}，但我聽不懂😅"

    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )

if __name__ == "__main__":
    # Flask 預設端口是 5000
    app.run(port=5000)
