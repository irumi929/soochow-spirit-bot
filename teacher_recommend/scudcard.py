import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
from typing import List

def ai_summary_with_dcard_links(department: str, max_retries: int = 3, verbose: bool = False) -> str:
    """
    AI 統整說明 + 三個 Dcard 文章連結（明確連到 dcard.tw）
    """
    query = f"東吳 {department} 推薦教授 site:dcard.tw"
    query_enc = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={query_enc}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    results = []
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "html.parser")

            for result in soup.select('.result'):
                if verbose:
                    print("==== result html ====")
                    print(result.prettify())
                title_tag = result.select_one('.result__a')
                desc_tag = result.select_one('.result__snippet')
                link = title_tag['href'] if title_tag and 'href' in title_tag.attrs else ""
                # 處理 duckduckgo 跳轉連結
                if link.startswith("//duckduckgo.com/l/?uddg="):
                    link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
                if link and "dcard.tw" in link and title_tag and title_tag.text.strip():
                    results.append({
                        "title": title_tag.text.strip(),
                        "url": link,
                        "description": desc_tag.text.strip() if desc_tag else "無摘要"
                    })
                if len(results) >= 3:
                    break
            if results:
                break
            if verbose:
                print("未抓到結果，DuckDuckGo 回傳內容如下：")
                print(res.text[:2000])
        except Exception as e:
            if verbose:
                print(f"搜尋失敗，第{attempt+1}次，錯誤訊息：{e}")
            time.sleep(1)

    # AI 統整說明
    if results:
        summary = f"根據 Dcard 上同學們的討論，東吳大學{department}推薦的教授有多位，大家普遍關注教授的教學風格、課程內容與評分方式。以下提供三篇相關 Dcard 討論串，供您參考：\n"
        for idx, item in enumerate(results, 1):
            summary += f"\n{idx}. [{item['title']}]({item['url']})\n"
        return summary
    else:
        return f"目前找不到東吳大學{department}推薦教授的 Dcard 文章連結。"

if __name__ == "__main__":
    department = "中文系"
    print(ai_summary_with_dcard_links(department, verbose=True))

def google_search_dcard(keyword):
    """
    回傳 Dcard 文章搜尋結果（list of dict），每個 dict 有 title/url/description
    """
    query = f"東吳 {keyword} 推薦教授 site:dcard.tw"
    query_enc = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={query_enc}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    results = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        for result in soup.select('.result'):
            title_tag = result.select_one('.result__a')
            desc_tag = result.select_one('.result__snippet')
            link = title_tag['href'] if title_tag and 'href' in title_tag.attrs else ""
            # 處理 duckduckgo 跳轉連結
            if link.startswith("//duckduckgo.com/l/?uddg="):
                link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
            if link and "dcard.tw" in link and title_tag and title_tag.text.strip():
                results.append({
                    "title": title_tag.text.strip(),
                    "url": link,
                    "description": desc_tag.text.strip() if desc_tag else "無摘要"
                })
            if len(results) >= 3:
                break
    except Exception as e:
        print(f"搜尋失敗，錯誤訊息：{e}")

    return results