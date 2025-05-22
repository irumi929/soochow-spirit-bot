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
