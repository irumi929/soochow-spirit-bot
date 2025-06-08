import os
import uuid
import requests
from urllib.parse import quote
import socket
from flask import Flask, request, abort, send_from_directory

# --- [修改點 1] 導入 LINE Bot SDK v3 的模組 ---
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest, # 用於構建回覆請求
    TextMessage as V3TextMessage, # 將 v3 TextMessage 重命名以避免與 linebot.models 衝突
    ImageMessage as V3ImageMessage, # 將 v3 ImageMessage 重命名
    LocationMessage as V3LocationMessage, # 將 v3 LocationMessage 重命名
    FlexMessage as V3FlexMessage, # 將 v3 FlexMessage 重命名
)
from linebot.v3.webhook import WebhookHandler # WebhookHandler 類別名不變，但導入路徑變了
from linebot.v3.webhooks import ( # 新增 webhooks 模組，用於事件物件
    MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent
)
from linebot.v3.exceptions import InvalidSignatureError

# --- [注意] 保留舊版 linebot.models 以兼容 Flex Message 的組件定義 ---
# 雖然推薦全面升級，但 Flex Message 的組件定義 (BubbleContainer, BoxComponent 等)
# 在 v3 的 MessagingApi 中還沒有直接的對應類別，通常這些是作為 JSON 結構傳遞的。
# 為了避免重寫整個 Flex Message 結構，我們暫時保留這些舊版導入。
# 未來如果您全面使用 v3，可能需要直接構建字典結構。
from linebot.models import (
    BubbleContainer, BoxComponent, TextComponent, ImageComponent,
    ButtonComponent, URIAction, CarouselContainer
)




import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from config import Config
    logging.info("DEBUG: Config module imported successfully.")
except Exception as e:
    logging.error(f"FATAL ERROR: Failed to import Config module: {e}", exc_info=True)
    exit(1) # 如果 Config 無法導入，直接退出

# 然後，確保 DBManager 也被導入
try:
    from db_manager import DBManager, UserState
    logging.info("DEBUG: DBManager module imported successfully.")
except Exception as e:
    logging.error(f"FATAL ERROR: Failed to import DBManager module: {e}", exc_info=True)
    exit(1) # 如果 DBManager 無法導入，直接退出


# 然後，使用 logging.info 打印環境變數
logging.info(f"DEBUG: os.getenv('LINE_CHANNEL_ACCESS_TOKEN') = {os.getenv('LINE_CHANNEL_ACCESS_TOKEN')[:5] if os.getenv('LINE_CHANNEL_ACCESS_TOKEN') else 'None'}")
logging.info(f"DEBUG: os.getenv('LINE_CHANNEL_SECRET') = {os.getenv('LINE_CHANNEL_SECRET')[:5] if os.getenv('LINE_CHANNEL_SECRET') else 'None'}")
logging.info(f"DEBUG: os.getenv('HUGGINGFACE_API_URL') = {os.getenv('HUGGINGFACE_API_URL')}")
logging.info(f"DEBUG: os.getenv('HUGGINGFACE_API_TOKEN') = {os.getenv('HUGGINGFACE_API_TOKEN')[:5] if os.getenv('HUGGINGFACE_API_TOKEN') else 'None'}")

try:
    logging.info(f"DEBUG: Config.LINE_CHANNEL_ACCESS_TOKEN first few chars from Config: {Config.LINE_CHANNEL_ACCESS_TOKEN[:5] if Config.LINE_CHANNEL_ACCESS_TOKEN else 'None'}")
    logging.info(f"DEBUG: Config.LINE_CHANNEL_SECRET first few chars from Config: {Config.LINE_CHANNEL_SECRET[:5] if Config.LINE_CHANNEL_SECRET else 'None'}")
    logging.info(f"DEBUG: Config.SQLITE_DB_PATH = {Config.SQLITE_DB_PATH}") # 新增此行，確認資料庫路徑
except Exception as e:
    logging.error(f"FATAL ERROR: Failed to access Config attributes: {e}", exc_info=True)
    exit(1) # 如果無法訪問 Config 屬性，直接退出

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- [修改點 2] 初始化 LINE Bot API (使用 v3 方式) ---
configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(ApiClient(configuration))

# WebhookHandler 實例化 (類別名不變，但引入路徑變了)
handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)

db_manager = DBManager(Config.SQLITE_DB_PATH) # DBManager 的 __init__ 會自動處理表格創建
try:
    db_manager = DBManager(Config.SQLITE_DB_PATH)
    logging.info("DEBUG: DBManager initialized successfully.")
except Exception as e:
    logging.error(f"FATAL ERROR: Failed to initialize DBManager: {e}", exc_info=True)
    exit(1) # 如果 DBManager 初始化失敗，直接退出

# --- Flask 靜態檔案路由 (用於提供本地儲存的圖片) ---
@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    # 確保只提供 UPLOAD_FOLDER 中的檔案，防止路徑遍歷攻擊
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- Hugging Face API 調用函數 ---
def get_huggingface_response(user_text):
    api_url = Config.HUGGINGFACE_API_URL
    if not api_url:
        print("HUGGINGFACE_API_URL not set in config.")
        return "很抱歉，AI 服務配置不完整。"

    headers = {}
    if Config.HUGGINGFACE_API_TOKEN:
        headers['Authorization'] = f"Bearer {Config.HUGGINGFACE_API_TOKEN}"
    headers['Content-Type'] = 'application/json'

    payload = {"inputs": user_text}
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status() # 檢查 HTTP 錯誤狀態碼 (4xx 或 5xx)
        result = response.json()
        if isinstance(result, list) and result:
            ai_reply = result[0].get("generated_text", "不好意思，我沒有理解您的意思。")
        elif isinstance(result, dict) and 'generated_text' in result:
            ai_reply = result.get("generated_text", "不好意思，我沒有理解您的意思。")
        else:
            ai_reply = "不好意思，AI 回覆格式不正確。"

        return ai_reply
    except requests.exceptions.RequestException as e:
        print(f"Error calling Hugging Face API: {e}")
        return "很抱歉，AI 服務目前無法回應，請稍後再試。"
    except Exception as e:
        print(f"Error processing Hugging Face response: {e}")
        return "很抱歉，AI 回覆處理出錯。"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    except Exception as e: # 捕獲其他可能發生的錯誤
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        abort(500)
    return 'OK' # 成功處理後返回 200 OK

# --- [修改點 3] 文本訊息處理函數 (使用 v3 事件和訊息物件) ---
@handler.add(MessageEvent, message=TextMessageContent) # 使用 TextMessageContent
def handle_text_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    reply_messages = [] # 用於收集要回覆的訊息物件

    if user_message == "撿到失物" or user_message == "上傳失物":
        new_item_id = db_manager.create_new_lost_item(user_id)
        db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_IMAGE, new_item_id)
        reply_messages.append(V3TextMessage(text="好的，請您依照以下步驟上傳失物：\n1. 請先傳送失物的『圖片』。"))
    elif user_message == "查看失物招領":
        items = db_manager.retrieve_lost_items()
        if items:
            flex_message = create_lost_items_flex_message(items)
            reply_messages.append(flex_message) # flex_message 已經是 V3FlexMessage 物件
        else:
            reply_messages.append(V3TextMessage(text="目前沒有失物招領資訊。"))
    elif user_message == "取消上傳":
        db_manager.clear_user_state(user_id)
        reply_messages.append(V3TextMessage(text="已取消失物上傳。"))
    # 處理流程中的文字訊息
    elif current_state_enum == UserState.REPORTING_WAIT_DESCRIPTION:
        if current_item_id:
            db_manager.save_item_description(current_item_id, user_message)
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_LOCATION, current_item_id)
            reply_messages.append(V3TextMessage(text="好的，請您提供撿到失物的『位置』(可直接傳送 Line 的位置訊息，或輸入文字描述)。"))
        else:
            db_manager.clear_user_state(user_id)
            reply_messages.append(V3TextMessage(text="上傳流程錯誤，請重新開始上傳失物的步驟。"))
    elif current_state_enum == UserState.REPORTING_WAIT_LOCATION:
        if current_item_id:
            db_manager.save_item_location(current_item_id, user_message)
            db_manager.clear_user_state(user_id) # 完成上報，清除狀態
            reply_messages.append(V3TextMessage(text="感謝您上傳失物！我們已將資訊發佈。"))
        else:
            db_manager.clear_user_state(user_id)
            reply_messages.append(V3TextMessage(text="上傳流程錯誤，請重新開始上傳失物的步驟。"))
    else:
        # 預設：交給 AI 回覆
        print(f"用戶發送了非指令/流程訊息: {user_message}，嘗試呼叫 AI")
        ai_response = get_huggingface_response(user_message)
        reply_messages.append(V3TextMessage(text=ai_response))

    # --- [修改點 4] 使用 LINE Bot SDK v3 的方式回覆訊息 ---
    # 使用 ReplyMessageRequest 來發送回覆
    if reply_messages: # 確保有訊息要回覆
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=reply_messages # 傳遞訊息物件列表
            )
        )

# --- [修改點 5] 圖片訊息處理函數 (使用 v3 事件和訊息物件) ---
@handler.add(MessageEvent, message=ImageMessageContent) # 使用 ImageMessageContent
def handle_image_message(event):
    user_id = event.source.user_id
    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    reply_messages = [] # 用於收集要回覆的訊息物件

    if current_state_enum == UserState.REPORTING_WAIT_IMAGE and current_item_id:
        try:
            # line_bot_api.get_message_content 在 v3 中的行為不變
            message_content = line_bot_api.get_message_content(event.message.id)
            image_data = message_content.content # 獲取圖片的位元組數據

            original_filename = event.message.id + '.jpg'
            unique_filename = f"{uuid.uuid4()}_{original_filename}"

            local_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            with open(local_file_path, 'wb') as f:
                f.write(image_data)

            # --- [重要提醒] 圖片 URL 的生成方式 ---
            # 當部署在 Hugging Face Spaces 時，request.host 會是您的 Space URL。
            # 確保這個 URL 是可訪問的 HTTPS URL。
            base_url = f"https://{request.host}"
            image_url = f"{base_url}/static/uploads/{unique_filename}"
            print(f"Generated image URL: {image_url}")

            # --- [再次強調] 強烈建議使用雲端儲存服務來替代本地儲存 ---
            # 因為容器內儲存不持久化，部署到 Hugging Face Space 後，
            # 圖片會隨著容器重啟而丟失。
            # 您需要修改這部分邏輯，將圖片上傳到 AWS S3, Cloudinary 等，
            # 並將這些服務返回的公開 URL 儲存到資料庫。
            # 例如：
            # from cloudinary.uploader import upload
            # upload_result = upload(image_data, folder="linebot_lost_and_found")
            # image_url = upload_result['secure_url']


            db_manager.save_item_image_url(current_item_id, image_url)
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_DESCRIPTION, current_item_id)

            reply_messages.append(V3TextMessage(text="圖片已接收！請輸入您撿到失物的詳細描述 (例如：物品名稱、顏色、品牌、特徵等)。"))
        except Exception as e:
            print(f"Error handling image message: {e}")
            import traceback
            traceback.print_exc()
            reply_messages.append(V3TextMessage(text="圖片處理失敗，請再試一次。"))
    else:
        reply_messages.append(V3TextMessage(text="目前不支援圖片上傳，請再試一次。"))

    # --- [修改點 6] 使用 LINE Bot SDK v3 的方式回覆訊息 ---
    if reply_messages: # 確保有訊息要回覆
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=reply_messages
            )
        )

# --- [修改點 7] 位置訊息處理函數 (使用 v3 事件和訊息物件) ---
@handler.add(MessageEvent, message=LocationMessageContent) # 使用 LocationMessageContent
def handle_location_message(event):
    user_id = event.source.user_id
    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    reply_messages = [] # 用於收集要回覆的訊息物件

    if current_state_enum == UserState.REPORTING_WAIT_LOCATION and current_item_id:
        location_info = event.message.address # 從 v3 的 LocationMessageContent 獲取地址
        # 您也可以獲取經緯度：
        # latitude = event.message.latitude
        # longitude = event.message.longitude
        # print(f"Received location: {location_info} ({latitude}, {longitude})")

        db_manager.save_item_location(current_item_id, location_info)
        db_manager.clear_user_state(user_id) # 完成上報，清除狀態

        reply_messages.append(V3TextMessage(text="位置已接收！感謝您完成失物上報。"))
    else:
        reply_messages.append(V3TextMessage(text="目前不支援位置訊息，請再試一次。"))

    # --- [修改點 8] 使用 LINE Bot SDK v3 的方式回覆訊息 ---
    if reply_messages: # 確保有訊息要回覆
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=reply_messages
            )
        )

# --- [修改點 9] Flex Message 構建函數 (保留舊版 linebot.models 定義，但返回 V3FlexMessage) ---
def create_lost_items_flex_message(items):
    if not items:
        return V3TextMessage(text="目前沒有失物招領資訊。") # 返回 V3 TextMessage

    bubbles = []
    for item in items:
        # 確保圖片 URL 是 HTTPS
        image_url = item.get('image_url', 'https://via.placeholder.com/450x300?text=No+Image')
        # 如果圖片 URL 是本地路徑，需要在這裡轉換為可公開訪問的 URL
        # 在 Hugging Face Space 環境中，request.host 會是您的 Space URL
        if image_url.startswith('/static/uploads/'):
            base_url = f"https://{request.host}"
            image_url = f"{base_url}{image_url}"
            print(f"Adjusted Flex Image URL: {image_url}") # 打印調整後的 URL

        description_text = f"描述: {item.get('description', '無')}"
        location_text = f"位置: {item.get('location', '無')}"
        report_date_str = item.get('report_date', '無').split('T')[0] # 僅取日期部分

        bubble = BubbleContainer(
            direction='ltr',
            hero=ImageComponent(
                url=image_url,
                size='full',
                aspect_ratio='20:13',
                aspect_mode='cover',
                action=URIAction(uri=image_url, label='查看大圖') # 查看大圖的 URIAction
            ),
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(text=description_text, wrap=True, size='md'),
                    TextComponent(text=location_text, wrap=True, size='sm', color='#666666'),
                    TextComponent(text=f"日期: {report_date_str}", wrap=True, size='sm', color='#666666'),
                ]
            ),
            footer=BoxComponent(
                layout='vertical',
                spacing='sm',
                contents=[
                    ButtonComponent(
                        style='link',
                        height='sm',
                        action=URIAction(label='了解 LINE 應用', uri='https://line.me/zh-hant/')
                    ),
                    ButtonComponent(
                        style='link',
                        height='sm',
                        action=URIAction(label='地圖查看位置', uri=f'http://maps.google.com/?q={quote(item.get("location", ""))}') # 修改為更通用的 Google Maps 查詢
                    )
                ]
            )
        )
        bubbles.append(bubble)
        if len(bubbles) >= 10: # Flex Message Carousel 限制最多 10 個 Bubble
            break

    if bubbles:
        # 返回 V3 FlexMessage 物件
        return V3FlexMessage(alt_text="失物招領資訊", contents=CarouselContainer(contents=bubbles))
    else:
        return V3TextMessage(text="目前沒有失物招領資訊。")

# --- [修改點 10] 移除 Flask 應用程式啟動代碼 ---
# 由於您使用 Docker 和 Gunicorn，這些代碼不再需要
# if __name__ == "__main__":
#     app.run(host='0.0.0.0', port=5000, debug=True)

@app.route("/")
def health_check():
    logging.info("INFO: Health check route / accessed. Returning OK.")
    return "OK", 200

logging.info("INFO: Flask application is fully initialized.")

'''
# --- 新增的網路監聽日誌 ---
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('0.0.0.0', 8000))
    logging.info("INFO: Successfully bound to 0.0.0.0:8000 (socket test).")
    s.close()
except Exception as e:
    logging.error(f"FATAL ERROR: Could not bind to 0.0.0.0:8000 (socket test): {e}", exc_info=True)
    exit(1)
# --- 結束新增 ---
'''
