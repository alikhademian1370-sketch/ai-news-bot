import feedparser
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta
import time

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

RSS_SOURCES = [
    {
        "name": "زومیت – هوش مصنوعی",
        "url": "https://www.zoomit.ir/feed/",
        "keywords": ["هوش مصنوعی", "AI", "ChatGPT", "Gemini", "یادگیری ماشین"],
        "emoji": "🔵"
    },
    {
        "name": "دیجیاتو – هوش مصنوعی",
        "url": "https://digiato.com/feed/",
        "keywords": ["هوش مصنوعی", "AI", "ChatGPT", "Gemini", "یادگیری ماشین"],
        "emoji": "🟣"
    },
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "keywords": [],
        "emoji": "🟢"
    },
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "keywords": [],
        "emoji": "🟡"
    },
]

SCRAPE_SOURCES = [
    {
        "name": "هوشیو",
        "url": "https://hooshio.com/news/",
        "emoji": "🔴",
        "article_selector": "article",
        "title_selector": "h2, h3",
        "link_selector": "a",
    },
    {
        "name": "ایران هوش مصنوعی",
        "url": "https://iranaiai.ir/",
        "emoji": "🟠",
        "article_selector": "article",
        "title_selector": "h2, h3",
        "link_selector": "a",
    },
]

def is_recent(entry):
    try:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if not published:
            return True
        pub_time = datetime(*published[:6])
        return datetime.utcnow() - pub_time < timedelta(hours=24)
    except Exception:
        return True

def has_keyword(text, keywords):
    if not keywords:
        return True
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)

def fetch_rss_news(source):
    news = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries:
            if not is_recent(entry):
                continue
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            if has_keyword(title + " " + summary, source["keywords"]):
                news.append({"title": title, "link": link, "source": source["name"], "emoji": source["emoji"]})
    except Exception as e:
        print(f"خطا در {source['name']}: {e}")
    return news

def fetch_scrape_news(source):
    news = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(source["url"], headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select(source["article_selector"])[:8]
        for article in articles:
            title_tag = article.select_one(source["title_selector"])
            link_tag = article.select_one(source["link_selector"])
            if title_tag and link_tag:
                title = title_tag.get_text(strip=True)
                link = link_tag.get("href", "")
                if link and not link.startswith("http"):
                    base = source["url"].rstrip("/")
                    link = base + "/" + link.lstrip("/")
                if title:
                    news.append({"title": title, "link": link, "source": source["name"], "emoji": source["emoji"]})
    except Exception as e:
        print(f"خطا در scraping {source['name']}: {e}")
    return news

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    resp = requests.post(url, data=data, timeout=10)
    if not resp.ok:
        print(f"خطا در ارسال تلگرام: {resp.text}")

def main():
    all_news = {}
    for source in RSS_SOURCES:
        news = fetch_rss_news(source)
        if news:
            all_news[source["name"]] = news
        time.sleep(1)
    for source in SCRAPE_SOURCES:
        news = fetch_scrape_news(source)
        if news:
            all_news[source["name"]] = news
        time.sleep(1)
    if not all_news:
        send_telegram("📭 امروز خبر جدیدی یافت نشد.")
        return
    today = datetime.now().strftime("%Y/%m/%d")
    send_telegram(f"🤖 <b>اخبار هوش مصنوعی — {today}</b>\n{'─'*30}")
    time.sleep(1)
    for source_name, articles in all_news.items():
        emoji = articles[0]["emoji"]
        msg = f"{emoji} <b>{source_name}</b>\n\n"
        for item in articles[:5]:
            title = item["title"][:100]
            link = item["link"]
            msg += f"• <a href='{link}'>{title}</a>\n\n"
        send_telegram(msg)
        time.sleep(1)
    send_telegram("✅ پایان اخبار امروز")

if __name__ == "__main__":
    main()
