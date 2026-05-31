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

def extract_image_from_entry(entry):
    # روش ۱: media:content
    media_content = entry.get("media_content", [])
    if media_content:
        for media in media_content:
            url = media.get("url", "")
            if url and any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return url

    # روش ۲: media:thumbnail
    media_thumbnail = entry.get("media_thumbnail", [])
    if media_thumbnail:
        return media_thumbnail[0].get("url", "")

    # روش ۳: enclosures
    enclosures = entry.get("enclosures", [])
    for enc in enclosures:
        if "image" in enc.get("type", ""):
            return enc.get("href", "")

    # روش ۴: عکس داخل محتوای HTML
    content = ""
    if entry.get("content"):
        content = entry["content"][0].get("value", "")
    elif entry.get("summary"):
        content = entry["summary"]

    if content:
        soup = BeautifulSoup(content, "html.parser")
        img = soup.find("img")
        if img:
            src = img.get("src", "")
            if src and src.startswith("http"):
                return src

    return None

def fetch_article_summary(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            summary = og_desc["content"].strip()
            return summary[:197] + "..." if len(summary) > 200 else summary

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            summary = meta_desc["content"].strip()
            return summary[:197] + "..." if len(summary) > 200 else summary

    except Exception as e:
        print(f"خطا در fetch_article_summary: {e}")
    return ""

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
                image_url = extract_image_from_entry(entry)
                news.append({
                    "title": title,
                    "link": link,
                    "source": source["name"],
                    "emoji": source["emoji"],
                    "image_url": image_url
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
                img_tag = article.find("img")
                image_url = None
                if img_tag:
                    image_url = img_tag.get("src") or img_tag.get("data-src")
                if title:
                    news.append({
                        "title": title,
                        "link": link,
                        "source": source["name"],
                        "emoji": source["emoji"],
                        "image_url": image_url
                    })
    except Exception as e:
        print(f"خطا در scraping {source['name']}: {e}")
    return news

def send_telegram_text(text):
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

# ───────────── تابع جدید: دانلود عکس ─────────────
def download_image(image_url):
    """
    عکس رو از سایت دانلود می‌کنه و به صورت bytes برمی‌گردونه.
    اگه موفق نشد، None برمی‌گردونه.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": image_url,  # بعضی سایت‌ها Referer چک می‌کنن
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        }
        resp = requests.get(image_url, headers=headers, timeout=15)
        content_type = resp.headers.get("Content-Type", "")

        # مطمئن بشیم فایل واقعاً عکسه
        if resp.ok and "image" in content_type:
            return resp.content, content_type
        else:
            print(f"دانلود عکس ناموفق — status: {resp.status_code}, type: {content_type}")
            return None, None
    except Exception as e:
        print(f"خطا در دانلود عکس: {e}")
        return None, None

# ───────────── تابع اصلاح‌شده: ارسال عکس ─────────────
def send_telegram_photo(image_url, caption):
    """
    عکس رو ابتدا دانلود می‌کنه، بعد با multipart/form-data به تلگرام می‌فرسته.
    اگه دانلود یا ارسال شکست خورد، متن رو بدون عکس می‌فرسته.
    """
    image_data, content_type = download_image(image_url)

    if image_data:
        # پسوند فایل رو از content_type تشخیص بده
        ext = "jpg"
        if content_type:
            if "png" in content_type:
                ext = "png"
            elif "webp" in content_type:
                ext = "webp"
            elif "gif" in content_type:
                ext = "gif"

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        data = {
            "chat_id": CHAT_ID,
            "caption": caption,
            "parse_mode": "HTML"
        }
        files = {
            "photo": (f"image.{ext}", image_data, content_type or "image/jpeg")
        }
        resp = requests.post(url, data=data, files=files, timeout=30)

        if resp.ok:
            return  # موفق بود، تموم شد
        else:
            print(f"خطا در ارسال عکس به تلگرام: {resp.text}")

    # fallback: اگه عکس نیومد یا ارسال شکست خورد
    send_telegram_text(caption)

def send_news_item(item):
    title = item["title"]
    link = item["link"]
    emoji = item["emoji"]
    summary = item.get("summary", "")
    image_url = item.get("image_url")

    caption = f"{emoji} <b>{title}</b>\n\n"
    if summary:
        caption += f"{summary}\n\n"
    caption += f"🔗 <a href='{link}'>ادامه مطلب</a>"

    if image_url:
        send_telegram_photo(image_url, caption)
    else:
        send_telegram_text(caption)

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
        send_telegram_text("📭 امروز خبر جدیدی یافت نشد.")
        return

    today = datetime.now().strftime("%Y/%m/%d")
    send_telegram_text(f"🤖 <b>اخبار هوش مصنوعی — {today}</b>\n{'─'*30}")
    time.sleep(1)

    for source_name, articles in all_news.items():
        emoji = articles[0]["emoji"]
        send_telegram_text(f"{emoji} <b>{source_name}</b>")
        time.sleep(0.5)

        for item in articles[:5]:
            # اگه عکس از RSS نیومد، از og:image صفحه خبر بگیر
            if not item.get("image_url") and item["link"]:
                try:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    resp = requests.get(item["link"], headers=headers, timeout=10)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    og_image = soup.find("meta", property="og:image")
                    if og_image and og_image.get("content"):
                        item["image_url"] = og_image["content"]
                    og_desc = soup.find("meta", property="og:description")
                    if og_desc and og_desc.get("content"):
                        item["summary"] = og_desc["content"][:200]
                except Exception:
                    pass

            send_news_item(item)
            time.sleep(1.5)

        time.sleep(1)

    send_telegram_text("✅ پایان اخبار امروز")

if __name__ == "__main__":
    main()
