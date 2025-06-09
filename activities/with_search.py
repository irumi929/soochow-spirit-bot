from flask import Flask, render_template, request, session, flash
from flask_session import Session
from bs4 import BeautifulSoup
import markdown
import os
import logging

from google import genai
from google.genai import types
from google.genai.types import Tool, GoogleSearch, GenerateContentConfig

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "sookey123")
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

google_api_key = os.getenv("GOOGLE_API_KEY")
if not google_api_key:
    raise EnvironmentError("❌ GOOGLE_API_KEY 環境變數未設定！")

client = genai.Client(api_key=google_api_key)
google_search_tool = Tool(google_search=GoogleSearch())

chat = client.chats.create(
    model="gemini-2.0-flash",
    config=GenerateContentConfig(
        system_instruction="你是一個繁體中文的AI助手，請用繁體中文回答，你很了解東吳大學在2025年6月10號以後到學期末的活動資訊。你會知道以下這些活動:活動日期：2025/06/17;活動標題：【美育活動畢業標準】東吳吉他社│49屆期末成果發表〈吉點了！還4不出來喝9嗎〉;活動詳情：這次活動將場地設置在公館Pipe，開放給全校師生與外校學生參與，以更高的品質為目標來籌畫此次期末成發，藉由音樂演出也能推廣東吳吉他社和東吳大學的藝術素養。也想藉由期末成果發表的表演，與大家分享我們整個學期的收穫和成長。同時希望能透過我們對音樂的熱情和喜愛，吸引到更多對音樂有興趣、有夢想的人加入吉他社，促進音樂欣賞文化在大學校園的流動，以提升藝文素養。活動流程：17:45~18:00 進場 18:00~21:30 表演 21:30~22:00 散場與場復。是否需要付費：否。活動時間：17:45~21:15。報名時間：2025/05/20 00:00~2025/06/17 18:00。總攜伴人數限制（不含本人）：0。活動舉辦單位：群育暨美育中心。活動地點分類：校外。活動地點：Pipe Live Music。活動總人數限制：150。活動已報名人數：4。活動可報名人數：146。活動報名狀態：可報名。//活動日期：2025/06/18。活動標題：【美育活動畢業標準】狂戀大提琴-音樂學系大提琴重奏團音樂會。活動詳情：演出日期調整為2025.06.11(三)。演出人員：指導/侯柔安，東吳大學音樂學系大提琴重奏團。演出曲目：Heitor Villa-Lobos: Bachianas Brasileiras No.1(等多首精彩曲目)。是否需要付費：否。活動時間：19:00~21:00。報名時間：2025/03/04 00:00~2025/06/18 00:00。總攜伴人數限制（不含本人）：0。活動舉辦單位：音樂學系。活動地點分類：雙溪校區。活動地點：松怡廳。活動總人數限制：300。活動已報名人數：25。活動可報名人數：275。活動報名狀態：可報名。//活動日期：2025/06/20。活動標題：【美育活動畢業標準】東吳熱舞社│貳拾伍屆傳賢成果展-《塵》。活動詳情：「塵」，是世間萬象流轉的痕跡，亦是滄桑與無常的見證。它承載過往，也預示變化，如同每一次舞動，瞬息即逝卻深刻不滅。以「塵」為名，借東方文化的意象，描繪塵世之中的情感與故事。在光影交錯間，舞出生命的韻律，在塵埃飛揚處，尋找屬於我們的舞蹈軌跡。它承載過往，也預示變化，如同每一次舞動，瞬息即逝卻深刻不滅。於是我們舞。在光影交錯之中，以身體為語言，每一個步伐，都像是在塵土上留下的痕跡，短暫，卻存在。在不斷消散的軌跡中，我們試圖留下什麼，也學會放下什麼。終於明白，塵，不只是結束的象徵，也是每一次重生的開始。活動流程:18：10～19：00 觀眾入場，19：00～19：30 成發上半場，19：40～20：00中場休息+抽獎，20：00～20：35成發下半場，20：40～21：00感性時間+官方拍照，21：00～21：15自由拍。是否需要付費：否。活動時間：15:00~17:00。報名時間：2025/05/20 00:00~2025/06/20 15:15。總攜伴人數限制（不含本人）：0。活動舉辦單位：群育暨美育中心。活動地點分類：雙溪校區。活動地點：傳賢堂。活動總人數限制：1000。活動已報名人數：16。活動可報名人數：984。活動報名狀態：可報名。",
        tools=[google_search_tool],
        response_modalities=["TEXT"],
    )
)

def query(question):
    app.logger.info(f"使用者問題：{question}")
    try:
        response = chat.send_message(message=question)
        return response.text
    except Exception as e:
        app.logger.error(f"Gemini 回應錯誤：{e}")
        return "發生錯誤，請稍後再試。"

@app.route("/", methods=["GET", "POST"])
def search():
    # 初始化聊天歷史
    if "chat_history" not in session:
        session["chat_history"] = [
            {
                "role": "bot",
                "text": "哈囉！很高興為你服務！請問有什麼我可以幫忙的嗎？我對東吳大學的活動資訊很了解！"
            }
        ]

    if request.method == "POST":
        user_input = request.form.get("query", "").strip()
        if user_input:
            # 將使用者訊息加入聊天歷史
            session["chat_history"].append({"role": "user", "text": user_input})

            # 送到 Gemini AI
            raw_response = query(user_input)

            # 可選：用 markdown 轉換並解析純文字
            html_msg = markdown.markdown(raw_response)
            soup = BeautifulSoup(html_msg, "html.parser")
            answer = soup.get_text()

            # 將機器人回答加入歷史
            session["chat_history"].append({"role": "bot", "text": answer})

            # 強制更新 session
            session.modified = True
        else:
            flash("請輸入問題內容", "warning")

    return render_template("index.html", chat_history=session.get("chat_history", []))

if __name__ == "__main__":
    app.run(debug=True)