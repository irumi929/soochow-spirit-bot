import os
import logging
from flask import Flask, request, abort, render_template
from bs4 import BeautifulSoup
import markdown
import re

from google import genai
from google.genai import types
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from scudcard import google_search_dcard

# 初始化 Gemini AI
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)
google_search_tool = Tool(
    google_search=GoogleSearch()
)
chat = client.chats.create(
    model="gemini-2.0-flash",
    config=GenerateContentConfig(
        system_instruction="你是一個中文的AI助手，請用繁體中文回答，並專注於搜尋Dcard相關內容。",
        tools=[google_search_tool],
        response_modalities=["TEXT"],
    )
)

# 初始化 Flask 與 LINE
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
app.logger.setLevel(logging.INFO)

channel_secret = os.getenv("LINE_CHANNEL_SECRET", "YOUR_CHANNEL_SECRET")
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

def query(payload: str) -> str:
    """送出 prompt 給 Gemini 並回傳回應文字"""
    response = chat.send_message(message=payload)
    return response.text

# 網頁首頁：表單 + 結果
@app.route("/", methods=['GET'])
def web_index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def web_search():
    ai_summary_block = ""
    ai_links_block = ""
    error = None
    department = request.form.get('department', '').strip()
    app.logger.info("使用者輸入查詢: %s", department)

    if department:
        try:
            results = google_search_dcard(department)
            app.logger.info("找到文章數: %d", len(results))
            app.logger.info("results sample: %s", results[0] if results else "None")
            if results:
                articles_text = ""
                for idx, item in enumerate(results, 1):
                    articles_text += f"{idx}. {item['title']}\n{item['url']}\n{item['description']}\n\n"
                prompt = (
                    "請依照以下格式統整出最多三位被學生讚美的老師與推薦原因，並美化語句寫成小段落，格式如下（不要加任何粗體或星號）：\n"
                    "老師姓名\n"
                    "推薦原因：（若原文沒有推薦原因，請參考留言或說明查無明確推薦原因）\n"
                    "介紹:（請用一小段話介紹這位老師與學生對他的看法）\n"
                    "每個欄位後請加一個換行，每位老師之間請加兩個換行，不要用空格分隔。\n"
                    "請每位老師之間用一個空行分隔，且不要出現未具名的老師。\n"
                    "注意：「資科」是資料科學，不是資管，請勿混淆。\n"
                    "最後請分成兩個區塊，第一區塊是AI統整，第二區塊是連結導向，格式如下：\n"
                    "===AI統整===\n(老師/推薦原因/介紹)\n===連結導向===\n"
                    "🔗 [文章標題1](連結1)\n🔗 [文章標題2](連結2)\n🔗 [文章標題3](連結3)\n"
                    f"\n以下是搜尋結果：\n{articles_text}"
                )
                ai_full = query(prompt).strip()
                # 分割兩區塊
                ai_summary_block = ""
                ai_links_block = ""
                if "===連結導向===" in ai_full:
                    parts = ai_full.split("===連結導向===")
                    ai_summary_block = markdown.markdown(parts[0].replace("===AI統整===","").strip())
                    ai_links_block = markdown.markdown(parts[1].strip())
                    # 讓所有連結新分頁開啟
                    ai_links_block = re.sub(r'<a ', '<a target="_blank" ', ai_links_block)
                    # 讓每個連結換行
                    ai_links_block = re.sub(r'(</a>)', r'\1<br>', ai_links_block)
                else:
                    ai_summary_block = markdown.markdown(ai_full)
                    ai_links_block = ""
            else:
                ai_summary_block = ""
        except Exception as e:
            import traceback
            app.logger.error("搜尋錯誤: %s", str(e))
            app.logger.error(traceback.format_exc())
            error = "搜尋時發生錯誤，請稍後再試。"

    return render_template('index.html', ai_summary_block=ai_summary_block, ai_links_block=ai_links_block, error=error, department=department)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.warning("Invalid signature. Please check channel credentials.")
        abort(400)
    except Exception as e:
        app.logger.error("LINE 處理錯誤: %s", str(e))
        abort(500)

    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_input = event.message.text.strip()
    # 先用 google_search_dcard 搜尋
    results = google_search_dcard(user_input)
    if not results:
        reply = ""
    else:
        # 將搜尋結果整理成文字
        articles_text = ""
        for idx, item in enumerate(results, 1):
            articles_text += f"{idx}. {item['title']}\n{item['url']}\n{item['description']}\n\n"
        # 丟給 Gemini AI 統整
        prompt = (
            f"以下是 Dcard 上關於「{user_input}」的搜尋結果，請幫我用繁體中文統整重點並摘要：\n\n{articles_text}"
        )
        reply = query(prompt).strip()

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)],
            )
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))