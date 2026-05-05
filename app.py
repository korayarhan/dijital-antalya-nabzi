import csv
import os
import datetime as dt
import html
import re
import urllib.parse
from pathlib import Path
import feedparser
import smtplib
from email.message import EmailMessage
import json
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "keywords.txt"
SOCIAL_CSV = ROOT / "data" / "manual_social" / "social_manual.csv"
AUTO_SOCIAL_CSV = ROOT / "data" / "auto_social" / "social_auto.csv"
PRESIDENT_X_CSV = ROOT / "data" / "auto_social" / "president_x_posts.csv"
PRESIDENT_X_REPLIES_CSV = ROOT / "data" / "auto_social" / "president_x_replies.csv"
YOUTUBE_SOCIAL_CSV = ROOT / "data" / "auto_social" / "youtube_social.csv"
YOUTUBE_WATCH_CSV = ROOT / "data" / "social_watch" / "youtube_watch.csv"
YOUTUBE_SUMMARY_CSV = ROOT / "data" / "auto_social" / "youtube_summary.csv"
ACCOUNTS_MAP_CSV = ROOT / "data" / "social_watch" / "accounts_map.csv"
PRESIDENT_X_USERNAME = "mesutkocagoztr"
WATCH_KEYWORDS_CSV = ROOT / "data" / "social_watch" / "watch_keywords.csv"
CRISIS_CSV = ROOT / "data" / "manual_crisis" / "crisis_status.csv"
CRISIS_LOG_CSV = ROOT / "data" / "manual_crisis" / "crisis_log.csv"
ALERT_LOG_CSV = ROOT / "data" / "alerts" / "alert_log.csv"
TEAM_ACTIONS_CSV = ROOT / "data" / "team_actions" / "team_actions.csv"
DYNAMIC_KEYWORDS = ROOT / "data" / "dynamic_keywords.txt"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

POSITIVE_WORDS = [
    "hizmet", "asfalt", "açılış", "ödül", "teşekkür", "çocuk",
    "şenlik", "proje", "destek", "spor", "başarı", "tamamlandı",
    "coşku", "yatırım", "park", "festival", "yardım", "duyarlılık",
    "bayrak", "personel", "mahalle", "memnuniyet", "etkinlik"
]

RISK_WORDS = [
    "dava", "facia", "kaza", "tepki", "şikayet", "kriz",
    "eleştiri", "borç", "iddia", "tartışma", "soruşturma",
    "yargı", "protesto", "usulsüz", "ceza", "gündem oldu"
]

CORE_TERMS = [
    "mesut", "kocagöz", "kepez", "antalya", "büyükşehir",
    "belediye", "belediyesi", "teleferik", "duacı", "asfalt",
    "borç", "drag", "23 nisan", "çocuk", "bayrak", "personel"
]

LOCAL_INCLUDE_TERMS = [
    "kepez",
    "mesut kocagöz",
    "mesut kocagoz",
    "antalya kepez",
    "kepez belediyesi",
    "kepez belediye başkanı",
    "kepez belediye baskani",
    "antalya büyükşehir",
    "antalya buyuksehir",
    "antalya büyükşehir belediyesi",
    "antalya buyuksehir belediyesi",
    "duacı",
    "duaci",
    "varsak",
    "sütçüler",
    "sutculer",
    "güneş mahallesi",
    "gunes mahallesi",
    "habibler",
    "teomanpaşa",
    "teomanpasa",
    "fabrikalar mahallesi",
    "şafak mahallesi",
    "safak mahallesi",
]

LOCAL_EXCLUDE_TERMS = [
    "korkuteli",
    "alanya",
    "manavgat",
    "serik",
    "kaş",
    "kas",
    "kalkan",
    "finike",
    "kumluca",
    "demre",
    "gazipaşa",
    "gazipasa",
    "akseki",
    "gündoğmuş",
    "gundogmus",
    "elmali",
    "elmalı",
    "ibradı",
    "ibradi",
    "muratpaşa belediyesi",
    "muratpasa belediyesi",
    "konyaaltı belediyesi",
    "konyaalti belediyesi",
    "döşemealtı belediyesi",
    "dosemealti belediyesi",
    "aksu belediyesi",
]

STOPWORDS = {
    "ve", "ile", "bir", "bu", "da", "de", "için", "olan", "olarak",
    "son", "yeni", "gün", "daha", "çok", "sonra", "önce", "başkanı",
    "belediye", "belediyesi", "antalya", "kepez", "mesut", "kocagöz",
    "haber", "gündem", "açıklama", "başkan", "yerel", "gazete", "medya"
}


def esc(x):
    return html.escape(str(x or ""))


def clean_text(text):
    text = html.unescape(str(text or ""))
    text = re.sub(r"<.*?>", "", text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text(text):
    text = str(text or "").lower().replace("ı", "i")
    text = re.sub(r"[^a-zA-ZğüşöçıİĞÜŞÖÇ0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def read_keyword_file(path):
    if not path.exists():
        return []
    return [x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.strip().startswith("#")]


def read_keywords():
    base = read_keyword_file(CONFIG)
    dynamic = read_keyword_file(DYNAMIC_KEYWORDS)
    combined, seen = [], set()
    for keyword in base + dynamic:
        key = keyword.lower().strip()
        if key and key not in seen:
            seen.add(key)
            combined.append(keyword)
    return combined[:30]


def classify(text):
    t = normalize_text(text)
    positive = sum(1 for w in POSITIVE_WORDS if normalize_text(w) in t)
    risk = sum(1 for w in RISK_WORDS if normalize_text(w) in t)

    if risk > positive:
        tone = "Riskli"
    elif positive > risk:
        tone = "Olumlu"
    else:
        tone = "Nötr"

    return tone, min(10, risk * 3 + (2 if tone == "Riskli" else 0)), min(10, positive * 2 + (2 if tone == "Olumlu" else 0))


def topic_key(title):
    t = normalize_text(title)
    if "teleferik" in t or "facia" in t or "dava" in t:
        return "teleferik_davasi"
    if "asfalt" in t or "duaci" in t or "duacı" in t or "yol" in t:
        return "hizmet_asfalt"
    if "bayrak" in t or "personel" in t or "odul" in t or "ödül" in t:
        return "bayrak_personel"
    if "23 nisan" in t or "cocuk" in t or "çocuk" in t or "senlik" in t or "şenlik" in t:
        return "cocuk_aile"
    if "borc" in t or "borç" in t or "mali" in t:
        return "mali_disiplin"
    if "drag" in t or "spor" in t:
        return "spor_etkinlik"
    if "buyuksehir" in t or "büyükşehir" in t or "ulasim" in t or "ulaşım" in t:
        return "buyuksehir_ulasim"
    words = [w for w in t.split() if len(w) > 3 and w not in STOPWORDS]
    return "_".join(words[:4]) or "genel"


def google_news_url(keyword):
    q = urllib.parse.quote_plus(keyword)
    return f"https://news.google.com/rss/search?q={q}&hl=tr&gl=TR&ceid=TR:tr"


LOCAL_INCLUDE_TERMS = [
    "kepez",
    "mesut kocagöz",
    "mesut kocagoz",
    "antalya kepez",
    "kepez belediyesi",
    "kepez belediye başkanı",
    "kepez belediye baskani",
    "antalya büyükşehir",
    "antalya buyuksehir",
    "antalya büyükşehir belediyesi",
    "antalya buyuksehir belediyesi",
    "duacı",
    "duaci",
    "varsak",
    "sütçüler",
    "sutculer",
    "güneş mahallesi",
    "gunes mahallesi",
    "habibler",
    "teomanpaşa",
    "teomanpasa",
    "fabrikalar mahallesi",
    "şafak mahallesi",
    "safak mahallesi",
]

LOCAL_EXCLUDE_TERMS = [
    "korkuteli",
    "alanya",
    "manavgat",
    "serik",
    "kaş",
    "kas",
    "kalkan",
    "finike",
    "kumluca",
    "demre",
    "gazipaşa",
    "gazipasa",
    "akseki",
    "gündoğmuş",
    "gundogmus",
    "elmali",
    "elmalı",
    "ibradı",
    "ibradi",
    "muratpaşa belediyesi",
    "muratpasa belediyesi",
    "konyaaltı belediyesi",
    "konyaalti belediyesi",
    "döşemealtı belediyesi",
    "dosemealti belediyesi",
    "aksu belediyesi",
]

def contains_any(text, terms):
    return any(normalize_text(term) in text for term in terms)


def is_relevant(title, summary, keyword):
    body_text = normalize_text(f"{title} {summary}")
    full_text = normalize_text(f"{title} {summary} {keyword}")

    # Haber gövdesinde Kepez / Mesut Kocagöz / Antalya Büyükşehir bağlantısı yoksa alma.
    has_local_connection = contains_any(body_text, LOCAL_INCLUDE_TERMS)
    if not has_local_connection:
        return False

    # Haber başka ilçeye kayıyorsa ve Kepez bağlantısı zayıfsa ele.
    outside_hit = contains_any(body_text, LOCAL_EXCLUDE_TERMS)

    strong_kepez_or_mesut = contains_any(
        body_text,
        [
            "kepez",
            "mesut kocagöz",
            "mesut kocagoz",
            "duacı",
            "duaci",
            "varsak",
            "sütçüler",
            "sutculer",
        ],
    )

    bigcity_hit = contains_any(
        body_text,
        [
            "antalya büyükşehir",
            "antalya buyuksehir",
            "antalya büyükşehir belediyesi",
            "antalya buyuksehir belediyesi",
        ],
    )

    if outside_hit and not strong_kepez_or_mesut and not bigcity_hit:
        return False

    # Ana takip konularımızdan en az biri de geçsin.
    return contains_any(full_text, CORE_TERMS)
NEWS_MAX_AGE_DAYS = 7  # Son 7 gün. İstersen 3 yapabiliriz.


def parse_news_date(item):
    try:
        if hasattr(item, "published_parsed") and item.published_parsed:
            return dt.date(
                item.published_parsed.tm_year,
                item.published_parsed.tm_mon,
                item.published_parsed.tm_mday
            )
        if hasattr(item, "updated_parsed") and item.updated_parsed:
            return dt.date(
                item.updated_parsed.tm_year,
                item.updated_parsed.tm_mon,
                item.updated_parsed.tm_mday
            )
    except Exception:
        return None

    return None


def is_recent_news(item, max_days=NEWS_MAX_AGE_DAYS):
    news_date = parse_news_date(item)

    # Tarih okunamıyorsa haberi rapora alma.
    # Çünkü eski haberlerin kaçmasını engellemek istiyoruz.
    if not news_date:
        return False

    today = dt.date.today()
    oldest_allowed = today - dt.timedelta(days=max_days)

    return oldest_allowed <= news_date <= today

def fetch_news():
    rows, undated_rows, seen_topics = [], [], set()

    for keyword in read_keywords():
        feed = feedparser.parse(google_news_url(keyword))

        for item in feed.entries[:12]:
            title = clean_text(getattr(item, "title", ""))
            link = getattr(item, "link", "")
            date = getattr(item, "published", "")
            summary = clean_text(getattr(item, "summary", ""))

            if not title or not is_relevant(title, summary, keyword):
                continue

            news_date = parse_news_date(item)
            is_undated = news_date is None

            if news_date is not None and not is_recent_news(item):
                continue

            topic = topic_key(title)
            if topic in seen_topics:
                continue

            seen_topics.add(topic)

            tone, risk, opportunity = classify(title + " " + summary)

            row = {
                "keyword": keyword,
                "title": title,
                "link": link,
                "date": date if date else "Tarih okunamadı",
                "summary": summary,
                "tone": tone,
                "risk": risk,
                "opportunity": opportunity,
                "topic": topic,
            }

            if is_undated:
                undated_rows.append(row)
            else:
                rows.append(row)

    return rows, undated_rows


def to_float(x):
    try:
        return float(str(x or "0").replace(",", "."))
    except ValueError:
        return 0.0

def read_watch_keywords():
    if not WATCH_KEYWORDS_CSV.exists():
        return []

    keywords = []
    try:
        with WATCH_KEYWORDS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                keyword = str(row.get("keyword", "") or "").strip()
                category = str(row.get("category", "") or "").strip()
                priority = str(row.get("priority", "") or "").strip()

                if keyword:
                    keywords.append({
                        "keyword": keyword,
                        "category": category,
                        "priority": priority,
                    })
    except Exception as e:
        print(f"Takip kelimeleri okunamadı: {e}")
        return []

    return keywords


def score_x_post(text, matched_keyword):
    text_norm = normalize_text(text)
    keyword_norm = normalize_text(matched_keyword)

    risk_words = [
        "şikayet", "sikayet", "tepki", "kriz", "dava", "soruşturma", "sorusturma",
        "ölüm", "olum", "yaralı", "yarali", "kaza", "facia", "mağdur", "magdur",
        "ihmal", "skandal", "çöp", "cop", "asfalt", "yol bozuk", "temizlik",
        "ulaşım", "ulasim", "gecikme", "sorun", "eleştiri", "elestiri"
    ]

    opportunity_words = [
        "teşekkür", "tesekkur", "başarılı", "basarili", "hizmet", "çalışma",
        "calisma", "destek", "ödül", "odul", "memnun", "güzel", "guzel",
        "park", "sosyal yardım", "yardım", "yol çalışması", "temizlik çalışması"
    ]

    risk_hits = sum(1 for word in risk_words if word in text_norm)
    opportunity_hits = sum(1 for word in opportunity_words if word in text_norm)

    risk_score = min(10, 2 + risk_hits * 2)
    opportunity_score = min(10, 2 + opportunity_hits * 2)

    if any(word in text_norm for word in ["ölüm", "olum", "yaralı", "yarali", "kaza", "facia"]):
        risk_score = max(risk_score, 7)

    if keyword_norm in text_norm and matched_keyword:
        risk_score = max(risk_score, 4)

    if risk_score >= 6:
        sentiment = "negative"
        action_note = "X üzerinde riskli paylaşım tespit edildi. Yayılım, yorum tonu ve yerel basına sıçrama ihtimali izlenmeli."
    elif opportunity_score >= 6:
        sentiment = "positive"
        action_note = "Olumlu/fırsat içeriği tespit edildi. Hizmet iletişimiyle büyütülebilir."
    else:
        sentiment = "neutral"
        action_note = "İçerik izlemeye alınmalı. Şu aşamada acil aksiyon gerekmiyor."

    topic = matched_keyword if matched_keyword else "X otomatik takip"

    return sentiment, risk_score, opportunity_score, topic, action_note

def fetch_president_x_posts():
    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        print("Başkan X gönderileri atlandı: X_BEARER_TOKEN yok.")
        return

    username = PRESIDENT_X_USERNAME.replace("@", "").strip()
    if not username:
        print("Başkan X gönderileri atlandı: kullanıcı adı yok.")
        return

    PRESIDENT_X_CSV.parent.mkdir(parents=True, exist_ok=True)

    try:
        # 1) Kullanıcı adından X kullanıcı ID'sini al
        user_params = urllib.parse.urlencode({
            "user.fields": "id,name,username,public_metrics"
        })

        user_url = f"https://api.x.com/2/users/by/username/{urllib.parse.quote(username)}?{user_params}"

        user_req = urllib.request.Request(
            user_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "YerelLiderAI/1.0",
            },
        )

        with urllib.request.urlopen(user_req, timeout=30) as response:
            user_payload = json.loads(response.read().decode("utf-8"))

        user_data = user_payload.get("data", {}) or {}
        user_id = user_data.get("id", "")

        if not user_id:
            print("Başkan X gönderileri atlandı: kullanıcı ID bulunamadı.")
            return

        # 2) Kullanıcının son gönderilerini al
        post_params = urllib.parse.urlencode({
            "max_results": "10",
            "tweet.fields": "created_at,public_metrics,author_id,text",
            "exclude": "retweets,replies",
        })

        posts_url = f"https://api.x.com/2/users/{user_id}/tweets?{post_params}"

        posts_req = urllib.request.Request(
            posts_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "YerelLiderAI/1.0",
            },
        )

        with urllib.request.urlopen(posts_req, timeout=30) as response:
            posts_payload = json.loads(response.read().decode("utf-8"))

        rows = []

        for post in posts_payload.get("data", []):
            text = post.get("text", "")
            metrics = post.get("public_metrics", {}) or {}

            likes = metrics.get("like_count", 0) or 0
            replies = metrics.get("reply_count", 0) or 0
            reposts = metrics.get("retweet_count", 0) or 0
            quotes = metrics.get("quote_count", 0) or 0
            engagement = likes + replies + reposts + quotes

            post_url = f"https://x.com/{username}/status/{post.get('id')}"

            rows.append({
                "date": str(post.get("created_at", ""))[:10],
                "platform": "X / Twitter",
                "account": f"@{username}",
                "content": text.replace("\n", " ").strip(),
                "topic": topic_key(text),
                "likes": likes,
                "replies": replies,
                "reposts": reposts,
                "quotes": quotes,
                "engagement": engagement,
                "url": post_url,
                "source_type": "Başkan X Hesabı",
            })

        with PRESIDENT_X_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            fieldnames = [
                "date",
                "platform",
                "account",
                "content",
                "topic",
                "likes",
                "replies",
                "reposts",
                "quotes",
                "engagement",
                "url",
                "source_type",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"Başkan X gönderileri çekildi. Kayıt sayısı: {len(rows)}")

    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except:
            pass
        print(f"Başkan X gönderileri alınamadı. HTTP {e.code}: {detail[:500]}")

    except Exception as e:
        print(f"Başkan X gönderileri alınamadı: {e}")

def fetch_president_x_replies():
    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        print("Başkan X yanıtları atlandı: X_BEARER_TOKEN yok.")
        return

    username = PRESIDENT_X_USERNAME.replace("@", "").strip()
    president_posts = read_president_x_posts()[:3]

    if not president_posts:
        print("Başkan X yanıtları atlandı: Başkan gönderisi yok.")
        return

    PRESIDENT_X_REPLIES_CSV.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    try:
        for main_post in president_posts:
            post_url = main_post.get("url", "")
            match = re.search(r"/status/(\d+)", post_url)

            if not match:
                continue

            post_id = match.group(1)

            query = f"conversation_id:{post_id} -from:{username} lang:tr -is:retweet"

            params = urllib.parse.urlencode({
                "query": query,
                "max_results": "10",
                "tweet.fields": "created_at,public_metrics,author_id,text,conversation_id",
                "expansions": "author_id",
                "user.fields": "username,name",
            })

            url = f"https://api.x.com/2/tweets/search/recent?{params}"

            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "YerelLiderAI/1.0",
                },
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))

            users = {}
            for user in payload.get("includes", {}).get("users", []):
                users[user.get("id")] = user

            for reply in payload.get("data", []):
                if reply.get("id") == post_id:
                    continue

                text = reply.get("text", "")
                sentiment, risk_score, opportunity_score, topic, action_note = score_x_post(text, "yorum")

                author = users.get(reply.get("author_id"), {}) or {}
                reply_username = author.get("username", "")
                reply_account = f"@{reply_username}" if reply_username else "X kullanıcısı"

                reply_url = f"https://x.com/{reply_username}/status/{reply.get('id')}" if reply_username else ""

                rows.append({
                    "post_id": post_id,
                    "post_date": main_post.get("date", ""),
                    "post_topic": main_post.get("topic", ""),
                    "reply_date": str(reply.get("created_at", ""))[:10],
                    "reply_account": reply_account,
                    "reply_text": text.replace("\n", " ").strip(),
                    "sentiment": sentiment,
                    "risk_score": risk_score,
                    "opportunity_score": opportunity_score,
                    "reply_url": reply_url,
                    "source_type": "Başkan X Yanıtı",
                })

        with PRESIDENT_X_REPLIES_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            fieldnames = [
                "post_id",
                "post_date",
                "post_topic",
                "reply_date",
                "reply_account",
                "reply_text",
                "sentiment",
                "risk_score",
                "opportunity_score",
                "reply_url",
                "source_type",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"Başkan X yanıtları çekildi. Kayıt sayısı: {len(rows)}")

    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except:
            pass
        print(f"Başkan X yanıtları alınamadı. HTTP {e.code}: {detail[:500]}")

    except Exception as e:
        print(f"Başkan X yanıtları alınamadı: {e}")

def is_relevant_youtube_comment(video_title, comment_text, watch_topic):
    combined = normalize_text(f"{video_title} {comment_text} {watch_topic}")

    relevance_terms = [
        "kepez",
        "mesut",
        "kocagoz",
        "kocagöz",
        "kepez belediyesi",
        "antalya kepez",
        "teleferik",
        "dava",
        "sikayet",
        "şikayet",
        "asfalt",
        "temizlik",
        "park",
        "ulasim",
        "ulaşim",
        "ulaşım",
        "mahalle",
        "varsak",
        "duaci",
        "duacı",
        "belediye",
        "baskan",
        "başkan",
    ]

    return any(normalize_text(term) in combined for term in relevance_terms)

def read_youtube_watch_list():
    default_items = [
        {
            "type": "query",
            "value": "Mesut Kocagöz",
            "topic": "Mesut Kocagöz",
            "note": "Varsayılan YouTube araması",
        },
        {
            "type": "query",
            "value": "Kepez Belediyesi",
            "topic": "Kepez Belediyesi",
            "note": "Varsayılan YouTube araması",
        },
    ]

    if not YOUTUBE_WATCH_CSV.exists():
        return default_items

    rows = []

    try:
        with YOUTUBE_WATCH_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                item_type = str(row.get("type", "") or "").strip().lower()
                value = str(row.get("value", "") or "").strip()
                topic = str(row.get("topic", "") or "").strip()
                note = str(row.get("note", "") or "").strip()

                if item_type and value:
                    rows.append({
                        "type": item_type,
                        "value": value,
                        "topic": topic or value,
                        "note": note,
                    })

    except Exception as e:
        print(f"YouTube takip listesi okunamadı: {e}")
        return default_items

    return rows or default_items


def youtube_video_id_from_value(value):
    value = str(value or "").strip()

    if "youtube.com/watch" in value and "v=" in value:
        parsed = urllib.parse.urlparse(value)
        qs = urllib.parse.parse_qs(parsed.query)
        return qs.get("v", [""])[0]

    if "youtu.be/" in value:
        return value.rstrip("/").split("/")[-1].split("?")[0]

    if len(value) >= 8 and " " not in value and "/" not in value:
        return value

    return ""

def youtube_channel_handle_from_value(value):
    value = str(value or "").strip()

    if "youtube.com/@" in value:
        path = urllib.parse.urlparse(value).path.strip("/")
        return path if path.startswith("@") else f"@{path}"

    if value.startswith("@"):
        return value

    return ""


def youtube_channel_id_from_value(value, api_key):
    value = str(value or "").strip()

    if "/channel/" in value:
        path = urllib.parse.urlparse(value).path
        parts = [x for x in path.split("/") if x]
        if "channel" in parts:
            idx = parts.index("channel")
            if len(parts) > idx + 1:
                return parts[idx + 1]

    if value.startswith("UC") and len(value) > 15:
        return value

    handle = youtube_channel_handle_from_value(value)
    if not handle:
        return ""

    params = urllib.parse.urlencode({
        "part": "contentDetails",
        "forHandle": handle,
        "key": api_key,
    })

    url = f"https://www.googleapis.com/youtube/v3/channels?{params}"

    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    items = payload.get("items", [])
    if not items:
        return ""

    return items[0].get("id", "")


def youtube_channel_video_candidates(channel_value, api_key, max_results=5):
    channel_id = youtube_channel_id_from_value(channel_value, api_key)

    if not channel_id:
        return []

    channel_params = urllib.parse.urlencode({
        "part": "contentDetails",
        "id": channel_id,
        "key": api_key,
    })

    channel_url = f"https://www.googleapis.com/youtube/v3/channels?{channel_params}"

    with urllib.request.urlopen(channel_url, timeout=30) as response:
        channel_payload = json.loads(response.read().decode("utf-8"))

    channel_items = channel_payload.get("items", [])
    if not channel_items:
        return []

    uploads_playlist = (
        channel_items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads", "")
    )

    if not uploads_playlist:
        return []

    playlist_params = urllib.parse.urlencode({
        "part": "snippet",
        "playlistId": uploads_playlist,
        "maxResults": str(max_results),
        "key": api_key,
    })

    playlist_url = f"https://www.googleapis.com/youtube/v3/playlistItems?{playlist_params}"

    with urllib.request.urlopen(playlist_url, timeout=30) as response:
        playlist_payload = json.loads(response.read().decode("utf-8"))

    candidates = []

    for item in playlist_payload.get("items", []):
        snippet = item.get("snippet", {}) or {}
        resource = snippet.get("resourceId", {}) or {}
        video_id = resource.get("videoId", "")

        if video_id:
            candidates.append({
                "video_id": video_id,
                "video_title": snippet.get("title", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
            })

    return candidates

def fetch_youtube_social_comments():
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()

    if not api_key:
        print("YouTube taraması atlandı: YOUTUBE_API_KEY yok.")
        return

    YOUTUBE_SOCIAL_CSV.parent.mkdir(parents=True, exist_ok=True)
    YOUTUBE_SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)

    watch_items = read_youtube_watch_list()

    rows = []
    summary_rows = []
    seen_comments = set()
    total_skipped_videos = 0
    total_checked_videos = 0

    try:
        for watch in watch_items:
            item_type = str(watch.get("type", "query") or "query").strip().lower()
            term = watch.get("value", "")
            watch_topic = watch.get("topic", term)
            watch_note = watch.get("note", "")

            video_candidates = []

            source_name = watch_topic or term
            checked_videos = 0
            skipped_videos = 0
            relevant_comments = 0
            saved_comments = 0

            if item_type == "video":
                direct_video_id = youtube_video_id_from_value(term)
                if direct_video_id:
                    video_candidates.append({
                        "video_id": direct_video_id,
                        "video_title": watch_topic,
                        "channel_title": watch_note,
                        "published_at": "",
                    })

            elif item_type == "channel":
                try:
                    video_candidates = youtube_channel_video_candidates(term, api_key, max_results=50)
                except Exception as e:
                    print(f"YouTube kanal taraması atlandı: {term} / {e}")
                    summary_rows.append({
                        "source": source_name,
                        "type": item_type,
                        "topic": watch_topic,
                        "checked_videos": 0,
                        "relevant_comments": 0,
                        "saved_comments": 0,
                        "skipped_videos": 0,
                        "note": f"Kanal taraması atlandı: {e}",
                    })
                    continue

            elif item_type == "query":
                search_params = urllib.parse.urlencode({
                    "part": "snippet",
                    "q": term,
                    "type": "video",
                    "maxResults": "2",
                    "order": "date",
                    "regionCode": "TR",
                    "relevanceLanguage": "tr",
                    "key": api_key,
                })

                search_url = f"https://www.googleapis.com/youtube/v3/search?{search_params}"

                with urllib.request.urlopen(search_url, timeout=30) as response:
                    search_payload = json.loads(response.read().decode("utf-8"))

                for video in search_payload.get("items", []):
                    video_id = video.get("id", {}).get("videoId", "")
                    snippet = video.get("snippet", {}) or {}

                    if video_id:
                        video_candidates.append({
                            "video_id": video_id,
                            "video_title": snippet.get("title", ""),
                            "channel_title": snippet.get("channelTitle", ""),
                            "published_at": snippet.get("publishedAt", ""),
                        })

            else:
                summary_rows.append({
                    "source": source_name,
                    "type": item_type,
                    "topic": watch_topic,
                    "checked_videos": 0,
                    "relevant_comments": 0,
                    "saved_comments": 0,
                    "skipped_videos": 0,
                    "note": "Bilinmeyen YouTube takip tipi",
                })
                continue

            for video_data in video_candidates:
                video_id = video_data.get("video_id", "")
                video_title = video_data.get("video_title", "")
                channel_title = video_data.get("channel_title", "")
                published_at = video_data.get("published_at", "")
                video_url = f"https://www.youtube.com/watch?v={video_id}"

                if not video_id:
                    continue

                checked_videos += 1
                total_checked_videos += 1

                if channel_title and source_name in [watch_topic, term]:
                    source_name = channel_title

                try:
                    video_params = urllib.parse.urlencode({
                        "part": "statistics",
                        "id": video_id,
                        "key": api_key,
                    })

                    video_info_url = f"https://www.googleapis.com/youtube/v3/videos?{video_params}"

                    with urllib.request.urlopen(video_info_url, timeout=30) as response:
                        video_info_payload = json.loads(response.read().decode("utf-8"))

                    video_items = video_info_payload.get("items", [])
                    if not video_items:
                        skipped_videos += 1
                        total_skipped_videos += 1
                        continue

                    comment_count = int(video_items[0].get("statistics", {}).get("commentCount", 0) or 0)

                    if comment_count <= 0:
                        skipped_videos += 1
                        total_skipped_videos += 1
                        continue

                except Exception:
                    skipped_videos += 1
                    total_skipped_videos += 1
                    continue

                comment_params = urllib.parse.urlencode({
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": "10",
                    "order": "time",
                    "textFormat": "plainText",
                    "key": api_key,
                })

                comment_url = f"https://www.googleapis.com/youtube/v3/commentThreads?{comment_params}"

                try:
                    with urllib.request.urlopen(comment_url, timeout=30) as response:
                        comment_payload = json.loads(response.read().decode("utf-8"))

                except urllib.error.HTTPError:
                    skipped_videos += 1
                    total_skipped_videos += 1
                    continue

                for comment in comment_payload.get("items", []):
                    top_comment = (
                        comment.get("snippet", {})
                        .get("topLevelComment", {})
                        .get("snippet", {})
                    )

                    comment_id = comment.get("id", "")
                    if comment_id in seen_comments:
                        continue

                    seen_comments.add(comment_id)

                    text = clean_text(top_comment.get("textDisplay", ""))
                    author = clean_text(top_comment.get("authorDisplayName", "YouTube kullanıcısı"))
                    like_count = top_comment.get("likeCount", 0) or 0
                    comment_date = str(top_comment.get("publishedAt", published_at))[:10]

                    if not text:
                        continue

                    if not is_relevant_youtube_comment(video_title, text, watch_topic):
                        continue

                    relevant_comments += 1

                    combined_text = f"{video_title} {text}"
                    sentiment, risk_score, opportunity_score, topic, action_note = score_x_post(combined_text, watch_topic)

                    rows.append({
                        "date": comment_date,
                        "platform": "YouTube",
                        "account": author,
                        "content": text.replace("\n", " ").strip(),
                        "topic": topic or watch_topic,
                        "sentiment": sentiment,
                        "risk_score": risk_score,
                        "opportunity_score": opportunity_score,
                        "likes": like_count,
                        "comments": 1,
                        "shares": 0,
                        "views": 0,
                        "url": video_url,
                        "action_note": f"YouTube yorumu takip edildi. Video: {video_title} / Kanal: {channel_title}. {action_note}",
                        "source_type": "Otomatik YouTube",
                    })

                    saved_comments += 1

            summary_rows.append({
                "source": source_name,
                "type": item_type,
                "topic": watch_topic,
                "checked_videos": checked_videos,
                "relevant_comments": relevant_comments,
                "saved_comments": saved_comments,
                "skipped_videos": skipped_videos,
                "note": watch_note,
            })

        with YOUTUBE_SOCIAL_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            fieldnames = [
                "date",
                "platform",
                "account",
                "content",
                "topic",
                "sentiment",
                "risk_score",
                "opportunity_score",
                "likes",
                "comments",
                "shares",
                "views",
                "url",
                "action_note",
                "source_type",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        with YOUTUBE_SUMMARY_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            fieldnames = [
                "source",
                "type",
                "topic",
                "checked_videos",
                "relevant_comments",
                "saved_comments",
                "skipped_videos",
                "note",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary_rows)

        print(f"YouTube otomatik tarama tamamlandı. Kayıt sayısı: {len(rows)} / Kontrol edilen video: {total_checked_videos} / Atlanan video: {total_skipped_videos}")

    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except:
            pass
        print(f"YouTube taraması başarısız. HTTP {e.code}: {detail[:500]}")

    except Exception as e:
        print(f"YouTube taraması başarısız: {e}")
        
def fetch_x_social_posts():
    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        print("X taraması atlandı: X_BEARER_TOKEN yok.")
        return

    keywords = read_watch_keywords()
    if not keywords:
        print("X taraması atlandı: takip kelimesi yok.")
        return

    AUTO_SOCIAL_CSV.parent.mkdir(parents=True, exist_ok=True)

    # X sorgusunu daraltıyoruz:
    # Kepez / Mesut Kocagöz / Kepez Belediyesi bağlamı + risk kelimeleri birlikte aranacak.
    context_terms = [
        '"Mesut Kocagöz"',
        '"Mesut Kocagoz"',
        '"Kepez Belediyesi"',
        '"Kepez Belediye"',
        '"Kepez Belediye Başkanı"',
        '"Kepez Belediye Baskani"',
        "Kepez",
    ]

    risk_terms = [
        "şikayet",
        "sikayet",
        "tepki",
        "dava",
        "teleferik",
        "asfalt",
        "temizlik",
        "park",
        "ulaşım",
        "ulasim",
        "kriz",
        "soruşturma",
        "sorusturma",
        "ihmal",
        "mağdur",
        "magdur",
    ]

    context_query = "(" + " OR ".join(context_terms) + ")"
    risk_query = "(" + " OR ".join(risk_terms) + ")"
    query = f"({context_query} {risk_query}) lang:tr -is:retweet"

    params = urllib.parse.urlencode({
        "query": query,
        "max_results": "10",
        "tweet.fields": "created_at,public_metrics,author_id,text",
        "expansions": "author_id",
        "user.fields": "username,name",
    })

    url = f"https://api.x.com/2/tweets/search/recent?{params}"
    rows = []

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "YerelLiderAI/1.0",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        users = {}
        for user in payload.get("includes", {}).get("users", []):
            users[user.get("id")] = user

        for post in payload.get("data", []):
            text = post.get("text", "")
            text_norm = normalize_text(text)

            context_hit = any(
                normalize_text(term.replace('"', "")) in text_norm
                for term in context_terms
            )

            risk_hit = any(
                normalize_text(term) in text_norm
                for term in risk_terms
            )

            # Üçüncü filtre: uygunluk skoru
            # Amaç: Sadece "Kepez" geçti diye alakasız gönderileri rapora almamak.
            strong_context_terms = [
                "mesut kocagöz",
                "mesut kocagoz",
                "kepez belediyesi",
                "kepez belediye",
                "kepez belediye başkanı",
                "kepez belediye baskani",
            ]

            service_terms = [
                "belediye",
                "başkan",
                "baskan",
                "hizmet",
                "asfalt",
                "yol",
                "temizlik",
                "park",
                "ulaşım",
                "ulasim",
                "sosyal yardım",
                "sosyal yardim",
                "mahalle",
                "zabıta",
                "zabita",
            ]

            political_terms = [
                "chp",
                "ak parti",
                "meclis",
                "aday",
                "seçim",
                "secim",
                "polemik",
                "eleştiri",
                "elestiri",
            ]

            exclude_terms = [
                "kepezspor",
                "kepez spor",
                "satılık",
                "satilik",
                "kiralık",
                "kiralik",
                "emlak",
                "daire",
                "konut",
                "arsa",
                "otomobil",
                "araç",
                "arac",
                "iş ilanı",
                "is ilani",
                "personel alımı",
                "personel alimi",
                "okul",
                "maç",
                "mac",
            ]

            strong_context_hit = any(normalize_text(term) in text_norm for term in strong_context_terms)
            weak_kepez_hit = "kepez" in text_norm
            service_hit = any(normalize_text(term) in text_norm for term in service_terms)
            political_hit = any(normalize_text(term) in text_norm for term in political_terms)
            exclude_hit = any(normalize_text(term) in text_norm for term in exclude_terms)

            relevance_score = 0

            if strong_context_hit:
                relevance_score += 6

            if weak_kepez_hit:
                relevance_score += 2

            if service_hit:
                relevance_score += 3

            if political_hit:
                relevance_score += 2

            if risk_hit:
                relevance_score += 3

            if exclude_hit:
                relevance_score -= 6

            # Hem ana bağlam hem risk kelimesi yoksa alma.
            if not context_hit or not risk_hit:
                continue

            # Sadece zayıf Kepez eşleşmesi varsa ve belediye/hizmet/siyasi bağlam yoksa alma.
            if weak_kepez_hit and not strong_context_hit and not service_hit and not political_hit:
                continue

            # Uygunluk skoru düşükse rapora alma.
            if relevance_score < 7:
                continue

            matched_context = ""
            for term in context_terms:
                clean_term = term.replace('"', "")
                if normalize_text(clean_term) in text_norm:
                    matched_context = clean_term
                    break

            matched_risk = ""
            for term in risk_terms:
                if normalize_text(term) in text_norm:
                    matched_risk = term
                    break

            if matched_context and matched_risk:
                matched_keyword = f"{matched_context} + {matched_risk}"
            else:
                matched_keyword = matched_context or matched_risk or "X otomatik takip"

            sentiment, risk_score, opportunity_score, topic, action_note = score_x_post(
                text,
                matched_keyword
            )

            metrics = post.get("public_metrics", {}) or {}
            author = users.get(post.get("author_id"), {}) or {}
            username = author.get("username", "")
            account = f"@{username}" if username else "X kullanıcısı"

            likes = metrics.get("like_count", 0) or 0
            comments = metrics.get("reply_count", 0) or 0
            shares = (metrics.get("retweet_count", 0) or 0) + (metrics.get("quote_count", 0) or 0)

            post_url = f"https://x.com/{username}/status/{post.get('id')}" if username else ""

            rows.append({
                "date": str(post.get("created_at", ""))[:10],
                "platform": "X / Twitter",
                "account": account,
                "content": text.replace("\n", " ").strip(),
                "topic": topic,
                "sentiment": sentiment,
                "risk_score": risk_score,
                "opportunity_score": opportunity_score,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "views": 0,
                "url": post_url,
                "action_note": action_note,
                "source_type": "Otomatik X",
            })

        with AUTO_SOCIAL_CSV.open("w", encoding="utf-8-sig", newline="") as f:
            fieldnames = [
                "date",
                "platform",
                "account",
                "content",
                "topic",
                "sentiment",
                "risk_score",
                "opportunity_score",
                "likes",
                "comments",
                "shares",
                "views",
                "url",
                "action_note",
                "source_type",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"X otomatik tarama tamamlandı. Kayıt sayısı: {len(rows)}")

    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except:
            pass
        print(f"X taraması başarısız. HTTP {e.code}: {detail[:500]}")

    except Exception as e:
        print(f"X taraması başarısız: {e}")

def read_accounts_map():
    if not ACCOUNTS_MAP_CSV.exists():
        return {}

    accounts = {}

    try:
        with ACCOUNTS_MAP_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                platform = str(row.get("platform", "") or "").strip()
                account = str(row.get("account", "") or "").strip()

                if not account:
                    continue

                key = normalize_text(f"{platform}:{account}")

                accounts[key] = {
                    "platform": platform,
                    "account": account,
                    "type": str(row.get("type", "") or "").strip(),
                    "side": str(row.get("side", "") or "").strip(),
                    "influence_level": str(row.get("influence_level", "") or "").strip(),
                    "watch_level": str(row.get("watch_level", "") or "").strip(),
                    "notes": str(row.get("notes", "") or "").strip(),
                }

    except Exception as e:
        print(f"Hesap haritası okunamadı: {e}")
        return {}

    return accounts


def account_map_info(platform, account, accounts_map):
    platform = str(platform or "").strip()
    account = str(account or "").strip()

    key = normalize_text(f"{platform}:{account}")

    if key in accounts_map:
        return accounts_map[key]

    account_only_key = normalize_text(f":{account}")

    for saved_key, info in accounts_map.items():
        if saved_key.endswith(account_only_key):
            return info

    return {
        "platform": platform,
        "account": account,
        "type": "bilinmeyen",
        "side": "bilinmeyen",
        "influence_level": "dusuk",
        "watch_level": "normal",
        "notes": "Hesap haritasında kayıt yok.",
    }

def account_influence_comment(acc_info):
    account_type = normalize_text(acc_info.get("type", ""))
    side = normalize_text(acc_info.get("side", ""))
    influence = normalize_text(acc_info.get("influence_level", ""))
    watch = normalize_text(acc_info.get("watch_level", ""))

    if "baskan" in account_type:
        return "Başkan hesabı olduğu için görünürlük ve yorum tonu ayrıca takip edilmeli."

    if "yerel_medya" in account_type or "medya" in side:
        if "yuksek" in influence:
            return "Yüksek etkili yerel medya kaynağı. Alakalı yorum varsa ekip tarafından öncelikli kontrol edilmeli."
        return "Yerel medya kaynağı. Alakalı yorumlar kamuoyu tonu açısından takip edilmeli."

    if "rakip" in side or "siyasi" in account_type:
        return "Siyasi çevreye yakın kaynak olabilir. Yorum ve paylaşım dili algı yönetimi açısından izlenmeli."

    if "yuksek" in influence or "yuksek" in watch:
        return "Etkisi yüksek kaynak. Yayılım riski veya fırsat etkisi normal kayıtlardan daha önemli görülmeli."

    if "bilinmeyen" in account_type:
        return "Hesap haritasında kayıt bulunamadı. Gerekirse bu kaynak daha sonra sınıflandırılmalı."

    return "Kaynak takipte. Şimdilik standart izleme yeterli."

def safe_score_value(value, default=0):
    try:
        return float(str(value or default).replace(",", ".").strip())
    except:
        return default


def account_effect_bonus(acc_info):
    account_type = normalize_text(acc_info.get("type", ""))
    side = normalize_text(acc_info.get("side", ""))
    influence = normalize_text(acc_info.get("influence_level", ""))
    watch = normalize_text(acc_info.get("watch_level", ""))

    bonus = 0
    reasons = []

    if "yerel_medya" in account_type or "medya" in side:
        bonus += 1
        reasons.append("yerel medya kaynağı")

    if "rakip" in side or "siyasi" in account_type:
        bonus += 2
        reasons.append("siyasi/rakip çevre ihtimali")

    if "mahalle" in account_type or "sikayet" in account_type or "şikayet" in account_type:
        bonus += 1
        reasons.append("mahalle/şikayet kaynağı")

    if "yuksek" in influence or "yüksek" in influence:
        bonus += 1
        reasons.append("yüksek etkili kaynak")

    if "yuksek" in watch or "yüksek" in watch:
        bonus += 1
        reasons.append("yüksek takip seviyesi")

    if "baskan" in account_type:
        bonus += 1
        reasons.append("başkan hesabı hassasiyeti")

    if bonus > 3:
        bonus = 3

    if not reasons:
        reasons.append("standart kaynak etkisi")

    return bonus, ", ".join(reasons)


def account_adjusted_risk_score(base_risk, acc_info):
    base = safe_score_value(base_risk, 0)
    bonus, reason = account_effect_bonus(acc_info)

    adjusted = base + bonus

    if adjusted > 10:
        adjusted = 10

    return round(adjusted, 1), bonus, reason


def account_adjusted_risk_note(base_risk, acc_info):
    adjusted, bonus, reason = account_adjusted_risk_score(base_risk, acc_info)

    if bonus <= 0:
        return f"Hesap etkili risk: {adjusted}/10. Kaynak standart etki seviyesinde görünüyor."

    return f"Hesap etkili risk: {adjusted}/10. +{bonus} etki eklendi. Neden: {reason}."

def youtube_channel_base_risk(relevant_comments):
    relevant = safe_score_value(relevant_comments, 0)

    if relevant >= 10:
        return 7
    if relevant >= 5:
        return 6
    if relevant >= 2:
        return 5
    if relevant >= 1:
        return 4

    return 2


def youtube_channel_risk_note(relevant_comments, acc_info):
    base_risk = youtube_channel_base_risk(relevant_comments)
    adjusted, bonus, reason = account_adjusted_risk_score(base_risk, acc_info)

    if bonus > 0:
        return f"Kanal etkili risk: {adjusted}/10. Temel risk {base_risk}/10, hesap etkisi +{bonus}. Neden: {reason}."

    return f"Kanal etkili risk: {adjusted}/10. Temel risk {base_risk}/10, hesap etkisi standart."

def read_youtube_summary(limit=20):
    if not YOUTUBE_SUMMARY_CSV.exists():
        return []

    rows = []

    try:
        with YOUTUBE_SUMMARY_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                item = {
                    "source": str(row.get("source", "") or "").strip(),
                    "type": str(row.get("type", "") or "").strip(),
                    "topic": str(row.get("topic", "") or "").strip(),
                    "checked_videos": str(row.get("checked_videos", "") or "0").strip(),
                    "relevant_comments": str(row.get("relevant_comments", "") or "0").strip(),
                    "saved_comments": str(row.get("saved_comments", "") or "0").strip(),
                    "skipped_videos": str(row.get("skipped_videos", "") or "0").strip(),
                    "note": str(row.get("note", "") or "").strip(),
                }

                if any(item.values()):
                    rows.append(item)

    except Exception as e:
        print(f"YouTube özet dosyası okunamadı: {e}")
        return []

    return rows[-limit:]
    
def youtube_summary_html(items):
    if not items:
        return """
<div class="card">
<p class="muted">YouTube kanal takip özeti henüz oluşmadı.</p>
</div>
"""

    rows_html = ""
    accounts_map = read_accounts_map()

    for item in items:
        source = item.get("source", "")
        item_type = item.get("type", "")
        checked = item.get("checked_videos", "0")
        relevant = item.get("relevant_comments", "0")
        saved = item.get("saved_comments", "0")
        skipped = item.get("skipped_videos", "0")

        acc_info = account_map_info("YouTube", source, accounts_map)
        influence_comment = account_influence_comment(acc_info)
        risk_note = youtube_channel_risk_note(relevant, acc_info)

        account_meta = f"""
<p class="muted" style="margin-top:6px;">
  <b>Hesap tipi:</b> {esc(acc_info.get("type", ""))} •
  <b>Taraf:</b> {esc(acc_info.get("side", ""))} •
  <b>Etki:</b> {esc(acc_info.get("influence_level", ""))} •
  <b>Takip:</b> {esc(acc_info.get("watch_level", ""))}
</p>
<p class="muted" style="margin-top:4px;">
  <b>Kaynak yorumu:</b> {esc(influence_comment)}
</p>
</p>
<p class="muted" style="margin-top:4px;">
  <b>Kanal risk yorumu:</b> {esc(risk_note)}
</p>
"""

        try:
            relevant_int = int(float(str(relevant).replace(",", ".") or 0))
        except:
            relevant_int = 0

        if relevant_int > 0:
            status_text = "Alakalı yorum var, ekip gözle kontrol etmeli."
            status_color = "#d97706"
            status_bg = "#fffbeb"
        else:
            status_text = "Alakalı yorum bulunmadı, takipte kalınmalı."
            status_color = "#64748b"
            status_bg = "#f8fafc"

        rows_html += f"""
<div class="item" style="border-left:6px solid #dc2626; background:#fff7ed;">
  <h3>{esc(source)}</h3>
  {account_meta}
  <p><b>Kaynak tipi:</b> {esc(item_type)}</p>
  <p><b>Kontrol edilen video:</b> {esc(checked)} • <b>Alakalı yorum:</b> {esc(relevant)} • <b>Kaydedilen yorum:</b> {esc(saved)} • <b>Atlanan video:</b> {esc(skipped)}</p>
  <p>
    <span style="display:inline-block; padding:6px 10px; border-radius:999px; border:1px solid {status_color}; background:{status_bg}; color:{status_color}; font-weight:700;">
      {esc(status_text)}
    </span>
  </p>
</div>
"""

    return rows_html

def read_social_data():
    sources = [
        (SOCIAL_CSV, "Manuel"),
        (AUTO_SOCIAL_CSV, "Otomatik"),
        (YOUTUBE_SOCIAL_CSV, "Otomatik YouTube"),
    ]

    rows = []

    def to_float_local(value, default=0):
        try:
            return float(str(value or "0").replace(",", ".").strip())
        except:
            return default

    def get_value(row, *keys, default=""):
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip() != "":
                return str(value).strip()
        return default
        
    accounts_map = read_accounts_map()

    for csv_path, default_source_type in sources:
        if not csv_path.exists():
            continue

        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    likes = to_float_local(get_value(row, "likes", "like", "begeni", "beğeni", default="0"))
                    comments = to_float_local(get_value(row, "comments", "comment", "yorum", default="0"))
                    shares = to_float_local(get_value(row, "shares", "share", "paylasim", "paylaşım", default="0"))
                    views = to_float_local(get_value(row, "views", "view", "goruntulenme", "görüntülenme", default="0"))

                    good_comments = to_float_local(get_value(row, "good_comments", "iyi_yorum", default="0"))
                    neutral_comments = to_float_local(get_value(row, "neutral_comments", "notr_yorum", "nötr_yorum", default="0"))
                    bad_comments = to_float_local(get_value(row, "bad_comments", "kotu_yorum", "kötü_yorum", default="0"))

                    sentiment = get_value(row, "sentiment", "duygu", "tone", default="neutral")

                    if sentiment == "positive":
                        tone = "İyi"
                        good_comments = good_comments or 1
                    elif sentiment == "negative":
                        tone = "Kötü"
                        bad_comments = bad_comments or 1
                    elif sentiment == "neutral":
                        tone = "Nötr"
                        neutral_comments = neutral_comments or 1
                    else:
                        tone = sentiment

                    engagement = likes + comments + shares
                    like_rate = round((likes / views) * 100, 2) if views else 0
                    engagement_rate = round((engagement / views) * 100, 2) if views else 0

                    risk_score = to_float_local(get_value(row, "risk_score", "risk", default="0"))
                    opportunity_score = to_float_local(get_value(row, "opportunity_score", "opportunity", default="0"))

                    action_note = get_value(row, "action_note", "action", "aksiyon", "not")
                    
                    platform_value = get_value(row, "platform", "Platform")
                    account_value = get_value(row, "account", "hesap", "account_name")

                    acc_info = account_map_info(
                        platform_value,
                        account_value,
                        accounts_map
                    )

                    account_adjusted_risk, account_effect_bonus_value, account_risk_reason = account_adjusted_risk_score(
                        risk_score,
                        acc_info
                    )
                    
                    item = {
                        "date": get_value(row, "date", "tarih"),
                        "platform": platform_value,
                         "account": account_value,
                        "content": get_value(row, "content", "icerik", "içerik", "text"),
                        "topic": get_value(row, "topic", "konu"),
                        "tone": tone,
                        "sentiment": sentiment,
                        "likes": likes,
                        "comments": comments,
                        "shares": shares,
                        "views": views,
                        "good_comments": good_comments,
                        "neutral_comments": neutral_comments,
                        "bad_comments": bad_comments,
                        "like_rate": like_rate,
                        "engagement_rate": engagement_rate,
                        "risk_score": risk_score,
                        "opportunity_score": opportunity_score,
                        "url": get_value(row, "url", "link"),
                        "link": get_value(row, "url", "link"),
                        "action_note": action_note,
                        "notes": action_note,
                        "risk_note": action_note,
                        "account_type": acc_info.get("type", ""),
                         "account_side": acc_info.get("side", ""),
                         "account_influence_level": acc_info.get("influence_level", ""),
                         "account_watch_level": acc_info.get("watch_level", ""),
                         "account_notes": acc_info.get("notes", ""),
                         "account_adjusted_risk_score": account_adjusted_risk,
                         "account_effect_bonus": account_effect_bonus_value,
                         "account_risk_reason": account_risk_reason,
                         "source_type": get_value(row, "source_type", default=default_source_type),
                    }

                    if any(str(v).strip() for v in item.values()):
                        rows.append(item)

        except Exception as e:
            print(f"Sosyal medya verisi okunamadı: {csv_path} - {e}")

    return rows

def read_crisis_status():
    default_status = {
        "active": "yes",
        "status": "İzleniyor",
        "manual_note": "Manuel kriz notu henüz girilmedi.",
        "last_action": "Son aksiyon henüz girilmedi.",
        "next_action": "Sıradaki aksiyon henüz belirlenmedi.",
        "responsible": "Basın / ilgili birim",
        "updated_by": "Sistem"
    }

    if not CRISIS_CSV.exists():
        return default_status

    try:
        with CRISIS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                result = default_status.copy()
                for key in result:
                    value = str(row.get(key, "") or "").strip()
                    if value:
                        result[key] = value
                return result
    except Exception:
        return default_status

    return default_status

def read_crisis_log():
    if not CRISIS_LOG_CSV.exists():
        return []

    rows = []
    try:
        with CRISIS_LOG_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = {
                    "time": str(row.get("time", "") or "").strip(),
                    "event": str(row.get("event", "") or "").strip(),
                    "action": str(row.get("action", "") or "").strip(),
                    "result": str(row.get("result", "") or "").strip(),
                    "responsible": str(row.get("responsible", "") or "").strip(),
                    "next_step": str(row.get("next_step", "") or "").strip(),
                    "note": str(row.get("note", "") or "").strip(),
                }
                if any(item.values()):
                    rows.append(item)
    except Exception:
        return []

    return rows[-20:]

def generate_dynamic_keywords(news, social):
    candidates = []
    for item in news:
        text = normalize_text(item.get("title", "") + " " + item.get("summary", ""))
        if "teleferik" in text or "dava" in text:
            candidates.append("Mesut Kocagöz teleferik davası")
        if "asfalt" in text or "duaci" in text or "duacı" in text or "yol" in text:
            candidates.append("Kepez asfalt çalışması")
        if "bayrak" in text or "personel" in text or "ödül" in text or "odul" in text:
            candidates.append("Kepez bayrak personel ödül")
        if "23 nisan" in text or "çocuk" in text or "cocuk" in text or "şenlik" in text:
            candidates.append("Kepez 23 Nisan çocuk etkinliği")
        if "borç" in text or "borc" in text or "mali" in text:
            candidates.append("Kepez Belediyesi borç mali disiplin")
        if "drag" in text or "spor" in text:
            candidates.append("Kepez drag pisti spor")
        if "büyükşehir" in text or "buyuksehir" in text or "ulaşım" in text or "ulasim" in text:
            candidates.append("Antalya Büyükşehir Belediyesi ulaşım")
    for item in social:
        topic = clean_text(item.get("topic", ""))
        if topic:
            candidates.append(topic)
    result, seen = [], set()
    for keyword in candidates:
        key = normalize_text(keyword)
        if key and key not in seen:
            seen.add(key)
            result.append(keyword)
        if len(result) >= 12:
            break
    return result


def save_dynamic_keywords(keywords):
    DYNAMIC_KEYWORDS.parent.mkdir(parents=True, exist_ok=True)
    content = "# Sistem tarafından otomatik üretilen dinamik anahtar kelimeler\n# Bu dosya her çalışmada güncellenir\n\n"
    content += "\n".join(keywords) + "\n"
    DYNAMIC_KEYWORDS.write_text(content, encoding="utf-8")


def unique_by_topic(items, limit):
    result, used = [], set()
    for item in items:
        key = item.get("topic") or topic_key(item.get("title", ""))
        if key in used:
            continue
        used.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result

def early_warning_decision(crisis_plan, crisis_status, social_sum):
    level_text = normalize_text(crisis_plan.get("level", ""))
    human_text = normalize_text(crisis_plan.get("human_sensitivity", ""))
    status_text = normalize_text(crisis_status.get("status", ""))

    risky_item = social_sum.get("risky") or {}

    try:
        social_risk_score = float(risky_item.get("risk_score", 0) or 0)
    except:
        social_risk_score = 0

    risk_topic = crisis_plan.get("risk_topic", "Riskli başlık belirlenemedi.")

    if "yuksek" in level_text or "cok yuksek" in human_text or social_risk_score >= 7:
        return {
            "decision": "ACİL ALARM",
            "notify_level": "Sayın Başkan + Basın + Hukuk + ilgili birim",
            "show_to_president": "Evet",
            "reason": f"{risk_topic} başlığında risk seviyesi veya insani hassasiyet yüksek görünüyor. Konu hızlı büyümeden tek merkezli kriz koordinasyonu gerekir.",
            "first_action": "İlk 30 dakika içinde basın, hukuk ve ilgili birim aynı bilgi notunda hizalanmalı. Sayın Başkan’a kısa, sakin ve yönlendirici bir özet sunulmalı."
        }

    if "orta" in level_text or social_risk_score >= 4 or "müdahale" in status_text:
        return {
            "decision": "TAKİPTE KAL / HAZIR BEKLE",
            "notify_level": "Ekip içi takip: Basın + ilgili birim",
            "show_to_president": "Şimdilik hayır",
            "reason": f"{risk_topic} başlığında orta seviye takip ihtiyacı var. Konu izlenmeli; yayılım artarsa Sayın Başkan’a kısa bilgi notu hazırlanmalı.",
            "first_action": "Yorum hızı, paylaşım artışı ve yerel basına sıçrama ihtimali izlenmeli. Açıklama taslağı hazır tutulmalı ama hemen yayınlanmamalı."
        }

    return {
        "decision": "NORMAL TAKİP",
        "notify_level": "Sosyal medya / basın ekibi rutin takip",
        "show_to_president": "Hayır",
        "reason": "Şu an acil bildirim gerektiren güçlü kriz sinyali görünmüyor.",
        "first_action": "Rutin takip sürdürülmeli. Yeni haber, yorum artışı veya olumsuz yayılım olursa karar tekrar değerlendirilmeli."
    }

def append_alert_log(early_warning, crisis_plan, crisis_status, report_time, mail_to, email_sent, note):
    ALERT_LOG_CSV.parent.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now()
    file_exists = ALERT_LOG_CSV.exists()

    fieldnames = [
        "date",
        "time",
        "risk_level",
        "decision",
        "crisis_title",
        "status",
        "email_to",
        "email_sent",
        "note",
        "reason",
        "first_action",
        "crisis_panel_url",
        "daily_report_url",
    ]

    row = {
        "date": now.strftime("%Y-%m-%d"),
        "time": report_time or now.strftime("%H:%M"),
        "risk_level": crisis_plan.get("level", ""),
        "decision": early_warning.get("decision", ""),
        "crisis_title": crisis_plan.get("risk_topic", ""),
        "status": crisis_status.get("status", ""),
        "email_to": mail_to,
        "email_sent": email_sent,
        "note": note,
        "reason": early_warning.get("reason", ""),
        "first_action": early_warning.get("first_action", ""),
        "crisis_panel_url": "https://korayarhan.github.io/dijital-antalya-nabzi/reports/crisis_panel.html",
        "daily_report_url": "https://korayarhan.github.io/dijital-antalya-nabzi/reports/daily_report.html",
    }

    try:
        with ALERT_LOG_CSV.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow(row)

        print("Bildirim geçmişi kaydedildi.")

    except Exception as e:
        print(f"Bildirim geçmişi kaydedilemedi: {e}")

def send_early_warning_email(early_warning, crisis_plan, crisis_status, report_time):
    enabled = str(os.getenv("ALERT_EMAIL_ENABLED", "false")).lower() in ["1", "true", "yes", "evet"]

    if not enabled:
        print("E-posta bildirimi kapalı.")
        return

    decision = early_warning.get("decision", "")

    notify_medium = str(os.getenv("ALERT_NOTIFY_ON_MEDIUM", "false")).lower() in ["1", "true", "yes", "evet"]

    should_send = "ACİL ALARM" in decision or "ACIL ALARM" in decision

    if notify_medium and "TAKİPTE KAL" in decision:
        should_send = True

    if not should_send:
        print("E-posta gönderilmedi: karar seviyesi mail için yeterli değil.")
        return

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    mail_to = os.getenv("ALERT_EMAIL_TO", "")
    mail_from = os.getenv("ALERT_EMAIL_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_password or not mail_to:
        append_alert_log(
            early_warning,
            crisis_plan,
            crisis_status,
            report_time,
            mail_to,
            "Hayır",
            "SMTP secret bilgileri eksik",
        )
        print("E-posta gönderilmedi: SMTP secret bilgileri eksik.")
        return

    risk_topic = crisis_plan.get("risk_topic", "")
    risk_level = crisis_plan.get("level", "")
    status = crisis_status.get("status", "")

    subject = f"Yerel Lider AI - {decision} - {risk_topic}"

    body = f"""
Yerel Lider AI Erken Uyarı

Karar: {early_warning.get("decision", "")}
Bildirim seviyesi: {early_warning.get("notify_level", "")}
Sayın Başkan’a acil gösterilsin mi?: {early_warning.get("show_to_president", "")}

Risk seviyesi: {risk_level}
Kriz başlığı: {risk_topic}
Durum: {status}
Güncelleme saati: {report_time}

Neden:
{early_warning.get("reason", "")}

İlk aksiyon:
{early_warning.get("first_action", "")}

Kriz paneli:
https://korayarhan.github.io/dijital-antalya-nabzi/reports/crisis_panel.html

Günlük rapor:
https://korayarhan.github.io/dijital-antalya-nabzi/reports/daily_report.html
"""

    try:
        msg = EmailMessage()
        msg["From"] = mail_from
        msg["To"] = mail_to
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)

        append_alert_log(
            early_warning,
            crisis_plan,
            crisis_status,
            report_time,
            mail_to,
            "Evet",
            "E-posta gönderildi",
        )

        print(f"Erken uyarı e-postası gönderildi: {mail_to}")

    except Exception as e:
        append_alert_log(
            early_warning,
            crisis_plan,
            crisis_status,
            report_time,
            mail_to,
            "Hayır",
            f"E-posta gönderilemedi: {e}",
        )
        print(f"E-posta gönderilemedi: {e}")
def crisis_related_news(items, risk_topic, limit=5):
    topic_text = normalize_text(risk_topic)

    keywords = []

    if any(k in topic_text for k in ["teleferik", "dava", "yargi", "yargı", "sorusturma", "soruşturma", "facia", "mahkeme"]):
        keywords += ["teleferik", "dava", "yargi", "yargı", "soruşturma", "sorusturma", "facia", "mahkeme"]

    if any(k in topic_text for k in ["asfalt", "yol", "temizlik", "park", "ulasim", "ulaşım", "hizmet", "mahalle", "sikayet", "şikayet"]):
        keywords += ["asfalt", "yol", "temizlik", "park", "ulaşım", "ulasim", "hizmet", "mahalle", "şikayet", "sikayet"]

    if any(k in topic_text for k in ["rakip", "ak parti", "chp", "polemik", "siyasi", "elestiri", "eleştiri", "iddia"]):
        keywords += ["rakip", "ak parti", "chp", "polemik", "siyasi", "eleştiri", "elestiri", "iddia"]

    if any(k in topic_text for k in ["borc", "borç", "mali", "butce", "bütçe", "para", "ihale"]):
        keywords += ["borç", "borc", "mali", "bütçe", "butce", "para", "ihale"]

    for word in topic_text.split():
        if len(word) > 3 and word not in STOPWORDS:
            keywords.append(word)

    clean_keywords = []
    seen = set()
    for key in keywords:
        nk = normalize_text(key)
        if nk and nk not in seen:
            seen.add(nk)
            clean_keywords.append(nk)

    scored = []
    crisis_topic_key = topic_key(risk_topic)

    for item in items:
        body = normalize_text(
            f"{item.get('title', '')} {item.get('summary', '')} {item.get('topic', '')} {item.get('keyword', '')}"
        )

        match_count = sum(1 for key in clean_keywords if key in body)
        same_topic = item.get("topic") == crisis_topic_key or topic_key(item.get("title", "")) == crisis_topic_key

        if match_count > 0 or same_topic:
            try:
                base_risk = int(float(item.get("risk", 0) or 0))
            except:
                base_risk = 0

            score = base_risk + (match_count * 5) + (8 if same_topic else 0)
            scored.append((score, item))

    if scored:
        scored = sorted(scored, key=lambda x: x[0], reverse=True)
        return [item for score, item in scored[:limit]]

    return unique_by_topic(
        sorted(items, key=lambda x: x.get("risk", 0), reverse=True),
        limit
    )

def top_items(news):
    positive_candidates = sorted([x for x in news if x["tone"] == "Olumlu"], key=lambda x: x["opportunity"], reverse=True)
    service_candidates = sorted([x for x in news if any(k in normalize_text(x.get("title", "")) for k in ["asfalt", "duaci", "duacı", "hizmet", "mahalle", "yol", "park"])], key=lambda x: x["opportunity"], reverse=True)
    risk_candidates = sorted([x for x in news if x["tone"] == "Riskli"], key=lambda x: x["risk"], reverse=True)

    positive = unique_by_topic(positive_candidates, 5)
    risky = unique_by_topic(risk_candidates, 5)

    important = []
    for group in [positive_candidates, service_candidates, risk_candidates]:
        if group and group[0] not in important:
            important.append(group[0])

    if len(important) < 3:
        for item in sorted(news, key=lambda x: x["risk"] + x["opportunity"], reverse=True):
            if item not in important:
                important.append(item)
            if len(important) >= 3:
                break

    return important[:3], positive, risky


def social_summary(social):
    def safe_int(item, key):
        try:
            return int(float(item.get(key, 0) or 0))
        except:
            return 0

    if not social:
        return {
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "total_views": 0,
            "total_good": 0,
            "total_neutral": 0,
            "total_bad": 0,
            "like_rate": 0,
            "engagement_rate": 0,
            "best_like": None,
            "most_comments": None,
            "risky": None,
            "opportunity": None,
            "social_mood": "Veri yok",
            "main_topic": "Bugün sosyal medya verisi yok.",
            "risk_text": "Sosyal medya tarafında ölçülebilir risk bulunamadı.",
            "opportunity_text": "Bugün sosyal medya tarafında özel bir fırsat görünmüyor.",
            "action_text": "Sosyal medya verisi geldiğinde tekrar değerlendirme yapılmalı."
        }

    total_likes = sum(safe_int(x, "likes") for x in social)
    total_comments = sum(safe_int(x, "comments") for x in social)
    total_shares = sum(safe_int(x, "shares") for x in social)
    total_views = sum(safe_int(x, "views") for x in social)

    total_good = sum(safe_int(x, "good_comments") for x in social)
    total_neutral = sum(safe_int(x, "neutral_comments") for x in social)
    total_bad = sum(safe_int(x, "bad_comments") for x in social)

    like_rate = (total_likes / total_views * 100) if total_views else 0
    engagement_rate = ((total_likes + total_comments + total_shares) / total_views * 100) if total_views else 0

    best_like = max(social, key=lambda x: safe_int(x, "likes"))
    most_comments = max(social, key=lambda x: safe_int(x, "comments"))
    risky = max(social, key=lambda x: safe_int(x, "risk_score"))
    opportunity = max(social, key=lambda x: safe_int(x, "likes") + safe_int(x, "shares") + safe_int(x, "good_comments"))

    max_risk = safe_int(risky, "risk_score")

    if total_bad > total_good and max_risk >= 5:
        social_mood = "Riskli"
    elif total_good >= total_bad and total_good >= total_neutral:
        social_mood = "Olumlu"
    else:
        social_mood = "Nötr"

    main_topic = most_comments.get("topic", "Sosyal medyada öne çıkan konu belirlenemedi.")

    if max_risk >= 7:
        risk_text = "Yüksek riskli bir sosyal medya başlığı var. Konu büyümeden soğukkanlı ve kontrollü aksiyon alınmalı."
        action_text = "İlk 30 dakikada konu doğrulanmalı, ilgili birimden bilgi alınmalı ve acele açıklama yapılmamalı."
    elif max_risk >= 4:
        risk_text = "Orta seviye sosyal medya riski var. Yorumlar ve paylaşım hızı takip edilmeli."
        action_text = "Konu izlenmeli, gerekirse kısa ve sakin bir bilgilendirme dili hazırlanmalı."
    else:
        risk_text = "Şu an sosyal medya tarafında belirgin kriz sinyali görünmüyor."
        action_text = "Olumlu görünürlük korunmalı, iyi etkileşim alan içerikler büyütülmeli."

    opportunity_topic = opportunity.get("topic", "Olumlu görünürlük fırsatı belirlenemedi.")
    opportunity_text = f"En güçlü fırsat başlığı: {opportunity_topic}. Bu içerik Sayın Başkan'ın hizmet ve insan hikayesi diliyle desteklenebilir."

    return {
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_views": total_views,
        "total_good": total_good,
        "total_neutral": total_neutral,
        "total_bad": total_bad,
        "like_rate": like_rate,
        "engagement_rate": engagement_rate,
        "best_like": best_like,
        "most_comments": most_comments,
        "risky": risky,
        "opportunity": opportunity,
        "social_mood": social_mood,
        "main_topic": main_topic,
        "risk_text": risk_text,
        "opportunity_text": opportunity_text,
        "action_text": action_text
    }

def build_auto_crisis_summary(news, social_sum):
    result = dict(social_sum or {})
    risky_social = result.get("risky") or {}

    try:
        social_score = float(risky_social.get("risk_score", 0) or 0)
    except:
        social_score = 0

    risky_news = sorted(
        [x for x in news if str(x.get("tone", "")) == "Riskli" or float(x.get("risk", 0) or 0) >= 4],
        key=lambda x: float(x.get("risk", 0) or 0),
        reverse=True
    )

    if not risky_news:
        return result

    best_news = risky_news[0]

    try:
        news_score = float(best_news.get("risk", 0) or 0)
    except:
        news_score = 0

    # Haber riski sosyal riskten yüksekse veya 7 üstüyse kriz kaynağını haber yap.
    if news_score >= social_score or news_score >= 7 or not risky_social:
        title = clean_text(best_news.get("title", "Riskli haber başlığı"))
        summary = clean_text(best_news.get("summary", ""))

        result["risky"] = {
            "date": best_news.get("date", ""),
            "platform": "Google News / İnternet Haberi",
            "account": best_news.get("keyword", ""),
            "topic": title,
            "tone": "Kötü",
            "risk_score": news_score,
            "opportunity_score": best_news.get("opportunity", 0),
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "views": 0,
            "good_comments": 0,
            "neutral_comments": 0,
            "bad_comments": 1,
            "like_rate": 0,
            "engagement_rate": 0,
            "notes": summary[:260],
            "risk_note": f"Otomatik haber taramasından riskli başlık yakalandı. Anahtar kelime: {best_news.get('keyword', '')}",
            "link": best_news.get("link", "")
        }

        result["social_mood"] = "Riskli" if news_score >= 7 else "Nötr"
        result["main_topic"] = title
        result["risk_text"] = f"Otomatik haber taramasında riskli başlık yakalandı: {title}"
        result["action_text"] = "Haber kaynağı, yayılım hızı ve yerel basına sıçrama ihtimali kontrol edilmeli."

    return result

def crisis_action_plan(social_sum):
    risky_item = social_sum.get("risky") or {}

    try:
        risk_score = int(float(risky_item.get("risk_score", 0) or 0))
    except:
        risk_score = 0

    risk_topic = risky_item.get("topic", "Riskli başlık belirlenemedi.")
    social_mood = social_sum.get("social_mood", "Nötr")
    topic_text = normalize_text(risk_topic)

    human_keywords = [
        "olum", "ölüm", "vefat", "hayatini kaybetti", "hayatını kaybetti",
        "can kaybi", "can kaybı", "yarali", "yaralı", "yaralanma",
        "kaza", "facia", "afet", "yangin", "yangın", "sel",
        "cocuk", "çocuk", "aile", "magdur", "mağdur", "cenaze"
    ]

    heavy_human_keywords = [
        "olum", "ölüm", "vefat", "hayatini kaybetti", "hayatını kaybetti",
        "can kaybi", "can kaybı", "facia", "yarali", "yaralı", "yaralanma"
    ]

    is_human_sensitive = any(k in topic_text for k in human_keywords)
    is_heavy_human = any(k in topic_text for k in heavy_human_keywords)

    def human_layer():
        if is_heavy_human or "teleferik" in topic_text or "facia" in topic_text:
            return {
                "human_sensitivity": "Çok yüksek",
                "emotional_context": "Bu başlık sadece siyasi veya kurumsal risk değildir. İçinde can kaybı, yaralanma, aile acısı veya mağduriyet ihtimali bulunduğu için toplum öncelikle insani hassasiyet, samimi üzüntü ve saygılı bir dil görmek ister.",
                "public_expectation": "Kamuoyu ilk aşamada savunma değil; acının görüldüğünü, mağdur ailelere saygı duyulduğunu, hukuki sürece saygı gösterildiğini ve bilgi kirliliğinden kaçınıldığını görmek ister.",
                "opening_line": "İlk cümle insanı merkeze almalı: 'Hayatını kaybeden vatandaşımıza Allah’tan rahmet, ailesine ve yakınlarına başsağlığı diliyoruz.' Can kaybı bilgisi kesin değilse bu cümle doğrulanmadan kullanılmamalı.",
                "avoid_language": "'Bizim suçumuz yok', 'biz haklıyız', 'siyasi saldırı var', 'zaten süreç devam ediyor' gibi soğuk, savunmacı veya mağdur ailelerin acısını ikinci plana atan ifadeler ilk açıklamada kullanılmamalı.",
                "statement_draft": "Kamuoyuna yansıyan ve hepimizi derinden üzen bu süreç hassasiyetle takip edilmektedir. Hayatını kaybeden vatandaşımız varsa Allah’tan rahmet, ailesine ve yakınlarına başsağlığı diliyoruz. Hukuki sürece saygımız tamdır. Bilgi kirliliğine yol açmadan, ilgili kurumlarımızla birlikte süreci dikkatle takip etmeye devam edeceğiz.",
                "speaker_decision": "Teknik ve hukuki açıklamayı kurumsal hesap veya ilgili birim yapmalı. Ancak insani hassasiyet çok yüksek olduğu için Sayın Başkan kısa, sakin ve sadece taziye/hassasiyet çerçevesinde bir mesaj verebilir. Sayın Başkan teknik detaylara ve polemiğe girmemeli."
            }

        if is_human_sensitive:
            return {
                "human_sensitivity": "Yüksek",
                "emotional_context": "Bu başlıkta vatandaş mağduriyeti, aile hassasiyeti veya sosyal duyarlılık boyutu var. Dil sadece kurumsal değil, insan odaklı kurulmalı.",
                "public_expectation": "Kamuoyu sorunun görülmesini, vatandaşın yalnız bırakılmamasını ve çözüm iradesinin açıkça gösterilmesini bekler.",
                "opening_line": "İlk cümle vatandaşın duygusunu kabul etmeli: 'Yaşanan mağduriyeti dikkatle takip ediyoruz; vatandaşlarımızın yanında olduğumuzu özellikle ifade etmek isteriz.'",
                "avoid_language": "Vatandaşı suçlayan, şikayeti küçümseyen, soğuk bürokratik veya sadece teknik görünen ifadelerden kaçınılmalı.",
                "statement_draft": "Kamuoyuna yansıyan konu tarafımızca dikkatle takip edilmektedir. Vatandaşlarımızın yaşadığı mağduriyetleri önemsiyoruz. İlgili birimlerimiz süreci incelemekte olup, gerekli adımlar şeffaf ve çözüm odaklı biçimde atılacaktır.",
                "speaker_decision": "İlk açıklama kurumsal hesap veya ilgili birimden yapılmalı. Konu büyür veya insani hassasiyet artarsa Sayın Başkan kısa ve empatik bir mesajla devreye girebilir."
            }

        return {
            "human_sensitivity": "Normal",
            "emotional_context": "Bu başlıkta belirgin bir can kaybı, yaralanma veya ağır mağduriyet sinyali görünmüyor. Yine de dil ölçülü, sakin ve vatandaş odaklı kalmalı.",
            "public_expectation": "Kamuoyu net bilgi, sakin üslup ve çözüm odaklı yaklaşım bekler.",
            "opening_line": "İlk cümle kısa ve sakin olmalı: 'Konu ilgili birimlerimiz tarafından takip edilmektedir.'",
            "avoid_language": "Sert, alaycı, kişiselleştiren veya polemiği büyüten ifadelerden kaçınılmalı.",
            "statement_draft": "Kamuoyuna yansıyan konu ilgili birimlerimiz tarafından takip edilmektedir. Gerekli inceleme ve değerlendirmeler yapıldıktan sonra kamuoyu doğru bilgiyle bilgilendirilecektir.",
            "speaker_decision": "İlk aşamada kurumsal hesap veya ilgili birim yeterlidir. Sayın Başkan’ın doğrudan konuşması ancak konu büyürse değerlendirilmelidir."
        }

    def make_plan(level, what_not_to_do, first_30, first_2h, first_24h, speaker, data_needed, tone):
        h = human_layer()
        return {
            "level": level,
            "risk_topic": risk_topic,
            "what_not_to_do": what_not_to_do,
            "first_30": first_30,
            "first_2h": first_2h,
            "first_24h": first_24h,
            "speaker": speaker,
            "data_needed": data_needed,
            "tone": tone,
            "human_sensitivity": h["human_sensitivity"],
            "emotional_context": h["emotional_context"],
            "public_expectation": h["public_expectation"],
            "opening_line": h["opening_line"],
            "avoid_language": h["avoid_language"],
            "statement_draft": h["statement_draft"],
            "speaker_decision": h["speaker_decision"]
        }

    # 1) Teleferik / dava / yargı gündemi
    if any(k in topic_text for k in ["teleferik", "dava", "yargi", "yargı", "sorusturma", "soruşturma", "facia"]):
        return make_plan(
            "Yüksek" if risk_score >= 7 or social_mood == "Riskli" else "Orta",
            "Sayın Başkan doğrudan hukuki sürece dair kesin hüküm içeren, öfkeli veya savunmacı bir açıklama yapmamalı. Yargı süreci küçümsenmemeli, mağduriyet algısını artıracak ifadelerden kaçınılmalı.",
            "İlk 30 dakikada haberin kaynağı, paylaşım hızı, yorum tonu ve iddianın yeni mi eski mi olduğu kontrol edilmeli. Ekran görüntüleri ve linkler kaydedilmeli.",
            "İlk 2 saatte hukuk birimi, basın birimi ve ilgili kurumsal ekipten kısa bilgi alınmalı. Gerekirse sadece sürece saygılı, sakin ve kurumsal bir bilgilendirme notu hazırlanmalı.",
            "İlk 24 saatte konu büyürse açıklama hukuk diline uygun yapılmalı. Sayın Başkan’ın kişisel tartışmaya çekilmemesi, kurumsal ve insani hassasiyetin öne çıkarılması gerekir.",
            "İlk teknik açıklamayı doğrudan Sayın Başkan değil, kurumsal hesap, hukuk birimi veya yetkilendirilmiş ilgili birim yapmalı. İnsani hassasiyet çok yüksekse Sayın Başkan kısa ve sadece taziye/hassasiyet mesajıyla devreye girebilir.",
            "Haber linkleri, dava/süreç bilgisi, resmi açıklama geçmişi, varsa mahkeme takvimi, basın notu, mağduriyet bilgisi ve daha önce yapılan açıklamalar hazırlanmalı.",
            "Hukuka saygılı, sakin, mağdur aileleri önemseyen, polemiğe girmeyen ve insani hassasiyeti öne alan bir dil kullanılmalı."
        )

    # 2) Hizmet şikayeti / asfalt / temizlik / park / ulaşım
    if any(k in topic_text for k in ["asfalt", "yol", "temizlik", "park", "ulasim", "ulaşım", "hizmet", "mahalle", "sikayet", "şikayet"]):
        return make_plan(
            "Orta" if risk_score >= 4 else "Düşük",
            "Sayın Başkan şikayeti küçümseyen, vatandaşı suçlayan veya 'zaten yapıyoruz' gibi savunmacı bir dil kullanmamalı.",
            "İlk 30 dakikada şikayetin hangi mahalle, hangi sokak ve hangi hizmet başlığıyla ilgili olduğu netleştirilmeli. Aynı şikayetin farklı hesaplarda tekrar edip etmediği kontrol edilmeli.",
            "İlk 2 saatte ilgili müdürlükten mevcut durum ve işlem takvimi alınmalı. Çözüm varsa kısa not, çözüm yoksa sahaya kontrol talimatı hazırlanmalı.",
            "İlk 24 saatte sahadan fotoğraf, ekip çalışması veya planlanan işlem bilgisi alınmalı. Konu büyürse 'tespit ettik, programa aldık, takip ediyoruz' diliyle açıklama yapılmalı.",
            "Öncelik kurumsal hesapta olmalı. Gerekiyorsa ilgili müdürlük veya başkan yardımcısı teknik bilgi verebilir. Sayın Başkan doğrudan polemiğe girmemeli.",
            "Mahalle/sokak bilgisi, talep kayıtları, çalışma programı, ekip yönlendirme bilgisi, önce/sonra fotoğrafı ve tahmini çözüm süresi hazırlanmalı.",
            "Vatandaşı anlayan, çözüm odaklı, sahaya inen ve net takvim veren bir dil kullanılmalı."
        )

    # 3) Siyasi saldırı / rakip görünürlüğü / polemik
    if any(k in topic_text for k in ["rakip", "ak parti", "chp", "polemik", "siyasi", "elestiri", "eleştiri", "iddia"]):
        return make_plan(
            "Orta" if risk_score >= 4 else "Düşük",
            "Sayın Başkan kişisel tartışmaya girmemeli, rakibin diline aynı sertlikle cevap vermemeli ve gündemi rakibin belirlemesine izin vermemeli.",
            "İlk 30 dakikada iddianın kimden çıktığı, ne kadar yayıldığı ve yerel basına taşınıp taşınmadığı kontrol edilmeli.",
            "İlk 2 saatte cevap verilip verilmeyeceğine karar verilmeli. Cevap gerekiyorsa kişiye değil konuya odaklanan kısa bir çerçeve hazırlanmalı.",
            "İlk 24 saatte polemik büyürse hizmet verisi, saha görüntüsü ve vatandaş faydası üzerinden gündem geri alınmalı.",
            "Cevap gerekiyorsa önce kurumsal hesap veya parti/iletişim ekibi konuşmalı. Sayın Başkan sadece stratejik ve sakin bir üst mesajla görünmeli.",
            "İddia metni, paylaşım linkleri, karşı veri, hizmet bilgisi, önceki açıklamalar ve kullanılabilecek kısa mesaj notu hazırlanmalı.",
            "Sakin, özgüvenli, hizmet odaklı ve polemiği büyütmeyen bir dil kullanılmalı."
        )

    # 4) Borç / mali disiplin / bütçe tartışması
    if any(k in topic_text for k in ["borc", "borç", "mali", "butce", "bütçe", "para", "ihale"]):
        return make_plan(
            "Orta" if risk_score >= 4 else "Düşük",
            "Sayın Başkan rakamsal konu netleşmeden açıklama yapmamalı. Eksik veriyle iddialı cümle kurulması ileride ters tepebilir.",
            "İlk 30 dakikada iddianın hangi rakama, hangi döneme ve hangi kaynağa dayandığı belirlenmeli.",
            "İlk 2 saatte mali işler biriminden net ve sade veri istenmeli. Gerekirse teknik tablo değil, vatandaşın anlayacağı kısa özet hazırlanmalı.",
            "İlk 24 saatte konu büyürse mali disiplin, şeffaflık ve hizmetlerin aksamaması çerçevesinde açıklama yapılmalı.",
            "İlk açıklama teknik ekip veya kurumsal hesap üzerinden yapılmalı. Sayın Başkan gerekiyorsa daha sonra güven veren genel mesajla desteklemeli.",
            "Borç tablosu, dönem karşılaştırması, ödeme planı, hizmetlere etkisi ve resmi belge notları hazırlanmalı.",
            "Şeffaf, sakin, rakama dayalı ve güven veren bir dil kullanılmalı."
        )

    # 5) Genel risk seviyesi
    if risk_score >= 7 or social_mood == "Riskli":
        return make_plan(
            "Yüksek",
            "Sayın Başkan doğrudan, duygusal veya suçlayıcı bir açıklama yapmamalı. Konu doğrulanmadan savunmacı dil kullanılmamalı.",
            "İlk 30 dakikada olay doğrulanmalı, ekran görüntüleri/linkler kaydedilmeli, ilgili müdürlükten net bilgi istenmeli.",
            "İlk 2 saatte kısa, sakin ve kurumsal bir bilgilendirme hazırlanmalı. Gerekirse sahadan fotoğraf, belge veya işlem kaydı alınmalı.",
            "İlk 24 saatte konu kapanmadıysa yapılan işlem kamuoyuna sade bir dille anlatılmalı, mağduriyet varsa çözüm adımı görünür kılınmalı.",
            "İlk açıklamayı doğrudan Sayın Başkan değil, ilgili başkan yardımcısı veya birim müdürlüğü yapmalı. Sayın Başkan ancak konu büyürse devreye girmeli.",
            "Olay tarihi, yer bilgisi, ilgili birim kaydı, varsa önceki başvurular, işlem durumu, fotoğraf/video ve resmi belge hazırlanmalı.",
            "Sakin, empatik, kanıta dayalı ve çözüm odaklı dil kullanılmalı."
        )

    if risk_score >= 4:
        return make_plan(
            "Orta",
            "Konu küçümsenmemeli, alaycı veya sert cevap verilmemeli. Yorumlara tek tek duygusal karşılık verilmemeli.",
            "İlk 30 dakikada paylaşım ve yorum hızı izlenmeli, iddianın doğru olup olmadığı kontrol edilmeli.",
            "İlk 2 saatte ilgili birimden bilgi alınmalı. Gerekirse kısa bir bilgilendirme notu hazırlanmalı.",
            "İlk 24 saatte konu büyürse kurumsal açıklama yapılmalı; büyümezse hizmet/hikaye diliyle olumlu gündem desteklenmeli.",
            "Şimdilik Sayın Başkan’ın doğrudan konuşmasına gerek yok. Kurumsal hesap veya ilgili birim yeterli olabilir.",
            "Konuya ait temel bilgi, ilgili müdürlük görüşü, varsa işlem kaydı ve kısa açıklama notu hazırlanmalı.",
            "Sakin, ölçülü, açıklayıcı ve tartışmayı büyütmeyen dil kullanılmalı."
        )

    return make_plan(
        "Düşük",
        "Gereksiz açıklama yaparak konu büyütülmemeli.",
        "İlk 30 dakikada sadece takip edilmeli.",
        "İlk 2 saatte yorumlarda ani artış olup olmadığı kontrol edilmeli.",
        "İlk 24 saatte olumlu gündem ve hizmet iletişimi desteklenmeli.",
        "Açıklama gerekmez. Sosyal medya ekibi takipte kalmalı.",
        "Şimdilik özel belge gerekmez; konu büyürse ilgili bilgi toplanmalı.",
        "Doğal, sakin ve pozitif iletişim korunmalı."
    )

def bar(label, value, color_class):
    value = max(0, min(100, float(value or 0)))
    return f"""
    <div class="bar-row">
        <div class="bar-label"><span>{esc(label)}</span><b>%{value:.1f}</b></div>
        <div class="bar"><div class="{color_class}" style="width:{value:.1f}%"></div></div>
    </div>
    """

def section_label(title, color, bg):
    return f"""
<div style="border:2px solid {color}; border-left:8px solid {color}; background:{bg}; border-radius:18px; padding:14px 18px; margin:26px 0 14px 0; font-weight:800; font-size:24px; color:{color};">
{esc(title)}
</div>
"""

def report_main_menu():
    return """
<div style="border:2px solid #0f172a; border-left:8px solid #0f172a; background:#f8fafc; border-radius:18px; padding:16px; margin:22px 0;">
  <div style="font-size:24px; font-weight:800; color:#0f172a; margin-bottom:10px;">📌 Rapor Ana Menüsü / Hızlı Erişim</div>
  <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:10px;">
    <a href="#acil-durum" style="padding:12px; border-radius:14px; background:#fef2f2; color:#b91c1c; text-decoration:none; font-weight:800; border:1px solid #fecaca;">🚨 Acil Durum</a>
    <a href="#haberler" style="padding:12px; border-radius:14px; background:#eff6ff; color:#2563eb; text-decoration:none; font-weight:800; border:1px solid #bfdbfe;">📰 Haberler</a>
    <a href="#onemli-basliklar" style="padding:12px; border-radius:14px; background:#eff6ff; color:#2563eb; text-decoration:none; font-weight:800; border:1px solid #bfdbfe;">⭐ Önemli Başlıklar</a>
    <a href="#olumlu-haberler" style="padding:12px; border-radius:14px; background:#f0fdf4; color:#15803d; text-decoration:none; font-weight:800; border:1px solid #bbf7d0;">✅ Olumlu Haberler</a>
    <a href="#riskli-haberler" style="padding:12px; border-radius:14px; background:#fef2f2; color:#dc2626; text-decoration:none; font-weight:800; border:1px solid #fecaca;">⚠️ Riskli Haberler</a>
    <a href="#sosyal-medya" style="padding:12px; border-radius:14px; background:#f5f3ff; color:#7c3aed; text-decoration:none; font-weight:800; border:1px solid #ddd6fe;">📱 Sosyal Medya</a>
    <a href="#youtube-sosyal" style="padding:12px; border-radius:14px; background:#fff7ed; color:#dc2626; text-decoration:none; font-weight:800; border:1px solid #fed7aa;">📺 YouTube Nabzı</a>
    <a href="#kriz-aksiyon" style="padding:12px; border-radius:14px; background:#fef2f2; color:#b91c1c; text-decoration:none; font-weight:800; border:1px solid #fecaca;">🧯 Kriz Aksiyon</a>
    <a href="#baskan-x" style="padding:12px; border-radius:14px; background:#ecfdf5; color:#059669; text-decoration:none; font-weight:800; border:1px solid #bbf7d0;">👤 Başkan X</a>
    <a href="#sosyal-kayitlar" style="padding:12px; border-radius:14px; background:#fffbeb; color:#d97706; text-decoration:none; font-weight:800; border:1px solid #fde68a;">🗂 Sosyal Kayıtlar</a>
    <a href="#strateji" style="padding:12px; border-radius:14px; background:#f8fafc; color:#334155; text-decoration:none; font-weight:800; border:1px solid #cbd5e1;">📊 Strateji</a>
    <a href="crisis_panel.html" style="padding:12px; border-radius:14px; background:#fee2e2; color:#991b1b; text-decoration:none; font-weight:800; border:1px solid #fecaca;">🚨 Kriz Paneli</a>
    <a href="team_report.html" style="padding:12px; border-radius:14px; background:#f1f5f9; color:#0f172a; text-decoration:none; font-weight:800; border:1px solid #cbd5e1;">👥 Ekip Raporu</a>
  </div>
</div>
"""

def news_card(item):
    return f"""
<div class="item" style="border-left:6px solid #2563eb; background:#eff6ff;">
<h3>{esc(item["title"])}</h3>
<p><b>Anahtar kelime:</b> {esc(item["keyword"])}</p>
<p>
<span class="pill">{esc(item["tone"])}</span>
<span class="pill">Risk: {item["risk"]}/10</span>
<span class="pill">Fırsat: {item["opportunity"]}/10</span>
</p>
<p>{esc(item.get("summary", ""))[:240]}</p>
<a href="{esc(item.get("link", ""))}" target="_blank" style="display:inline-block; margin-top:8px; padding:9px 12px; border-radius:10px; background:#2563eb; color:white; text-decoration:none; font-weight:700;">Haberi Aç</a>
</div>
"""


def social_link(link):
    link = str(link or "").strip()
    if not link:
        return ""
    if "example.com" in link:
        return '<p class="muted"><b>Link:</b> Manuel sosyal medya verisi</p>'
    return f'<p><a href="{esc(link)}" target="_blank">Gönderiyi aç</a></p>'


def social_card(title, item):
    if not item:
        return f'<div class="item"><h3>{esc(title)}</h3><p class="muted">Henüz sosyal medya verisi girilmedi.</p></div>'
    return f"""
    <div class="item" style="border-left:6px solid #7c3aed; background:#f5f3ff;">
        <h3>{esc(title)}</h3>
        <p><b>{esc(item.get("topic"))}</b></p>
        <p class="muted">{esc(item.get("platform"))} • {esc(item.get("date"))}</p>
        <p>Beğeni: <b>{int(item["likes"])}</b> • Yorum: <b>{int(item["comments"])}</b> • Paylaşım: <b>{int(item["shares"])}</b> • Görüntülenme: <b>{int(item["views"])}</b></p>
        <p>Beğenme oranı: <b>%{item["like_rate"]:.2f}</b> • Etkileşim oranı: <b>%{item["engagement_rate"]:.2f}</b></p>
        <p>Risk: <b>{item["risk_score"]}/10</b> • Fırsat: <b>{item["opportunity_score"]}/10</b></p>
        <p>{esc(item.get("notes"))}</p>
        <p class="risk-note">{esc(item.get("risk_note"))}</p>
        {social_link(item.get("link"))}
    </div>
    """

def read_president_x_posts():
    if not PRESIDENT_X_CSV.exists():
        return []

    rows = []

    def to_int_local(value, default=0):
        try:
            return int(float(str(value or "0").replace(",", ".").strip()))
        except:
            return default

    try:
        with PRESIDENT_X_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = {
                    "date": str(row.get("date", "") or "").strip(),
                    "platform": str(row.get("platform", "") or "").strip(),
                    "account": str(row.get("account", "") or "").strip(),
                    "content": str(row.get("content", "") or "").strip(),
                    "topic": str(row.get("topic", "") or "").strip(),
                    "likes": to_int_local(row.get("likes", 0)),
                    "replies": to_int_local(row.get("replies", 0)),
                    "reposts": to_int_local(row.get("reposts", 0)),
                    "quotes": to_int_local(row.get("quotes", 0)),
                    "engagement": to_int_local(row.get("engagement", 0)),
                    "url": str(row.get("url", "") or "").strip(),
                    "source_type": str(row.get("source_type", "") or "").strip(),
                }

                if any(str(v).strip() for v in item.values()):
                    rows.append(item)

    except Exception as e:
        print(f"Başkan X gönderileri okunamadı: {e}")
        return []

    return sorted(rows, key=lambda x: x.get("engagement", 0), reverse=True)


def president_x_card(title, item):
    if not item:
        return f"""
<div class="item" style="border-left:6px solid #059669; background:#ecfdf5;">
<h3>{esc(title)}</h3>
<p>Henüz Başkan X hesabı verisi yok.</p>
</div>
"""

    content = esc(item.get("content", ""))[:260]

    return f"""
<div class="item" style="border-left:6px solid #059669; background:#ecfdf5;">
<h3>{esc(title)}</h3>
<p><b>Tarih:</b> {esc(item.get("date", ""))}</p>
<p><b>Konu:</b> {esc(item.get("topic", ""))}</p>
<p>{content}</p>
<p>
<b>Beğeni:</b> {item.get("likes", 0)} •
<b>Yanıt:</b> {item.get("replies", 0)} •
<b>Repost:</b> {item.get("reposts", 0)} •
<b>Quote:</b> {item.get("quotes", 0)} •
<b>Toplam etkileşim:</b> {item.get("engagement", 0)}
</p>
{social_link(item.get("url", ""))}
</div>
"""

def read_president_x_replies():
    if not PRESIDENT_X_REPLIES_CSV.exists():
        return []

    rows = []

    def to_float_local(value, default=0):
        try:
            return float(str(value or "0").replace(",", ".").strip())
        except:
            return default

    try:
        with PRESIDENT_X_REPLIES_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = {
                    "post_id": str(row.get("post_id", "") or "").strip(),
                    "post_date": str(row.get("post_date", "") or "").strip(),
                    "post_topic": str(row.get("post_topic", "") or "").strip(),
                    "reply_date": str(row.get("reply_date", "") or "").strip(),
                    "reply_account": str(row.get("reply_account", "") or "").strip(),
                    "reply_text": str(row.get("reply_text", "") or "").strip(),
                    "sentiment": str(row.get("sentiment", "") or "").strip(),
                    "risk_score": to_float_local(row.get("risk_score", 0)),
                    "opportunity_score": to_float_local(row.get("opportunity_score", 0)),
                    "reply_url": str(row.get("reply_url", "") or "").strip(),
                    "source_type": str(row.get("source_type", "") or "").strip(),
                }

                if item["reply_text"]:
                    rows.append(item)

    except Exception as e:
        print(f"Başkan X yanıtları okunamadı: {e}")
        return []

    return rows


def president_x_replies_summary(replies):
    total = len(replies)
    risky = [x for x in replies if x.get("risk_score", 0) >= 6 or x.get("sentiment") == "negative"]
    positive = [x for x in replies if x.get("sentiment") == "positive"]
    neutral = [x for x in replies if x.get("sentiment") == "neutral"]

    if total == 0:
        mood = "Veri yok"
        comment = "Son gönderiler için okunabilir yanıt verisi bulunamadı."
        action = "Yorum takibi devam etmeli."
    elif len(risky) >= 3:
        mood = "Riskli"
        comment = "Yanıtlarda dikkat gerektiren bir yoğunluk var. Olumsuz ton ve tekrar eden şikayetler kontrol edilmeli."
        action = "Basın ekibi riskli yanıtları incelemeli; gerekirse kısa bilgi notu hazırlanmalı."
    elif len(risky) >= 1:
        mood = "Kontrollü takip"
        comment = "Az sayıda riskli yanıt var. Şu aşamada büyüme eğilimi izlenmeli."
        action = "Yorum hızı ve aynı şikayetin tekrar edip etmediği takip edilmeli."
    elif len(positive) > len(neutral):
        mood = "Olumlu"
        comment = "Yanıt tonu genel olarak olumlu görünüyor."
        action = "Olumlu etkileşim alan dil ve konu başlıkları sonraki paylaşımlarda güçlendirilebilir."
    else:
        mood = "Nötr"
        comment = "Yanıtlar genel olarak nötr seviyede görünüyor."
        action = "Takip sürmeli; günlük raporda detay gösterilmesine gerek yok."

    top_risky = sorted(risky, key=lambda x: x.get("risk_score", 0), reverse=True)[:1]
    top_text = top_risky[0].get("reply_text", "")[:180] if top_risky else ""

    return {
        "total": total,
        "risky_count": len(risky),
        "positive_count": len(positive),
        "neutral_count": len(neutral),
        "mood": mood,
        "comment": comment,
        "action": action,
        "top_risky_text": top_text,
    }


def president_x_replies_card(summary):
    risky_text = summary.get("top_risky_text", "")

    risky_html = ""
    if risky_text:
        risky_html = f"""
<p><b>Dikkat çeken riskli yanıt:</b> {esc(risky_text)}</p>
"""

    return f"""
<div class="item" style="border-left:6px solid #059669; background:#ecfdf5;">
<h3>Başkan X Yanıt Özeti</h3>
<p><b>Toplam yanıt:</b> {summary.get("total", 0)} • <b>Riskli yanıt:</b> {summary.get("risky_count", 0)} • <b>Genel ton:</b> {esc(summary.get("mood", ""))}</p>
<p><b>Yorum:</b> {esc(summary.get("comment", ""))}</p>
<p><b>İlk aksiyon:</b> {esc(summary.get("action", ""))}</p>
{risky_html}
</div>
"""

def read_team_actions(limit=20):
    if not TEAM_ACTIONS_CSV.exists():
        return []

    rows = []

    try:
        with TEAM_ACTIONS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = {
                    "date": str(row.get("date", "") or "").strip(),
                    "time": str(row.get("time", "") or "").strip(),
                    "alert_topic": str(row.get("alert_topic", "") or "").strip(),
                    "action_taken": str(row.get("action_taken", "") or "").strip(),
                    "result": str(row.get("result", "") or "").strip(),
                    "responsible": str(row.get("responsible", "") or "").strip(),
                    "next_step": str(row.get("next_step", "") or "").strip(),
                    "status": str(row.get("status", "") or "").strip(),
                    "note": str(row.get("note", "") or "").strip(),
                }

                if any(item.values()):
                    rows.append(item)

    except Exception as e:
        print(f"Ekip aksiyon kayıtları okunamadı: {e}")
        return []

    return rows[-limit:]

def read_alert_log(limit=20):
    if not ALERT_LOG_CSV.exists():
        return []

    rows = []

    try:
        with ALERT_LOG_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = {
                    "date": str(row.get("date", "") or "").strip(),
                    "time": str(row.get("time", "") or "").strip(),
                    "risk_level": str(row.get("risk_level", "") or "").strip(),
                    "decision": str(row.get("decision", "") or "").strip(),
                    "crisis_title": str(row.get("crisis_title", "") or "").strip(),
                    "status": str(row.get("status", "") or "").strip(),
                    "email_to": str(row.get("email_to", "") or "").strip(),
                    "email_sent": str(row.get("email_sent", "") or "").strip(),
                    "note": str(row.get("note", "") or "").strip(),
                    "reason": str(row.get("reason", "") or "").strip(),
                    "first_action": str(row.get("first_action", "") or "").strip(),
                    "crisis_panel_url": str(row.get("crisis_panel_url", "") or "").strip(),
                    "daily_report_url": str(row.get("daily_report_url", "") or "").strip(),
                }

                if any(item.values()):
                    rows.append(item)

    except Exception as e:
        print(f"Bildirim geçmişi okunamadı: {e}")
        return []

    return rows[-limit:]

def build_system_learning_note(news, social, alert_logs, team_actions, president_replies, crisis_plan, early_warning):
    def safe_float(value, default=0):
        try:
            return float(str(value or "0").replace(",", ".").strip())
        except:
            return default

    risky_social_count = len([x for x in social if safe_float(x.get("risk_score", 0)) >= 6])
    high_risk_social_count = len([x for x in social if safe_float(x.get("risk_score", 0)) >= 8])
    risky_reply_count = len([x for x in president_replies if safe_float(x.get("risk_score", 0)) >= 6])

    top_social = sorted(
        social,
        key=lambda x: safe_float(x.get("risk_score", 0)),
        reverse=True
    )

    top_topic = ""
    if top_social:
        top_topic = top_social[0].get("topic", "") or top_social[0].get("content", "")[:60]

    risk_level = crisis_plan.get("level", "")
    decision = early_warning.get("decision", "")

    if high_risk_social_count >= 1 or "ACİL ALARM" in decision or "ACIL ALARM" in decision:
        main_risk = "Bugün sistem yüksek riskli bir başlık yakaladı. Kriz paneli ve ekip aksiyonları yakından takip edilmeli."
    elif risky_social_count >= 1 or risky_reply_count >= 1:
        main_risk = "Bugün takip gerektiren orta seviyede sosyal medya riski var. Yayılım hızı ve tekrar eden konu kontrol edilmeli."
    else:
        main_risk = "Bugün belirgin yüksek riskli sosyal medya hareketi görünmüyor. Normal takip yeterli."

    if top_topic:
        repeated_topic = f"Öne çıkan takip konusu: {top_topic}"
    else:
        repeated_topic = "Bugün öne çıkan tekrar eden konu netleşmedi."

    if risky_social_count >= 5:
        filter_note = "Riskli kayıt sayısı yüksek. X filtreleri ve uygunluk skoru tekrar kontrol edilmeli."
    elif risky_social_count == 0:
        filter_note = "Riskli kayıt sayısı düşük. Filtreler şimdilik dengeli görünüyor."
    else:
        filter_note = "Filtreler çalışıyor; ancak alakasız kayıt olup olmadığı ekip tarafından gözle kontrol edilmeli."

    if team_actions:
        action_note = "Ekip aksiyon kayıtları girilmeye başlanmış. Bildirimden sonra alınan aksiyonların düzenli yazılması önemli."
    else:
        action_note = "Henüz ekip aksiyon kaydı yok. İlk fırsatta ekip aksiyon giriş alışkanlığı oluşturulmalı."

    if alert_logs:
        archive_note = "Bildirim geçmişi oluşuyor. Bu kayıtlar ileride arşiv ve geçmiş kriz analizi için kullanılacak."
    else:
        archive_note = "Bildirim geçmişi henüz oluşmadı. İlk alarm sonrası kayıt kontrol edilmeli."

    next_improvement = "Ekip raporunda aksiyonların durumuna göre 'Beklemede / Tamamlandı / Başkan bilgilendirilmeli' ayrımı güçlendirilebilir."

    return {
        "main_risk": main_risk,
        "repeated_topic": repeated_topic,
        "filter_note": filter_note,
        "action_note": action_note,
        "archive_note": archive_note,
        "next_improvement": next_improvement,
        "risk_level": risk_level,
    }

def team_action_status_badge(status):
    raw_status = str(status or "").strip()
    status_norm = normalize_text(raw_status)

    if not raw_status:
        label = "Durum yok"
        color = "#64748b"
        bg = "#f8fafc"
    elif "baskan" in status_norm and "bilgilendir" in status_norm:
        label = raw_status
        color = "#b91c1c"
        bg = "#fef2f2"
    elif "kriz" in status_norm or "panele" in status_norm:
        label = raw_status
        color = "#b91c1c"
        bg = "#fef2f2"
    elif "tamam" in status_norm or "kapandi" in status_norm:
        label = raw_status
        color = "#15803d"
        bg = "#f0fdf4"
    elif "devam" in status_norm or "mudahale" in status_norm:
        label = raw_status
        color = "#d97706"
        bg = "#fffbeb"
    elif "bekle" in status_norm or "takip" in status_norm:
        label = raw_status
        color = "#2563eb"
        bg = "#eff6ff"
    else:
        label = raw_status
        color = "#475569"
        bg = "#f8fafc"

    return f"""
<span style="display:inline-block; padding:6px 10px; border-radius:999px; border:1px solid {color}; background:{bg}; color:{color}; font-weight:700; font-size:13px;">
{esc(label)}
</span>
"""

def social_account_meta_html(item):
    account_type = item.get("account_type", "") or "bilinmeyen"
    account_side = item.get("account_side", "") or "bilinmeyen"
    influence = item.get("account_influence_level", "") or "dusuk"
    watch = item.get("account_watch_level", "") or "normal"
    adjusted_risk = item.get("account_adjusted_risk_score", item.get("risk_score", 0))
    bonus = item.get("account_effect_bonus", 0)
    reason = item.get("account_risk_reason", "")

    return f"""
<div class="small" style="margin-top:6px;">
<b>Hesap tipi:</b> {esc(account_type)} •
<b>Taraf:</b> {esc(account_side)} •
<b>Etki:</b> {esc(influence)} •
<b>Takip:</b> {esc(watch)}
</div>
<div class="small" style="margin-top:4px;">
<b>Hesap etkili risk:</b> {adjusted_risk}/10 •
<b>Etki bonusu:</b> +{bonus} •
<b>Neden:</b> {esc(reason)}
</div>
"""

def x_risk_action_comment(item):
    text = normalize_text(
        f"{item.get('content', '')} {item.get('text', '')} {item.get('topic', '')} {item.get('action_note', '')}"
    )

    account_type = normalize_text(item.get("account_type", ""))
    account_side = normalize_text(item.get("account_side", ""))
    influence = normalize_text(item.get("account_influence_level", ""))
    adjusted_risk = safe_score_value(
        item.get("account_adjusted_risk_score", item.get("risk_score", 0))
    )

    service_terms = [
        "asfalt", "yol", "temizlik", "cop", "çöp", "park", "ulasim", "ulaşim",
        "ulaşım", "mahalle", "sikayet", "şikayet", "magdur", "mağdur"
    ]

    legal_crisis_terms = [
        "teleferik", "facia", "kaza", "olum", "ölüm", "yarali",
        "yaralı", "sorusturma", "soruşturma", "ihmal", "mahkeme",
        "savci", "savcı", "iddianame", "yargi", "yargı", "tutuklu",
        "tutuklama", "ceza", "hukuk"
    ]

    legal_dava_context_terms = [
        "teleferik", "mahkeme", "savci", "savcı", "iddianame",
        "yargi", "yargı", "tutuklu", "tutuklama", "ceza",
        "hukuk", "sorusturma", "soruşturma", "ihmal", "kaza",
        "olum", "ölüm", "yarali", "yaralı"
    ]

    political_dava_phrases = [
        "dava arkadas", "dava arkadaş", "dava adami", "dava adamı",
        "ulku davasi", "ülkü davası", "davamiz", "davamız",
        "dava buyuk", "dava büyük", "siyasi dava"
    ]

    is_political_dava = any(phrase in text for phrase in political_dava_phrases)
    is_legal_dava = ("dava" in text and any(term in text for term in legal_dava_context_terms))

    if any(term in text for term in legal_crisis_terms) or is_legal_dava:
        return "Kriz/hukuki hassasiyet içeren X kaydı olabilir. Basın ve hukuk birimi birlikte kontrol etmeli; açıklama dili dikkatli kurulmalı."

    if is_political_dava:
        return "Siyasi/ideolojik söylem içeren X kaydı gibi görünüyor. Hukuki kriz gibi değerlendirilmemeli; siyasi görünürlük ve algı açısından takip edilmeli."
    
    if any(term in text for term in service_terms):
        return "Hizmet/şikayet başlığı gibi görünüyor. İlgili birimden saha bilgisi alınmalı; gerekirse kurumsal hesap kısa bilgilendirme yapmalı."

    if "siyasi" in account_type or "rakip" in account_side:
        return "Siyasi çevre kaynaklı görünürlük olabilir. Polemiğe girmeden takip edilmeli; tekrar ederse algı yönetimi notu hazırlanmalı."

    if "yerel_medya" in account_type or "medya" in account_side:
        return "Yerel medya kaynağı üzerinden görünürlük oluşmuş. Ekip yorum tonunu ve haberleşme ihtimalini gözle kontrol etmeli."

    if "alakasiz" in account_type:
        return "Kaynak düşük öncelikli/alakasız görünüyor. Şimdilik sadece filtre kalitesi açısından izlenmeli."

    if adjusted_risk >= 8:
        return "Hesap etkili risk yüksek. Ekip bu kaydı öncelikli kontrol etmeli ve gerekirse aksiyon kaydı açmalı."

    if adjusted_risk >= 6:
        return "Takip gerektiren X kaydı. Yayılım, tekrar eden konu ve hesap etkisi izlenmeli."

    return "Şu aşamada standart takip yeterli. Tekrar ederse yeniden değerlendirilmeli."

def x_service_followup_status(item):
    text = normalize_text(
        f"{item.get('content', '')} {item.get('text', '')} {item.get('topic', '')} {item.get('action_note', '')}"
    )

    account = normalize_text(item.get("account", ""))
    account_type = normalize_text(item.get("account_type", ""))
    account_side = normalize_text(item.get("account_side", ""))

    service_terms = [
        "asfalt", "yol", "kaldirim", "kaldırım", "temizlik", "cop", "çöp",
        "park", "ulasim", "ulaşim", "ulaşım", "mahalle", "sikayet", "şikayet",
        "magdur", "mağdur", "su", "kanalizasyon", "otobus", "otobüs",
        "durak", "cukur", "çukur", "bozuk", "sokak"
    ]

    is_service_issue = any(term in text for term in service_terms)
    
    political_dava_phrases = [
        "dava arkadas",
        "dava arkadaş",
        "dava adami",
        "dava adamı",
        "ulku davasi",
        "ülkü davası",
        "davamiz",
        "davamız",
        "dava buyuk",
        "dava büyük",
        "dava büyüğü",
        "dava buyugu",
        "siyasi dava"
    ]

    is_political_dava = any(phrase in text for phrase in political_dava_phrases)

    if is_political_dava:
        return "Siyasi/ideolojik söylem içeren X kaydı gibi görünüyor. Hukuki kriz veya hizmet şikayeti gibi değerlendirilmemeli; siyasi görünürlük ve algı açısından takip edilmeli."

    legal_crisis_terms = [
        "teleferik", "dava", "mahkeme", "savci", "savcı", "iddianame",
        "yargi", "yargı", "tutuklu", "tutuklama", "ceza", "hukuk",
        "sorusturma", "soruşturma", "ihmal", "kaza", "olum", "ölüm",
        "yarali", "yaralı", "facia"
    ]

    is_legal_crisis = any(term in text for term in legal_crisis_terms)

    if is_legal_crisis:
        return "Hukuki/kriz takip başlığı gibi görünüyor. Kurumsal cevap yerine basın-hukuk koordinasyonu ve kontrollü açıklama dili tercih edilmeli."

    is_corporate_account = (
        "kepezbelediyesi" in account
        or "kurumsal" in account_type
        or "belediye" in account_side
    )

    is_citizen_like = (
        "vatandas" in account_type
        or "vatandaş" in account_type
        or "sikayet" in account_type
        or "şikayet" in account_type
        or "bilinmeyen" in account_type
    )

    if is_service_issue and is_corporate_account:
        return "Kurumsal hesap hizmet/şikayet başlığına cevap veya duyuru üretmiş olabilir. Ekip, bu cevabın konuyu kapatıp kapatmadığını takip etmeli."

    if is_service_issue and is_citizen_like:
        return "Vatandaş/hizmet şikayeti gibi görünüyor. Kurumsal cevap var mı kontrol edilmeli; gerekirse ilgili birimden saha bilgisi alınmalı."

    if is_service_issue and ("yerel_medya" in account_type or "medya" in account_side):
        return "Hizmet konusu yerel medya görünürlüğüne taşınmış olabilir. Ekip, haberleşme ihtimali ve yorum tonunu kontrol etmeli."

    if "siyasi" in account_type or "rakip" in account_side:
        return "Siyasi kaynaklı X görünürlüğü var. Hizmet şikayetiyle birleşirse algı yönetimi açısından ayrıca izlenmeli."

    return "Hizmet şikayeti veya kurumsal cevap gerektiren net bir durum görünmüyor. Standart takip yeterli."

def x_social_summary_html(social, president_replies):
    x_items = []

    for item in social:
        platform_raw = str(item.get("platform", "") or "").lower()

        if "twitter" in platform_raw or platform_raw.strip() == "x" or platform_raw.startswith("x "):
            x_items.append(item)

    risky_x_items = sorted(
        [
            item for item in x_items
            if safe_score_value(item.get("account_adjusted_risk_score", item.get("risk_score", 0))) >= 6
        ],
        key=lambda x: safe_score_value(x.get("account_adjusted_risk_score", x.get("risk_score", 0))),
        reverse=True
    )[:5]

    risky_replies = [
        item for item in president_replies
        if safe_score_value(item.get("risk_score", 0)) >= 6
    ]

    if len(risky_x_items) >= 3 or len(risky_replies) >= 2:
        status_text = "X tarafında ekip kontrolü gerektiren riskli hareket var."
        status_color = "#b91c1c"
        status_bg = "#fef2f2"
    elif len(risky_x_items) >= 1 or len(risky_replies) >= 1:
        status_text = "X tarafında takip gerektiren sınırlı risk var."
        status_color = "#d97706"
        status_bg = "#fffbeb"
    else:
        status_text = "X tarafında şu an belirgin yüksek riskli hareket görünmüyor."
        status_color = "#15803d"
        status_bg = "#f0fdf4"

    rows_html = ""

    for item in risky_x_items:
        adjusted_risk = item.get("account_adjusted_risk_score", item.get("risk_score", 0))
        reason = item.get("account_risk_reason", "")
        action_comment = x_risk_action_comment(item)
        service_followup = x_service_followup_status(item)
        account_type = item.get("account_type", "bilinmeyen")
        account_side = item.get("account_side", "bilinmeyen")
        influence = item.get("account_influence_level", "dusuk")
        watch = item.get("account_watch_level", "normal")

        content = item.get("content", "") or item.get("text", "") or ""
        if len(content) > 180:
            content = content[:180] + "..."

        rows_html += f"""
<tr>
<td>{esc(item.get("date", ""))}</td>
<td>{esc(item.get("account", ""))}</td>
<td>{esc(item.get("topic", ""))}</td>
<td>{item.get("risk_score", 0)}/10</td>
<td>{adjusted_risk}/10</td>
<td>
{esc(content)}
<div class="small" style="margin-top:6px;">
<b>Hesap tipi:</b> {esc(account_type)} •
<b>Taraf:</b> {esc(account_side)} •
<b>Etki:</b> {esc(influence)} •
<b>Takip:</b> {esc(watch)}
</div>
<div class="small" style="margin-top:4px;">
<b>Risk nedeni:</b> {esc(reason)}
</div>
<div class="small" style="margin-top:4px;">
<b>X aksiyon yorumu:</b> {esc(action_comment)}
</div>
<div class="small" style="margin-top:4px;">
<b>Hizmet/cevap takibi:</b> {esc(service_followup)}
</div>
</td>
<td>{social_link(item.get("link", ""))}</td>
</tr>
"""

    if not rows_html:
        rows_html = "<tr><td colspan='7'>Riskli X kaydı bulunamadı.</td></tr>"

    return f"""
<div class="card">
<p>
<b>Toplam X kaydı:</b> {len(x_items)} •
<b>Riskli X kaydı:</b> {len(risky_x_items)} •
<b>Başkan X yanıtı:</b> {len(president_replies)} •
<b>Riskli Başkan X yanıtı:</b> {len(risky_replies)}
</p>

<p>
<span style="display:inline-block; padding:6px 10px; border-radius:999px; border:1px solid {status_color}; background:{status_bg}; color:{status_color}; font-weight:700;">
{esc(status_text)}
</span>
</p>

<table>
<tr>
<th>Tarih</th>
<th>Hesap</th>
<th>Konu</th>
<th>Risk</th>
<th>Hesap Etkili Risk</th>
<th>İçerik / Hesap Yorumu</th>
<th>Link</th>
</tr>
{rows_html}
</table>
</div>
"""

def president_x_replies_detail_html(replies):
    if not replies:
        return """
<div class="card">
<p class="small">Başkan X yanıtlarında okunabilir veri bulunamadı.</p>
</div>
"""

    risky_replies = sorted(
        [
            item for item in replies
            if safe_score_value(item.get("risk_score", 0)) >= 6
            or normalize_text(item.get("sentiment", "")) == "negative"
        ],
        key=lambda x: safe_score_value(x.get("risk_score", 0)),
        reverse=True
    )

    if len(risky_replies) >= 3:
        status_text = "Başkan X yanıtlarında dikkat gerektiren risk yoğunluğu var."
        status_color = "#b91c1c"
        status_bg = "#fef2f2"
        action_text = "Basın ekibi riskli yanıtları tek tek incelemeli; tekrar eden şikayet varsa kısa bilgi notu hazırlanmalı."
    elif len(risky_replies) >= 1:
        status_text = "Başkan X yanıtlarında sınırlı riskli yorum var."
        status_color = "#d97706"
        status_bg = "#fffbeb"
        action_text = "Yorumların yayılımı ve aynı konunun tekrar edip etmediği takip edilmeli."
    else:
        status_text = "Başkan X yanıtlarında belirgin yüksek risk görünmüyor."
        status_color = "#15803d"
        status_bg = "#f0fdf4"
        action_text = "Takip sürmeli; günlük detay müdahalesi gerekmiyor."

    rows_html = ""

    for item in risky_replies[:5]:
        reply_text = item.get("reply_text", "")
        if len(reply_text) > 220:
            reply_text = reply_text[:220] + "..."

        rows_html += f"""
<tr>
<td>{esc(item.get("reply_date", ""))}</td>
<td>{esc(item.get("reply_account", ""))}</td>
<td>{item.get("risk_score", 0)}/10</td>
<td>{esc(reply_text)}</td>
<td>{social_link(item.get("reply_url", ""))}</td>
</tr>
"""

    if not rows_html:
        rows_html = "<tr><td colspan='5'>Riskli Başkan X yanıtı bulunamadı.</td></tr>"

    return f"""
<div class="card">
<p>
<b>Toplam Başkan X yanıtı:</b> {len(replies)} •
<b>Riskli yanıt:</b> {len(risky_replies)}
</p>

<p>
<span style="display:inline-block; padding:6px 10px; border-radius:999px; border:1px solid {status_color}; background:{status_bg}; color:{status_color}; font-weight:700;">
{esc(status_text)}
</span>
</p>

<p><b>İlk aksiyon:</b> {esc(action_text)}</p>

<table>
<tr>
<th>Tarih</th>
<th>Hesap</th>
<th>Risk</th>
<th>Yanıt</th>
<th>Link</th>
</tr>
{rows_html}
</table>
</div>
"""

def unmapped_x_accounts_html(social):
    accounts_map = read_accounts_map()
    found = {}

    for item in social:
        platform = str(item.get("platform", "") or "").strip()
        platform_norm = normalize_text(platform)

        if "twitter" not in platform_norm and platform_norm != "x" and not platform_norm.startswith("x "):
            continue

        account = str(item.get("account", "") or "").strip()
        if not account:
            continue

        acc_info = account_map_info(platform, account, accounts_map)

        if normalize_text(acc_info.get("type", "")) != "bilinmeyen":
            continue

        key = normalize_text(account)

        if key not in found:
            found[key] = {
                "account": account,
                "count": 0,
                "max_risk": 0,
                "sample_topic": "",
                "sample_content": "",
                "sample_link": "",
            }

        found[key]["count"] += 1

        risk_value = safe_score_value(
            item.get("account_adjusted_risk_score", item.get("risk_score", 0))
        )

        if risk_value > found[key]["max_risk"]:
            found[key]["max_risk"] = risk_value
            found[key]["sample_topic"] = item.get("topic", "")
            found[key]["sample_content"] = item.get("content", "") or item.get("text", "")
            found[key]["sample_link"] = item.get("link", "")

    items = sorted(found.values(), key=lambda x: (x["max_risk"], x["count"]), reverse=True)[:10]

    if not items:
        return """
<div class="card">
<p class="small">Sınıflandırılacak yeni X hesabı bulunamadı. Mevcut hesap haritası bu kayıtlar için yeterli görünüyor.</p>
</div>
"""

    rows_html = ""

    for item in items:
        content = item.get("sample_content", "")
        if len(content) > 180:
            content = content[:180] + "..."

        rows_html += f"""
<tr>
<td>{esc(item.get("account", ""))}</td>
<td>{item.get("count", 0)}</td>
<td>{item.get("max_risk", 0)}/10</td>
<td>{esc(item.get("sample_topic", ""))}</td>
<td>{esc(content)}</td>
<td>{social_link(item.get("sample_link", ""))}</td>
</tr>
"""

    return f"""
<div class="card">
<p class="small">
Bu bölüm, X tarafında görünen ama hesap haritasında henüz sınıflandırılmamış hesapları gösterir. 
Ekip bu hesapları kontrol edip <b>accounts_map.csv</b> dosyasına ekleyebilir.
</p>

<table>
<tr>
<th>Hesap</th>
<th>Kayıt</th>
<th>En yüksek risk</th>
<th>Örnek konu</th>
<th>Örnek içerik</th>
<th>Link</th>
</tr>
{rows_html}
</table>

<p class="small">
Örnek ekleme formatı: <b>X,@hesapadi,yerel_medya,medya,orta,orta,Not</b>
</p>
</div>
"""

def clean_topic_title(raw_topic):
    text = normalize_text(raw_topic)

    if not text:
        return "Genel"

    # Alt çizgi ve tireleri boşluk yap
    text = text.replace("_", " ").replace("-", " ")

    words = text.split()

    cleaned_words = []
    for w in words:
        if len(w) > 2:
            cleaned_words.append(w)

    if not cleaned_words:
        return "Genel"

    cleaned = " ".join(cleaned_words[:5])  # max 5 kelime

    # Türkçe karakter düzeltme
    replacements = {
        "ogrenci": "Öğrenci",
        "kent": "Kent",
        "lokanta": "Lokanta",
        "ulasim": "Ulaşım",
        "erisebilir": "Erişilebilir",
        "guvenli": "Güvenli",
    }

    for k, v in replacements.items():
        cleaned = cleaned.replace(k, v)

    # Baş harfleri büyüt
    cleaned = " ".join([w.capitalize() for w in cleaned.split()])

    return cleaned

def president_x_reply_topic_summary_html(replies):
    if not replies:
        return """
<div class="card">
<p class="small">Başkan X yanıtlarında konu analizi yapılacak veri bulunamadı.</p>
</div>
"""

    topic_map = {}

    for item in replies:
        text = str(item.get("reply_text", "") or "")
        post_topic = str(item.get("post_topic", "") or "")
        combined = f"{post_topic} {text}"

        topic = post_topic or topic_key(combined)
        topic = clean_topic_title(topic)
        if not topic:
            topic = "genel"

        if topic not in topic_map:
            topic_map[topic] = {
                "topic": topic,
                "count": 0,
                "risk_count": 0,
                "max_risk": 0,
                "sample_text": "",
                "sample_account": "",
                "sample_link": "",
            }

        risk_value = safe_score_value(item.get("risk_score", 0))
        sentiment = normalize_text(item.get("sentiment", ""))

        topic_map[topic]["count"] += 1

        if risk_value >= 6 or sentiment == "negative":
            topic_map[topic]["risk_count"] += 1

        if risk_value > topic_map[topic]["max_risk"]:
            topic_map[topic]["max_risk"] = risk_value
            topic_map[topic]["sample_text"] = text
            topic_map[topic]["sample_account"] = item.get("reply_account", "")
            topic_map[topic]["sample_link"] = item.get("reply_url", "")

    topics = sorted(
        topic_map.values(),
        key=lambda x: (x["risk_count"], x["count"], x["max_risk"]),
        reverse=True
    )[:6]

    repeated_topics = [x for x in topics if x["count"] >= 2]
    risky_topics = [x for x in topics if x["risk_count"] >= 1]

    if risky_topics:
        status_text = "Başkan X yanıtlarında risk içeren konu başlıkları var. Ekip yorumları gözle kontrol etmeli."
        status_color = "#d97706"
        status_bg = "#fffbeb"
        action_text = "Riskli başlıkların yayılıp yayılmadığı ve aynı konuda yeni yanıt gelip gelmediği takip edilmeli."
    elif repeated_topics:
        status_text = "Başkan X yanıtlarında tekrar eden konu var. Şimdilik risk düşük ama izlenmeli."
        status_color = "#2563eb"
        status_bg = "#eff6ff"
        action_text = "Tekrar eden konu başlıkları haftalık raporda ayrıca değerlendirilmeli."
    else:
        status_text = "Başkan X yanıtlarında belirgin tekrar eden veya riskli konu görünmüyor."
        status_color = "#15803d"
        status_bg = "#f0fdf4"
        action_text = "Standart takip yeterli."

    rows_html = ""

    for item in topics:
        sample_text = item.get("sample_text", "")
        if len(sample_text) > 180:
            sample_text = sample_text[:180] + "..."

        rows_html += f"""
<tr>
<td>{esc(item.get("topic", ""))}</td>
<td>{item.get("count", 0)}</td>
<td>{item.get("risk_count", 0)}</td>
<td>{item.get("max_risk", 0)}/10</td>
<td>{esc(item.get("sample_account", ""))}</td>
<td>{esc(sample_text)}</td>
<td>{social_link(item.get("sample_link", ""))}</td>
</tr>
"""

    if not rows_html:
        rows_html = "<tr><td colspan='7'>Konu özeti üretilemedi.</td></tr>"

    return f"""
<div class="card">
<p>
<span style="display:inline-block; padding:6px 10px; border-radius:999px; border:1px solid {status_color}; background:{status_bg}; color:{status_color}; font-weight:700;">
{esc(status_text)}
</span>
</p>

<p><b>İlk aksiyon:</b> {esc(action_text)}</p>

<table>
<tr>
<th>Konu</th>
<th>Yanıt Sayısı</th>
<th>Riskli Yanıt</th>
<th>En Yüksek Risk</th>
<th>Örnek Hesap</th>
<th>Örnek Yanıt</th>
<th>Link</th>
</tr>
{rows_html}
</table>
</div>
"""

def build_team_report(news, social, early_warning, crisis_plan, crisis_status, report_time):
    now_tr = dt.datetime.utcnow() + dt.timedelta(hours=3)
    today = now_tr.date().isoformat()

    def safe_float(value, default=0):
        try:
            return float(str(value or "0").replace(",", ".").strip())
        except:
            return default

    alert_logs = read_alert_log(20)
    team_actions = read_team_actions(20)
    crisis_log = read_crisis_log()
    president_replies = read_president_x_replies()
    accounts_map = read_accounts_map()
    learning_note = build_system_learning_note(
        news,
        social,
        alert_logs,
        team_actions,
        president_replies,
        crisis_plan,
        early_warning,
    )
    
    youtube_summary = read_youtube_summary()
    x_summary_html = x_social_summary_html(social, president_replies)
    president_replies_detail = president_x_replies_detail_html(president_replies)
    president_reply_topics = president_x_reply_topic_summary_html(president_replies)
    unmapped_x_accounts = unmapped_x_accounts_html(social)
    
    risky_social = sorted(
        social,
        key=lambda x: safe_float(x.get("risk_score", 0)),
        reverse=True
    )[:10]

    risky_replies = sorted(
        [x for x in president_replies if safe_float(x.get("risk_score", 0)) >= 6],
        key=lambda x: safe_float(x.get("risk_score", 0)),
        reverse=True
    )[:10]

    alert_rows = ""
    for item in alert_logs:
        alert_rows += f"""
<tr>
<td>{esc(item.get("date", ""))}</td>
<td>{esc(item.get("time", ""))}</td>
<td>{esc(item.get("risk_level", ""))}</td>
<td>{esc(item.get("decision", ""))}</td>
<td>{esc(item.get("crisis_title", ""))}</td>
<td>{esc(item.get("email_sent", ""))}</td>
<td>{esc(item.get("note", ""))}</td>
</tr>
"""

    if not alert_rows:
        alert_rows = "<tr><td colspan='7'>Henüz bildirim geçmişi kaydı yok.</td></tr>"

    team_action_rows = ""
    for item in team_actions:
        team_action_rows += f"""
<tr>
<td>{esc(item.get("date", ""))}</td>
<td>{esc(item.get("time", ""))}</td>
<td>{esc(item.get("alert_topic", ""))}</td>
<td>{esc(item.get("action_taken", ""))}</td>
<td>{esc(item.get("result", ""))}</td>
<td>{esc(item.get("responsible", ""))}</td>
<td>{esc(item.get("next_step", ""))}</td>
<td>{team_action_status_badge(item.get("status", ""))}</td>
</tr>
"""

    if not team_action_rows:
        team_action_rows = "<tr><td colspan='8'>Henüz ekip aksiyon kaydı yok.</td></tr>"

            

        risky_social_rows = ""
        for item in risky_social:
            acc_info = account_map_info(
            item.get("platform", ""),
            item.get("account", ""),
            accounts_map
        )

        account_meta = f"""
<div class="small" style="margin-top:6px;">
<b>Hesap tipi:</b> {esc(acc_info.get("type", ""))} •
<b>Taraf:</b> {esc(acc_info.get("side", ""))} •
<b>Etki:</b> {esc(acc_info.get("influence_level", ""))} •
<b>Takip:</b> {esc(acc_info.get("watch_level", ""))}
</div>
"""

        risky_social_rows += f"""
<tr>
<td>{esc(item.get("date", ""))}</td>
<td>{esc(item.get("platform", ""))}</td>
<td>{esc(item.get("topic", ""))}</td>
<td>{esc(item.get("tone", ""))}</td>
<td>{item.get("risk_score", 0)}/10</td>
<td>{esc(item.get("action_note", ""))}{social_account_meta_html(item)}</td>
<td>{social_link(item.get("link", ""))}</td>
</tr>
"""

    if "risky_social_rows" not in locals():
        risky_social_rows = ""
        
    if not risky_social_rows:
        risky_social_rows = "<tr><td colspan='7'>Riskli sosyal medya kaydı bulunamadı.</td></tr>"
        
    risky_reply_rows = ""
    for item in risky_replies:
        risky_reply_rows += f"""
<tr>
<td>{esc(item.get("reply_date", ""))}</td>
<td>{esc(item.get("reply_account", ""))}</td>
<td>{item.get("risk_score", 0)}/10</td>
<td>{esc(item.get("reply_text", ""))[:220]}</td>
<td>{social_link(item.get("reply_url", ""))}</td>
</tr>
"""

    if not risky_reply_rows:
        risky_reply_rows = "<tr><td colspan='5'>Riskli Başkan X yanıtı bulunamadı.</td></tr>"

    crisis_log_rows = ""
    for item in crisis_log:
        crisis_log_rows += f"""
<tr>
<td>{esc(item.get("time", ""))}</td>
<td>{esc(item.get("event", ""))}</td>
<td>{esc(item.get("action", ""))}</td>
<td>{esc(item.get("result", ""))}</td>
<td>{esc(item.get("responsible", ""))}</td>
<td>{esc(item.get("next_step", ""))}</td>
</tr>
"""

    if not crisis_log_rows:
        crisis_log_rows = "<tr><td colspan='6'>Henüz müdahale kaydı yok.</td></tr>"

    team_doc = f"""
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yerel Lider AI - Ekip Raporu</title>
<style>
body {{
    margin:0;
    background:#f5f5f4;
    color:#1f2937;
    font-family:Arial, sans-serif;
    line-height:1.55;
}}
header {{
    background:#111827;
    color:white;
    padding:28px;
}}
.container {{
    max-width:1120px;
    margin:0 auto;
    padding:22px;
}}
.card {{
    background:white;
    border-radius:18px;
    padding:22px;
    margin:18px 0;
    box-shadow:0 8px 24px rgba(0,0,0,0.06);
    overflow-x:auto;
}}
table {{
    width:100%;
    border-collapse:collapse;
    font-size:14px;
}}
th, td {{
    border-bottom:1px solid #e5e7eb;
    text-align:left;
    padding:10px;
    vertical-align:top;
}}
th {{
    background:#f3f4f6;
}}
.small {{
    color:#6b7280;
    font-size:14px;
}}
</style>
</head>
<body>

<header>
<h1>Yerel Lider AI - Ekip Operasyon Raporu</h1>
<p>Tarih: {today} • Güncelleme saati: {report_time}</p>
</header>

<div class="container">

{section_label("🚨 Güncel Kriz / Alarm Özeti", "#b91c1c", "#fef2f2")}
<div class="card">
<p><b>Risk seviyesi:</b> {esc(crisis_plan.get("level", ""))}</p>
<p><b>Kriz başlığı:</b> {esc(crisis_plan.get("risk_topic", ""))}</p>
<p><b>Karar:</b> {esc(early_warning.get("decision", ""))}</p>
<p><b>Durum:</b> {esc(crisis_status.get("status", ""))}</p>
<p><b>İlk aksiyon:</b> {esc(early_warning.get("first_action", ""))}</p>
</div>

{section_label("🧠 Günlük Sistem Öğrenme Notu", "#4f46e5", "#eef2ff")}
<div class="card">
<p><b>Ana risk değerlendirmesi:</b> {esc(learning_note.get("main_risk", ""))}</p>
<p><b>Tekrarlayan / öne çıkan konu:</b> {esc(learning_note.get("repeated_topic", ""))}</p>
<p><b>Filtre notu:</b> {esc(learning_note.get("filter_note", ""))}</p>
<p><b>Ekip aksiyon notu:</b> {esc(learning_note.get("action_note", ""))}</p>
<p><b>Arşiv notu:</b> {esc(learning_note.get("archive_note", ""))}</p>
<p><b>Bir sonraki küçük gelişim:</b> {esc(learning_note.get("next_improvement", ""))}</p>
</div>

{section_label("📺 YouTube Kanal Takibi", "#dc2626", "#fff7ed")}
<div class="card">
<p class="small">Yerel YouTube kanallarında kontrol edilen videolar ve yerel gündemle alakalı bulunan yorum sayıları.</p>
{youtube_summary_html(youtube_summary)}
</div>

{section_label("🐦 X Sosyal Ağ Özeti", "#111827", "#f8fafc")}
{x_summary_html}

{section_label("💬 Başkan X Yanıt Detayı", "#059669", "#ecfdf5")}
{president_replies_detail}

{section_label("🔁 Başkan X Tekrar Eden Yanıt Konuları", "#2563eb", "#eff6ff")}
{president_reply_topics}

{section_label("🧭 Sınıflandırılacak X Hesapları", "#7c3aed", "#f5f3ff")}
{unmapped_x_accounts}


{section_label("📣 Bildirim Geçmişi / Alarm Kayıtları", "#0ea5e9", "#f0f9ff")}
<div class="card">
<table>
<tr>
<th>Tarih</th>
<th>Saat</th>
<th>Risk</th>
<th>Karar</th>
<th>Kriz Başlığı</th>
<th>Mail</th>
<th>Not</th>
</tr>
{alert_rows}
</table>
</div>

{section_label("✅ Bekleyen / Alınan Ekip Aksiyonları", "#16a34a", "#f0fdf4")}
<div class="card">
<table>
<tr>
<th>Tarih</th>
<th>Saat</th>
<th>Konu</th>
<th>Alınan Aksiyon</th>
<th>Sonuç</th>
<th>Sorumlu</th>
<th>Sıradaki Adım</th>
<th>Durum</th>
</tr>
{team_action_rows}
</table>
</div>

{section_label("📱 En Riskli Sosyal Medya Kayıtları", "#7c3aed", "#f5f3ff")}
<div class="card">
<table>
<tr>
<th>Tarih</th>
<th>Platform</th>
<th>Konu</th>
<th>Ton</th>
<th>Risk</th>
<th>Aksiyon Notu</th>
<th>Link</th>
</tr>
{risky_social_rows}
</table>
</div>

{section_label("👤 Başkan X Riskli Yanıt Takibi", "#059669", "#ecfdf5")}
<div class="card">
<table>
<tr>
<th>Tarih</th>
<th>Hesap</th>
<th>Risk</th>
<th>Yanıt</th>
<th>Link</th>
</tr>
{risky_reply_rows}
</table>
</div>

{section_label("🕒 Müdahale Kayıtları", "#d97706", "#fffbeb")}
<div class="card">
<table>
<tr>
<th>Saat</th>
<th>Olay</th>
<th>Yapılan İşlem</th>
<th>Sonuç</th>
<th>Sorumlu</th>
<th>Sıradaki Adım</th>
</tr>
{crisis_log_rows}
</table>
</div>

</div>
</body>
</html>
"""

    out = REPORTS / "team_report.html"
    out.write_text(team_doc, encoding="utf-8")
    print(f"Ekip raporu hazır: {out}")
def build_report(news, social, undated_news=None):
    undated_news = undated_news or []
    now_tr = dt.datetime.utcnow() + dt.timedelta(hours=3)
    today = now_tr.date().isoformat()
    report_time = now_tr.strftime("%H:%M")
    important, positive_news, risky_news = top_items(news)
    social_sum = social_summary(social)
    youtube_summary = read_youtube_summary()
    crisis_sum = build_auto_crisis_summary(news, social_sum)
    crisis_plan = crisis_action_plan(social_sum)
    crisis_status = read_crisis_status()
    
    active_raw = str(crisis_status.get("active", "")).strip().lower()
    active_label = "Aktif" if active_raw in ["yes", "evet", "true", "1", "aktif"] else "Pasif"
    early_warning = early_warning_decision(crisis_plan, crisis_status, crisis_sum)
    risk_level_raw = normalize_text(str(crisis_plan.get("level", "")))
    risk_alarm_html = ""

    if "yuksek" in risk_level_raw:
        risk_alarm_html = """
    <div class="card danger" style="border:3px solid #dc2626;">
      <h2>🔴 YÜKSEK RİSK ALARMI</h2>
      <p><b>İlk 30 dakika içinde:</b> Basın birimi, hukuk birimi ve ilgili müdürlük aynı bilgi notunda hizalanmalı.</p>
      <p><b>Sayın Başkan için uyarı:</b> Konu doğrulanmadan kişisel, duygusal, öfkeli veya savunmacı açıklama yapılmamalı.</p>
      <p><b>Öncelik:</b> Doğrulama, insani hassasiyet, resmi bilgi, tek merkezden iletişim ve hukuki güvenlik.</p>
    </div>
    """
    elif "orta" in risk_level_raw:
        risk_alarm_html = """
    <div class="card human" style="border:2px solid #f97316;">
      <h2>🟠 ORTA RİSK TAKİBİ</h2>
      <p><b>Durum:</b> Konu izlenmeli; yayılım, yorum tonu ve yerel basına sıçrama ihtimali takip edilmeli.</p>
      <p><b>Öneri:</b> Basın birimi ve ilgili birim hazırda beklemeli. Açıklama gerekip gerekmediği gelişmelere göre değerlendirilmeli.</p>
    </div>
    """
    crisis_log = read_crisis_log()

    crisis_log_html = ""
    for item in crisis_log:
        crisis_log_html += f"""
    <div style="padding:12px; border-radius:12px; background:#ffffff; border:1px solid #e2e8f0; margin-bottom:10px;">
      <div style="font-weight:bold; color:#991b1b;">{esc(item.get("time", ""))} - {esc(item.get("event", ""))}</div>
      <div><b>Yapılan işlem:</b> {esc(item.get("action", ""))}</div>
      <div><b>Sonuç:</b> {esc(item.get("result", ""))}</div>
      <div><b>Sorumlu:</b> {esc(item.get("responsible", ""))}</div>
      <div><b>Sıradaki adım:</b> {esc(item.get("next_step", ""))}</div>
      <div><b>Not:</b> {esc(item.get("note", ""))}</div>
    </div>
    """

    if not crisis_log_html:
        crisis_log_html = "<div class='card'>Henüz yapılan işlem / müdahale kaydı girilmedi.</div>"

    if not crisis_log_html:
        crisis_log_html = "<div class='card'>Henüz kriz zaman çizelgesi girilmedi.</div>"
    
    positive_count = sum(1 for x in news if x["tone"] == "Olumlu")
    neutral_count = sum(1 for x in news if x["tone"] == "Nötr")
    risk_count = sum(1 for x in news if x["tone"] == "Riskli")
    total_news = len(news)

    if risk_count > positive_count:
        general_tone = "Dikkat Gerektiren"
        general_comment = "Riskli başlıklar olumlu başlıklardan fazla. Bugün daha kontrollü ve sakin iletişim önerilir."
    elif positive_count > risk_count:
        general_tone = "Olumlu"
        general_comment = "Olumlu görünürlük riskli başlıklardan güçlü. Bugün hizmet ve insan hikayesi dili büyütülebilir."
    else:
        general_tone = "Nötr"
        general_comment = "Gündem dengeli. Olumlu başlıklar güçlendirilmeli, riskli başlıklar izlenmelidir."

    total_comment_tone = social_sum["total_good"] + social_sum["total_neutral"] + social_sum["total_bad"]
    good_pct = social_sum["total_good"] / total_comment_tone * 100 if total_comment_tone else 0
    neutral_pct = social_sum["total_neutral"] / total_comment_tone * 100 if total_comment_tone else 0
    bad_pct = social_sum["total_bad"] / total_comment_tone * 100 if total_comment_tone else 0

    important_html = "".join(news_card(x) for x in important) or "<p>Öne çıkan haber bulunamadı.</p>"
    positive_html = "".join(news_card(x) for x in positive_news) or "<p>Olumlu haber bulunamadı.</p>"
    risky_html = "".join(news_card(x) for x in risky_news) or "<p>Riskli haber bulunamadı.</p>" 
    undated_html = "".join(news_card(x) for x in unique_by_topic(undated_news, 8)) or """
    <p>Tarihi okunamayan haber bulunamadı.</p>
    """
    social_rows = ""
    for item in social:
        social_rows += f"""
            <tr><td>{esc(item.get("date"))}</td><td>{esc(item.get("platform"))}</td><td>{esc(item.get("topic"))}</td><td>{esc(item.get("tone"))}</td><td>%{item["like_rate"]:.2f}</td><td>{item["risk_score"]}/10</td><td>{item["opportunity_score"]}/10</td><td>{social_link(item.get("link", ""))}</td></tr>
        """
    if not social_rows:
        social_rows = "<tr><td colspan='8'>Henüz manuel sosyal medya verisi girilmedi.</td></tr>"
    president_posts = read_president_x_posts()
    president_top3 = president_posts[:3]

    president_x_html = ""
    for idx, post in enumerate(president_top3, start=1):
        president_x_html += president_x_card(f"{idx}. Öne Çıkan Gönderi", post)

    if not president_x_html:
        president_x_html = "<div class='item'>Henüz Sayın Başkan X hesabından gönderi verisi alınamadı.</div>"
    if risk_count >= 3 or bad_pct >= 35:
        alert_level = "Yüksek dikkat"
        alert_summary = "Bugün riskli haberler veya olumsuz yorum oranı belirgin seviyede. Savunmacı polemik yerine sakin, belgeye dayalı ve hizmet odaklı iletişim tercih edilmelidir."
        strategy_focus = "Riskleri büyütmeden kontrol etmek, olumlu hizmet başlıklarını görünür tutmak ve Sayın Başkanın profilini güven veren bir çizgide korumak."
        daily_language = "Sakin, net, polemikten uzak ve vatandaşın gündelik hayatına dokunan bir dil kullanılmalıdır."
    elif risk_count >= 1 or bad_pct >= 20:
        alert_level = "Kontrollü takip"
        alert_summary = "Bugün risk tamamen yüksek değil ancak takip edilmesi gereken başlıklar var. Olumsuz yorumların büyüyüp büyümediği gün içinde izlenmelidir."
        strategy_focus = "Olumlu gündemi canlı tutarken riskli başlıklara karşı hazırlıklı olmak."
        daily_language = "Hizmet, mahalle teması ve vatandaş memnuniyeti öne çıkarılmalı; tartışmalı başlıklarda ölçülü kalınmalıdır."
    else:
        alert_level = "Normal seyir"
        alert_summary = "Bugün kriz riski düşük görünüyor. Bu tablo, hizmet ve insan hikayesi anlatımı için uygun bir zemin oluşturuyor."
        strategy_focus = "Olumlu görünürlüğü artırmak, sahadan güçlü içerikler üretmek ve başkanın çalışkan/ulaşılabilir profilini güçlendirmek."
        daily_language = "Pozitif, sade, samimi ve mahalleye dokunan bir dil kullanılmalıdır."

    best_news_title = important[0]["title"] if important else "Bugün öne çıkan net haber başlığı yok."
    best_social_topic = social_sum["opportunity"].get("topic", "") if social_sum["opportunity"] else "Henüz öne çıkan sosyal medya fırsatı yok."
    tomorrow_keywords = ", ".join(read_keywords()[:12])
    president_replies = read_president_x_replies()
    president_reply_summary = president_x_replies_summary(president_replies)
    president_reply_html = president_x_replies_card(president_reply_summary)

    html_doc = f"""
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yerel Liderlik AI Günlük Raporu</title>
<style>
:root {{
    --bg:#f4efe7;
    --card:#ffffff;
    --ink:#17212b;
    --muted:#5f6670;
    --line:#d6cbbd;
    --accent:#7a5c36;
    --dark:#1f2933;
    --good:#0f6b3f;
    --bad:#b42318;
    --neutral:#6b6259;
    --warn:#b26a00;
}}
* {{ box-sizing:border-box; }}
body {{
    margin:0;
    background:var(--bg);
    color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
    line-height:1.45;
}}
header {{
    background:linear-gradient(135deg,#1f2933,#7a5c36);
    color:white;
    padding:24px 16px;
}}
header h1 {{ margin:0 0 6px; font-size:23px; letter-spacing:-.3px; }}
header p {{ margin:0; opacity:.94; font-size:14px; }}
main {{ padding:16px; max-width:980px; margin:auto; }}
.card,.item {{
    background:var(--card);
    border:1px solid var(--line);
    border-radius:18px;
    padding:16px;
    margin-bottom:14px;
    box-shadow:0 8px 22px rgba(31,41,51,.06);
    page-break-inside:avoid;
}}
h2 {{ font-size:19px; margin:4px 0 12px; }}
h3 {{ font-size:15px; margin:0 0 8px; }}
.muted {{ color:var(--muted); font-size:13px; }}
.kpis {{ display:grid; grid-template-columns:repeat(2,1fr); gap:10px; margin:10px 0; }}
@media(min-width:760px) {{
    .kpis {{ grid-template-columns:repeat(4,1fr); }}
    .grid {{ grid-template-columns:1fr 1fr; }}
}}
.kpi {{ background:#fbfaf8; border:1px solid var(--line); border-radius:16px; padding:14px; }}
.kpi b {{ display:block; font-size:24px; color:var(--dark); }}
.kpi span {{ color:var(--muted); font-size:12px; font-weight:700; }}
.grid {{ display:grid; gap:12px; }}
.pill {{
    display:inline-flex;
    background:#f1eee8;
    color:var(--dark);
    border-radius:999px;
    padding:5px 8px;
    margin:2px 3px 2px 0;
    font-size:12px;
    font-weight:800;
}}
.pill.olumlu {{ background:#e4f4ec; color:var(--good); }}
.pill.riskli {{ background:#fde9e7; color:var(--bad); }}
.pill.nötr {{ background:#f1eee8; color:var(--neutral); }}
.bar-row {{ margin:10px 0; }}
.bar-label {{ display:flex; justify-content:space-between; font-size:13px; margin-bottom:5px; }}
.bar {{ height:11px; background:#ebe4dc; border-radius:999px; overflow:hidden; }}
.bar div {{ height:100%; }}
.bar .good {{ background:var(--good); }}
.bar .neutral {{ background:var(--neutral); }}
.bar .bad {{ background:var(--bad); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; background:white; border-radius:14px; overflow:hidden; }}
th,td {{ padding:9px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
th {{ background:#fbfaf8; }}
a {{ color:#1f2933; font-weight:800; }}
.risk-note {{ color:var(--bad); }}
.notice {{ border-left:6px solid var(--accent); }}
@media print {{
    body {{ background:white; }}
    header {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
    .card,.item {{ box-shadow:none; }}
}}
</style>
</head>
<body>

<header>
    <h1>Yerel Liderlik AI Günlük Raporu</h1>
    <p>Takip edilen isim: Mesut Kocagöz • Bölge: Antalya / Kepez • Tarih: {today} • Güncelleme saati: {report_time}
    <div id="acil-durum"></div>
    {section_label("🚨 Acil Durum / Kriz Paneli", "#b91c1c", "#fef2f2")}
<div style="margin:18px 0; padding:16px; border:2px solid #dc2626; border-left:8px solid #b91c1c; border-radius:16px; background:#fef2f2; box-shadow:0 2px 10px rgba(185,28,28,0.10);">
  <a href="crisis_panel.html" style="font-size:18px; font-weight:bold; color:#991b1b; text-decoration:none;">
    🚨 Acil Eylem Planı / Kriz Panelini Aç
  </a>
  <div style="margin-top:6px; color:#7f1d1d;">
    Risk seviyesi: {esc(crisis_plan.get("level", ""))} • Durum: {esc(crisis_status.get("status", ""))} • Son güncelleme: {report_time}
  <div style="margin-top:8px; color:#7f1d1d;">
    Erken uyarı: {esc(early_warning.get("decision", ""))} • Bildirim: {esc(early_warning.get("notify_level", ""))}
  </div>
</div>
</div>
... Acil Eylem Planı / Kriz Paneli kartı ...

<div style="margin:10px 0 18px 0; padding:14px; border:2px solid #334155; border-left:8px solid #0f172a; border-radius:16px; background:#f8fafc;">
  <a href="team_report.html" style="font-size:22px; font-weight:bold; color:#0f172a; text-decoration:none;">
    👥 Ekip Operasyon Raporunu Aç
  </a>
  <div style="margin-top:6px; color:#475569;">
    Alarm geçmişi, riskli sosyal medya kayıtları, Başkan X yanıtları ve müdahale kayıtları ekip tarafından buradan takip edilir.
  </div>
</div>

</header>

<main>

{report_main_menu()}

<div id="haberler"></div>
{section_label("📰 Haberler ve Günlük Genel Özet", "#2563eb", "#eff6ff")}

<div class="card" style="border-left:6px solid #2563eb; background:#eff6ff;">
    <h2>1. Günün Genel Algısı</h2>
    <div class="kpis">
        <div class="kpi"><b>{total_news}</b><span>Toplam haber</span></div>
        <div class="kpi"><b>{positive_count}</b><span>Olumlu</span></div>
        <div class="kpi"><b>{neutral_count}</b><span>Nötr</span></div>
        <div class="kpi"><b>{risk_count}</b><span>Riskli</span></div>
    </div>
    <p><b>Genel tablo:</b> {esc(general_tone)}</p>
    <p>{esc(general_comment)}</p>
</div>

<div id="onemli-basliklar"></div>
<div class="card"><h2>2. Bugünün En Önemli 3 Başlığı<h2>{important_html}</div>
<div id="olumlu-haberler"></div>
<div class="card"><h2>3. Öne Çıkan Olumlu Haberler</h2>{positive_html}</div>
<div id="riskli-haberler"></div>
<div class="card"><h2>4. Riskli / İzlenmesi Gereken Haberler</h2>{risky_html}</div>

<div class="card">
 <h2>4.1 Tarihi Okunamayan Ama Takip Edilmesi Gereken Haberler</h2>
 <p class="muted">Bu bölümdeki haberler Kepez / Antalya / Mesut Kocagöz filtresinden geçmiştir; ancak haber tarihi sistem tarafından okunamadığı için ana günlük gündeme doğrudan dahil edilmemiştir.</p>
 {undated_html}
</div>

{section_label("📱 Sosyal Medya Nabzı", "#7c3aed", "#f5f3ff")}

<div class="card">
<div id="sosyal-medya"></div>
 <h2>5. Sosyal Medya Etkileşim Analizi</h2>
    <div class="kpis">
        <div class="kpi"><b>{int(social_sum["total_likes"])}</b><span>Toplam beğeni</span></div>
        <div class="kpi"><b>{int(social_sum["total_comments"])}</b><span>Toplam yorum</span></div>
        <div class="kpi"><b>%{social_sum["like_rate"]:.2f}</b><span>Beğenme oranı</span></div>
        <div class="kpi"><b>%{social_sum["engagement_rate"]:.2f}</b><span>Etkileşim oranı</span></div>
    </div>
    
       <div class="card" style="border-left:6px solid #7c3aed; background:#f5f3ff;">
            <h3>Sayın Başkan İçin Sosyal Medya Özeti</h3>
            <p><b>Genel ton:</b> {esc(social_sum.get("social_mood", ""))}</p>
            <p><b>Öne çıkan konu:</b> {esc(social_sum.get("main_topic", ""))}</p>
            <p><b>Risk yorumu:</b> {esc(social_sum.get("risk_text", ""))}</p>
            <p><b>Fırsat yorumu:</b> {esc(social_sum.get("opportunity_text", ""))}</p>
            <p><b>İlk aksiyon önerisi:</b> {esc(social_sum.get("action_text", ""))}</p>
        </div>
        
        <div id="kriz-aksiyon"></div>
        {section_label("🚨 Kriz / Soğukkanlı Aksiyon", "#b91c1c", "#fef2f2")}
        
        <div style="border:2px solid #dc2626; border-radius:16px; padding:16px; margin:18px 0; background:#fff7ed;">

  <h2 style="margin-top:0; color:#991b1b;">🚨 Kriz Anında Soğukkanlı Aksiyon Planı</h2>

  <div style="font-size:18px; font-weight:bold; margin-bottom:10px;">
    Risk seviyesi: <span style="color:#dc2626;">{esc(crisis_plan.get("level", ""))}</span>
  </div>

  <div style="padding:12px; border-radius:12px; background:#ffffff; margin-bottom:12px;">
    <b>Risk başlığı:</b><br>
    {esc(crisis_plan.get("risk_topic", ""))}
  </div>

<div style="padding:12px; border-radius:12px; background:#fef2f2; border:1px solid #fecaca; margin-bottom:12px;">
  <b>İnsani hassasiyet seviyesi:</b><br>
  {esc(crisis_plan.get("human_sensitivity", ""))}
</div>

<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin-bottom:12px;">

  <div style="padding:12px; border-radius:12px; background:#ffffff;">
    <b>🫶 Duygusal zemin</b><br>
    {esc(crisis_plan.get("emotional_context", ""))}
  </div>

  <div style="padding:12px; border-radius:12px; background:#ffffff;">
    <b>👥 Kamuoyu beklentisi</b><br>
    {esc(crisis_plan.get("public_expectation", ""))}
  </div>

</div>

<div style="padding:12px; border-radius:12px; background:#fff7ed; margin-bottom:12px;">
  <b>İlk cümle nasıl olmalı?</b><br>
  {esc(crisis_plan.get("opening_line", ""))}
</div>

<div style="padding:12px; border-radius:12px; background:#fee2e2; margin-bottom:12px;">
  <b>Kesinlikle kaçınılacak dil:</b><br>
  {esc(crisis_plan.get("avoid_language", ""))}
</div>

<div style="padding:12px; border-radius:12px; background:#f8fafc; margin-bottom:12px;">
  <b>Açıklama taslağı:</b><br>
  {esc(crisis_plan.get("statement_draft", ""))}
</div>

<div style="padding:12px; border-radius:12px; background:#ecfeff; margin-bottom:12px;">
  <b>Açıklamayı kim yapmalı?</b><br>
  {esc(crisis_plan.get("speaker_decision", ""))}
</div>

  <div style="padding:12px; border-radius:12px; background:#fee2e2; margin-bottom:12px;">
    <b>Sayın Başkan'ın yapmaması gereken şey:</b><br>
    {esc(crisis_plan.get("what_not_to_do", ""))}
  </div>

  <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin-bottom:12px;">

    <div style="padding:12px; border-radius:12px; background:#ffffff;">
      <b>⏱ İlk 30 dakika</b><br>
      {esc(crisis_plan.get("first_30", ""))}
    </div>

    <div style="padding:12px; border-radius:12px; background:#ffffff;">
      <b>🕑 İlk 2 saat</b><br>
      {esc(crisis_plan.get("first_2h", ""))}
    </div>

    <div style="padding:12px; border-radius:12px; background:#ffffff;">
      <b>📅 İlk 24 saat</b><br>
      {esc(crisis_plan.get("first_24h", ""))}
    </div>

  </div>

  <div style="padding:12px; border-radius:12px; background:#fef3c7; margin-bottom:12px;">
    <b>Kim konuşmalı?</b><br>
    {esc(crisis_plan.get("speaker", ""))}
  </div>

  <div style="padding:12px; border-radius:12px; background:#ecfeff; margin-bottom:12px;">
    <b>Hazırlanacak veri / belge:</b><br>
    {esc(crisis_plan.get("data_needed", ""))}
  </div>

  <div style="padding:12px; border-radius:12px; background:#f0fdf4;">
    <b>İletişim dili:</b><br>
    {esc(crisis_plan.get("tone", ""))}
  </div>

</div>

    <h3>Yorum Duygu Dağılımı</h3>
    {bar("İyi yorum", good_pct, "good")}
    {bar("Nötr yorum", neutral_pct, "neutral")}
    {bar("Kötü yorum", bad_pct, "bad")}
</div>

<div class="grid">
    {social_card("6. En Yüksek Beğenme Oranlı Paylaşım", social_sum["best_like"])}
    {social_card("7. En Çok Yorum Alan Paylaşım", social_sum["most_comments"])}
    {social_card("8. En Riskli Sosyal İçerik", social_sum["risky"])}
    {social_card("9. En Büyük Fırsat İçeriği", social_sum["opportunity"])}
</div>

<div id="youtube-sosyal"></div>
{section_label("📺 YouTube Sosyal Nabız / Kanal Takibi", "#dc2626", "#fff7ed")}
<div class="card" style="border-left:6px solid #dc2626; background:#fff7ed;">
  <h2>YouTube Kanal Takibi</h2>
  <p class="muted">Yerel YouTube kanallarında kontrol edilen son videolar ve yerel gündemle alakalı bulunan yorum sayıları.</p>
  {youtube_summary_html(youtube_summary)}
</div>

<div id="baskan-x"></div>
{section_label("👤 Sayın Başkan’ın X Hesabı", "#059669", "#ecfdf5")}

<div class="card">
  <h2>10. Sayın Başkan’ın X Hesabı – Öne Çıkan 3 Gönderi</h2>
  <p class="small">Bu bölüm günlük raporda sadece en yüksek etkileşimli 3 gönderiyi gösterir. Haftalık ve aylık raporlarda detaylı performans analizi ayrıca yapılacaktır.</p>
  {president_x_html}

  {president_reply_html}
</div>

<div id="sosyal-kayitlar"></div>
{section_label("🗂 Sosyal Medya Kayıtları", "#d97706", "#fffbeb")}

<div class="card" style="border-left:6px solid #d97706; background:#fffbeb;">
    <h2>11. Manuel ve Otomatik Sosyal Medya Kayıtları</h2>
    <table>
        <tr><th>Tarih</th><th>Platform</th><th>Konu</th><th>Ton</th><th>Beğenme</th><th>Risk</th><th>Fırsat</th><th>Gönderi</th></tr>
        {social_rows}
    </table>
</div>

<div id="strateji"></div>
{section_label("📊 Stratejik Değerlendirme", "#334155", "#f8fafc")}

<div class="card" style="border-left:6px solid #334155; background:#f8fafc;">
<h2>11. Stratejik Erken Uyarı ve Günlük Değerlendirme</h2>

<h3>A) Alarm Seviyesi</h3>
<p><b>{esc(alert_level)}</b></p>
<p>{esc(alert_summary)}</p>

<h3>B) Sayısal Durum</h3>
<p>Bugün sistemde <b>{total_news}</b> haber tarandı. Bunların <b>{positive_count}</b> tanesi olumlu, <b>{neutral_count}</b> tanesi nötr, <b>{risk_count}</b> tanesi riskli görünüyor.</p>

<p>Sosyal medyada kötü yorum oranı <b>%{bad_pct:.1f}</b>, iyi yorum oranı <b>%{good_pct:.1f}</b>, nötr yorum oranı <b>%{neutral_pct:.1f}</b> seviyesinde.</p>

<h3>C) İzlenmesi Gereken Başlıklar</h3>
<p>Teleferik, dava, borç, şikayet, hizmet aksaması, ulaşım, asfalt, temizlik, park ve sosyal yardım başlıkları gün içinde ayrıca takip edilmelidir.</p>

<p>Bir başlıkta yorum artışı, aynı şikayetin farklı hesaplardan tekrar etmesi veya yerel basında aynı konunun büyütülmesi durumunda konu ayrıca not alınmalıdır.</p>

<h3>D) Bugünün Ana Fırsatı</h3>
<p>Bugün öne çıkarılabilecek en güçlü haber başlığı:</p>
<p><b>{esc(best_news_title)}</b></p>

<p>Sosyal medya tarafında fırsat olarak izlenecek başlık:</p>
<p><b>{esc(best_social_topic)}</b></p>
</div>

<div class="card">
<h2>12. Stratejik Yorum</h2>

<h3>A) Bugünün Ana Stratejisi</h3>
<p>{esc(strategy_focus)}</p>

<p>Bugün iletişimde amaç sadece haber paylaşmak değil; Mesut Kocagöz algısını “sahada çalışan, gündemi takip eden, hizmeti önceleyen ve krizleri büyütmeden yöneten Sayın Başkan” çizgisinde güçlendirmek olmalıdır.</p>

<h3>B) Öne Çıkarılacak Konu</h3>
<p>Hizmet, mahalle çalışması, çocuk/aile teması, personel emeği, vatandaş memnuniyeti ve sahadan görüntü içeren içerikler öne çıkarılmalıdır.</p>

<p>Özellikle fotoğraf veya kısa video ile desteklenen paylaşımlar tercih edilmelidir. Sadece makam dili değil, vatandaşla temas eden sade bir anlatım kullanılmalıdır.</p>

<h3>C) Dikkat Edilecek Risk</h3>
<p>Riskli başlıklarda hızlı ve sert cevap verilmemelidir. Önce konu büyüyor mu, kimler yayıyor, yorumlarda tekrar eden ana şikayet ne, bunlar izlenmelidir.</p>

<p>Konu büyürse cevap dili belgeye dayalı, kısa, sakin ve kurumsal olmalıdır. Kişisel tartışmaya girilmemelidir.</p>

<h3>D) Önerilen İletişim Dili</h3>
<p>{esc(daily_language)}</p>

<p>Bugün kullanılabilecek ana mesaj şudur:</p>
<p><b>“Kepez’de önceliğimiz, vatandaşın günlük hayatına dokunan işleri sahada ve sürdürülebilir biçimde büyütmek. Hizmeti mahalle mahalle görünür hale getirmeye devam ediyoruz.”</b></p>
</div>

<div class="card">
    <h2>13. Bugün Ne Yapılmalı?</h2>
    <div class="item"><h3>1) Paylaşım Önerisi</h3><p>Bugün sosyal medyada hizmet ve insan hikayesi taşıyan içerikler öne çıkarılmalıdır. Özellikle mahalle çalışması, çocuk/aile teması, personel emeği ve vatandaşla temas içeren kısa videolar tercih edilmelidir.</p></div>
    <div class="item"><h3>2) Takip Edilecek Risk</h3><p>Teleferik, dava, borç, şikayet ve hizmet aksaması başlıkları gün içinde tekrar kontrol edilmelidir. Bu konularda yorum artışı olursa ayrıca not alınmalı ve büyüme eğilimi izlenmelidir.</p></div>
    <div class="item"><h3>3) Sahada Kullanılacak Mesaj</h3><p>“Kepez’de hizmet mahalle mahalle ilerliyor. Önceliğimiz vatandaşın gündelik hayatına dokunan işleri görünür ve sürdürülebilir hale getirmek.” mesajı sahada ve sosyal medya dilinde kullanılabilir.</p></div>
    <div class="item"><h3>4) Cevap Verilmemesi Gereken Konu</h3><p>Kaynağı belirsiz, kişisel saldırı içeren veya büyüme ihtimali düşük yorumlara doğrudan cevap verilmemelidir. Bu tür içerikler sadece takip edilmeli; resmi cevap ancak konu büyürse ve belgeye dayalı biçimde hazırlanmalıdır.</p></div>
</div>

<div class="card">
    <h2>14. Yarın Takip Edilecek Başlıklar</h2>
    <div class="item"><h3>A) Takip Edilecek Fırsat Başlıkları</h3><p>Hizmet, mahalle çalışmaları, asfalt, çocuk/aile etkinlikleri, spor organizasyonları, personel emeği ve vatandaş memnuniyeti başlıkları takip edilmelidir.</p></div>
    <div class="item"><h3>B) Takip Edilecek Risk Başlıkları</h3><p>Teleferik davası, borç söylemi, hizmet şikayetleri, olumsuz yerel basın haberleri ve sosyal medyada büyüme ihtimali olan eleştiriler ayrıca izlenmelidir.</p></div>
    <div class="item"><h3>C) Sosyal Medyada Bakılacak Başlıklar</h3><p>Instagram, Facebook, X, YouTube ve TikTok üzerinde beğeni oranı, yorum tonu, kötü yorum artışı ve en çok paylaşılan içerikler kontrol edilmelidir.</p></div>
    <div class="item"><h3>D) Sistem Anahtar Kelimeleri</h3><p>{esc(tomorrow_keywords)}</p></div>
</div>

</main>
</body>
</html>"""

    crisis_related = crisis_related_news(
        risky_news,
        crisis_plan.get("risk_topic", ""),
        limit=5
    )

    if crisis_related:
        crisis_news_html = "".join(news_card(x) for x in crisis_related)
    else:
        risky_social = crisis_sum.get("risky") or {}
        crisis_news_html = f"""
    <div class="card" style="background:#fff7ed; border:1px solid #fed7aa;">
      <h2>Kriz sosyal medya verisinden tespit edildi</h2>
      <p><b>Haber tarafında durum:</b><br>Kriz başlığıyla ilişkili riskli haber bulunamadı.</p>
      <p><b>Sosyal medya / manuel kriz konusu:</b><br>{esc(risky_social.get("topic", "Konu bilgisi yok"))}</p>
      <p><b>Platform:</b><br>{esc(risky_social.get("platform", "Platform bilgisi yok"))}</p>
      <p><b>Risk skoru:</b><br>{esc(str(risky_social.get("risk_score", "")))}</p>
      <p><b>Not:</b><br>Bu kriz başlığı haberlerden değil, sosyal medya/manual takip verisinden tetiklenmiş olabilir. Haber tarafı ayrıca izlenmeye devam edilmelidir.</p>
    </div>
    """

    crisis_panel_doc = f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Acil Eylem Planı / Kriz Paneli</title>
  <style>
    body {{
      margin:0;
      font-family: Arial, sans-serif;
      background:#f8fafc;
      color:#0f172a;
      line-height:1.55;
    }}
    .wrap {{
      max-width:980px;
      margin:0 auto;
      padding:18px;
    }}
    .top {{
      background:#7f1d1d;
      color:white;
      border-radius:18px;
      padding:20px;
      margin-bottom:16px;
    }}
    .top h1 {{
      margin:0 0 10px 0;
      font-size:28px;
    }}
    .status {{
      display:grid;
      grid-template-columns:repeat(auto-fit, minmax(190px, 1fr));
      gap:10px;
      margin-top:14px;
    }}
    .status div {{
      background:rgba(255,255,255,0.14);
      padding:12px;
      border-radius:12px;
    }}
    .card {{
      background:white;
      border-radius:16px;
      padding:16px;
      margin:14px 0;
      box-shadow:0 2px 10px rgba(15,23,42,0.06);
    }}
    .danger {{
      background:#fee2e2;
      border:1px solid #fecaca;
    }}
    .human {{
      background:#fff7ed;
      border:1px solid #fed7aa;
    }}
    .info {{
      background:#ecfeff;
      border:1px solid #a5f3fc;
    }}
    .soft {{
      background:#f8fafc;
      border:1px solid #e2e8f0;
    }}
    .grid {{
      display:grid;
      grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));
      gap:12px;
    }}
    .btn {{
      display:inline-block;
      margin-bottom:14px;
      padding:10px 14px;
      border-radius:999px;
      background:#0f172a;
      color:white;
      text-decoration:none;
      font-weight:bold;
    }}
    h2 {{
      margin-top:0;
      color:#991b1b;
    }}
    .small {{
      color:#64748b;
      font-size:14px;
    }}
  </style>
</head>
<body>
  <div class="wrap">

    <a class="btn" href="daily_report.html">← Günlük rapora dön</a>

    <div class="top">
      <h1>🚨 Acil Eylem Planı / Kriz Paneli</h1>
      <div>Takip edilen isim: Mesut Kocagöz • Bölge: Antalya / Kepez</div>

      <div class="status">
        <div><b>Risk seviyesi</b><br>{esc(crisis_plan.get("level", ""))}</div>
        <div><b>Kriz başlığı</b><br>{esc(crisis_plan.get("risk_topic", ""))}</div>
        <div><b>Son güncelleme</b><br>{today} • {report_time}</div>
        <div><b>Durum</b><br>{esc(crisis_status.get("status", "İzleniyor"))}</div>
      </div>
    </div>

    {risk_alarm_html}
    
    {section_label("📣 Bildirim / Erken Uyarı Kararı", "#0ea5e9", "#f0f9ff")}

    <div class="card info" style="border:2px solid #0ea5e9;">
      <h2>📣 Bildirim / Erken Uyarı Kararı</h2>
      <p><b>Karar:</b><br>{esc(early_warning.get("decision", ""))}</p>
      <p><b>Bildirim seviyesi:</b><br>{esc(early_warning.get("notify_level", ""))}</p>
      <p><b>Sayın Başkan’a acil gösterilsin mi?</b><br>{esc(early_warning.get("show_to_president", ""))}</p>
      <p><b>Neden:</b><br>{esc(early_warning.get("reason", ""))}</p>
      <p><b>İlk aksiyon:</b><br>{esc(early_warning.get("first_action", ""))}</p>
    </div>

    {section_label("📝 Manuel Kriz Durum Notu", "#0891b2", "#ecfeff")}

    <div class="card info">
      <h2>Manuel Kriz Durum Notu</h2>
      <p><b>Aktif kriz durumu:</b><br>{esc(active_label)}</p>
      <p><b>Güncel durum:</b><br>{esc(crisis_status.get("status", ""))}</p>
      <p><b>Manuel not:</b><br>{esc(crisis_status.get("manual_note", ""))}</p>
      <p><b>Son yapılan aksiyon:</b><br>{esc(crisis_status.get("last_action", ""))}</p>
      <p><b>Sıradaki aksiyon:</b><br>{esc(crisis_status.get("next_action", ""))}</p>
      <p><b>Sorumlu ekip / kişi:</b><br>{esc(crisis_status.get("responsible", ""))}</p>
      <p><b>Güncelleyen:</b><br>{esc(crisis_status.get("updated_by", ""))}</p>
    </div>

    {section_label("🕒 Yapılan İşlemler / Müdahale Kayıtları", "#d97706", "#fffbeb")}

    <div class="card soft">
      <h2>🕒 Yapılan İşlemler / Müdahale Kayıtları</h2>
      <p class="small">Bu bölüm kriz boyunca yapılan işlemleri, alınan aksiyonları, sonuçları ve sıradaki adımları takip etmek için kullanılır.</p>
      {crisis_log_html}
    </div>

    {section_label("🔎 Otomatik Kriz Kaynağı", "#334155", "#f8fafc")}

    <div class="card soft">
      <h2>🔎 Otomatik Kriz Kaynağı</h2>
      <p><b>Kaynak:</b><br>{esc((crisis_sum.get("risky") or {}).get("platform", ""))}</p>
      <p><b>Konu:</b><br>{esc((crisis_sum.get("risky") or {}).get("topic", ""))}</p>
      <p><b>Risk skoru:</b><br>{esc(str((crisis_sum.get("risky") or {}).get("risk_score", "")))}</p>
      <p><b>Not:</b><br>{esc((crisis_sum.get("risky") or {}).get("risk_note", ""))}</p>
    </div>

    {section_label("🚨 Sayın Başkan İçin İlk Uyarı", "#b91c1c", "#fef2f2")}

    <div class="card danger">
      <h2>Sayın Başkan İçin İlk Uyarı</h2>
      <p><b>Şu an yapılmaması gereken:</b><br>{esc(crisis_plan.get("what_not_to_do", ""))}</p>
      <p><b>İlk doğru hamle:</b><br>{esc(crisis_plan.get("first_30", ""))}</p>
      <p><b>Sayın Başkan konuşmalı mı?</b><br>{esc(crisis_plan.get("speaker_decision", crisis_plan.get("speaker", "")))}</p>
    </div>

    {section_label("🫶 İnsani Hassasiyet Analizi", "#ea580c", "#fff7ed")}

    <div class="card human">
      <h2>İnsani Hassasiyet Analizi</h2>
      <p><b>İnsani hassasiyet seviyesi:</b><br>{esc(crisis_plan.get("human_sensitivity", ""))}</p>
      <p><b>Duygusal zemin:</b><br>{esc(crisis_plan.get("emotional_context", ""))}</p>
      <p><b>Kamuoyu beklentisi:</b><br>{esc(crisis_plan.get("public_expectation", ""))}</p>
      <p><b>İlk cümle nasıl olmalı?</b><br>{esc(crisis_plan.get("opening_line", ""))}</p>
    </div>

    <div class="grid">
      <div class="card">
        <h2>⏱ İlk 30 Dakika</h2>
        <p>{esc(crisis_plan.get("first_30", ""))}</p>
      </div>

      <div class="card">
        <h2>🕑 İlk 2 Saat</h2>
        <p>{esc(crisis_plan.get("first_2h", ""))}</p>
      </div>

      <div class="card">
        <h2>📅 İlk 24 Saat</h2>
        <p>{esc(crisis_plan.get("first_24h", ""))}</p>
      </div>
    </div>

    <div class="card danger">
      <h2>Kesinlikle Kaçınılacak Dil</h2>
      <p>{esc(crisis_plan.get("avoid_language", ""))}</p>
    </div>

    <div class="card soft">
      <h2>Açıklama Taslağı</h2>
      <p>{esc(crisis_plan.get("statement_draft", ""))}</p>
      <p class="small">Not: Bu metin yayınlanmadan önce hukuk ve basın birimi tarafından kontrol edilmelidir.</p>
    </div>

    <div class="card info">
      <h2>Açıklamayı Kim Yapmalı?</h2>
      <p>{esc(crisis_plan.get("speaker_decision", crisis_plan.get("speaker", "")))}</p>
    </div>

    <div class="card">
      <h2>Hazırlanacak Veri / Belge</h2>
      <p>{esc(crisis_plan.get("data_needed", ""))}</p>
    </div>

    <div class="card">
      <h2>İletişim Dili</h2>
      <p>{esc(crisis_plan.get("tone", ""))}</p>
    </div>

    {section_label("📰 Kriz Başlığıyla İlişkili Haber / Sosyal Kaynaklar", "#2563eb", "#eff6ff")}

    <div class="card">
      <h2>Kriz Başlığıyla İlişkili Haber / Sosyal Kaynaklar</h2>
      {crisis_news_html}
    </div>

  </div>
</body>
</html>
"""

    crisis_out = REPORTS / "crisis_panel.html"
    crisis_out.write_text(crisis_panel_doc, encoding="utf-8")
    print(f"Kriz paneli hazır: {crisis_out}")

    out = REPORTS / "daily_report.html"
    out.write_text(html_doc, encoding="utf-8")
    print(f"Rapor hazır: {out}")
    
    build_team_report(news, social, early_warning, crisis_plan, crisis_status, report_time)
    
    send_early_warning_email(early_warning, crisis_plan, crisis_status, report_time)

def main():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    news, undated_news = fetch_news()
    fetch_x_social_posts()
    fetch_youtube_social_comments()
    fetch_president_x_posts()
    fetch_president_x_replies()
    social = read_social_data()

    save_dynamic_keywords(generate_dynamic_keywords(news, social))

    html = build_report(news, social, undated_news)
    # save_report(html)

if __name__ == "__main__":
    main()
