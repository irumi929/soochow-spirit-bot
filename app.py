import os
from flask import Flask, request, abort, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, LocationMessage
from linebot.models import FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ImageComponent, ButtonComponent, URIAction, CarouselContainer

from config import Config
from db_manager import DBManager, UserState 
import uuid
import requests 
from urllib.parse import quote

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER

line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
db_manager = DBManager(Config.SQLITE_DB_PATH) 

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
    headers['Content-Type'] = 'application/json' # 根據API要求

    # 這是 Gradio API 的常見輸入格式，請根據您的 Spaces API 調整
    payload = {"data": [user_text]}

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status() # 檢查 HTTP 錯誤狀態碼 (4xx 或 5xx)
        result = response.json()
        # 根據 Hugging Face Spaces 返回的數據結構提取 AI 回覆
        ai_reply = result.get("data", ["不好意思，我沒有理解您的意思。"])[0] # 假設返回在 'data' 列表的第一個元素
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
        # 這裡打印詳細錯誤堆疊，以便調試
        import traceback
        traceback.print_exc()
        abort(500)
    return 'OK' # 成功處理後返回 200 OK

# --- 訊息處理器 ---

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    
    # 正確地獲取用戶狀態和當前項目ID
    # current_state_enum 是 UserState 枚舉的一個成員 (例如 UserState.NONE)
    # current_item_id 是字串或 None
    current_state_enum, current_item_id = db_manager.get_user_state(user_id) 
    
 
    if user_message == "撿到失物" or user_message == "上報失物":
        new_item_id = db_manager.create_new_lost_item(user_id)
        db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_IMAGE, new_item_id)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="好的，請您依照以下步驟上報失物：\n1. 請先傳送失物的『圖片』。")
        )
        return

    elif user_message == "查看失物招領":
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

    # 處理流程中的文字訊息
    # 直接使用枚舉物件進行比較
    if current_state_enum == UserState.REPORTING_WAIT_DESCRIPTION:
        if current_item_id:
            db_manager.save_item_description(current_item_id, user_message)
            # 更新狀態並傳遞當前的 item_id
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_LOCATION, current_item_id)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="好的，請您提供撿到失物的『位置』(可直接傳送 Line 的位置訊息，或輸入文字描述)。")
            )
        else:
            # 如果沒有 current_item_id 但處於等待描述的狀態，可能是流程出錯
            db_manager.clear_user_state(user_id) # 清除狀態以防止循環錯誤
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="上報流程錯誤，請重新開始『我撿到失物』。"))
        return
    elif current_state_enum == UserState.REPORTING_WAIT_LOCATION:
        if current_item_id:
            db_manager.save_item_location(current_item_id, user_message)
            db_manager.clear_user_state(user_id) # 完成上報，清除狀態
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="感謝您上報失物！我們已將資訊發佈。")
            )
        else:
            # 如果沒有 current_item_id 但處於等待位置的狀態
            db_manager.clear_user_state(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="上報流程錯誤，請重新開始『我撿到失物』。"))
        return

    # 預設：交給 AI 回覆
    print(f"用戶發送了非指令/流程訊息: {user_message}，嘗試呼叫 AI")
    ai_response = get_huggingface_response(user_message)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=ai_response)
    )

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
            
            # 確保 UPLOAD_FOLDER 存在
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            local_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            with open(local_file_path, 'wb') as f:
                f.write(image_data)

            # 確保生成的 URL 是 HTTPS
            base_url = request.url_root.rstrip('/')
            if not base_url.startswith('https://'):
                base_url = f"https://{request.host}" 
            
            image_url = f"{base_url}/static/uploads/{unique_filename}"
            print(f"Generated image URL (corrected): {image_url}") # 打印修正後的 URL
         
            
            db_manager.save_item_image_url(current_item_id, image_url) 
            db_manager.update_user_state(user_id, UserState.REPORTING_WAIT_DESCRIPTION, current_item_id) 

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="圖片已接收！請輸入您撿到失物的詳細描述 (例如：物品名稱、顏色、品牌、特徵等)。")
            )
        except Exception as e:
            print(f"Error handling image message: {e}")
            import traceback
            traceback.print_exc()
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
    # 正確地獲取用戶狀態和當前項目ID
    current_state_enum, current_item_id = db_manager.get_user_state(user_id)

    # 直接使用枚舉物件進行比較
    if current_state_enum == UserState.REPORTING_WAIT_LOCATION and current_item_id:
        location_info = event.message.address 
        db_manager.save_item_location(current_item_id, location_info)
        db_manager.clear_user_state(user_id) # 完成上報，清除狀態

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
        image_url = item.get('image_url', 'https://via.placeholder.com/450x300?text=No+Image')
        
        description_text = f"描述: {item.get('description', '無')}"
        location_text = f"位置: {item.get('location', '無')}"
        report_date_str = item.get('report_date', '無').split('T')[0]

        bubble = BubbleContainer(
            direction='ltr',
            hero=ImageComponent(
                url=image_url,
                size='full',
                aspect_ratio='20:13',
                aspect_mode='cover',
                action=URIAction(uri=image_url, label='查看大圖') # 這裡的 image_url 必須是 HTTPS
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
                        action=URIAction(label='地圖查看位置', uri=f'https://www.google.com/maps/search/?api=1&query={quote(item.get("location", ""))}')
                    )
                ]
            )
        )
        bubbles.append(bubble)
        if len(bubbles) >= 10:
            break
    
    if bubbles:
        return FlexSendMessage(alt_text="失物招領資訊", contents=CarouselContainer(contents=bubbles))
    else:
        return TextSendMessage(text="目前沒有失物招領資訊。")

if __name__ == "__main__":
    if not os.path.exists(Config.UPLOAD_FOLDER):
        os.makedirs(Config.UPLOAD_FOLDER)