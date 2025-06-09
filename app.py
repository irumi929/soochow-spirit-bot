import os
import uuid
import requests
from urllib.parse import quote
import socket
from flask import Flask, request, abort, send_from_directory
import json

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 從 linebot (v2) 導入核心類別 ---
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError

# --- 從 linebot.models 導入大多數訊息和組件類別 ---
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, LocationMessage,
    BubbleContainer, CarouselContainer,
    BoxComponent, TextComponent, ImageComponent, ButtonComponent, URIAction,
)
# 從 linebot.models 導入 TextSendMessage
from linebot.models import TextSendMessage


FlexSendMessage = None
try:
    from linebot.models import FlexSendMessage
    logging.info("DEBUG: FlexSendMessage imported successfully from linebot.models.")
except ImportError as e:
    logging.warning(f"WARNING: Could not import FlexSendMessage: {e}. Flex Message functionality will be limited or replaced with text messages.")

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

# --- 將 Line Webhook 處理邏輯合併到根目錄 ---
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

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    current_state_enum, current_item_id = db_manager.get_user_state(user_id)
    
    if user_message == "我撿到失物" or user_message == "上報失物":
        new_item_id = db_manager.create_new_lost_item(user_id)
        db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_IMAGE, new_item_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="好的，請您依照以下步驟上報失物：\n1. 請先傳送失物的『圖片』。")
        )
        return

    elif user_message == "找遺失物":
        items = db_manager.retrieve_lost_items()
        if items:
            # --- 判斷 FlexMessage 是否成功導入 ---
            if FlexSendMessage: # 如果 FlexMessage 成功導入，才使用 Flex Message
                flex_message = create_lost_items_flex_message(items)
                line_bot_api.reply_message(event.reply_token, flex_message)
            else: # 否則回退到文字訊息
                logging.warning("FlexMessage not available. Sending text message instead.")
                response_text = "目前有以下失物招領（由於 Flex Message 無法顯示）：\n"
                for i, item in enumerate(items):
                    description = item.get('description', '無')
                    location = item.get('location', '無')
                    report_date_str = item.get('report_date', '無').split('T')[0]
                    response_text += f"\n--- 失物 #{i+1} ---\n描述: {description}\n位置: {location}\n日期: {report_date_str}\n"
                    # 考慮在這裡添加圖片的 URL
                    image_url = item.get('image_url', '')
                    if image_url:
                        response_text += f"圖片連結: {image_url}\n"
                if len(response_text) > 2000:
                    response_text = response_text[:1990] + "...\n(內容過長，請精簡)"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response_text))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="目前沒有失物招領資訊。"))
        return

    elif user_message == "取消上報":
        db_manager.clear_user_state(user_id)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已取消失物上報。"))
        return

    if current_state_enum == UserState.REPORTING_WAIT_DESCRIPTION:
        if current_item_id:
            db_manager.save_item_description(current_item_id, user_message)
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_LOCATION, current_item_id)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="好的，請您提供撿到失物的『位置』(可直接傳送 Line 的位置訊息，或輸入文字描述)。")
            )
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="上報流程錯誤，請重新開始『我撿到失物』。"))
        return
    
    elif current_state_enum == UserState.REPORTING_WAIT_LOCATION:
        if current_item_id:
            db_manager.save_item_location(current_item_id, user_message)
            db_manager.clear_user_state(user_id) 
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="感謝您上報失物！我們已將資訊發佈。")
            )
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="上報流程錯誤，請重新開始『我撿到失物』。"))
        return

    print(f"用戶發送了非指令/流程訊息: {user_message}，嘗試呼叫 AI")
    #ai_response = get_huggingface_response(user_message)
    #line_bot_api.reply_message(
        #event.reply_token,
        #TextSendMessage(text=ai_response))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    user_id = event.source.user_id
    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    if current_state_enum == UserState.REPORTING_WAIT_IMAGE and current_item_id:
        try:
            message_content = line_bot_api.get_message_content(event.message.id)
            image_data = message_content.content

            original_filename = event.message.id + '.jpg'
            unique_filename = f"{uuid.uuid4()}_{original_filename}"

            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            local_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            with open(local_file_path, 'wb') as f:
                f.write(image_data)

            # 使用 request.url_root 來獲取應用程式的根 URL，並確保是 HTTPS
            image_url = request.url_root.rstrip('/') + '/static/uploads/' + unique_filename
            if not image_url.startswith('https://'): 
                image_url = image_url.replace('http://', 'https://')
            
            logging.info(f"Generated image URL: {image_url}") # 增加日誌，方便檢查 URL

            db_manager.save_item_image_url(current_item_id, image_url)
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_DESCRIPTION, current_item_id)

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="圖片已接收！請輸入您撿到失物的詳細描述 (例如：物品名稱、顏色、品牌、特徵等)。")
            )
        except Exception as e:
            logging.error(f"Error handling image message: {e}", exc_info=True) # 增加錯誤日誌
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="圖片處理失敗，請再試一次。")
            )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="目前不支援圖片上傳，請您先點選主選單的『我撿到失物』以開始上報流程。")
        )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    user_id = event.source.user_id
    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    if current_state_enum == UserState.REPORTING_WAIT_LOCATION and current_item_id:
        # 獲取經緯度
        latitude = event.message.latitude
        longitude = event.message.longitude

        location_info = f"{latitude},{longitude}" 

        db_manager.save_item_location(current_item_id, location_info)
        db_manager.clear_user_state(user_id) 

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="位置已接收！感謝您完成失物上報。")
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="目前不支援位置訊息，請您先點選主選單的『我撿到失物』以開始上報流程。")
        )

def create_lost_items_flex_message(items):
  
    if not FlexSendMessage or not BubbleContainer or not CarouselContainer or not BoxComponent or not TextComponent or not ImageComponent or not ButtonComponent or not URIAction:
        logging.warning("Flex Message components are not fully available. Returning a simple text message.")
        response_text = "目前有以下失物招領（由於 Flex Message 無法顯示）：\n"
        for i, item in enumerate(items):
            description = item.get('description', '無')
            location = item.get('location', '無')
            report_date_str = item.get('report_date', '無').split('T')[0]
            response_text += f"\n--- 失物 #{i+1} ---\n描述: {description}\n位置: {location}\n日期: {report_date_str}\n"
            image_url = item.get('image_url', '')
            if image_url:
                response_text += f"圖片連結: {image_url}\n"
        if len(response_text) > 2000:
            response_text = response_text[:1990] + "...\n(內容過長，請精簡)"
        return TextSendMessage(text=response_text)

    if not items:
        return TextSendMessage(text="目前沒有失物招領資訊。")

    bubbles = []
    for item in items:
        location = item.get("location", "")
        
        # 檢查位置是否為經緯度格式
        is_latlng = re.match(r'^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$', location.strip())
        
        # 根據是否為經緯度，決定地圖 URL
        # 注意：Google Maps URL 構造可能需要進一步確認，這裡假設簡單拼接
        map_url = f"https://www.google.com/maps/search/?api=1&query={quote(location)}" if is_latlng else None

        bubble = BubbleContainer(
            direction='ltr',
            hero=ImageComponent(
                url=item.get('image_url', 'https://via.placeholder.com/450x300?text=No+Image'),
                size='full',
                aspect_ratio='20:13',
                aspect_mode='cover',
                action=URIAction(uri=item.get('image_url', 'https://via.placeholder.com/450x300'), label='查看大圖')
            ),
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(text=f"描述: {item.get('description', '無')}", wrap=True, size='md'),
                    TextComponent(text=f"位置: {location}", wrap=True, size='sm', color='#666666'),
                    TextComponent(text=f"日期: {item.get('report_date', '無').split('T')[0]}", wrap=True, size='sm', color='#666666'),
                ]
            ),
            footer=BoxComponent(
                layout='vertical',
                spacing='sm',
                contents=[
                    ButtonComponent(
                        style='link',
                        height='sm',
                        action=URIAction(label='地圖查看位置', uri=map_url)
                    )
                ] if map_url else []  # 只有當 map_url 存在才顯示按鈕
            )
        )

        bubbles.append(bubble)
        if len(bubbles) >= 10:
            break

    return FlexSendMessage(alt_text="失物招領資訊", contents=CarouselContainer(contents=bubbles))

# 注意：這裡的 health_check 函數如果只處理 GET 請求，就不能和上面的 / 路由重複
# 如果您想保留，可以改成只處理 GET 請求，或者將其功能合併到 handle_root_requests 中
# 因為 handle_root_requests 已經處理了 GET 請求，這個 health_check 函數現在是多餘的
# 如果保留，它將永遠不會被調用，因為 / 路由已被 handle_root_requests 佔用。

# @app.route("/")
# def health_check():
#     logging.info(f"DEBUG: / route received a {request.method} request.")
#     logging.info(f"DEBUG: Request URL: {request.url}")
#     logging.info(f"DEBUG: Request Headers:")
#     for header, value in request.headers.items():
#         logging.info(f"DEBUG:   {header}: {value}")
#     logging.info("INFO: Health check route / accessed. Returning OK.")
#     return "Hello, I am running! (Flask App on Hugging Face Spaces)", 200

logging.info("INFO: Flask application is fully initialized.")