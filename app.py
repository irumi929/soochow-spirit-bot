import os
import uuid
import requests
from urllib.parse import quote
import socket
from flask import Flask, request, abort, send_from_directory
import json

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 從 linebot (v2) 導入所有必要的類別 ---
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, LocationMessage,
    FlexMessage,
    # Flex Message Components for v2
    BubbleContainer, CarouselContainer,
    BoxComponent, TextComponent, ImageComponent, ButtonComponent, URIAction,
)

try:
    from config import Config
    logging.info("DEBUG: Config module imported successfully.")
except Exception as e:
    logging.error(f"FATAL ERROR: Failed to import Config module: {e}", exc_info=True)
    exit(1)

try:
    from db_manager import DBManager, UserState
    logging.info("DEBUG: DBManager module imported successfully.")
except Exception as e:
    logging.error(f"FATAL ERROR: Failed to import DBManager module: {e}", exc_info=True)
    exit(1)

logging.info(f"DEBUG: Read LINE_CHANNEL_ACCESS_TOKEN length: {len(Config.LINE_CHANNEL_ACCESS_TOKEN) if Config.LINE_CHANNEL_ACCESS_TOKEN else 0}")
logging.info(f"DEBUG: Read LINE_CHANNEL_SECRET length: {len(Config.LINE_CHANNEL_SECRET) if Config.LINE_CHANNEL_SECRET else 0}")

try:
    # --- LineBotApi 和 WebhookHandler 的 v2 初始化方式 ---
    line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
    logging.info("DEBUG: LINE Bot API and WebhookHandler initialized successfully.")
except Exception as e:
    logging.critical(f"FATAL ERROR: Failed to initialize LINE Bot API or WebhookHandler. Exception: {e}", exc_info=True)
    line_bot_api = None
    handler = None

app = Flask(__name__)

try:
    app_port = os.getenv('GUNICORN_LISTEN_PORT')
    if not app_port:
        app_port = os.getenv('PORT', '5000')
    app.config['PORT'] = int(app_port)
    logging.info(f"DEBUG: Flask application configured to run on PORT: {app.config['PORT']}")
except ValueError:
    logging.error("FATAL ERROR: PORT environment variable is not a valid integer. Defaulting to 5000.")
    app.config['PORT'] = 5000
except Exception as e:
    logging.error(f"FATAL ERROR: Could not determine application PORT: {e}", exc_info=True)
    app.config['PORT'] = 5000

current_port = os.getenv('PORT')
logging.info(f"DEBUG: Application trying to run on PORT: {current_port}")

app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- V2 API 的初始化已經在前面完成，無需重複 ---
# line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
# handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
# V2 SDK 沒有 line_blob_api 這個概念，Blob 內容是通過 line_bot_api.get_message_content 獲取

db_manager = DBManager(Config.SQLITE_DB_PATH)
try:
    db_manager = DBManager(Config.SQLITE_DB_PATH)
    logging.info("DEBUG: DBManager initialized successfully.")
except Exception as e:
    logging.error(f"FATAL ERROR: Failed to initialize DBManager: {e}", exc_info=True)
    exit(1)

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/", methods=['POST', 'GET'])
def handle_root_requests():
    logging.info(f"DEBUG: / route received a {request.method} request (acting as webhook).")
    logging.info(f"DEBUG: Request URL: {request.url}")
    logging.info(f"DEBUG: Request Headers:")
    for header, value in request.headers.items():
        logging.info(f"DEBUG:   {header}: {value}")

    if request.method == 'GET':
        logging.info("INFO: Received GET request to / (likely health check or Line Webhook verification). Returning OK.")
        return "Hello, I am running! (Flask App on Hugging Face Spaces)", 200

    if handler is None:
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

        # --- v2 handler 處理方式不變 ---
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

    return 'OK'

# --- 文本訊息處理函數 (使用 v2 事件和訊息物件) ---
@handler.add(MessageEvent, message=TextMessage) # V2 中直接用 TextMessage
def handle_text_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    reply_messages = []

    if user_message == "上報失物":
        new_item_id = db_manager.create_new_lost_item(user_id)
        db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_IMAGE, new_item_id)
        reply_messages.append(TextMessage(text="好的，請您依照以下步驟上傳失物：\n1. 請先傳送失物的『圖片』。"))
    elif user_message == "找遺失物":
        items = db_manager.retrieve_lost_items()
        if items:
            # --- 使用 v2 的 FlexMessage 相關類別 ---
            flex_message = create_lost_items_flex_message(items)
            reply_messages.append(flex_message) # FlexMessage 物件
        else:
            reply_messages.append(TextMessage(text="目前沒有失物招領資訊。"))
    elif user_message == "取消上報":
        db_manager.clear_user_state(user_id)
        reply_messages.append(TextMessage(text="已取消失物上報。"))
    elif current_state_enum == UserState.REPORTING_WAIT_DESCRIPTION:
        if current_item_id:
            db_manager.save_item_description(current_item_id, user_message)
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_LOCATION, current_item_id)
            reply_messages.append(TextMessage(text="好的，請您提供撿到失物的『位置』(可直接傳送 Line 的位置訊息，或輸入文字描述)。"))
        else:
            db_manager.clear_user_state(user_id)
            reply_messages.append(TextMessage(text="上傳流程錯誤，請重新開始上傳失物的步驟。"))
    elif current_state_enum == UserState.REPORTING_WAIT_LOCATION:
        if current_item_id:
            db_manager.save_item_location(current_item_id, user_message)
            db_manager.clear_user_state(user_id)
            reply_messages.append(TextMessage(text="感謝您上傳失物！我們已將資訊發佈。"))
        else:
            db_manager.clear_user_state(user_id)
            reply_messages.append(TextMessage(text="上傳流程錯誤，請重新開始上傳失物的步驟。"))
    else:
        print(f"用戶發送了非指令/流程訊息: {user_message}，嘗試呼叫 AI")

    # --- 使用 LINE Bot SDK v2 的方式回覆訊息 ---
    if reply_messages:
        line_bot_api.reply_message(
            event.reply_token,
            reply_messages # 直接傳遞訊息物件列表
        )

# --- 圖片訊息處理函數 (使用 v2 事件和訊息物件) ---
@handler.add(MessageEvent, message=ImageMessage) # V2 中直接用 ImageMessage
def handle_image_message(event):
    user_id = event.source.user_id
    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    reply_messages = []

    if current_state_enum == UserState.REPORTING_WAIT_IMAGE and current_item_id:
        try:
            # --- V2 SDK 獲取訊息內容的方式 ---
            message_content = line_bot_api.get_message_content(event.message.id)
            image_data = message_content.content # V2 中 content 是屬性

            original_filename = event.message.id + '.jpg'
            unique_filename = f"{uuid.uuid4()}_{original_filename}"
            local_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            with open(local_file_path, 'wb') as f:
                # 這裡需要迭代 content.iter_content() 因為它可能是一個流
                for chunk in image_data:
                    f.write(chunk)

            base_url = f"https://{request.host}"
            image_url = f"{base_url}/static/uploads/{unique_filename}"
            print(f"Generated image URL: {image_url}")

            db_manager.save_item_image_url(current_item_id, image_url)
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_DESCRIPTION, current_item_id)

            reply_messages.append(TextMessage(text="圖片已接收！請輸入您撿到失物的詳細描述 (例如：物品名稱、顏色、品牌、特徵等)。"))
        except Exception as e:
            print(f"Error handling image message: {e}")
            import traceback
            traceback.print_exc()
            reply_messages.append(TextMessage(text="圖片處理失敗，請再試一次。"))
    else:
        reply_messages.append(TextMessage(text="目前不支援圖片上傳，請再試一次。"))

    if reply_messages:
        line_bot_api.reply_message(
            event.reply_token,
            reply_messages
        )

# --- 位置訊息處理函數 (使用 v2 事件和訊息物件) ---
@handler.add(MessageEvent, message=LocationMessage) # V2 中直接用 LocationMessage
def handle_location_message(event):
    user_id = event.source.user_id
    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    reply_messages = []

    if current_state_enum == UserState.REPORTING_WAIT_LOCATION and current_item_id:
        location_info = event.message.address # V2 的 LocationMessage 也有 address 屬性
        db_manager.save_item_location(current_item_id, location_info)
        db_manager.clear_user_state(user_id)

        reply_messages.append(TextMessage(text="位置已接收！感謝您完成失物上報。"))
    else:
        reply_messages.append(TextMessage(text="目前不支援位置訊息，請再試一次。"))

    if reply_messages:
        line_bot_api.reply_message(
            event.reply_token,
            reply_messages
        )

# --- Flex Message 建構函數 (v2 語法) ---
def create_lost_items_flex_message(items):
    if not items:
        return TextMessage(text="目前沒有失物招領資訊。")

    bubbles = []
    for item in items:
        image_url = item.get('image_url', 'https://via.placeholder.com/450x300?text=No+Image')
        if image_url.startswith('/static/uploads/'):
            base_url = f"https://{request.host}"
            image_url = f"{base_url}{image_url}"
            print(f"Adjusted Flex Image URL: {image_url}")

        description_text = f"描述: {item.get('description', '無')}"
        location_text = f"位置: {item.get('location', '無')}"
        report_date_str = item.get('report_date', '無').split('T')[0]

        # --- 使用 v2 的 Flex Message 組件類來構建 ---
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
        # v2 的 FlexMessage 構造器直接接收 alt_text 和內容
        return FlexMessage(
            alt_text="失物招領資訊",
            contents=CarouselContainer(contents=bubbles)
        )
    else:
        return TextMessage(text="目前沒有失物招領資訊。")

@app.route("/")
def health_check():
    logging.info(f"DEBUG: / route received a {request.method} request.")
    logging.info(f"DEBUG: Request URL: {request.url}")
    logging.info(f"DEBUG: Request Headers:")
    for header, value in request.headers.items():
        logging.info(f"DEBUG:   {header}: {value}")
    logging.info("INFO: Health check route / accessed. Returning OK.")
    return "Hello, I am running! (Flask App on Hugging Face Spaces)", 200

logging.info("INFO: Flask application is fully initialized.")