🧩 1. 基礎查詢服務模組
👉 名稱建議：CampusInfo 中樞站（或簡稱：CI 模組）

📘 說明：
提供日常查詢所需的一切資訊，包括課程、成績、活動、地圖、交通、失物，像是一個資訊服務的「樞紐」。

📌 備選名稱：

校園資訊站 Campus Info Center

學習生活小幫手

SmartQuery 智能查詢模組

🤖 2. 智慧預測與分析模組（機器學習）
👉 名稱建議：SmartPredict 智慧預測引擎（或簡稱：SP 模組）

📘 說明：
整合機器學習進行數據預測與分析，幫助使用者做出更好的決策，例如：活動人數、用餐時間等。

📌 備選名稱：

校園AI分析室

SmartCampus Insight

數據預測中心 DataForecast Core

💬 3. 互動與社群模組
👉 名稱建議：CampusConnect 校園互動圈（或簡稱：CC 模組）

📘 說明：
打造學生交流、社團互動與意見反饋的空間，營造出屬於學生的互助社群。

📌 備選名稱：

學習社群站 LearnTogether

互動留言區 CampusTalk

學生回饋中心



----------------------------------------------------
🧱 資料庫設計（建議表格數：3～4 個）
🗂️ 1. users 表（儲存用戶基本資訊）
欄位名稱	類型	說明
id	TEXT	使用者 Line ID（主鍵）
nickname	TEXT	暱稱（可選）
joined_at	DATETIME	加入時間

💬 2. chatrooms 表（儲存聊天室主題）
欄位名稱	類型	說明
id	INTEGER	主鍵，自動編號
room_name	TEXT	聊天室名稱，例如「微積分」「攝影社」
type	TEXT	類型（課程/社團）
created_at	DATETIME	建立時間

👥 3. memberships 表（使用者加入的聊天室）
欄位名稱	類型	說明
id	INTEGER	主鍵
user_id	TEXT	對應 users.id
chatroom_id	INTEGER	對應 chatrooms.id
joined_at	DATETIME	加入聊天室時間

🔄 這是一個 多對多關聯表，一個人可以加入多個聊天室，一個聊天室也有多人。

📝 4. messages 表（聊天室中的訊息記錄）
欄位名稱	類型	說明
id	INTEGER	主鍵
chatroom_id	INTEGER	對應聊天室
user_id	TEXT	發話者 ID
message	TEXT	發言內容
created_at	DATETIME	發言時間


---------------------------------------------------------------------------
| Space 名稱 (建議)            | 包含功能範圍                              | 理由 / 好處                    |
| ------------------------ | ----------------------------------- | -------------------------- |
| 1. tonlingbot-base       | 基本查詢服務（課程查詢、成績查詢、活動資訊、校園地圖、交通、失物招領） | 集中核心查詢功能，維護方便，更新迅速         |
| 2. tonlingbot-ai-chat    | AI 聊天機器人（對話聊天、問答、NLP 回饋）            | AI 模型獨立部署，避免影響主系統性能        |
| 3. tonlingbot-prediction | 智慧預測模組（活動參與、餐廳用餐人數預測等）              | 預測功能較複雜，獨立管理模型和資料          |
| 4. tonlingbot-community  | 學生社群互動（聊天室、討論區、社團互動）                | 互動與社群有特殊需求（UI、即時性等），獨立部署較佳 |



Irumi165/tonlingbot-community 其中一個有成功的space 刪了
課程查詢教室甚麼的資料在學校網站裡面 因為要登入所以很難爬 可以改成剩dcard爬資料(我在試)
