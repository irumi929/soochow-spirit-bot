import os
import uuid
import requests
from urllib.parse import quote
import socket
from flask import Flask, request, abort, send_from_directory
import json # 新增導入

# 從 linebot.v3.messaging 導入核心 API 和頂層訊息類別
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage as V3TextMessage,
    ImageMessage as V3ImageMessage,
    LocationMessage as V3LocationMessage,
    FlexMessage as V3FlexMessage,
    MessagingApiBlob,
)

# 從 linebot.v3.messaging.models.flex 導入 Flex Message 的具體組件類別
# 注意這裡的導入路徑變成了 linebot.v3.messaging.models.flex
from linebot.v3.messaging.models.flex import (
    BoxComponent,
    TextComponent,
    ImageComponent,
    ButtonComponent,
    URIAction,
    CarouselContainer, # CarouselContainer 和 BubbleContainer 也可能在這裡
    BubbleContainer,   # 如果在這裡導入仍失敗，再將它們移回 linebot.v3.messaging.models
)


from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent
)
from linebot.v3.exceptions import InvalidSignatureError



# ... 程式碼的其餘部分保持不變 ...

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


# 在Config導入之後，檢查讀取到的值是否完整
logging.info(f"DEBUG: Read LINE_CHANNEL_ACCESS_TOKEN length: {len(Config.LINE_CHANNEL_ACCESS_TOKEN) if Config.LINE_CHANNEL_ACCESS_TOKEN else 0}")
logging.info(f"DEBUG: Read LINE_CHANNEL_SECRET length: {len(Config.LINE_CHANNEL_SECRET) if Config.LINE_CHANNEL_SECRET else 0}")
# 甚至可以打印幾個中間字符，例如：
# logging.info(f"DEBUG: LINE_CHANNEL_ACCESS_TOKEN mid: {Config.LINE_CHANNEL_ACCESS_TOKEN[5:10] if Config.LINE_CHANNEL_ACCESS_TOKEN and len(Config.LINE_CHANNEL_ACCESS_TOKEN) > 10 else 'N/A'}")

# 在 LINE Bot API 初始化部分
try:
    configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
    line_bot_api = MessagingApi(ApiClient(configuration))
    handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
    logging.info("DEBUG: LINE Bot API and WebhookHandler initialized successfully.")
except Exception as e:
    # 強調這個錯誤，並確保在應用程式日誌中能看到它
    logging.critical(f"FATAL ERROR: Failed to initialize LINE Bot API or WebhookHandler. Exception: {e}", exc_info=True)
    line_bot_api = None # 確保它們是 None
    handler = None

app = Flask(__name__)

try:
    # 這裡我們嘗試從 Gunicorn 相關的環境變數中獲取，或回退到 $PORT
    # 注意：Gunicorn通常會設定自身的PORT，而不是直接用$PORT
    # 但如果 $PORT 是唯一的，就用 $PORT
    # 通常 Gunicorn 綁定的埠號就是它自己的 process 埠號
    app_port = os.getenv('GUNICORN_LISTEN_PORT') # Gunicorn可能設置這個變數
    if not app_port:
        app_port = os.getenv('PORT', '5000') # 回退到 $PORT 或預設 5000
    app.config['PORT'] = int(app_port)
    logging.info(f"DEBUG: Flask application configured to run on PORT: {app.config['PORT']}")
except ValueError:
    logging.error("FATAL ERROR: PORT environment variable is not a valid integer. Defaulting to 5000.")
    app.config['PORT'] = 5000 # 如果PORT不是數字，預設為5000
except Exception as e:
    logging.error(f"FATAL ERROR: Could not determine application PORT: {e}", exc_info=True)
    app.config['PORT'] = 5000 # 任何其他錯誤也預設為5000

current_port = os.getenv('PORT')
logging.info(f"DEBUG: Application trying to run on PORT: {current_port}")

app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- [修改點 2] 初始化 LINE Bot API (使用 v3 方式) ---
configuration = Configuration(access_token=Config.LINE_CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(ApiClient(configuration))
line_blob_api = MessagingApiBlob(ApiClient(configuration))

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

# --- **核心修改：將 /callback 路由邏輯移動到根目錄 / ** ---
@app.route("/", methods=['POST', 'GET']) # 將路由改為根目錄
def handle_root_requests(): # 函數名稱可以改，以反映其處理多種請求的性質
    # --- 新增的深度日誌 ---
    logging.info(f"DEBUG: / route received a {request.method} request (acting as webhook).")
    logging.info(f"DEBUG: Request URL: {request.url}")
    logging.info(f"DEBUG: Request Headers:")
    for header, value in request.headers.items():
        logging.info(f"DEBUG:   {header}: {value}")
    # --- 結束新增 ---

    if request.method == 'GET':
        # 如果是 GET 請求，可能來自瀏覽器訪問，或者 Line Webhook 驗證
        logging.info("INFO: Received GET request to / (likely health check or Line Webhook verification). Returning OK.")
        # 您可以返回更詳細的健康檢查信息，或者簡單的 OK
        return "Hello, I am running! (Flask App on Hugging Face Spaces)", 200 # 返回健康檢查訊息

    # 以下是處理 LINE Webhook 的 POST 請求邏輯
    if handler is None: # 如果 handler 沒有被成功初始化
        logging.error("ERROR: Line WebhookHandler is not initialized. Aborting POST request.")
        abort(500, description="Line WebhookHandler not initialized.")

    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        json_body = json.loads(body)
        if not json_body.get('events'):
            logging.info("INFO: Received POST request to / with empty or no events. Returning OK for verification.")
            return 'OK', 200

        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        logging.error("ERROR: Invalid signature. Check your channel access token/channel secret.")
        abort(400)
    except json.JSONDecodeError:
        logging.error("ERROR: Received non-JSON body to / POST request. Returning 400 Bad Request.")
        abort(400, description="Invalid JSON format.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        logging.error(f"ERROR: An unexpected error occurred: {e}\n{traceback.format_exc()}")
        abort(500)

    return 'OK' # 成功處理 POST 請求後返回 200 OK

# --- [修改點 3] 文本訊息處理函數 (使用 v3 事件和訊息物件) ---
@handler.add(MessageEvent, message=TextMessageContent) # 使用 TextMessageContent
def handle_text_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    reply_messages = [] # 用於收集要回覆的訊息物件

    if user_message == "上報失物":
        new_item_id = db_manager.create_new_lost_item(user_id)
        db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_IMAGE, new_item_id)
        reply_messages.append(V3TextMessage(text="好的，請您依照以下步驟上傳失物：\n1. 請先傳送失物的『圖片』。"))
    elif user_message == "找遺失物":
        items = db_manager.retrieve_lost_items()
        if items:
            flex_message = create_lost_items_flex_message(items)
            reply_messages.append(flex_message) # flex_message 已經是 V3FlexMessage 物件
        else:
            reply_messages.append(V3TextMessage(text="目前沒有失物招領資訊。"))
    elif user_message == "取消上報":
        db_manager.clear_user_state(user_id)
        reply_messages.append(V3TextMessage(text="已取消失物上報。"))
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
        #ai_response = get_huggingface_response(user_message) # 這行仍被註解掉了，請確認是否需要啟用
        #reply_messages.append(V3TextMessage(text=ai_response))

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
            # *** 修改這行！從 line_bot_api 改為 line_blob_api ***
            message_content = line_blob_api.get_message_content(event.message.id)
            image_data = message_content
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

def create_lost_items_flex_message(items):
    if not items:
        return V3TextMessage(text="目前沒有失物招領資訊。")

    bubbles = [] # 用於存放 BubbleContainer 物件
    for item in items:
        image_url = item.get('image_url', 'https://via.placeholder.com/450x300?text=No+Image')
        if image_url.startswith('/static/uploads/'):
            base_url = f"https://{request.host}"
            image_url = f"{base_url}{image_url}"
            print(f"Adjusted Flex Image URL: {image_url}")

        description_text = f"描述: {item.get('description', '無')}"
        location_text = f"位置: {item.get('location', '無')}"
        report_date_str = item.get('report_date', '無').split('T')[0]

        # 使用 BubbleContainer 和其他組件類來構建 Flex Message
        bubble = BubbleContainer(
            direction='ltr',
            hero=ImageComponent(
                url=image_url,
                size='full',
                aspect_ratio='20:13',
                aspect_mode='cover',
                action=URIAction(label='查看大圖', uri=image_url)
            ),
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(text=description_text, wrap=True, size='md'),
                    TextComponent(text=location_text, wrap=True, size='sm', color='#666666'),
                    TextComponent(text=f"日期: {report_date_str}", wrap=True, size='sm', color='#666666')
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
                        action=URIAction(label='地圖查看位置', uri=f'http://maps.google.com/maps?q={quote(item.get("location", ""))}')
                    )
                ]
            )
        )
        bubbles.append(bubble)
        if len(bubbles) >= 10:
            break

    if bubbles:
        # 現在直接使用 CarouselContainer 物件
        carousel_container = CarouselContainer(contents=bubbles)
        # V3FlexMessage 的 contents 參數將直接接收這個 CarouselContainer 物件
        return V3FlexMessage(alt_text="失物招領資訊", contents=carousel_container)
    else:
        return V3TextMessage(text="目前沒有失物招領資訊。")
    
@app.route("/")
def health_check():
    # --- 新增的深度日誌 ---
    logging.info(f"DEBUG: / route received a {request.method} request.")
    logging.info(f"DEBUG: Request URL: {request.url}")
    logging.info(f"DEBUG: Request Headers:")
    for header, value in request.headers.items():
        logging.info(f"DEBUG:   {header}: {value}")
    # --- 結束新增 ---
    logging.info("INFO: Health check route / accessed. Returning OK.")
    return "Hello, I am running! (Flask App on Hugging Face Spaces)", 200 # <-- 保持這個訊息，方便您在瀏覽器確認

logging.info("INFO: Flask application is fully initialized.")
