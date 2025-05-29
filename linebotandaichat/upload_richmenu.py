import json
import os
import requests

from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.messaging.models import RichMenuRequest, RichMenuSize, RichMenuArea, RichMenuBounds, PostbackAction

# 載入 channel access token
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
configuration = Configuration(access_token=channel_access_token)
headers = {
    'Authorization': f'Bearer {channel_access_token}',
    'Content-Type': 'image/jpeg'
}

# 讀取 richmenu.json
with open('richmenu.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 建立 SDK 需要的物件
richmenu_request = RichMenuRequest(
    size=RichMenuSize(width=data["size"]["width"], height=data["size"]["height"]),
    selected=data["selected"],
    name=data["name"],
    chat_bar_text=data["chatBarText"],
    areas=[
        RichMenuArea(
            bounds=RichMenuBounds(
                x=area["bounds"]["x"],
                y=area["bounds"]["y"],
                width=area["bounds"]["width"],
                height=area["bounds"]["height"],
            ),
            action=PostbackAction(
                data=area["action"]["data"],
                display_text=area["action"].get("displayText", "")
            )
        )
        for area in data["areas"]
    ]
)

with ApiClient(configuration) as api_client:
    line_bot_api = MessagingApi(api_client)

    # 創建 Rich Menu
    richmenu = line_bot_api.create_rich_menu(richmenu_request)
    print(f"RichMenu ID: {richmenu.rich_menu_id}")

    # 上傳圖片 (用 HTTP POST)
    image_path = '來聊天呀bro.jpg'
    url = f'https://api-data.line.me/v2/bot/richmenu/{richmenu.rich_menu_id}/content'

    with open(image_path, 'rb') as image_file:
        response = requests.post(url, headers=headers, data=image_file)
        if response.status_code == 200:
            print("✅ 圖片上傳成功")
        else:
            print(f"❌ 圖片上傳失敗: {response.status_code} {response.text}")

    # 設定為預設 Rich Menu (用 HTTP POST)
    url = f'https://api.line.me/v2/bot/user/all/richmenu/{richmenu.rich_menu_id}'

    response = requests.post(url, headers={'Authorization': f'Bearer {channel_access_token}'})
    if response.status_code == 200:
        print("✅ 設為預設 Rich Menu 成功")
    else:
        print(f"❌ 設為預設 Rich Menu 失敗: {response.status_code} {response.text}")
