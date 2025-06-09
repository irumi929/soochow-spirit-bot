import os
import re
from flask import Flask, request, abort, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, LocationMessage
from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ImageComponent, ButtonComponent, URIAction, CarouselContainer 
from config import Config
from db_manager import DBManager, UserState
import uuid
#import requests

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER

line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
db_manager = DBManager(Config.SQLITE_DB_PATH) 

UPLOAD_FOLDER = os.path.join(os.getcwd(), "static", "uploads")

'''
def get_huggingface_response(user_text):
    api_url = Config.HUGGINGFACE_API_URL
    if not api_url:
        print("HUGGINGFACE_API_URL not set in config.")
        return "很抱歉，AI 服務配置不完整。"

    headers = {}
    if Config.HUGGINGFACE_API_TOKEN:
        headers['Authorization'] = f"Bearer {Config.HUGGINGFACE_API_TOKEN}"
    headers['Content-Type'] = 'application/json'

    payload = {"inputs": [user_text]}

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status() # 檢查 HTTP 錯誤狀態碼 (4xx 或 5xx)
        result = response.json()
        ai_reply = result.get("inputs", ["不好意思，我沒有理解您的意思。"])[0] 
        return ai_reply
    except requests.exceptions.RequestException as e:
        print(f"Error calling Hugging Face API: {e}")
        return "很抱歉，AI 服務目前無法回應，請稍後再試。"
    except Exception as e:
        print(f"Error processing Hugging Face response: {e}")
        return "很抱歉，AI 回覆處理出錯。"
'''

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
            flex_message = create_lost_items_flex_message(items)
            line_bot_api.reply_message(event.reply_token, flex_message)
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

            image_url = request.url_root.rstrip('/') + '/static/uploads/' + unique_filename

            if not image_url.startswith('https://') and not app.debug: 
                image_url = image_url.replace('http://', 'https://')

            db_manager.save_item_image_url(current_item_id, image_url)
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_DESCRIPTION, current_item_id)

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="圖片已接收！請輸入您撿到失物的詳細描述 (例如：物品名稱、顏色、品牌、特徵等)。")
            )
        except Exception as e:
            print(f"Error handling image message: {e}")
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
    if not items:
        return TextSendMessage(text="目前沒有失物招領資訊。")

    bubbles = []
    for item in items:
        location = item.get("location", "")
        
        is_latlng = re.match(r'^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$', location.strip())

        map_url = f"https://www.google.com/maps/search/?api=1&query={location}" if is_latlng else None

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

