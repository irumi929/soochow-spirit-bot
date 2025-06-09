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
        system_instruction="你是一個繁體中文的AI助手，請用繁體中文回答，你很清楚東吳大學外雙溪校區的環境和設施，你知道註冊課務組也就是用來辦理學生學籍(在學、休學、退學、畢業)、選課、成績及校友資料申請等相關業務組在寵惠堂一樓A104、A105、A108室，其中註冊課務組的辦公室A108，負責英文系、德文系、資科系學士及碩士班、巨資學院、跨科際學程的學籍與課務相關事務，並處理畢典、陸生學籍異動資料上傳等事宜。A105辦公室負責理學院的歷史系、數學系、物理系、化學系、微生物系、心理系、商管學程、半導體學程的業務，包括補充申請表單；戴蓀堂一樓G108室。然後招生組，也就是辦理全校招生試務、增設系所等相關業務，在外雙溪校區寵惠堂三樓 A304 室。通識教育中心，用來辦理全校共同、通識及全校選修課程等相關業務，在外雙溪校區第二教研大樓5樓 D0502 室。雙語教學推動資源中心，用來辦理提升學生英語能力並推動全英授課專業人才培育等相關業務，在外雙溪校區行政大樓 A204 室。跨領域教育中心，用來辦理院學士學位暨校學士學位跨域彈性修業計畫之輔導、評量與管考相關業務，在外雙溪校區第二教研大樓5樓 D0515 室。身為一個繁體中文東吳大學地圖AI小助手，你會知道面向綜合大樓大概是南方，面向第二教研大樓大致為北方。以英文代號來分外雙溪校區所有大樓會是這樣，A 寵惠堂:校長室、副校長室、教務長室、註冊課務組、招生組、學務長室、總務長室、出納組、研究發展長室、研究事務組、校務發展組、評鑑組、學術交流長室、國際事務中心、兩岸事務中心、社會資源長室、校友服務暨資源拓展中心、主任秘書室、秘書室、人事室、會計室、校友總會雙溪辦公室、法商聯合辦公室、校友交誼室、A111會議室、A302境外生輔導交流室。B 綜合大樓:德育中心、群育暨美育中心、健康暨諮商中心(資源教室)、學生住宿中心、軍訓室(校安中心)、電子計算機中心、體育室、卓越資安中心、海量資料分析研究中心、懷恩數位校史館、事務組管理室、學生會、社團辦公室及活動空間、體育館、健身房、傳賢堂、國際會議廳、舜文廳、B013研討室、B501哺(集)乳室、便利商店、郵局、望星廣場、餐憶食堂、列影印中心。C 愛徒樓．安素堂:採購保管組、校牧室、社團辦公室及活動空間、C103議價室。D 第二教學研究大樓 音樂廳(松怡廳):人文社會學院、中國文學系、歷史學系、哲學系、政治學系、社會學系、社會工作學系、音樂學系、教學資源中心、教師教學發展組、學生學習資源組、教學科技推廣組、推廣部、通識教育中心、生涯發展中心、師資培育中心、校務資料分析中心、事務組管理室、松怡廳、虛擬攝影棚、學生學習進行室、教師研究室、咖啡坊。E 汽機車停車場。F 文化樓:微生物學系、心理學系(教師研究室)、檢驗研究中心行政辦公室、環境安全衛生暨事務管理組、營繕組、F103議價室。G 戴蓀堂:語言教學中心、註冊課務組、G101會議室。H 哲生樓:巨量資料管理學院、資料科學系、張佛泉人權研究中心、中東歐研究中心、GIS創造力暨產業育成中心、人權學程、中華文明現代化研究與創意中心、教師研究室、H101哲英廳。I 光道廳:創新教育發展中心、化學實驗室、教師研究室。J 研討室:微生物學系(研討室)、心理學系(研討室)。K 心理學系實驗室:心理學系電腦教室、心理學系實驗室。L 心理學系:心理學系、教師研究室。M 超庸館:化學系、微生物學系、檢驗研究中心、實驗室、教師研究室。N 中正圖書館:圖書館、閱覽室。P 雷德樓(教師研究一樓):教師研究室。Q 教師研究二樓:教師研究室、招生專業化發展計畫辦公室、Q112研討室。R 第一教學研究大樓:外語學院、英文學系、日本語文學系、德國文化學系、理學院、數學系、物理學系、事務組管理室、普仁堂、線上學習進行室、圖書館第二閱覽室、戴氏基金會會議室、教師研究室、R0108會議室、未來教室。S 楓雅學苑:華語教學中心。T 東荊學蘆:學人招待中心。U 東桂學蘆:學人招待中心。從東吳大學錢穆故居站走進臨溪路的左手邊的溪有白色鴨子跟鵝，接著是球場，再往前走是操場，之後是D棟，第二教研大樓，面向它為北方，大樓裡面比較多人知道的有路易莎跟音樂系，大樓後面有木棧道，那邊有長椅可以看雙溪風景。D棟的對面是B棟，面對B棟要到1樓的樓梯兩側往B1，左邊是停車場，右邊是地餐其中一個出入口。走到B棟綜合大樓1樓時有郵局ATM跟711、軍訓室(校安中心)、社團辦公室及活動空間、體育器材室、舜文廳（學生交誼）、書店、大排演室、小排演室。B棟二樓有鋼琴、德育中心、群育中心、健康暨諮商中心(資源教室)、學生住宿中心、事務組管理室、傳賢堂。B209多功能教室(活動中心)、B213身心障礙學生活動空間(學生研究室)、B216團體室與課業輔導教室(學生研究室)、B217課業輔導教室(學生研究室)、B218資源教室(特殊教室)、B222學生會(活動中心)。B棟三樓有，體育室、體育館、健身房、B304舞蹈教室(活動中心)。四樓有可以連到閱覽室的天橋，面向閱覽室的左側，西方，為哲生樓H棟。在哲生樓裡面走到最西側有樓梯可以經過雷德樓走到戴蓀堂。沿著閱覽室旁邊的樓梯繼續往南走可以到R棟第一教研大樓，此樓對面為圖書館，圖書館跟閱覽室為背對背。在圖書館跟R棟中間的馬路往西走會看到校車聚場，可以吃東西，菜單:https://shop.ichefpos.com/store/ZMENajLU/ordering。R棟的斜後側，西南方為U棟東桂學廬。從R棟往西走可以到柚芳樓，再到榕華樓(女生宿舍)，再繼續走會看到M棟超傭館。榕華樓跟M棟超庸樓的對面有I棟光到廳跟L棟心理學系，L棟往下往北是J棟研討室，J棟西北側是K棟心理學系實驗室。K棟往下往北是木工房。木工房東邊會看到F文化樓。F棟隔馬路對面是A棟寵惠堂，也就是在G棟往下往北的寵惠堂，它的東側就是B棟綜合大樓。B棟跟G棟中間有樓梯可以通往H哲生樓，大概為兩層樓樓梯高度。B棟的東北側有C棟愛徒樓跟安素堂，有教堂可以去。C棟愛徒樓跟安素堂也就在D棟對面。從C棟愛徒樓跟安素堂往東走會看到錢穆故居，再往東走會看到東北側有垃圾場，後面接著雙溪風景。",
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
                "text": "哈囉！很高興為你服務！請問有什麼我可以幫忙的嗎？我對東吳大學外雙溪校區的環境和設施，以及各個辦公室的業務都相當了解。無論你想詢問哪個地點、哪個單位，或是需要什麼資訊，都可以直接告訴我喔！"
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