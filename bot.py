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

def fetch_article_details(url):
    """
    متن خلاصه و تصویر شاخص رو از صفحه خبر استخراج می‌کنه
    Returns: (summary, image_url)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        # --- استخراج تصویر شاخص ---
        image_url = None

        # روش ۱: og:image (بهترین روش - اکثر سایت‌ها دارن)
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]

        # روش ۲: twitter:image
        if not image_url:
            tw_image = soup.find("meta", attrs={"name": "twitter:image"})
            if tw_image and tw_image.get("content"):
                image_url = tw_image["content"]

        # روش ۳: اولین تصویر بزرگ در مقاله
        if not image_url:
            article = soup.find("article") or soup.find("main") or soup
            for img in article.find_all("img"):
                src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if src and any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                    # فیلتر تصاویر کوچک (آیکون، لوگو)
                    width = img.get("width")
                    if width and int(str(width).replace("px","")) < 200:
                        continue
                    image_url = src
                    break

        # اصلاح URL نسبی
        if image_url and image_url.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            image_url = f"{parsed.scheme}://{parsed.netloc}{image_url}"

        # --- استخراج خلاصه متن ---
        summary = ""

        # روش ۱: og:description
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            summary = og_desc["content"].strip()

        # روش ۲: meta description
        if not summary:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                summary = meta_desc["content"].strip()

        # روش ۳: اولین پاراگراف مقاله
        if not summary:
            article = soup.find("article") or soup.find("main")
            if article:
                paragraphs = article.find_all("p")
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 80:  # پاراگراف‌های واقعی، نه کوتاه
                        summary = text
                        break

        # برش خلاصه به ۲۰۰ کاراکتر
        if summary and len(summary) > 200:
            summary = summary[:197] + "..."

        return summary, image_url

    except Exception as e:
        print(f"خطا در fetch_article_details برای {url}: {e}")
        return "", None

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
                news.append({
                    "title": title,
                    "link": link,
                    "source": source["name"],
                    "emoji": source["emoji"]
                })
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
                    news.append({
                        "title": title,
                        "link": link,
                        "source": source["name"],
                        "emoji": source["emoji"]
                    })
    except Exception as e:
        print(f"خطا در scraping {source['name']}: {e}")
    return news

def send_telegram_text(text):
    """ارسال پیام متنی ساده"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    resp = requests.post(url, data=data, timeout=10)
    if not resp.ok:
        print(f"خطا در ارسال تلگرام: {resp.text}")

def send_telegram_photo(image_url, caption):
    """ارسال عکس + کپشن به تلگرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    data = {
        "chat_id": CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    resp = requests.post(url, data=data, timeout=15)
    if not resp.ok:
        # اگه عکس لود نشد، بدون عکس بفرست
        print(f"خطا در ارسال عکس، ارسال بدون عکس: {resp.text}")
        send_telegram_text(caption)

def send_news_item(item):
    """
    هر خبر رو با عکس + خلاصه می‌فرسته
    فرمت: عکس شاخص + عنوان + خلاصه + لینک
    """
    title = item["title"]
    link = item["link"]
    emoji = item["emoji"]
    summary = item.get("summary", "")
    image_url = item.get("image_url")

    # ساخت کپشن
    caption = f"{emoji} <b>{title}</b>\n\n"
    if summary:
        caption += f"{summary}\n\n"
    caption += f"🔗 <a href='{link}'>ادامه مطلب</a>"

    # ارسال با یا بدون عکس
    if image_url:
        send_telegram_photo(image_url, caption)
    else:
        send_telegram_text(caption)

def main():
    all_news = {}

    # جمع‌آوری اخبار RSS
    for source in RSS_SOURCES:
        news = fetch_rss_news(source)
        if news:
            all_news[source["name"]] = news
        time.sleep(1)

    # جمع‌آوری اخبار scraping
    for source in SCRAPE_SOURCES:
        news = fetch_scrape_news(source)
        if news:
            all_news[source["name"]] = news
        time.sleep(1)

    if not all_news:
        send_telegram_text("📭 امروز خبر جدیدی یافت نشد.")
        return

    # پیام سرصفحه
    today = datetime.now().strftime("%Y/%m/%d")
    send_telegram_text(f"🤖 <b>اخبار هوش مصنوعی — {today}</b>\n{'─'*30}")
    time.sleep(1)

    # ارسال هر منبع
    for source_name, articles in all_news.items():
        emoji = articles[0]["emoji"]

        # هدر منبع
        send_telegram_text(f"{emoji} <b>{source_name}</b>")
        time.sleep(0.5)

        # ارسال هر خبر با عکس + خلاصه
        for item in articles[:5]:
            # دریافت جزئیات مقاله (خلاصه + تصویر)
            if item["link"]:
                summary, image_url = fetch_article_details(item["link"])
                item["summary"] = summary
                item["image_url"] = image_url

            send_news_item(item)
            time.sleep(1.5)  # تاخیر بین هر خبر

        time.sleep(1)

    send_telegram_text("✅ پایان اخبار امروز")

if __name__ == "__main__":
    main()
                    

