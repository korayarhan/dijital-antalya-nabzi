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
ARCHIVE_DIR = ROOT / "data" / "archive"
DAILY_DECISION_LOG_CSV = ARCHIVE_DIR / "daily_decision_log.csv"
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
                "parsed_date": news_date.isoformat() if news_date else "",
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
    title_norm = normalize_text(video_title)
    comment_norm = normalize_text(comment_text)
    topic_norm = normalize_text(watch_topic)
    combined = normalize_text(f"{video_title} {comment_text} {watch_topic}")

    # 1) Sadece emoji, kalp, boş veya çok kısa yorumları alma.
    comment_core = re.sub(r"\s+", "", comment_norm)
    if len(comment_core) < 3:
        return False

    # 2) Güçlü yerel bağlam olmadan genel "başkan / belediye" kelimesine güvenme.
    strong_local_terms = [
        "kepez",
        "kepez belediyesi",
        "kepez belediye",
        "kepez belediye başkanı",
        "kepez belediye baskani",
        "mesut",
        "mesut kocagöz",
        "mesut kocagoz",
        "kocagöz",
        "kocagoz",
        "antalya kepez",
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

    # Antalya genelinde ama proje için kritik olabilecek güçlü bağlamlar.
    strategic_local_terms = [
        "antalya büyükşehir",
        "antalya buyuksehir",
        "antalya büyükşehir belediyesi",
        "antalya buyuksehir belediyesi",
        "teleferik",
    ]

    service_or_risk_terms = [
        "şikayet",
        "sikayet",
        "tepki",
        "eleştiri",
        "elestiri",
        "kriz",
        "dava",
        "soruşturma",
        "sorusturma",
        "ihmal",
        "mağdur",
        "magdur",
        "asfalt",
        "yol",
        "temizlik",
        "park",
        "ulaşım",
        "ulasim",
        "mahalle",
        "zabıta",
        "zabita",
        "okul",
        "inşaat",
        "insaat",
        "sosyal yardım",
        "sosyal yardim",
    ]

    # Başka il/siyasi genel içerikleri elemek için zayıf bağlam kontrolü.
    out_of_scope_terms = [
        "adana",
        "mersin",
        "istanbul",
        "ankara",
        "izmir",
        "bursa",
        "konya",
        "il başkanlığı",
        "il baskanligi",
        "chp adana",
        "ak parti adana",
    ]

    strong_local_hit = any(normalize_text(term) in combined for term in strong_local_terms)
    strategic_hit = any(normalize_text(term) in combined for term in strategic_local_terms)
    service_or_risk_hit = any(normalize_text(term) in combined for term in service_or_risk_terms)
    out_of_scope_hit = any(normalize_text(term) in combined for term in out_of_scope_terms)

    # Güçlü Kepez / Mesut / Antalya Büyükşehir / teleferik bağlantısı varsa al.
    if strong_local_hit or strategic_hit:
        return True

    # Başka il veya genel siyasi içerikse, güçlü yerel bağlam yoksa alma.
    if out_of_scope_hit:
        return False

    # Sadece "başkan" veya "belediye" geçti diye alma.
    # Ancak Antalya + hizmet/risk birlikte varsa takipte tut.
    antalya_hit = "antalya" in combined
    if antalya_hit and service_or_risk_hit:
        return True

    return False


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
    seen_social_keys = set()

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

                    # YouTube için ikinci güvenlik filtresi:
                    # CSV'de eski/alakasız kayıt kalmışsa rapora alma.
                    if csv_path == YOUTUBE_SOCIAL_CSV:
                        youtube_check_text = normalize_text(
                            f"{item.get('content', '')} {item.get('topic', '')} {item.get('account', '')}"
                    )

                        youtube_content_core = re.sub(
                            r"\s+",
                            "",
                            normalize_text(item.get("content", ""))
                    )

                    strong_youtube_terms = [
                        "kepez",
                        "kepez belediyesi",
                        "mesut",
                        "mesut kocagoz",
                        "mesut kocagöz",
                        "kocagoz",
                        "kocagöz",
                        "antalya kepez",
                        "duaci",
                        "duacı",
                        "varsak",
                        "sutculer",
                        "sütçüler",
                        "teleferik",
                    ]

                    youtube_service_terms = [
                        "sikayet",
                        "şikayet",
                        "tepki",
                        "elestiri",
                        "eleştiri",
                        "dava",
                        "kriz",
                        "asfalt",
                        "yol",
                        "park",
                        "temizlik",
                        "ulasim",
                        "ulaşım",
                        "mahalle",
                        "okul",
                        "insaat",
                        "inşaat",
                    ]

                    strong_youtube_hit = any(
                        normalize_text(term) in youtube_check_text
                        for term in strong_youtube_terms
                    )

                    antalya_service_hit = (
                        "antalya" in youtube_check_text
                        and any(
                            normalize_text(term) in youtube_check_text
                            for term in youtube_service_terms
                        )
                    )

                    # Sadece emoji, kalp veya çok kısa yorumları alma.
                    if len(youtube_content_core) < 3:
                        continue

                    # Güçlü Kepez/Mesut/yerel bağlam yoksa rapora alma.
                    if not strong_youtube_hit and not antalya_service_hit:
                        continue

                if any(str(v).strip() for v in item.values()):
                    unique_platform = normalize_text(item.get("platform", ""))
                    unique_account = normalize_text(item.get("account", ""))
                    unique_url = normalize_text(item.get("url", "") or item.get("link", ""))
                    unique_content = normalize_text(item.get("content", ""))[:160]

                    if unique_url:
                        dedup_key = f"url|{unique_platform}|{unique_url}"
                    else:
                        dedup_key = f"text|{unique_platform}|{unique_account}|{unique_content}"

                    if dedup_key in seen_social_keys:
                        continue

                    seen_social_keys.add(dedup_key)
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

def opportunity_context(text, source=""):
    norm = normalize_text(text)
    source_norm = normalize_text(source)

    if any(term in norm for term in [
        "asfalt", "yol", "altyapi", "alt yapi", "duaci",
        "park", "bahce", "temizlik", "bakim", "onarim"
    ]):
        return (
            "Hizmet görünürlüğü fırsatı",
            "Kurumsal hesap + ilgili müdürlük",
            "Sahadan fotoğraf/video toplanıp kısa hizmet kartı hazırlanmalı. Mahalle adı özellikle vurgulanmalı."
        )

    if any(term in norm for term in [
        "mahalle", "muhtar", "saha", "hemsehri", "ziyaret", "vatandas"
    ]):
        return (
            "Mahalle / saha teması fırsatı",
            "Basın birimi + saha ekibi",
            "Başkanın sahada dinleyen ve çözüm takip eden profili kısa içerikle desteklenmeli."
        )

    if any(term in norm for term in [
        "cocuk", "aile", "kadin", "yasli", "sosyal", "yardim", "etkinlik"
    ]):
        return (
            "Sosyal belediyecilik fırsatı",
            "Basın birimi + sosyal destek ekibi",
            "İnsani ve sıcak dil kullanılmalı. Fotoğraf/video varsa aile ve çocuk teması öne çıkarılmalı."
        )

    if any(term in norm for term in [
        "spor", "antalyaspor", "turnuva", "genclik", "genc", "kulup"
    ]):
        return (
            "Spor / şehir aidiyeti fırsatı",
            "Başkan hesabı + kurumsal hesap",
            "Şehir aidiyeti, gençlik ve ortak Antalya duygusu üzerinden pozitif iletişim yapılabilir."
        )

    if any(term in norm for term in [
        "butce", "basari", "odul", "proje", "acilis", "yeni adres", "yatirim"
    ]):
        return (
            "Kurumsal başarı / proje fırsatı",
            "Basın birimi + kurumsal hesap",
            "Başarı dili abartılmadan, somut hizmet ve vatandaş faydası üzerinden anlatılmalı."
        )

    if "baskan" in source_norm or "x performans" in source_norm:
        return (
            "Başkan iletişim performansı fırsatı",
            "Başkan iletişim ekibi",
            "İyi çalışan dil ve format not alınmalı; benzer içerik haftalık iletişim planına eklenmeli."
        )

    return (
        "Genel PR / görünürlük fırsatı",
        "Basın birimi",
        "Başlık takip edilmeli; uygun görülürse kısa sosyal medya içeriğine çevrilmeli."
    )

def opportunity_alert_decision(opportunity):
    score = safe_score_value(opportunity.get("score", 0))
    risk_score = safe_score_value(opportunity.get("risk_score", 0))
    opportunity_type = str(opportunity.get("type", ""))
    source = str(opportunity.get("source", ""))

    if score >= 8 and risk_score < 6:
        return {
            "alarm": True,
            "alarm_label": "FIRSAT ALARMI",
            "mail_candidate": "Evet",
            "whatsapp_candidate": "İleri aşamada evet",
            "alarm_reason": "Fırsat skoru yüksek, risk seviyesi kontrol edilebilir ve başlık görünürlük açısından büyütülebilir.",
        }

    if score >= 6 and risk_score < 6:
        return {
            "alarm": False,
            "alarm_label": "Güçlü fırsat / ekip takip",
            "mail_candidate": "Hayır",
            "whatsapp_candidate": "Hayır",
            "alarm_reason": "Fırsat değerli ancak anlık alarm gerektirecek seviyede değil. Ekip tarafından takip edilmesi yeterli.",
        }

    if "Başkan" in source or "performans" in source:
        return {
            "alarm": False,
            "alarm_label": "Performans fırsatı",
            "mail_candidate": "Hayır",
            "whatsapp_candidate": "Hayır",
            "alarm_reason": "Başkan iletişimi açısından not alınmalı; haftalık performans değerlendirmesine eklenebilir.",
        }

    return {
        "alarm": False,
        "alarm_label": "Günlük fırsat",
        "mail_candidate": "Hayır",
        "whatsapp_candidate": "Hayır",
        "alarm_reason": "Günlük raporda görünmesi yeterli. Şimdilik ayrıca bildirim gerekmez.",
    }

def build_opportunity_summary(news, social, president_posts, summary_day):
    candidates = []

    # 1) Haberlerden fırsat yakala
    for item in news:
        item_date = item.get("parsed_date", item.get("date", ""))
        if not same_day(item_date, summary_day):
            continue

        title = clean_text(item.get("title", ""))
        tone = str(item.get("tone", ""))
        opportunity_score = safe_score_value(item.get("opportunity", 0))
        risk_score = safe_score_value(item.get("risk", 0))

        if opportunity_score >= 3 or tone == "Olumlu":
            score = opportunity_score
            if risk_score <= 3:
                score += 1

            opp_type, opp_owner, smart_action = opportunity_context(title, "Haber fırsatı")

            candidates.append({
                "score": score,
                "source": "Haber fırsatı",
                "type": opp_type,
                "owner": opp_owner,
                "risk_score": risk_score,
                "title": title or "Olumlu haber başlığı",
                "reason": "Özet gününde olumlu/hizmet odaklı haber görünürlüğü oluştu.",
                "action": smart_action,
                "format": "Kısa video, görsel kart veya başkan/kurumsal hesap paylaşımı",
                "notify": "Mail gerekmez; günlük fırsat olarak takip edilsin.",
            })

        # 2) Sosyal medyadan fırsat yakala
        for item in social:
            if not same_day(item.get("date", ""), summary_day):
               continue

        topic = clean_text(item.get("topic", "Sosyal medya fırsatı"))
        opportunity_score = safe_score_value(item.get("opportunity_score", 0))
        risk_score = safe_score_value(item.get("risk_score", 0))
        likes = safe_score_value(item.get("likes", 0))
        comments = safe_score_value(item.get("comments", 0))
        shares = safe_score_value(item.get("shares", 0))
        views = safe_score_value(item.get("views", 0))
        engagement = likes + comments + shares

        if opportunity_score >= 5 or engagement >= 20 or views >= 1000:
            score = opportunity_score + min(3, engagement / 50)
            if risk_score >= 6:
                score -= 2

            opp_type, opp_owner, smart_action = opportunity_context(topic, "Sosyal medya fırsatı")

            candidates.append({
                "score": score,
                "source": "Sosyal medya fırsatı",
                "type": opp_type,
                "owner": opp_owner,
                "risk_score": risk_score,
                "title": topic,
                "reason": "Sosyal medyada etkileşim veya görünürlük değeri olan bir başlık tespit edildi.",
                "action": smart_action,
                "format": "Repost, hikaye, kısa video veya hizmet vurgulu ikinci paylaşım",
                "notify": "Takip edilsin; çok hızlı büyürse fırsat alarmına çevrilsin.",
            })

    # 3) Başkan X gönderilerinden fırsat yakala
    for item in president_posts:
        if not same_day(item.get("date", ""), summary_day):
            continue

        content = clean_text(item.get("content", "Başkan X gönderisi"))
        topic = clean_text(item.get("topic", "Başkan X gönderisi"))
        engagement = safe_score_value(item.get("engagement", 0))
        likes = safe_score_value(item.get("likes", 0))
        reposts = safe_score_value(item.get("reposts", 0))

        if engagement > 0:
            score = min(10, 4 + (engagement / 50))
            
            opp_type, opp_owner, smart_action = opportunity_context(f"{topic} {content}", "Başkan X performans fırsatı")
            
            candidates.append({
                "score": score,
                "source": "Başkan X performans fırsatı",
                "type": opp_type,
                "owner": opp_owner,
                "risk_score": 0,
                "title": topic or content[:90],
                "reason": f"Başkan X gönderisi etkileşim aldı. Beğeni: {int(likes)}, repost: {int(reposts)}, toplam etkileşim: {int(engagement)}.",
                "action": smart_action,
                "format": "Başkan hesabından devam paylaşımı veya kurumsal hesapla destekleme",
                "notify": "Mail gerekmez; performans fırsatı olarak izlenmeli.",

           })

    if not candidates:
        return {
            "level": "Fırsat yok",
            "type": "Belirgin fırsat yok",
            "owner": "Standart takip",
            "alarm": False,
            "alarm_label": "Fırsat yok",
            "mail_candidate": "Hayır",
            "whatsapp_candidate": "Hayır",
            "alarm_reason": "Belirgin fırsat bulunmadığı için bildirim gerekmez.",
            "title": "Özet gününde belirgin fırsat görünmüyor.",
            "source": "Genel takip",
            "score": 0,
            "reason": "Haber, sosyal medya ve Başkan X tarafında güçlü fırsat sinyali bulunmadı.",
            "action": "Standart takip yeterli. Yeni olumlu haber veya etkileşim artışı olursa tekrar değerlendirilir.",
            "format": "Standart günlük takip",
            "notify": "Bildirim gerekmez.",
        }

    best = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[0]
    best_score = safe_score_value(best.get("score", 0))

    if best_score >= 8:
        level = "Yüksek fırsat"
        notify = "FIRSAT ALARMI: Mail/WhatsApp bildirimi için aday."
    elif best_score >= 5:
        level = "Takip edilebilir fırsat"
        notify = best.get("notify", "Günlük takip yeterli.")
    else:
        level = "Düşük fırsat"
        notify = "Bildirim gerekmez; günlük raporda izlenmeli."

    best["level"] = level
    best["notify"] = notify
    best["score"] = round(best_score, 1)
    best.setdefault("type", "Genel PR / görünürlük fırsatı")
    best.setdefault("owner", "Basın birimi")
    
    alert_decision = opportunity_alert_decision(best)
    best.update(alert_decision)

    return best

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
    <div class="card" id="main-menu">
        <h3>Rapor Ana Menüsü / Hızlı Erişim</h3>
        <p>
            <a href="#kriz">Acil Durum</a> •
            <a href="#haberler">Haberler</a> •
            <a href="#sosyal">Sosyal Medya</a> •
            <a href="#youtube">YouTube Nabzı</a> •
            <a href="#kriz-aksiyon">Kriz Aksiyon</a> •
            <a href="#baskan-x">Başkan X</a> •
            <a href="team_report.html">Ekip Raporu</a> •
            <a href="crisis_panel.html">Kriz Paneli</a>
        </p>
    </div>
    """

def accordion_section(title, color, bg, content, opened=False, subtitle=""):
    open_attr = " open" if opened else ""

    subtitle_html = ""
    if subtitle:
        subtitle_html = f"""
                <div style="
                    font-size: 13px;
                    font-weight: 600;
                    opacity: 0.78;
                    margin-top: 6px;
                    line-height: 1.35;
                ">
                    {esc(subtitle)}
                </div>
        """

    return f"""
    <details class="accordion-section"{open_attr} style="
        margin: 14px 0;
        border-radius: 16px;
    ">
        <summary style="
            cursor: pointer;
            list-style: none;
            outline: none;
        ">
            <div style="
                border: 1.5px solid {color};
                background: {bg};
                color: {color};
                border-radius: 16px;
                padding: 13px 15px;
                font-size: 19px;
                font-weight: 750;
                line-height: 1.25;
                letter-spacing: 0.1px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                box-shadow: 0 5px 14px rgba(15, 23, 42, 0.04);
            ">
                <span>
                    <span>{esc(title)}</span>
                    {subtitle_html}
                </span>
                <span style="
                    font-size: 16px;
                    font-weight: 800;
                    opacity: 0.68;
                    flex-shrink: 0;
                ">⌄</span>
            </div>
        </summary>

        <div class="accordion-content" style="
            margin-top: 12px;
            padding: 2px 0 4px 0;
        ">
            {content}
        </div>
    </details>
    """

def same_day(value, today):
    value = str(value or "").strip()
    return value.startswith(today) or today in value


def is_x_platform(item):
    text = normalize_text(f"{item.get('platform', '')} {item.get('source_type', '')}")
    return "twitter" in text or text == "x" or text.startswith("x ")


def is_youtube_platform(item):
    text = normalize_text(f"{item.get('platform', '')} {item.get('source_type', '')}")
    return "youtube" in text


def dashboard_kpi(title, value, note, color="#334155", bg="#f8fafc"):
    value_text = str(value or "")

    if title == "Kriz / Alarm" and value_text.lower() == "takipte":
        value_text = "TAKİPTE"
        value_size = "24px"
    else:
        value_size = "34px"
    return f"""
    <div style="
        background:linear-gradient(180deg,rgba(255,255,255,0.10),rgba(255,255,255,0.045));
        border:1px solid rgba(255,255,255,0.12);
        border-left:5px solid {color};
        border-radius:18px;
        padding:16px;
        box-shadow:0 10px 24px rgba(0,0,0,0.28);
        min-height:175px;
        display:flex;
        flex-direction:column;
        justify-content:flex-start;
        gap:14px;
        box-sizing:border-box;
    ">
        <div style="font-size:13px;font-weight:850;color:#cbd5e1;line-height:1.35;">
            {esc(title)}
        </div>
        <div style="font-size:{value_size};font-weight:950;color:#f8fafc;line-height:1.05;">
            {esc(value_text)}
        </div>
        <div style="font-size:13px;font-weight:750;color:#94a3b8;line-height:1.4;">
            {esc(note)}
        </div>
    </div>
    """


def dashboard_bar(label, value, total, color):
    try:
        value = float(value or 0)
        total = float(total or 0)
    except:
        value, total = 0, 0

    pct = (value / total * 100) if total else 0
    pct = max(0, min(100, pct))

    return f"""
    <div style="margin:12px 0;">
        <div style="
            display:flex;
            justify-content:space-between;
            gap:10px;
            font-size:13px;
            font-weight:800;
            color:#334155;
            margin-bottom:6px;
        ">
            <span>{esc(label)}</span>
            <span>{int(value)} / {int(total)}</span>
        </div>
        <div style="
            height:10px;
            background:#e7e5e4;
            border-radius:999px;
            overflow:hidden;
        ">
            <div style="
                width:{pct:.1f}%;
                height:10px;
                background:{color};
                border-radius:999px;
            "></div>
        </div>
    </div>
    """

def detect_social_platform(item):
    text = normalize_text(f"{item.get('platform', '')} {item.get('source_type', '')}")

    if "instagram" in text:
        return "Instagram"
    if "facebook" in text:
        return "Facebook"
    if "tiktok" in text or "tik tok" in text:
        return "TikTok"
    if "youtube" in text:
        return "YouTube"
    if "twitter" in text or text == "x" or text.startswith("x ") or "x twitter" in text:
        return "X"

    platform = clean_text(item.get("platform", ""))
    return platform or "Diğer"


def social_tone_group(item):
    tone = normalize_text(f"{item.get('tone', '')} {item.get('sentiment', '')}")

    if "positive" in tone or "olumlu" in tone or "iyi" in tone:
        return "positive"

    if "negative" in tone or "riskli" in tone or "kotu" in tone or "kötü" in tone:
        return "negative"

    return "neutral"

def platform_pulse_comment(platform, risky_count, opportunity_count, positive_count, negative_count, comments, views, featured_topic):
    platform_norm = normalize_text(platform)
    topic_norm = normalize_text(featured_topic)

    if risky_count > 0:
        if "tiktok" in platform_norm or views >= 10000 or comments >= 50:
            return "Yayılım riski yüksek. Yorum artışı ve paylaşım hızı ekip tarafından takip edilmeli."

        if any(term in topic_norm for term in ["temizlik", "cop", "çöp", "asfalt", "yol", "park", "ulasim", "ulaşım"]):
            return "Hizmet şikayeti olarak takip edilmeli. İlgili birimden saha bilgisi alınmalı."

        if any(term in topic_norm for term in ["dava", "teleferik", "sorusturma", "soruşturma", "yolsuzluk", "rusvet", "rüşvet"]):
            return "Hukuki / kriz hassasiyeti var. Basın ve hukuk diliyle kontrollü takip edilmeli."

        return "Riskli sosyal medya başlığı var. Konu büyümeden yorum tonu ve yayılım kontrol edilmeli."

    if opportunity_count > 0:
        if any(term in topic_norm for term in ["asfalt", "yol", "park", "mahalle", "hizmet", "proje"]):
            return "Hizmet görünürlüğü fırsatı var. Kısa video veya görsel kartla büyütülebilir."

        if any(term in topic_norm for term in ["cocuk", "çocuk", "aile", "yasli", "yaşlı", "sosyal", "etkinlik"]):
            return "Sosyal belediyecilik fırsatı var. Sıcak ve insan odaklı dille paylaşılabilir."

        return "Olumlu görünürlük fırsatı var. Kurumsal hesap veya başkan hesabı destek paylaşımı yapabilir."

    if positive_count > negative_count:
        return "Genel ton olumlu. İyi çalışan içerik dili haftalık değerlendirmeye alınabilir."

    if negative_count > positive_count:
        return "Genel ton olumsuza yakın. Konu büyümeden ekip gözle kontrol etmeli."

    return "Standart takip yeterli. Belirgin risk veya fırsat sinyali görünmüyor."

def build_platform_social_pulse_html(social, summary_day):
    platform_groups = {}

    for item in social:
        if not same_day(item.get("date", ""), summary_day):
            continue

        platform = detect_social_platform(item)
        platform_groups.setdefault(platform, []).append(item)

    platform_order = ["X", "Instagram", "Facebook", "TikTok", "YouTube", "Diğer"]

    total_count = sum(len(items) for items in platform_groups.values())

    if total_count == 0:
        return """
        <div class="card" style="
            border-left:6px solid #64748b;
            background:#f8fafc;
            margin:14px 0 16px 0;
        ">
            <h2 style="margin-top:0;color:#334155;">📱 Platform Bazlı Sosyal Nabız</h2>
            <p style="font-weight:700;color:#64748b;">
                Özet gününde sosyal medya kaydı bulunamadı. Takip havuzu çalışmaya devam ediyor.
            </p>
        </div>
        """

    cards_html = ""

    for platform in platform_order:
        items = platform_groups.get(platform, [])
        if not items:
            continue

        count = len(items)

        positive_count = len([x for x in items if social_tone_group(x) == "positive"])
        negative_count = len([x for x in items if social_tone_group(x) == "negative"])
        neutral_count = max(0, count - positive_count - negative_count)

        risky_count = len([
            x for x in items
            if safe_score_value(x.get("account_adjusted_risk_score", x.get("risk_score", 0))) >= 6
        ])

        opportunity_count = len([
            x for x in items
            if safe_score_value(x.get("opportunity_score", 0)) >= 5
        ])

        likes = sum(safe_score_value(x.get("likes", 0)) for x in items)
        comments = sum(safe_score_value(x.get("comments", 0)) for x in items)
        shares = sum(safe_score_value(x.get("shares", 0)) for x in items)
        views = sum(safe_score_value(x.get("views", 0)) for x in items)

        def platform_item_priority(x):
            risk_value = safe_score_value(x.get("account_adjusted_risk_score", x.get("risk_score", 0)))
            opportunity_value = safe_score_value(x.get("opportunity_score", 0))
            engagement_value = (
                safe_score_value(x.get("likes", 0))
                + safe_score_value(x.get("comments", 0))
                + safe_score_value(x.get("shares", 0))
                + safe_score_value(x.get("views", 0)) / 1000
            )
            return (risk_value * 1000) + (opportunity_value * 200) + engagement_value

        featured_item = max(items, key=platform_item_priority)
        featured_url = clean_text(featured_item.get("url", ""))
        featured_topic = clean_text(
            featured_item.get("topic", "")
            or featured_item.get("title", "")
            or featured_item.get("content", "")
            or "Öne çıkan içerik"
        )

        if risky_count > 0:
            color = "#dc2626"
            bg = "#fef2f2"
            label = f"{risky_count} riskli kayıt"
        elif opportunity_count > 0:
            color = "#16a34a"
            bg = "#ecfdf5"
            label = f"{opportunity_count} fırsat kaydı"
        else:
            color = "#334155"
            bg = "#f8fafc"
            label = "Standart takip"
            
        platform_comment = platform_pulse_comment(
            platform,
            risky_count,
            opportunity_count,
            positive_count,
            negative_count,
            comments,
            views,
            featured_topic
        )
            
        if featured_url.startswith("http"):
            featured_link_html = f"""
            <div style="margin-top:10px;">
                <div style="
                    font-size:12px;
                    font-weight:800;
                    color:#64748b;
                    margin-bottom:6px;
                    line-height:1.35;
                ">
                    Öne çıkan: {esc(featured_topic[:90])}
                </div>
                <a href="{esc(featured_url)}" target="_blank" rel="noopener noreferrer" style="
                    display:inline-block;
                    background:{color};
                    color:white;
                    text-decoration:none;
                    border-radius:999px;
                    padding:8px 12px;
                    font-size:13px;
                    font-weight:900;
                ">
                    Gönderiyi aç
                </a>
            </div>
            """
        else:
            featured_link_html = f"""
            <div style="
                margin-top:10px;
                font-size:12px;
                font-weight:800;
                color:#64748b;
                line-height:1.35;
            ">
                Öne çıkan içerik için bağlantı yok.
            </div>
            """

        cards_html += f"""
        <div style="
            background:{bg};
            border:1px solid #e5e7eb;
            border-left:5px solid {color};
            border-radius:18px;
            padding:14px;
            box-shadow:0 6px 18px rgba(15,23,42,0.04);
        ">
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start;">
                <div>
                    <div style="font-size:17px;font-weight:900;color:#0f172a;">
                        {esc(platform)}
                    </div>
                    <div style="font-size:12px;font-weight:800;color:{color};margin-top:4px;">
                        {esc(label)}
                    </div>
                </div>

                <div style="
                    background:white;
                    border:1px solid #e2e8f0;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:13px;
                    font-weight:900;
                    color:#0f172a;
                ">
                    {count}
                </div>
            </div>

            <div style="
                margin-top:10px;
                font-size:13px;
                font-weight:800;
                color:#475569;
                line-height:1.45;
            ">
                Lehte: {positive_count} • Aleyhte: {negative_count} • Nötr: {neutral_count}
                <br>
                Beğeni: {int(likes)} • Yorum: {int(comments)} • Paylaşım: {int(shares)}
                <br>
                Görüntülenme: {int(views)}
            </div>

            <div style="
                margin-top:10px;
                background:white;
                border:1px solid #e2e8f0;
                border-radius:14px;
                padding:10px;
                font-size:12px;
                font-weight:800;
                color:#334155;
                line-height:1.4;
            ">
                <b>Kısa yorum:</b> {esc(platform_comment)}
            </div>

            {featured_link_html}
        </div>
        """

    return f"""
    <div id="platform-sosyal-nabiz" style="
        background:white;
        border:1px solid #e5e7eb;
        border-radius:22px;
        padding:16px;
        margin:14px 0 16px 0;
    ">
        <div style="
            display:flex;
            align-items:center;
            gap:10px;
            margin-bottom:12px;
        ">
            <div style="font-size:24px;">📱</div>
            <div>
                <div style="font-size:20px;font-weight:900;color:#0f172a;">
                    Platform Bazlı Sosyal Nabız
                </div>
                <div style="font-size:13px;font-weight:700;color:#64748b;">
                    Özet gününde sosyal medya platformlarının kayıt, risk, fırsat ve etkileşim durumu
                </div>
            </div>
        </div>

        <div style="
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
            gap:10px;
        ">
            {cards_html}
        </div>
    </div>
    """

def build_news_pool_summary_html(news):
    total_news = len(news)

    positive_count = 0
    neutral_count = 0
    risk_count = 0

    for item in news:
        tone_text = normalize_text(f"{item.get('tone', '')} {item.get('sentiment', '')}")
        risk_score = safe_score_value(item.get("risk", item.get("risk_score", 0)))

        if risk_score >= 6 or "risk" in tone_text or "kotu" in tone_text or "kötü" in tone_text:
            risk_count += 1
        elif "olumlu" in tone_text or "positive" in tone_text or "iyi" in tone_text:
            positive_count += 1
        else:
            neutral_count += 1

    if total_news == 0:
        general_note = "Son 7 günlük haber havuzunda kayıt bulunamadı."
        border_color = "#64748b"
    elif risk_count > positive_count:
        general_note = "Riskli başlıklar olumlu görünürlükten daha baskın. Haber dili yakından takip edilmeli."
        border_color = "#ef4444"
    elif positive_count >= risk_count:
        general_note = "Olumlu görünürlük riskli başlıklardan güçlü. Hizmet ve fırsat başlıkları öne çıkarılabilir."
        border_color = "#3b82f6"
    else:
        general_note = "Genel haber görünümü dengeli. Kritik başlıklar ayrıca takip edilmeli."
        border_color = "#64748b"

    return f"""
    <details id="son-7-gun-haber-havuzu" style="
        background:linear-gradient(180deg,rgba(255,255,255,0.09),rgba(255,255,255,0.045));
        border:1px solid rgba(255,255,255,0.12);
        border-left:6px solid {border_color};
        border-radius:22px;
        padding:0;
        margin:14px 0 16px 0;
        overflow:hidden;
        box-shadow:0 14px 34px rgba(0,0,0,0.28);
    ">
        <summary style="
            cursor:pointer;
            list-style:none;
            padding:16px;
            font-size:20px;
            font-weight:950;
            color:#f8fafc;
            line-height:1.35;
        ">
            📰 Son 7 Gün Haber Havuzu / Genel Algı
            <div style="
                font-size:13px;
                font-weight:750;
                color:#94a3b8;
                margin-top:6px;
                line-height:1.35;
            ">
                Toplam {total_news} haber • {positive_count} olumlu • {neutral_count} nötr • {risk_count} riskli
            </div>
        </summary>

        <div style="padding:0 16px 16px 16px;">
            <div style="
                display:grid;
                grid-template-columns:repeat(2,minmax(0,1fr));
                gap:10px;
                margin-bottom:12px;
            ">
                <div style="
                    background:rgba(15,23,42,0.78);
                    border:1px solid rgba(255,255,255,0.08);
                    border-radius:16px;
                    padding:12px;
                ">
                    <div style="font-size:24px;font-weight:950;color:#f8fafc;">{total_news}</div>
                    <div style="font-size:12px;font-weight:750;color:#94a3b8;margin-top:4px;">Toplam haber</div>
                </div>

                <div style="
                    background:rgba(15,23,42,0.78);
                    border:1px solid rgba(34,197,94,0.22);
                    border-radius:16px;
                    padding:12px;
                ">
                    <div style="font-size:24px;font-weight:950;color:#22c55e;">{positive_count}</div>
                    <div style="font-size:12px;font-weight:750;color:#94a3b8;margin-top:4px;">Olumlu</div>
                </div>

                <div style="
                    background:rgba(15,23,42,0.78);
                    border:1px solid rgba(148,163,184,0.18);
                    border-radius:16px;
                    padding:12px;
                ">
                    <div style="font-size:24px;font-weight:950;color:#cbd5e1;">{neutral_count}</div>
                    <div style="font-size:12px;font-weight:750;color:#94a3b8;margin-top:4px;">Nötr</div>
                </div>

                <div style="
                    background:rgba(15,23,42,0.78);
                    border:1px solid rgba(239,68,68,0.22);
                    border-radius:16px;
                    padding:12px;
                ">
                    <div style="font-size:24px;font-weight:950;color:#ef4444;">{risk_count}</div>
                    <div style="font-size:12px;font-weight:750;color:#94a3b8;margin-top:4px;">Riskli</div>
                </div>
            </div>

            <div style="
                background:rgba(15,23,42,0.78);
                border:1px solid rgba(255,255,255,0.08);
                border-radius:16px;
                padding:12px;
                font-size:14px;
                font-weight:800;
                color:#cbd5e1;
                line-height:1.45;
            ">
                <b style="color:#f8fafc;">Genel yorum:</b> {esc(general_note)}
            </div>
        </div>
    </details>
    """

def build_president_visual_summary_html(summary_day, social, all_news):
    try:
        display_day = dt.datetime.strptime(str(summary_day), "%Y-%m-%d").strftime("%d-%m-%Y")
        end_day = dt.datetime.strptime(str(summary_day), "%Y-%m-%d").date()
    except Exception:
        display_day = str(summary_day)
        end_day = dt.date.today()

    # Sosyal duygu dağılımı
    social_items = [
        item for item in social
        if same_day(item.get("date", ""), summary_day)
    ]

    positive_count = len([x for x in social_items if social_tone_group(x) == "positive"])
    negative_count = len([x for x in social_items if social_tone_group(x) == "negative"])
    neutral_count = max(0, len(social_items) - positive_count - negative_count)
    social_total = len(social_items)

    if social_total > 0:
        positive_pct = (positive_count / social_total) * 100
        neutral_pct = (neutral_count / social_total) * 100
        negative_pct = (negative_count / social_total) * 100
        positive_end = positive_pct
        neutral_end = positive_pct + neutral_pct

        donut_bg = (
            f"conic-gradient("
            f"#22c55e 0 {positive_end:.1f}%, "
            f"#64748b {positive_end:.1f}% {neutral_end:.1f}%, "
            f"#ef4444 {neutral_end:.1f}% 100%"
            f")"
        )
        social_note = f"{positive_count} lehte • {neutral_count} nötr • {negative_count} aleyhte"

        social_visual_html = f"""
            <div style="
                background:linear-gradient(180deg,rgba(255,255,255,0.09),rgba(255,255,255,0.045));
                border:1px solid rgba(255,255,255,0.12);
                border-radius:18px;
                padding:14px;
                box-shadow:0 10px 24px rgba(0,0,0,0.20);
            ">
                <div style="font-size:15px;font-weight:900;color:#f8fafc;margin-bottom:10px;">
                    Sosyal Duygu Dağılımı
                </div>

                <div style="
                    display:flex;
                    align-items:center;
                    gap:14px;
                ">
                    <div style="
                        width:92px;
                        height:92px;
                        border-radius:50%;
                        background:{donut_bg};
                        position:relative;
                        flex:0 0 auto;
                    ">
                        <div style="
                            position:absolute;
                            inset:20px;
                            background:#111827;
                            border-radius:50%;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            font-size:18px;
                            font-weight:950;
                            color:#f8fafc;
                        ">
                            {social_total}
                        </div>
                    </div>

                    <div style="
                        font-size:13px;
                        font-weight:800;
                        color:#cbd5e1;
                        line-height:1.55;
                    ">
                        <div><span style="color:#22c55e;">●</span> Lehte: {positive_count}</div>
                        <div><span style="color:#94a3b8;">●</span> Nötr: {neutral_count}</div>
                        <div><span style="color:#ef4444;">●</span> Aleyhte: {negative_count}</div>
                        <div style="margin-top:6px;color:#94a3b8;">{esc(social_note)}</div>
                    </div>
                </div>
            </div>
        """
    else:
        social_visual_html = f"""
            <div style="
                background:linear-gradient(180deg,rgba(255,255,255,0.09),rgba(255,255,255,0.045));
                border:1px solid rgba(255,255,255,0.12);
                border-left:5px solid #7c3aed;
                border-radius:18px;
                padding:14px;
                box-shadow:0 10px 24px rgba(0,0,0,0.20);
            ">
                <div style="font-size:15px;font-weight:900;color:#f8fafc;margin-bottom:10px;">
                    Sosyal Duygu Dağılımı
                </div>

                <div style="
                    background:rgba(15,23,42,0.78);
                    border:1px solid rgba(255,255,255,0.08);
                    border-radius:14px;
                    padding:14px;
                    color:#cbd5e1;
                    font-size:14px;
                    font-weight:800;
                    line-height:1.45;
                ">
                    Bugün sosyal medya kaydı yok.
                    <br>
                    <span style="color:#94a3b8;font-weight:750;">
                        Sistem X ve YouTube takip havuzunu izlemeye devam ediyor.
                    </span>
                </div>
            </div>
        """

    # Son 7 gün haber trendi
    trend_days = []
    for i in range(6, -1, -1):
        day = end_day - dt.timedelta(days=i)
        day_iso = day.isoformat()
        day_label = day.strftime("%d-%m")

        count = len([
            item for item in all_news
            if same_day(item.get("parsed_date", item.get("date", "")), day_iso)
        ])

        trend_days.append({
            "iso": day_iso,
            "label": day_label,
            "count": count,
        })

    max_count = max([x["count"] for x in trend_days] + [1])

    bars_html = ""
    for day in trend_days:
        height = max(8, int((day["count"] / max_count) * 70)) if max_count else 8
        is_summary_day = day["iso"] == str(summary_day)
        bar_color = "#3b82f6" if is_summary_day else "#475569"

        bars_html += f"""
        <div style="
            flex:1;
            display:flex;
            flex-direction:column;
            align-items:center;
            justify-content:flex-end;
            min-width:28px;
        ">
            <div style="
                height:{height}px;
                width:16px;
                border-radius:999px 999px 4px 4px;
                background:{bar_color};
                box-shadow:0 8px 16px rgba(0,0,0,0.25);
            "></div>
            <div style="
                margin-top:6px;
                font-size:10px;
                font-weight:800;
                color:#94a3b8;
                white-space:nowrap;
            ">
                {esc(day["label"])}
            </div>
            <div style="
                font-size:11px;
                font-weight:900;
                color:#f8fafc;
            ">
                {day["count"]}
            </div>
        </div>
        """

    return f"""
    <div id="baskan-app-gorsel-ozet" style="
        background:linear-gradient(180deg,rgba(255,255,255,0.10),rgba(255,255,255,0.045));
        border:1px solid rgba(255,255,255,0.12);
        border-radius:22px;
        padding:16px;
        margin:14px 0 16px 0;
        box-shadow:0 14px 34px rgba(0,0,0,0.30);
    ">
        <div style="
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:10px;
            margin-bottom:14px;
        ">
            <div>
                <div style="font-size:20px;font-weight:950;color:#f8fafc;">
                    Bugünün Görsel Özeti
                </div>
                <div style="font-size:13px;font-weight:750;color:#94a3b8;margin-top:4px;">
                    Haber, sosyal medya ve Başkan X performansı kısa görünüm
                </div>
            </div>
            <div style="font-size:26px;">📱</div>
        </div>

        <div style="
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
            gap:12px;
        ">
            {social_visual_html}

            <div style="
                background:linear-gradient(180deg,rgba(255,255,255,0.09),rgba(255,255,255,0.045));
                border:1px solid rgba(255,255,255,0.12);
                border-radius:18px;
                padding:14px;
                box-shadow:0 10px 24px rgba(0,0,0,0.20);
            ">
                <div style="font-size:15px;font-weight:900;color:#f8fafc;margin-bottom:10px;">
                    Son 7 Gün Haber Trendi
                </div>

                <div style="
                    height:112px;
                    display:flex;
                    align-items:flex-end;
                    gap:7px;
                    padding:4px 0 0 0;
                ">
                    {bars_html}
                </div>
            </div>
        </div>
    </div>
    """

def president_dashboard_panel(today, report_time, news, social, president_posts, crisis_plan, early_warning, opportunity_sum=None, all_news=None):
    opportunity_sum = opportunity_sum or {}
    all_news = all_news if all_news is not None else news
    try:
        display_day = dt.datetime.strptime(str(today), "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        display_day = str(today)
    
    today_news = [
        item for item in news
        if same_day(item.get("parsed_date", item.get("date", "")), today)
    ]

    today_x = [
        item for item in social
        if same_day(item.get("date", ""), today) and is_x_platform(item)
    ]

    today_youtube = [
        item for item in social
        if same_day(item.get("date", ""), today) and is_youtube_platform(item)
    ]

    all_x_dashboard = [
        item for item in social
        if is_x_platform(item)
    ]

    all_youtube_dashboard = [
        item for item in social
        if is_youtube_platform(item)
    ]

    today_president_posts = [
        item for item in president_posts
        if same_day(item.get("date", ""), today)
    ]

    x_positive = len([
        item for item in today_x
        if "iyi" in normalize_text(item.get("tone", "")) or "positive" in normalize_text(item.get("sentiment", ""))
    ])
    x_negative = len([
        item for item in today_x
        if "kotu" in normalize_text(item.get("tone", "")) or "negative" in normalize_text(item.get("sentiment", ""))
    ])
    x_neutral = max(0, len(today_x) - x_positive - x_negative)

    yt_positive = len([
        item for item in today_youtube
        if "iyi" in normalize_text(item.get("tone", "")) or "positive" in normalize_text(item.get("sentiment", ""))
    ])
    yt_negative = len([
        item for item in today_youtube
        if "kotu" in normalize_text(item.get("tone", "")) or "negative" in normalize_text(item.get("sentiment", ""))
    ])
    yt_neutral = max(0, len(today_youtube) - yt_positive - yt_negative)

    x_likes = sum(safe_score_value(item.get("likes", 0)) for item in today_x)
    x_comments = sum(safe_score_value(item.get("comments", 0)) for item in today_x)
    x_views = sum(safe_score_value(item.get("views", 0)) for item in today_x)

    yt_likes = sum(safe_score_value(item.get("likes", 0)) for item in today_youtube)
    yt_comments = sum(safe_score_value(item.get("comments", 0)) for item in today_youtube)
    yt_views = sum(safe_score_value(item.get("views", 0)) for item in today_youtube)

    president_engagement = sum(safe_score_value(item.get("engagement", 0)) for item in today_president_posts)
    president_likes = sum(safe_score_value(item.get("likes", 0)) for item in today_president_posts)
    president_replies = sum(safe_score_value(item.get("replies", 0)) for item in today_president_posts)
    president_reposts = sum(safe_score_value(item.get("reposts", 0)) for item in today_president_posts)
    president_quotes = sum(safe_score_value(item.get("quotes", 0)) for item in today_president_posts)

    president_max_metric = max(
        president_likes,
        president_replies,
        president_reposts,
        president_quotes,
        1
    )

    president_likes_pct = int((president_likes / president_max_metric) * 100)
    president_replies_pct = int((president_replies / president_max_metric) * 100)
    president_reposts_pct = int((president_reposts / president_max_metric) * 100)
    president_quotes_pct = int((president_quotes / president_max_metric) * 100)

    risk_level = str(crisis_plan.get("level", "") or "")
    risk_norm = normalize_text(risk_level)
    
    risk_topic_short = clean_text(crisis_plan.get("risk_topic", "") or "Bugünün ana başlığı belirlenemedi.")

    if len(risk_topic_short) > 95:
        risk_topic_short = risk_topic_short[:95] + "..."

    crisis_pulse = ""
    if "yuksek" in risk_norm or "yüksek" in risk_norm:
        crisis_pulse = "president-pulse"

    top_risk_news = ""
    # Buraya artık sadece özet günü haberleri gönderiliyor.
    risky_news = sorted(news, key=lambda x: safe_score_value(x.get("risk", 0)), reverse=True)
    if risky_news:
        top_risk_news = risky_news[0].get("title", "")

    top_opportunity_news = ""
    opportunity_news = sorted(news, key=lambda x: safe_score_value(x.get("opportunity", 0)), reverse=True)
    if opportunity_news:
        top_opportunity_news = opportunity_news[0].get("title", "")
        
    if today_president_posts:
        president_x_graph_html = f"""
        <div id="baskan-x-performans-grafik" style="
            background:#f0fdf4;
            border:1px solid #bbf7d0;
            border-left:6px solid #059669;
            border-radius:20px;
            padding:16px;
            margin:14px 0 16px 0;
        ">
            <div style="font-size:18px;font-weight:900;color:#064e3b;margin-bottom:6px;">
                👤 Başkan X Performans Grafiği
            </div>

            <div style="font-size:13px;font-weight:700;color:#64748b;margin-bottom:12px;line-height:1.35;">
                Bugün {len(today_president_posts)} Başkan X gönderisi analiz edildi.
                Toplam etkileşim: {int(president_engagement)}
            </div>

            <div style="margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;font-size:13px;font-weight:800;color:#334155;">
                    <span>Beğeni</span><span>{int(president_likes)}</span>
                </div>
                <div style="height:10px;background:#dcfce7;border-radius:999px;overflow:hidden;margin-top:5px;">
                    <div style="height:10px;width:{president_likes_pct}%;background:#16a34a;border-radius:999px;"></div>
                </div>
            </div>

            <div style="margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;font-size:13px;font-weight:800;color:#334155;">
                    <span>Repost</span><span>{int(president_reposts)}</span>
                </div>
                <div style="height:10px;background:#dcfce7;border-radius:999px;overflow:hidden;margin-top:5px;">
                    <div style="height:10px;width:{president_reposts_pct}%;background:#16a34a;border-radius:999px;"></div>
                </div>
            </div>

            <div style="margin-bottom:10px;">
                <div style="display:flex;justify-content:space-between;font-size:13px;font-weight:800;color:#334155;">
                    <span>Yanıt</span><span>{int(president_replies)}</span>
                </div>
                <div style="height:10px;background:#dcfce7;border-radius:999px;overflow:hidden;margin-top:5px;">
                    <div style="height:10px;width:{president_replies_pct}%;background:#16a34a;border-radius:999px;"></div>
                </div>
            </div>

            <div>
                <div style="display:flex;justify-content:space-between;font-size:13px;font-weight:800;color:#334155;">
                    <span>Alıntı / Quote</span><span>{int(president_quotes)}</span>
                </div>
                <div style="height:10px;background:#dcfce7;border-radius:999px;overflow:hidden;margin-top:5px;">
                    <div style="height:10px;width:{president_quotes_pct}%;background:#16a34a;border-radius:999px;"></div>
                </div>
            </div>
        </div>
        """
    else:
        president_x_graph_html = f"""
        <div id="baskan-x-performans-grafik" style="
            background:#f8fafc;
            border:1px solid #e2e8f0;
            border-left:6px solid #64748b;
            border-radius:20px;
            padding:16px;
            margin:14px 0 16px 0;
            color:#334155;
            font-weight:800;
            line-height:1.45;
        ">
            👤 Bugün Başkan X gönderisi bulunamadı.
            <br>
            <span style="color:#64748b;font-weight:700;">
                Gönderi geldiğinde performans grafiği burada görünecek.
            </span>
        </div>
        """
        
    news_pool_summary_html = build_news_pool_summary_html(all_news)
    president_visual_summary_html = build_president_visual_summary_html(today, social, all_news)
    platform_social_pulse_html = build_platform_social_pulse_html(social, today)

    if today_x:
        x_nabiz_html = f"""
        {dashboard_bar("Lehte", x_positive, len(today_x), "#16a34a")}
        {dashboard_bar("Nötr", x_neutral, len(today_x), "#64748b")}
        {dashboard_bar("Aleyhte", x_negative, len(today_x), "#dc2626")}

        <p style="font-size:14px;color:#475569;">
            X toplam görüntülenme: <b>{int(x_views)}</b> • Beğeni: <b>{int(x_likes)}</b> • Yorum: <b>{int(x_comments)}</b>
        </p>
        """
    else:
        x_nabiz_html = f"""
        <div style="
            background:#f8fafc;
            border:1px solid #e2e8f0;
            border-left:5px solid #7c3aed;
            border-radius:16px;
            padding:12px;
            margin:10px 0;
            color:#334155;
            font-weight:800;
            line-height:1.45;
        ">
            Bugün X kaydı yok.
            <br>
            <span style="color:#64748b;font-weight:700;">
                Takip havuzunda {len(all_x_dashboard)} X kaydı var. Sistem izlemeye devam ediyor.
            </span>
        </div>
        """

    if today_youtube:
        youtube_nabiz_html = f"""
        {dashboard_bar("Lehte", yt_positive, len(today_youtube), "#16a34a")}
        {dashboard_bar("Nötr", yt_neutral, len(today_youtube), "#64748b")}
        {dashboard_bar("Aleyhte", yt_negative, len(today_youtube), "#dc2626")}

        <p style="font-size:14px;color:#475569;">
            YouTube toplam görüntülenme: <b>{int(yt_views)}</b> • Beğeni: <b>{int(yt_likes)}</b> • Yorum: <b>{int(yt_comments)}</b>
        </p>
        """
    else:
        youtube_nabiz_html = f"""
        <div style="
            background:#fff7ed;
            border:1px solid #fed7aa;
            border-left:5px solid #dc2626;
            border-radius:16px;
            padding:12px;
            margin:8px 0 0 0;
            color:#334155;
            font-weight:800;
            line-height:1.45;
        ">
            Bugün YouTube kaydı yok.
            <br>
            <span style="color:#64748b;font-weight:700;">
                Takip havuzunda {len(all_youtube_dashboard)} YouTube kaydı var. Sistem izlemeye devam ediyor.
            </span>
        </div>
        """

    opportunity_level = str(opportunity_sum.get("level", "Fırsat yok"))
    opportunity_title = str(opportunity_sum.get("title", "Özet gününde belirgin fırsat görünmüyor."))
    opportunity_title_display = opportunity_title
    if "_" in opportunity_title or normalize_text(opportunity_title) in [
        "cocuk aile",
        "mali disiplin",
        "hizmet asfalt",
        "spor etkinlik",
        "teleferik davasi",
        "buyuksehir ulasim",
        "bayrak personel",
    ]:
        opportunity_title_display = clean_topic_title(opportunity_title)
    opportunity_source = str(opportunity_sum.get("source", "Genel takip"))
    opportunity_type = str(opportunity_sum.get("type", "Genel PR / görünürlük fırsatı"))
    opportunity_owner = str(opportunity_sum.get("owner", "Basın birimi"))
    opportunity_reason = str(opportunity_sum.get("reason", "Fırsat değerlendirmesi yapılmadı."))
    opportunity_action = str(opportunity_sum.get("action", "Standart takip yeterli."))
    opportunity_format = str(opportunity_sum.get("format", "Standart takip"))
    opportunity_notify = str(opportunity_sum.get("notify", "Bildirim gerekmez."))
    opportunity_score = safe_score_value(opportunity_sum.get("score", 0))
    opportunity_alarm = bool(opportunity_sum.get("alarm", False))
    opportunity_alarm_label = str(opportunity_sum.get("alarm_label", "Günlük fırsat"))
    opportunity_mail_candidate = str(opportunity_sum.get("mail_candidate", "Hayır"))
    opportunity_whatsapp_candidate = str(opportunity_sum.get("whatsapp_candidate", "Hayır"))
    opportunity_alarm_reason = str(opportunity_sum.get("alarm_reason", "Bildirim gerekmez."))

    opportunity_norm = normalize_text(opportunity_level)

    if "yuksek" in opportunity_norm or "yüksek" in opportunity_norm:
        opportunity_color = "#16a34a"
        opportunity_bg = "#ecfdf5"
        opportunity_border = "#86efac"
    elif "takip" in opportunity_norm:
        opportunity_color = "#d97706"
        opportunity_bg = "#fffbeb"
        opportunity_border = "#fed7aa"
    else:
        opportunity_color = "#64748b"
        opportunity_bg = "#f8fafc"
        opportunity_border = "#e2e8f0"

    if opportunity_alarm:
        opportunity_alarm_html = f"""
        <div style="
            background:#ecfdf5;
            border:1px solid #86efac;
            border-left:6px solid #16a34a;
            border-radius:14px;
            padding:12px;
            margin:10px 0;
            color:#065f46;
            font-size:14px;
            font-weight:900;
            line-height:1.45;
        ">
            🚀 {esc(opportunity_alarm_label)}<br>
            <span style="font-weight:800;color:#047857;">
                Mail adayı: {esc(opportunity_mail_candidate)} • WhatsApp/app adayı: {esc(opportunity_whatsapp_candidate)}
            </span>
            <br>
            <span style="font-weight:700;color:#334155;">
                {esc(opportunity_alarm_reason)}
            </span>
        </div>
        """
    else:
        opportunity_alarm_html = f"""
        <div style="
            background:#f8fafc;
            border:1px solid #e2e8f0;
            border-left:6px solid #94a3b8;
            border-radius:14px;
            padding:12px;
            margin:10px 0;
            color:#334155;
            font-size:14px;
            font-weight:800;
            line-height:1.45;
        ">
            {esc(opportunity_alarm_label)}<br>
            <span style="font-weight:700;color:#64748b;">
                Mail adayı: {esc(opportunity_mail_candidate)} • WhatsApp/app adayı: {esc(opportunity_whatsapp_candidate)}
            </span>
            <br>
            <span style="font-weight:700;color:#64748b;">
                {esc(opportunity_alarm_reason)}
            </span>
        </div>
        """

    opportunity_source_details_html = ""
    try:
        opportunity_source_details_html = decision_source_details_html(
            "fırsat",
            opportunity_sum,
            opportunity_color
        )
    except Exception:
        opportunity_source_details_html = ""

    opportunity_card_html = f"""
    <div id="baskan-firsat" style="
        background:{opportunity_bg};
        border:1px solid {opportunity_border};
        border-left:6px solid {opportunity_color};
        border-radius:20px;
        padding:16px;
        margin:14px 0 16px 0;
    ">
        <div style="font-size:18px;font-weight:900;color:{opportunity_color};margin-bottom:6px;">
            🌟 Bugünün Fırsatı
        </div>

        <div style="font-size:13px;font-weight:800;color:#64748b;margin-bottom:10px;line-height:1.35;">
            Seviye: {esc(opportunity_level)} • Skor: {esc(opportunity_score)}/10 • Kaynak: {esc(opportunity_source)}
        </div>

        <div style="font-size:16px;font-weight:900;color:#0f172a;line-height:1.35;margin-bottom:10px;">
           {esc(opportunity_title_display)}
        </div>

        <details style="
            background:white;
            border:1px solid {opportunity_border};
            border-radius:14px;
            padding:10px 12px;
            margin:10px 0;
        ">
            <summary style="
                cursor:pointer;
                font-size:13px;
                font-weight:900;
                color:{opportunity_color};
                list-style:none;
            ">
                Bu fırsat nereden geldi?
            </summary>

            <div style="
                margin-top:10px;
                color:#334155;
                font-size:13px;
                font-weight:750;
                line-height:1.45;
            ">
                <div><b>Kaynak:</b> {esc(opportunity_source)}</div>
                <div><b>Başlık:</b> {esc(opportunity_title_display)}</div>
                <div style="margin-top:8px;"><b>Neden fırsat?</b> {esc(opportunity_reason)}</div>
                <div style="margin-top:8px;"><b>Önerilen aksiyon:</b> {esc(opportunity_action)}</div>
            </div>
        </details>

        {opportunity_alarm_html}

        <div style="
            background:white;
            border:1px solid {opportunity_border};
            border-radius:14px;
            padding:12px;
            margin-bottom:10px;
            color:#334155;
            font-size:14px;
            font-weight:700;
            line-height:1.45;
        ">
            <b>Neden önemli?</b><br>
            {esc(opportunity_reason)}
        </div>

        <div style="
            background:white;
            border:1px solid {opportunity_border};
            border-radius:14px;
            padding:12px;
            margin-bottom:10px;
            color:#334155;
            font-size:14px;
            font-weight:700;
            line-height:1.45;
        ">
            <b>Önerilen aksiyon</b><br>
            {esc(opportunity_action)}
        </div>

        <div style="
            display:grid;
            grid-template-columns:1fr;
            gap:8px;
            color:#334155;
            font-size:13px;
            font-weight:800;
            line-height:1.35;
        ">
            <div><b>Fırsat türü:</b> {esc(opportunity_type)}</div>
            <div><b>Kim hareket etmeli?</b> {esc(opportunity_owner)}</div>
            <div><b>Önerilen format:</b> {esc(opportunity_format)}</div>
            <div><b>Bildirim kararı:</b> {esc(opportunity_notify)}</div>
        </div>
    </div>
    """

    decision_raw = str(early_warning.get("decision", "") or "")
    decision_upper = decision_raw.upper()

    high_risk = (
        "yuksek" in risk_norm
        or "yüksek" in risk_norm
        or "cok yuksek" in risk_norm
        or "çok yüksek" in risk_norm
    )

    medium_risk = "orta" in risk_norm

    strong_opportunity = (
        opportunity_alarm
        or opportunity_score >= 6
        or "yuksek" in opportunity_norm
        or "yüksek" in opportunity_norm
    )

    if high_risk:
        decision_card_html = f"""
        <div id="baskan-ozet" class="{crisis_pulse}" style="
            background:#fff;
            border:2px solid #b91c1c;
            border-left:7px solid #b91c1c;
            border-radius:22px;
            padding:16px;
            margin-bottom:16px;
        ">
            <div style="font-size:14px;font-weight:900;color:#64748b;line-height:1.45;">
                Kepez — {esc(display_day)} — ⚠️ Yüksek Risk
            </div>

            <div style="font-size:26px;font-weight:950;color:#991b1b;margin-top:10px;line-height:1.2;">
                Risk: {esc(risk_level)}
            </div>

            <div style="font-size:15px;font-weight:900;color:#0f172a;margin-top:10px;line-height:1.4;">
                Konu: {esc(risk_topic_short)}
            </div>

            <div style="
                background:#fef2f2;
                border:1px solid #fecaca;
                border-radius:14px;
                padding:12px;
                margin-top:12px;
                font-size:15px;
                font-weight:900;
                color:#7f1d1d;
                line-height:1.45;
            ">
                Şu an konuşma. Ekip takipte.
                <br>
                <span style="font-size:13px;font-weight:800;color:#991b1b;">
                    Detay ve aksiyon planı ekip raporu / kriz panelinde.
                </span>
            </div>
        </div>
        """

    elif medium_risk:
        decision_card_html = f"""
        <div id="baskan-ozet" style="
            background:linear-gradient(135deg,rgba(245,158,11,0.22),rgba(15,23,42,0.96));
            border:1.5px solid rgba(245,158,11,0.85);
            border-left:7px solid #f59e0b;
            border-radius:22px;
            padding:16px;
            margin-bottom:16px;
            box-shadow:0 14px 34px rgba(0,0,0,0.32);
        ">
            <div style="font-size:14px;font-weight:900;color:#fbbf24;line-height:1.4;">
                Kepez — {esc(display_day)} — 🟠 Takipte
            </div>

            <div style="font-size:25px;font-weight:950;color:#fef3c7;margin-top:10px;line-height:1.25;">
                Risk: {esc(risk_level)}
            </div>

            <div style="font-size:15px;font-weight:900;color:#f8fafc;margin-top:10px;line-height:1.45;">
                Konu: {esc(risk_topic_short)}
            </div>

            <div style="
                background:rgba(255,255,255,0.08);
                border:1px solid rgba(251,191,36,0.28);
                border-radius:15px;
                padding:12px;
                margin-top:12px;
                font-size:14px;
                font-weight:850;
                color:#e5e7eb;
                line-height:1.45;
            ">
                Ekip izlesin. Konu büyürse kriz paneli açılmalı.
            </div>
        </div>
        """

    elif strong_opportunity:
        decision_card_html = f"""
        <div id="baskan-ozet" style="
            background:#ecfdf5;
            border:2px solid #16a34a;
            border-left:7px solid #16a34a;
            border-radius:22px;
            padding:16px;
            margin-bottom:16px;
        ">

            <div style="font-size:24px;font-weight:950;color:#166534;margin-top:10px;line-height:1.25;">
                Güçlü fırsat tespit edildi
            </div>

            <div style="font-size:15px;font-weight:900;color:#0f172a;margin-top:10px;line-height:1.4;">
               {esc(opportunity_title_display)}
            </div>

            <div style="
                background:white;
                border:1px solid #bbf7d0;
                border-radius:14px;
                padding:11px;
                margin-top:10px;
                font-size:14px;
                font-weight:850;
                color:#334155;
                line-height:1.45;
            ">
                Ekip uygun formatı hazırlasın. Detay fırsat kartında.
            </div>
            
            {opportunity_source_details_html}
            
        </div>
        """

    else:
        decision_card_html = f"""
        <div id="baskan-ozet" style="
            background:#f8fafc;
            border:1.5px solid #cbd5e1;
            border-left:7px solid #64748b;
            border-radius:20px;
            padding:15px;
            margin-bottom:14px;
        ">
            <div style="font-size:14px;font-weight:900;color:#475569;line-height:1.4;">
                Kepez — {esc(display_day)} — Normal Takip
            </div>

            <div style="font-size:22px;font-weight:950;color:#0f172a;margin-top:8px;line-height:1.25;">
                Kritik durum yok
            </div>

            <div style="font-size:14px;font-weight:800;color:#64748b;margin-top:8px;line-height:1.4;">
                Günlük haber, X ve sosyal medya takibi devam ediyor.
            </div>
        </div>
        """
    if not high_risk and not medium_risk and not strong_opportunity:
        decision_card_html = ""

    today_social_total = len(today_x) + len(today_youtube)

    if today_social_total:
        social_kpi_note = f"X {len(today_x)} • YouTube {len(today_youtube)}"
    else:
        social_kpi_note = f"Bugün kayıt yok • Takip havuzu {len(all_x_dashboard) + len(all_youtube_dashboard)}"

    alarm_decision = str(early_warning.get("decision", "") or "NORMAL TAKİP")
    alarm_decision_upper = alarm_decision.upper()

    if "ACİL" in alarm_decision_upper or "ACIL" in alarm_decision_upper:
        alarm_value = "Alarm"
        alarm_note = f"Risk {risk_level} • Başkan konuşmasın"
        alarm_color = "#b91c1c"
        alarm_bg = "#fef2f2"
    elif "TAKİPTE" in alarm_decision_upper:
        alarm_value = "Takipte"
        alarm_note = f"Risk {risk_level} • Ekip izliyor"
        alarm_color = "#d97706"
        alarm_bg = "#fffbeb"
    else:
        alarm_value = "Normal"
        alarm_note = "Kritik alarm yok"
        alarm_color = "#64748b"
        alarm_bg = "#f8fafc"
        
    return f"""
    <style>
        html, body {{
            max-width: 100%;
            overflow-x: hidden;
        }}

        * {{
            box-sizing: border-box;
        }}

        img, video {{
            max-width: 100%;
        }}

        table {{
            display: block;
            width: 100%;
            max-width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}

        @media (max-width: 700px) {{
            body {{
                margin: 0;
                overflow-x: hidden;
            }}

            .container {{
                width: 100% !important;
                max-width: 100% !important;
                padding-left: 12px !important;
                padding-right: 12px !important;
            }}

            header {{
                width: 100% !important;
                max-width: 100% !important;
            }}
        }}
    </style>
    <style>
        @keyframes presidentPulse {{
            0% {{ box-shadow:0 0 0 0 rgba(185,28,28,0.45); }}
            70% {{ box-shadow:0 0 0 14px rgba(185,28,28,0); }}
            100% {{ box-shadow:0 0 0 0 rgba(185,28,28,0); }}
        }}

        .president-pulse {{
            animation: presidentPulse 1.4s infinite;
        }}

        .president-mobile-nav {{
            position: sticky;
            top: 0;
            z-index: 20;
            display:flex;
            gap:8px;
            overflow-x:auto;
            padding:10px 0;
            background:transparent;

        }}

        .president-mobile-nav a {{
            white-space:nowrap;
            text-decoration:none;
            background:rgba(255,255,255,0.10);
            color:#f8fafc;
            border:1px solid rgba(255,255,255,0.14);
            padding:9px 12px;
            border-radius:999px;
            font-size:13px;
            font-weight:800;

        }}

        .president-dashboard-layout {{
            display:block;
        }}

        .president-side-nav {{
            display:none;
        }}

        @media (min-width: 900px) {{
            .president-dashboard-layout {{
                display:grid;
                grid-template-columns:220px 1fr;
                gap:18px;
                align-items:start;
            }}

            .president-mobile-nav {{
                display:none;
            }}

            .president-side-nav {{
                display:block;
                position:sticky;
                top:18px;
                background:#0f172a;
                color:white;
                border-radius:20px;
                padding:16px;
            }}

            .president-side-nav a {{
                display:block;
                color:white;
                text-decoration:none;
                font-weight:800;
                padding:10px 8px;
                border-bottom:1px solid rgba(255,255,255,0.12);
            }}
        }}
    </style>

        <div style="
             background:linear-gradient(180deg,#0b1020 0%,#111827 48%,#0f172a 100%);
             border:1px solid rgba(255,255,255,0.10);
             border-radius:24px;
             padding:14px;
             margin:18px 0 24px 0;
             box-shadow:0 22px 55px rgba(0,0,0,0.38);
             color:#f8fafc;
        ">
        <div class="president-mobile-nav">
            <a href="#baskan-ozet">Özet</a>
            <a href="#baskan-haber">Haber</a>
            <a href="#baskan-x">X</a>
            <a href="#baskan-youtube">YouTube</a>
            <a href="#baskan-kriz">Kriz</a>
            <a href="team_report.html">Ekip</a>
        </div>

        <div class="president-dashboard-layout">
            <div class="president-side-nav">
                <div style="font-size:18px;font-weight:900;margin-bottom:12px;">Başkan Paneli</div>
                <a href="#baskan-ozet">Genel Özet</a>
                <a href="#baskan-haber">Haber Nabzı</a>
                <a href="#baskan-x">X Nabzı</a>
                <a href="#baskan-youtube">YouTube</a>
                <a href="#baskan-kriz">Kriz / Alarm</a>
                <a href="team_report.html">Ekip Raporu</a>
            </div>

            <div>
                
                {decision_card_html}
                
                <div style="
                     background:rgba(15,23,42,0.72);
                     border:1px solid rgba(255,255,255,0.08);
                     border-radius:20px;
                     padding:12px;
                     margin:0 0 12px 0;
                     font-size:13px;
                     font-weight:800;
                     color:#f8fafc;
                     line-height:1.4;
                     box-shadow:inset 0 1px 0 rgba(255,255,255,0.04);
                 ">

                <div style="
                    display:grid;
                    grid-template-columns:repeat(2,minmax(0,1fr));
                    gap:12px;
                    margin-bottom:16px;
                ">
                <a href="#detay-haberler" style="text-decoration:none;color:inherit;display:block;">
                    {dashboard_kpi("Bugünün Haberleri", len(today_news), f"Son 7 gün tarandı • bugün {len(today_news)} haber", "#2563eb", "#eff6ff")}
                </a>
                
                <a href="#detay-social" style="text-decoration:none;color:inherit;display:block;">
                    {dashboard_kpi("Bugünün Sosyal Nabzı", today_social_total, social_kpi_note, "#7c3aed", "#f5f3ff")}
                </a>
                
                <a href="#baskan-kriz" style="text-decoration:none;color:inherit;display:block;">
                     {dashboard_kpi("Kriz / Alarm", alarm_value, alarm_note, alarm_color, alarm_bg)}
            
                </a>
                    
                <a href="#detay-baskan-x" style="text-decoration:none;color:inherit;display:block;">
                    {dashboard_kpi("Başkan X Performansı", len(today_president_posts), f"Etkileşim {int(president_engagement)} • Yanıt {int(president_replies)}", "#059669", "#ecfdf5")}
                 </a>
                
                </div>

                      {president_visual_summary_html}

                     {news_pool_summary_html}
                    
                     <div id="detay-baskan-x"></div>
                     {president_x_graph_html}
                      
                     {opportunity_card_html}
                    
                     {platform_social_pulse_html}

                <div id="baskan-haber" style="
                    background:white;
                    border:1px solid #e5e7eb;
                    border-radius:22px;
                    padding:16px;
                    margin:14px 0;
                ">
                    <div style="
                        display:flex;
                        align-items:center;
                        gap:10px;
                        margin:0 0 12px 0;
                    ">
                        <div style="font-size:24px;">📊</div>
                        <div>
                            <div style="font-size:20px;font-weight:900;color:#0f172a;">
                                Günlük Haber ve Sosyal Nabız
                            </div>
                            <div style="font-size:13px;font-weight:700;color:#64748b;">
                                Özet günü için risk, fırsat ve sosyal hareket özeti
                            </div>
                        </div>
                    </div>

                    <div style="
                        display:grid;
                        grid-template-columns:1fr;
                        gap:10px;
                        margin:0 0 10px 0;
                    ">
                        <div style="
                            background:#fef2f2;
                            border:1px solid #fecaca;
                            border-left:5px solid #dc2626;
                            border-radius:16px;
                            padding:12px;
                        ">
                            <div style="font-size:13px;font-weight:900;color:#991b1b;margin-bottom:5px;">
                                Özet gününün risk başlığı
                            </div>
                            <div style="font-size:14px;font-weight:800;color:#334155;line-height:1.35;">
                                {esc(top_risk_news or "Özet gününde öne çıkan risk haberi yok.")}
                            </div>
                        </div>

                        <div style="
                            background:#ecfdf5;
                            border:1px solid #bbf7d0;
                            border-left:5px solid #16a34a;
                            border-radius:16px;
                            padding:12px;
                        ">
                            <div style="font-size:13px;font-weight:900;color:#166534;margin-bottom:5px;">
                                Özet gününün fırsat başlığı
                            </div>
                            <div style="font-size:14px;font-weight:800;color:#334155;line-height:1.35;">
                                {esc(top_opportunity_news or "Özet gününde öne çıkan fırsat haberi yok.")}
                            </div>
                        </div>
                    </div>

                    <div id="baskan-x" style="margin-top:8px;">
                        <h3>X Nabzı</h3>
                        {x_nabiz_html}
                    </div>

                   <div id="baskan-youtube" style="margin-top:8px;">
                        <h3>YouTube Nabzı</h3>
                        {youtube_nabiz_html}
                    </div>

                    <div id="baskan-kriz" style="
                        margin-top:16px;
                        padding:14px;
                        border-radius:18px;
                        background:#fef2f2;
                        border:1px solid #fecaca;
                        color:#7f1d1d;
                        font-weight:800;
                    ">
                        Kriz / alarm: {esc(early_warning.get("decision", ""))}. Detay gerekiyorsa kriz paneli veya ekip raporu açılmalı.
                    </div>
                </div>
            </div>
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

def classify_president_x_post(item):
    content = str(item.get("content", "") or "")
    topic = str(item.get("topic", "") or "")
    text = normalize_text(f"{content} {topic}")

    engagement = safe_score_value(item.get("engagement", 0))
    replies = safe_score_value(item.get("replies", 0))
    likes = safe_score_value(item.get("likes", 0))

    if any(term in text for term in ["teleferik", "dava", "mahkeme", "sorusturma", "soruşturma", "hukuk", "yargi", "yargı", "tutuklama"]):
        post_class = "Kriz / hukuki hassasiyet"
        communication_note = "Hassas konu. Yorumlar ve alıntılar izlenmeli; açıklama dili kontrollü ve belgeye dayalı olmalı."
    elif any(term in text for term in ["7 gun", "7 gün", "bir hafta", "haftalik", "haftalık", "hafta nasil gecti", "hafta nasıl geçti", "nasil gecti", "nasıl geçti", "gelecegi kepez", "geleceği kepez", "kepezde 7 gun", "kepezde 7 gün", "kepez de 7 gun", "kepez de 7 gün"]):
        post_class = "Haftalık hizmet özeti / kurumsal iletişim"
        communication_note = "Haftalık hizmet özeti niteliğinde içerik. Hizmetlerin toplu görünürlüğü için değerli; kısa video, mahalle adı, önce-sonra görseli ve somut sonuç diliyle güçlendirilebilir."

    elif any(term in text for term in ["meclis", "meclis toplantisi", "meclis toplantısı", "gundem maddesi", "gündem maddesi", "mayis ayi meclisi", "mayıs ayı meclisi", "belediye meclisi"]):
        post_class = "Kurumsal duyuru / meclis bilgilendirmesi"
        communication_note = "Kurumsal bilgilendirme içeriği. Sade, resmi ve anlaşılır dil korunmalı; vatandaşın anlayacağı kısa gündem özeti eklenirse erişim artabilir."
    elif any(term in text for term in [
        "yörük", "yoruk", "yoruk kultur", "yörük kültür",
        "topraklarin kadim", "toprakların kadim", "kadim deger", "kadim değer",
        "hidirellez", "hıdırellez",
        "kultur", "kültür",
        "senlik", "şenlik",
        "festival", "konser", "bayram", "kutlama", "anma", "nevruz",
        "yerel etkinlik", "gelenek", "kadim"
    ]):
        post_class = "Yerel kültür / toplum etkinliği"
        communication_note = (
            "Yerel kültür, mahalle aidiyeti ve sıcak toplum ilişkisi açısından değerli içerik. "
            "Gelenek, mahalle adı, katılım ve insan hikayesi vurgusu güçlendirilebilir."
        )
           
    elif any(term in text for term in ["video", "youtube", "youtu", "t co", "link", "canli yayin", "canlı yayın"]):
        post_class = "Video/link paylaşımı / kontrol edilecek içerik"
        communication_note = "Link veya video ağırlıklı paylaşım. İçeriğin ne anlattığı kısa bir cümleyle açıklanmalı; görsel başlık ve ilk cümle güçlendirilirse etkileşim artabilir."
    elif any(term in text for term in ["bas sagligi", "baş sağlığı", "bassagligi", "başsağlığı", "taziye", "vefat", "rahmet", "mekani cennet", "mekanı cennet", "gecmis olsun", "geçmiş olsun", "afet", "yangin", "yangın", "sel", "deprem", "firtina", "fırtına", "kaza", "yarali", "yaralı", "hayatini kaybeden", "hayatını kaybeden"]):
        post_class = "İnsani hassasiyet / taziye mesajı"
        communication_note = "Hassas ve insani duygu gerektiren içerik. Siyasi polemik dili kullanılmamalı; sade, samimi, acıyı paylaşan ve dayanışma vurgusu taşıyan bir dil korunmalı."
    elif any(term in text for term in ["borc", "borç", "mali", "butce", "bütçe", "tasarruf"]):
        post_class = "Mali disiplin / borç açıklaması"
        communication_note = "Mali konu olduğu için sade, rakamlı ve savunmacı olmayan dil tercih edilmeli."
    elif any(term in text for term in ["asfalt", "yol", "park", "temizlik", "cop", "çöp", "kaldirim", "kaldırım", "hizmet", "proje", "acilis", "açılış"]):
        post_class = "Hizmet / proje duyurusu"
        communication_note = "Hizmet görünürlüğü için değerli içerik. Fotoğraf, mahalle adı ve somut sonuç dili güçlendirilebilir."
    elif any(term in text for term in ["mahalle", "saha", "ziyaret", "vatandas", "vatandaş", "esnaf", "muhtar"]):
        post_class = "Mahalle / saha teması"
        communication_note = "Başkanın sahada ve ulaşılabilir görünmesini destekler. Benzer içerikler düzenli artırılabilir."
    elif any(term in text for term in ["cocuk", "çocuk", "aile", "23 nisan", "senlik", "şenlik", "festival", "kadin", "kadın", "genç"]):
        post_class = "Sosyal etkinlik / çocuk-aile"
        communication_note = "Pozitif duygu üretme potansiyeli yüksek. İnsan hikayesi ve sıcak görsellerle desteklenmeli."
    elif any(term in text for term in ["antalyaspor", "spor", "mac", "maç", "futbol", "basketbol", "voleybol", "takim", "takım", "taraftar", "tribun", "tribün", "galibiyet", "final", "sampiyon", "şampiyon", "drag"]):
        post_class = "Spor / şehir aidiyeti görünürlüğü"
        communication_note = "Spor ve şehir aidiyeti açısından değerli içerik. Taraftar duygusu, Antalya ortaklığı ve birlik dili öne çıkarılabilir."
    elif any(term in text for term in ["odul", "ödül", "personel", "bayrak", "kurumsal", "basari", "başarı"]):
        post_class = "Kurumsal başarı / personel görünürlüğü"
        communication_note = "Kurum aidiyeti ve güven algısı için faydalı. Personel emeği görünür kılınabilir."
    elif any(term in text for term in ["chp", "ak parti", "siyasi", "rakip", "secim", "seçim", "dava arkadas", "dava arkadaş"]):
        post_class = "Siyasi görünürlük / algı"
        communication_note = "Siyasi algı yönü var. Polemik üretmeden, hizmet ve birlik dili korunmalı."
    else:
        post_class = "Genel mesaj"
        communication_note = "Genel iletişim içeriği. Etkileşim düşükse daha somut hizmet, saha veya insan hikayesiyle desteklenebilir."

    if engagement >= 1000:
        performance = "Yüksek etkileşim"
        performance_note = "İyi performans almış. Benzer dil ve görsel yapı tekrar kullanılabilir."
    elif engagement >= 400:
        performance = "İyi performans"
        performance_note = "Takipçi ilgisi oluşmuş. Konu haftalık analizde ayrıca değerlendirilebilir."
    elif engagement >= 100:
        performance = "Orta performans"
        performance_note = "Standart görünürlük almış. Başlık, görsel ve paylaşım saati test edilebilir."
    else:
        performance = "Düşük performans"
        performance_note = "Etkileşim düşük. Daha güçlü görsel, daha kısa metin veya daha net hizmet sonucu denenebilir."

    if post_class == "İnsani hassasiyet / taziye mesajı":
        if engagement >= 400:
            performance_note = "Hassas içerik iyi görünürlük almış. Bu tür paylaşımlarda amaç yüksek etkileşim değil; doğru, saygılı ve dayanışmacı dilin korunmasıdır."
        elif engagement >= 100:
            performance_note = "Hassas içerik standart görünürlük almış. Taziye ve geçmiş olsun mesajlarında etkileşim kıyasından çok dilin samimiyeti önemlidir."
        else:
            performance_note = "Etkileşim düşük olsa bile bu tür içerikler zorunlu insani hassasiyet mesajıdır. Daha fazla etkileşim hedeflenmemeli; sade ve saygılı dil korunmalıdır."

        action_note = "Standart takip yeterli. Yorumlarda siyasi polemik, alaycı ifade veya yanlış anlaşılma oluşursa ekip sessizce kontrol etmeli."

    elif replies >= 10 and post_class in ["Kriz / hukuki hassasiyet", "Siyasi görünürlük / algı", "Mali disiplin / borç açıklaması"]:
        action_note = "Yorumlar öncelikli izlenmeli; riskli yanıt varsa ekip raporunda takip edilmeli."
    elif replies >= 10:
        action_note = "Yorum sayısı dikkat çekiyor. Vatandaş soruları ve şikayetleri kontrol edilmeli."
    elif performance == "Düşük performans":
        action_note = "Benzer içerik tekrar paylaşılacaksa anlatım dili ve görsel güçlendirilmeli."
    else:
        action_note = "Standart takip yeterli. İyi çalışan başlıklar haftalık rapora alınabilir."

    return {
        "class": post_class,
        "performance": performance,
        "communication_note": communication_note,
        "performance_note": performance_note,
        "action_note": action_note,
        "engagement": engagement,
        "replies": replies,
        "likes": likes,
    }


def president_x_post_classification_html(posts):
    if not posts:
        return """
        <div class="card">
            <b>Başkan X gönderi sınıflandırması:</b> Henüz Başkan X gönderisi bulunamadı.
            <br><small>Gönderiler çekildiğinde burada tür, performans ve iletişim yorumu görünecek.</small>
        </div>
        """

    def post_class_style(post_class):
        class_norm = normalize_text(post_class)

        if "kriz" in class_norm or "hukuki" in class_norm:
            return "#b91c1c", "#fef2f2"

        if "insani" in class_norm or "taziye" in class_norm:
            return "#7c3aed", "#f5f3ff"

        if "hizmet" in class_norm or "proje" in class_norm:
            return "#0369a1", "#f0f9ff"

        if "mahalle" in class_norm or "saha" in class_norm:
            return "#166534", "#f0fdf4"

        if "kultur" in class_norm or "kültür" in class_norm or "toplum" in class_norm:
            return "#0f766e", "#ecfdf5"

        if "spor" in class_norm or "sehir" in class_norm or "şehir" in class_norm:
            return "#1d4ed8", "#eff6ff"

        if "siyasi" in class_norm or "algi" in class_norm or "algı" in class_norm:
            return "#b45309", "#fff7ed"

        if "mali" in class_norm or "borc" in class_norm or "borç" in class_norm:
            return "#b45309", "#fffbeb"

        return "#475569", "#f8fafc"

    def performance_style(performance):
        perf_norm = normalize_text(performance)

        if "yuksek" in perf_norm or "yüksek" in perf_norm:
            return "#166534", "#f0fdf4"

        if "iyi" in perf_norm:
            return "#0369a1", "#f0f9ff"

        if "orta" in perf_norm:
            return "#b45309", "#fff7ed"

        if "dusuk" in perf_norm or "düşük" in perf_norm:
            return "#475569", "#f8fafc"

        return "#475569", "#f8fafc"

    cards_html = ""

    for post in posts[:10]:
        result = classify_president_x_post(post)

        post_class = result.get("class", "")
        performance = result.get("performance", "")

        class_color, class_bg = post_class_style(post_class)
        perf_color, perf_bg = performance_style(performance)

        content = str(post.get("content", "") or "")
        if len(content) > 260:
            content = content[:260] + "..."

        engagement = int(result.get("engagement", 0))
        replies = int(result.get("replies", 0))
        likes = int(result.get("likes", 0))

        cards_html += f"""
        <div class="card" style="
            border-left: 5px solid {class_color};
            margin: 14px 0;
        ">
            <div style="
                display:flex;
                justify-content:space-between;
                gap:10px;
                align-items:flex-start;
                flex-wrap:wrap;
                margin-bottom:8px;
            ">
                <div>
                    <b>{esc(post_class)}</b>
                    <br><small>{esc(post.get("date", ""))} • {esc(post.get("account", ""))}</small>
                </div>

                <div style="
                    background:{class_bg};
                    color:{class_color};
                    border:1px solid {class_color};
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                    white-space:normal;
                ">
                    {esc(post_class)}
                </div>
            </div>

            <p style="margin:8px 0;">
                {esc(content)}
            </p>

            <div style="
                display:flex;
                gap:8px;
                flex-wrap:wrap;
                margin:10px 0;
            ">
                <span style="
                    background:#f8fafc;
                    border:1px solid #cbd5e1;
                    color:#334155;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    Etkileşim: {engagement}
                </span>

                <span style="
                    background:#f8fafc;
                    border:1px solid #cbd5e1;
                    color:#334155;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    Beğeni: {likes}
                </span>

                <span style="
                    background:#f8fafc;
                    border:1px solid #cbd5e1;
                    color:#334155;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    Yanıt: {replies}
                </span>

                <span style="
                    background:{perf_bg};
                    border:1px solid {perf_color};
                    color:{perf_color};
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    {esc(performance)}
                </span>
            </div>

            <p style="margin:8px 0;">
                <b>İletişim yorumu:</b> {esc(result.get("communication_note", ""))}
            </p>

            <p style="margin:8px 0;">
                <b>Performans notu:</b> {esc(result.get("performance_note", ""))}
            </p>

            <p style="margin:8px 0;">
                <b>Aksiyon:</b> {esc(result.get("action_note", ""))}
            </p>

            <div style="margin-top:10px;">
                {social_link(post.get("url", "") or post.get("link", ""))}
            </div>
        </div>
        """

    return f"""
    <div class="card">
        <b>Başkan X gönderi sınıflandırması:</b> Son {min(len(posts), 10)} gönderi tür, performans ve iletişim önerisine göre sınıflandırıldı.
        <br><small>Bu bölüm Başkan’ın kendi X paylaşımlarını sadece etkileşim olarak değil, siyasi iletişim ve içerik türü açısından da değerlendirir.</small>
    </div>

    {cards_html}
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

def append_daily_decision_log(report_date, report_time, news, social, crisis_plan, early_warning, opportunity_sum, learning_note=None, team_actions=None):
    learning_note = learning_note or {}
    opportunity_sum = opportunity_sum or {}
    team_actions = team_actions or []

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    risky_news = sorted(
        news,
        key=lambda x: safe_score_value(x.get("risk", 0)),
        reverse=True
    )

    main_risk_title = clean_text(
        crisis_plan.get("risk_topic", "")
        or crisis_plan.get("title", "")
        or (risky_news[0].get("title", "") if risky_news else "")
    )

    x_count = len([
        x for x in social
        if "twitter" in normalize_text(x.get("platform", "")) or normalize_text(x.get("platform", "")) == "x"
    ])

    youtube_count = len([
        x for x in social
        if "youtube" in normalize_text(x.get("platform", ""))
    ])

    row = {
        "date": report_date,
        "time": report_time,
        "news_count": len(news),
        "social_count": len(social),
        "x_count": x_count,
        "youtube_count": youtube_count,
        "risk_level": crisis_plan.get("level", ""),
        "early_warning_decision": early_warning.get("decision", ""),
        "main_risk_title": main_risk_title,
        "opportunity_level": opportunity_sum.get("level", ""),
        "opportunity_score": opportunity_sum.get("score", ""),
        "opportunity_title": opportunity_sum.get("title", ""),
        "opportunity_type": opportunity_sum.get("type", ""),
        "opportunity_owner": opportunity_sum.get("owner", ""),
        "opportunity_alarm_label": opportunity_sum.get("alarm_label", ""),
        "opportunity_mail_candidate": opportunity_sum.get("mail_candidate", ""),
        "operator_status": learning_note.get("operator_status", ""),
        "data_health": learning_note.get("data_health", ""),
        "team_action_count": len(team_actions),
        "note": "Otomatik günlük karar hafızası kaydı",
    }

    fieldnames = list(row.keys())
    file_exists = DAILY_DECISION_LOG_CSV.exists()

    with DAILY_DECISION_LOG_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    print(f"Günlük karar hafızası kaydı eklendi: {DAILY_DECISION_LOG_CSV}")

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
    
    news_count = len(news)
    social_count = len(social)
    alert_count = len(alert_logs)
    action_count = len(team_actions)
    reply_count = len(president_replies)

    x_count = len([
        x for x in social
        if "twitter" in normalize_text(x.get("platform", "")) or normalize_text(x.get("platform", "")) == "x"
    ])

    youtube_count = len([
        x for x in social
        if "youtube" in normalize_text(x.get("platform", ""))
    ])

    data_warnings = []

    if news_count == 0:
        data_warnings.append("Haber verisi boş geldi")

    if social_count == 0:
        data_warnings.append("Sosyal medya verisi boş geldi")

    if x_count == 0:
        data_warnings.append("X verisi bugün boş görünüyor")

    if youtube_count == 0:
        data_warnings.append("YouTube verisi bugün boş görünüyor")

    if "ACİL ALARM" in decision or "ACIL ALARM" in decision:
        if action_count == 0:
            data_warnings.append("Alarm var ama ekip aksiyon kaydı yok")

    if data_warnings:
        operator_status = "Kontrol gerekiyor"
        data_health = " • ".join(data_warnings)
        operator_action = "Operatör raporu gözle kontrol etmeli; veri kanalları, alarm kararı ve ekip aksiyon kaydı kontrol edilmeli."
    else:
        operator_status = "Sistem sağlıklı"
        data_health = "Haber, sosyal medya ve ekip raporu temel kontrolleri normal görünüyor."
        operator_action = "Standart takip yeterli. Kritik alarm yoksa manuel müdahale gerekmiyor."

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
        "operator_status": operator_status,
        "data_health": data_health,
        "operator_action": operator_action,
    }

def build_data_flow_quality_html(news, social, president_posts, president_replies, youtube_summary, undated_news=None):
    undated_news = undated_news or []

    def to_int_local(value, default=0):
        try:
            return int(float(str(value or "0").replace(",", ".").strip()))
        except:
            return default

    def metric_card(label, value, note="", color="#334155", bg="#f8fafc"):
        value_text = str(value)
        return f"""
        <div style="
            background:{bg};
            border:1px solid {color};
            border-radius:14px;
            padding:12px;
            min-height:82px;
        ">
            <div style="font-size:12px;font-weight:700;color:{color};margin-bottom:6px;">
                {esc(label)}
            </div>
            <div style="font-size:24px;font-weight:800;color:#0f172a;line-height:1;">
                {esc(value_text)}
            </div>
            <div style="font-size:12px;color:#64748b;margin-top:6px;line-height:1.35;">
                {esc(note)}
            </div>
        </div>
        """

    def note_box(text, color="#475569", bg="#f8fafc"):
        return f"""
        <div style="
            background:{bg};
            border-left:4px solid {color};
            border-radius:12px;
            padding:10px 12px;
            margin:8px 0;
            color:#334155;
            line-height:1.45;
            font-size:14px;
        ">
            {esc(text)}
        </div>
        """

    x_items = [item for item in social if is_x_platform(item)]
    youtube_items = [item for item in social if is_youtube_platform(item)]

    manual_items = [
        item for item in social
        if "manuel" in normalize_text(item.get("source_type", ""))
    ]

    auto_items = [
        item for item in social
        if "otomatik" in normalize_text(item.get("source_type", ""))
        or is_x_platform(item)
        or is_youtube_platform(item)
    ]

    checked_videos = sum(to_int_local(row.get("checked_videos", 0)) for row in youtube_summary)
    relevant_comments = sum(to_int_local(row.get("relevant_comments", 0)) for row in youtube_summary)
    saved_comments = sum(to_int_local(row.get("saved_comments", 0)) for row in youtube_summary)
    skipped_videos = sum(to_int_local(row.get("skipped_videos", 0)) for row in youtube_summary)

    warnings = []
    notes = []

    if len(news) == 0:
        warnings.append("Haber verisi boş geldi. RSS, anahtar kelime veya filtre kontrol edilmeli.")

    if len(social) == 0:
        warnings.append("Sosyal medya verisi boş geldi. Manuel + otomatik sosyal kayıtlar kontrol edilmeli.")

    if len(x_items) == 0:
        warnings.append("X verisi boş görünüyor. X token, otomatik tarama ve filtre kontrol edilmeli.")

    if len(youtube_summary) == 0 and len(youtube_items) == 0:
        warnings.append("YouTube kanal özeti ve YouTube sosyal kayıtları boş görünüyor.")

    if len(youtube_summary) > 0 and checked_videos == 0:
        warnings.append("YouTube takip listesi var ama kontrol edilen video sayısı 0 görünüyor.")

    if len(president_posts) == 0:
        notes.append("Başkan X gönderisi okunamadı veya son kayıt yok. X token / kullanıcı adı kontrol edilebilir.")

    if len(president_replies) == 0:
        notes.append("Başkan X yanıt verisi yok. Bu her zaman hata değildir; yorum yoksa normal olabilir.")

    if len(undated_news) > 0:
        notes.append(f"{len(undated_news)} haberin tarihi okunamadı. Eski haber kaçmasını önlemek için ana rapor verisine alınmadı.")

    if len(youtube_summary) > 0 and checked_videos > 0 and relevant_comments == 0:
        notes.append("YouTube tarafında video kontrolü var ama alakalı yorum 0. Bu normal olabilir; yine de YouTube filtre örnekleri gözle kontrol edilmeli.")

    if not warnings:
        status = "Veri akışı normal"
        status_note = "Temel veri kanalları çalışıyor görünüyor. Yine de örnek kayıtlar gözle kontrol edilmeli."
        status_color = "#0f766e"
        status_bg = "#ecfdf5"
    else:
        status = "Kontrol gerekiyor"
        status_note = "Bir veya daha fazla veri kanalında boşluk var. Operatör kaynakları ve filtreleri kontrol etmeli."
        status_color = "#b45309"
        status_bg = "#fff7ed"

    warning_html = "".join([note_box(item, "#b91c1c", "#fef2f2") for item in warnings])
    if not warning_html:
        warning_html = note_box("Kritik veri uyarısı yok.", "#0f766e", "#ecfdf5")

    notes_html = "".join([note_box(item, "#0369a1", "#f0f9ff") for item in notes])
    if not notes_html:
        notes_html = note_box("Ek not yok.", "#64748b", "#f8fafc")

    return f"""
    <div style="display:flex;flex-direction:column;gap:14px;">

        <div style="
            background:{status_bg};
            border:1px solid {status_color};
            border-radius:16px;
            padding:14px;
        ">
            <div style="font-size:14px;font-weight:800;color:{status_color};margin-bottom:6px;">
                Veri akışı genel durumu: {esc(status)}
            </div>
            <div style="font-size:13px;color:#475569;line-height:1.45;">
                {esc(status_note)}
            </div>
        </div>

        <div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:8px;">Haber Akışı</div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;">
                {metric_card("Raporlanan haber", len(news), "Ana rapora giren haber")}
                {metric_card("Tarihi okunamayan", len(undated_news), "Eski haber kaçmasın diye ayrıldı")}
            </div>
        </div>

        <div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:8px;">Sosyal Medya Akışı</div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;">
                {metric_card("Toplam sosyal", len(social), "Manuel + otomatik kayıt")}
                {metric_card("X kayıtları", len(x_items), "X / Twitter kaynaklı kayıt")}
                {metric_card("YouTube sosyal", len(youtube_items), "Yorum / video kaynaklı kayıt")}
                {metric_card("Otomatik", len(auto_items), "Sistem tarafından çekilen")}
                {metric_card("Manuel", len(manual_items), "Ekip tarafından girilen")}
            </div>
        </div>

        <div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:8px;">Başkan X Akışı</div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;">
                {metric_card("Başkan X gönderisi", len(president_posts), "Son çekilen başkan paylaşımları")}
                {metric_card("Başkan X yanıtı", len(president_replies), "Gönderilere gelen yanıtlar")}
            </div>
        </div>

        <div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:8px;">YouTube Kanal Kontrolü</div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;">
                {metric_card("YouTube kaynak", len(youtube_summary), "Takip edilen kanal/kaynak")}
                {metric_card("Kontrol edilen video", checked_videos, "Taranan video sayısı")}
                {metric_card("Alakalı yorum", relevant_comments, "Filtreye takılan yorum")}
                {metric_card("Kaydedilen yorum", saved_comments, "Rapora/veriye yazılan yorum")}
                {metric_card("Atlanan video", skipped_videos, "Yorum/uygunluk nedeniyle atlanan")}
            </div>
        </div>

        <div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:8px;">Kontrol Uyarıları</div>
            {warning_html}
        </div>

        <div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:8px;">Ek Notlar</div>
            {notes_html}
        </div>

        <div style="
            background:#f8fafc;
            border:1px solid #cbd5e1;
            border-radius:14px;
            padding:12px;
            font-size:13px;
            color:#475569;
            line-height:1.5;
        ">
            <strong>Operatör yorumu:</strong>
            Bu bölüm verinin gerçekten akıp akmadığını görmek içindir. Burada boşluk varsa önce kaynak, token, CSV ve filtre kontrol edilmeli; sonra dashboard yorumlarına güvenilmeli.
        </div>

    </div>
    """

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

def x_service_complaint_followup_html(social):
    service_terms = [
        "asfalt", "yol", "kaldirim", "kaldırım", "temizlik", "cop", "çöp",
        "park", "ulasim", "ulaşım", "mahalle", "sikayet", "şikayet",
        "magdur", "mağdur", "su", "kanalizasyon", "otobus", "otobüs",
        "durak", "cukur", "çukur", "bozuk", "sokak", "bakim", "bakım",
        "onarim", "onarım", "calisma", "çalışma"
    ]

    complaint_terms = [
        "şikayet", "sikayet", "mağdur", "magdur", "bozuk", "çukur", "cukur",
        "yapılmadı", "yapilmadi", "çözülmedi", "cozulmedi", "bekliyoruz",
        "yardım", "yardim", "sorun", "rezalet", "tepki", "neden"
    ]

    corporate_reply_terms = [
        "ekiplerimiz", "müdahale", "mudahale", "tamamlandı", "tamamlandi",
        "çalışma başlattı", "calisma baslatti", "giderildi", "çözüldü",
        "cozuldu", "programa alındı", "programa alindi", "bilgilendirme",
        "teşekkür ederiz", "tesekkur ederiz", "talebiniz"
    ]

    corporate_announcement_terms = [
        "hizmete sunduk", "çalışmalarımız", "calismalarimiz", "devam ediyor",
        "tamamladık", "tamamladik", "açılış", "acilis", "proje",
        "yeniledik", "bakım", "bakim", "onardık", "onardik",
        "temizlik çalışması", "yol çalışması", "park çalışması"
    ]

    def service_record_type(item, followup):
        text = normalize_text(
            f"{item.get('content', '')} {item.get('text', '')} {item.get('topic', '')} {item.get('action_note', '')}"
        )
        account = normalize_text(item.get("account", ""))
        account_type = normalize_text(item.get("account_type", ""))
        account_side = normalize_text(item.get("account_side", ""))
        followup_norm = normalize_text(followup)

        is_corporate_account = (
            "kepezbelediyesi" in account
            or "kurumsal" in account_type
            or "belediye" in account_side
        )

        is_media_account = (
            "yerel_medya" in account_type
            or "medya" in account_side
            or "gazete" in account_type
            or "haber" in account_type
        )

        has_complaint = any(term in text for term in complaint_terms)
        has_reply = any(term in text for term in corporate_reply_terms)
        has_announcement = any(term in text for term in corporate_announcement_terms)

        if is_corporate_account and has_reply:
            return "Kurumsal cevap / müdahale bilgisi"

        if is_corporate_account and has_announcement:
            return "Kurumsal duyuru / hizmet paylaşımı"

        if is_corporate_account:
            return "Kurumsal duyuru / kontrol edilecek paylaşım"

        if is_media_account:
            return "Yerel medya görünürlüğü"

        if has_complaint or "vatandas" in account_type or "vatandaş" in account_type or "bilinmeyen" in account_type:
            return "Vatandaş şikayeti / saha kontrolü"

        if "kurumsal hesap" in followup_norm:
            return "Kurumsal cevap / müdahale bilgisi"

        return "Takip edilecek hizmet başlığı"

    def record_type_style(record_type):
        record_norm = normalize_text(record_type)

        if "vatandas" in record_norm or "vatandaş" in record_norm:
            return "#b45309", "#fff7ed"

        if "kurumsal cevap" in record_norm or "mudahale" in record_norm or "müdahale" in record_norm:
            return "#166534", "#f0fdf4"

        if "kurumsal duyuru" in record_norm:
            return "#0369a1", "#f0f9ff"

        if "medya" in record_norm:
            return "#7c3aed", "#f5f3ff"

        return "#475569", "#f8fafc"

    items = []

    for item in social:
        platform_norm = normalize_text(item.get("platform", ""))
        source_norm = normalize_text(item.get("source_type", ""))

        is_x_item = (
            "twitter" in platform_norm
            or platform_norm == "x"
            or platform_norm.startswith("x ")
            or "x" in source_norm
        )

        if not is_x_item:
            continue

        text = normalize_text(
            f"{item.get('content', '')} {item.get('text', '')} {item.get('topic', '')} {item.get('action_note', '')}"
        )

        if not any(term in text for term in service_terms):
            continue

        followup = x_service_followup_status(item)
        followup_norm = normalize_text(followup)

        # Hukuki kriz ve siyasi/ideolojik kayıtları bu hizmet şikayeti bölümünden ayırıyoruz.
        if "hukuki" in followup_norm or "siyasi ideolojik" in followup_norm:
            continue

        record_type = service_record_type(item, followup)
        
        account_norm = normalize_text(item.get("account", ""))
        text_norm_for_pr = normalize_text(item.get("content", "") or item.get("text", ""))

        is_official_president_or_municipality = (
            "mesutkocagoztr" in account_norm
            or "kepezbelediyesi" in account_norm
        )

        is_direct_reply_or_public_response = (
            text_norm_for_pr.startswith("haberantalya")
            or text_norm_for_pr.startswith("akdeniz")
            or text_norm_for_pr.startswith("benfatih")
            or text_norm_for_pr.startswith("hissearz")
            or "merhabalar" in text_norm_for_pr
            or "dm" in text_norm_for_pr
            or "adres bilgileri" in text_norm_for_pr
            or "bahse konu" in text_norm_for_pr
        )

        if is_official_president_or_municipality and not is_direct_reply_or_public_response:
            continue

        items.append({
            "date": item.get("date", ""),
            "account": item.get("account", ""),
            "record_type": record_type,
            "topic": clean_topic_title(item.get("topic", "")),
            "risk": safe_score_value(item.get("account_adjusted_risk_score", item.get("risk_score", 0))),
            "content": item.get("content", "") or item.get("text", ""),
            "followup": followup,
            "link": item.get("link", ""),
        })

    items = sorted(items, key=lambda x: x.get("risk", 0), reverse=True)[:10]

    if not items:
        return """
        <div class="card">
            <b>Hizmet şikayeti / kurumsal cevap takibi:</b> Şu an X tarafında ayrı takip gerektiren net hizmet şikayeti görünmüyor.
            <br><small>Vatandaş şikayeti, kurumsal cevap ve kurumsal duyuru kayıtları geldiğinde burada kartlar halinde listelenecek.</small>
        </div>
        """

    type_counts = {}
    for item in items:
        record_type = item.get("record_type", "Takip edilecek hizmet başlığı")
        type_counts[record_type] = type_counts.get(record_type, 0) + 1

    summary_text = " • ".join([f"{key}: {value}" for key, value in type_counts.items()])

    cards_html = ""

    for item in items:
        content = item.get("content", "")
        if len(content) > 240:
            content = content[:240] + "..."

        record_type = item.get("record_type", "")
        badge_color, badge_bg = record_type_style(record_type)

        cards_html += f"""
        <div class="card" style="
            border-left: 5px solid {badge_color};
            margin: 14px 0;
        ">
            <div style="
                display:flex;
                justify-content:space-between;
                gap:10px;
                align-items:flex-start;
                flex-wrap:wrap;
                margin-bottom:8px;
            ">
                <div>
                    <b>{esc(item.get("topic", ""))}</b>
                    <br><small>{esc(item.get("date", ""))} • {esc(item.get("account", ""))}</small>
                </div>
                <div style="
                    background:{badge_bg};
                    color:{badge_color};
                    border:1px solid {badge_color};
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                    white-space:normal;
                ">
                    {esc(record_type)}
                </div>
            </div>

            <p style="margin:8px 0;">
                {esc(content)}
            </p>

            <div style="
                display:flex;
                gap:8px;
                flex-wrap:wrap;
                margin:10px 0;
            ">
                <span style="
                    background:#f8fafc;
                    border:1px solid #cbd5e1;
                    color:#334155;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    Risk: {item.get("risk", 0)}/10
                </span>
            </div>

            <p style="margin:8px 0;">
                <b>Takip durumu:</b> {esc(item.get("followup", ""))}
            </p>

            <div style="margin-top:10px;">
                {social_link(item.get("link", ""))}
            </div>
        </div>
        """

    return f"""
    <div class="card">
        <b>Hizmet şikayeti / kurumsal cevap durumu:</b> {len(items)} kayıt takip listesine alındı.
        <br><small>{esc(summary_text)}</small>
        <br><small>Bu bölüm gerçek vatandaş şikayeti, belediyenin verdiği cevap ve belediyenin kendi hizmet duyurusunu ayrı ayrı gösterir.</small>
    </div>

    {cards_html}
    """

def is_official_pr_or_service_item(item):
    account = normalize_text(item.get("account", ""))
    account_type = normalize_text(item.get("account_type", ""))
    source_type = normalize_text(item.get("source_type", ""))

    text = normalize_text(
        f"{item.get('content', '')} {item.get('text', '')} {item.get('topic', '')} {item.get('action_note', '')}"
    )

    is_official_account = (
        "mesutkocagoztr" in account
        or "kepezbelediyesi" in account
        or "baskan" in account_type
        or "başkan" in account_type
        or "kurumsal" in account_type
        or "belediye" in account_type
        or "baskan x hesabi" in source_type
        or "başkan x hesabi" in source_type
    )

    serious_risk_terms = [
        "teleferik", "facia", "kaza", "olum", "ölüm", "yarali", "yaralı",
        "dava", "mahkeme", "savci", "savcı", "iddianame", "yargi", "yargı",
        "sorusturma", "soruşturma", "tutuklama", "tutuklu", "ceza",
        "yolsuzluk", "rüşvet", "rusvet", "usulsuz", "usulsüz",
        "ihmal", "skandal", "protesto", "kriz"
    ]

    has_serious_risk = any(term in text for term in serious_risk_terms)

    return is_official_account and not has_serious_risk

def x_social_summary_html(social, president_replies):
    x_items = []

    for item in social:
        platform_norm = normalize_text(item.get("platform", ""))
        source_norm = normalize_text(item.get("source_type", ""))

        is_x_item = (
            "twitter" in platform_norm
            or platform_norm == "x"
            or platform_norm.startswith("x ")
            or "x" in source_norm
        )

        if is_x_item:
            x_items.append(item)

    def is_official_pr_or_service_item(item):
        account = normalize_text(item.get("account", ""))
        account_type = normalize_text(item.get("account_type", ""))
        source_type = normalize_text(item.get("source_type", ""))

        text = normalize_text(
            f"{item.get('content', '')} {item.get('text', '')} {item.get('topic', '')} {item.get('action_note', '')}"
        )

        is_official_account = (
            "mesutkocagoztr" in account
            or "kepezbelediyesi" in account
            or "baskan" in account_type
            or "başkan" in account_type
            or "kurumsal" in account_type
            or "belediye" in account_type
            or "baskan x hesabi" in source_type
            or "başkan x hesabi" in source_type
        )

        serious_risk_terms = [
            "teleferik", "facia", "kaza", "olum", "ölüm", "yarali", "yaralı",
            "dava", "mahkeme", "savci", "savcı", "iddianame", "yargi", "yargı",
            "sorusturma", "soruşturma", "tutuklama", "tutuklu", "ceza",
            "yolsuzluk", "rüşvet", "rusvet", "usulsuz", "usulsüz",
            "ihmal", "skandal", "protesto", "kriz"
        ]

        has_serious_risk = any(term in text for term in serious_risk_terms)

        # Başkan / belediye hesabından gelen normal hizmet, duyuru veya PR içerikleri
        # yüksek etki nedeniyle riskli sosyal medya kartına düşmesin.
        return is_official_account and not has_serious_risk

    risky_x_items = sorted(
        [
            item for item in x_items
            if safe_score_value(item.get("account_adjusted_risk_score", item.get("risk_score", 0))) >= 6
            and not is_official_pr_or_service_item(item)
        ],
        key=lambda x: safe_score_value(x.get("account_adjusted_risk_score", x.get("risk_score", 0))),
        reverse=True
    )[:6]

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

    def x_card_style(item):
        adjusted_risk = safe_score_value(
            item.get("account_adjusted_risk_score", item.get("risk_score", 0))
        )
        account_type = normalize_text(item.get("account_type", ""))
        account_side = normalize_text(item.get("account_side", ""))

        if adjusted_risk >= 8:
            return "#b91c1c", "#fef2f2", "Yüksek risk"
        if adjusted_risk >= 6:
            return "#d97706", "#fffbeb", "Takip gerektirir"
        if "yerel_medya" in account_type or "medya" in account_side:
            return "#7c3aed", "#f5f3ff", "Yerel medya"
        if "baskan" in account_type:
            return "#0369a1", "#f0f9ff", "Başkan hesabı"
        return "#475569", "#f8fafc", "Standart takip"

    cards_html = ""

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
        if len(content) > 240:
            content = content[:240] + "..."

        badge_color, badge_bg, badge_text = x_card_style(item)

        cards_html += f"""
        <div class="card" style="
            border-left: 5px solid {badge_color};
            margin: 14px 0;
        ">
            <div style="
                display:flex;
                justify-content:space-between;
                gap:10px;
                align-items:flex-start;
                flex-wrap:wrap;
                margin-bottom:8px;
            ">
                <div>
                    <b>{esc(clean_topic_title(item.get("topic", "")))}</b>
                    <br><small>{esc(item.get("date", ""))} • {esc(item.get("account", ""))}</small>
                </div>

                <div style="
                    background:{badge_bg};
                    color:{badge_color};
                    border:1px solid {badge_color};
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                    white-space:normal;
                ">
                    {esc(badge_text)}
                </div>
            </div>

            <p style="margin:8px 0;">
                {esc(content)}
            </p>

            <div style="
                display:flex;
                gap:8px;
                flex-wrap:wrap;
                margin:10px 0;
            ">
                <span style="
                    background:#f8fafc;
                    border:1px solid #cbd5e1;
                    color:#334155;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    Risk: {item.get("risk_score", 0)}/10
                </span>

                <span style="
                    background:#f8fafc;
                    border:1px solid #cbd5e1;
                    color:#334155;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    Hesap etkili risk: {adjusted_risk}/10
                </span>
            </div>

            <p style="margin:8px 0;">
                <b>Hesap tipi:</b> {esc(account_type)} •
                <b>Taraf:</b> {esc(account_side)} •
                <b>Etki:</b> {esc(influence)} •
                <b>Takip:</b> {esc(watch)}
            </p>

            <p style="margin:8px 0;">
                <b>Risk nedeni:</b> {esc(reason)}
            </p>

            <p style="margin:8px 0;">
                <b>X aksiyon yorumu:</b> {esc(action_comment)}
            </p>

            <p style="margin:8px 0;">
                <b>Hizmet/cevap takibi:</b> {esc(service_followup)}
            </p>

            <div style="margin-top:10px;">
                {social_link(item.get("link", ""))}
            </div>
        </div>
        """

    if not cards_html:
        cards_html = """
        <div class="card">
            Riskli X kaydı bulunamadı.
            <br><small>X tarafında şu an ekip kontrolü gerektiren belirgin riskli kayıt görünmüyor.</small>
        </div>
        """

    return f"""
    <div class="card">
        <b>Toplam X kaydı:</b> {len(x_items)} •
        <b>Riskli X kaydı:</b> {len(risky_x_items)} •
        <b>Başkan X yanıtı:</b> {len(president_replies)} •
        <b>Riskli Başkan X yanıtı:</b> {len(risky_replies)}
        <br>
        <span style="
            display:inline-block;
            margin-top:10px;
            background:{status_bg};
            color:{status_color};
            border:1px solid {status_color};
            border-radius:999px;
            padding:7px 11px;
            font-size:13px;
            font-weight:700;
        ">
            {esc(status_text)}
        </span>
    </div>

    {cards_html}
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
        return "Genel yorum gündemi"

    text = text.replace("_", " ").replace("-", " ")

    # Önce sistemin ürettiği ana konu kodlarını doğrudan okunur başlığa çevir.
    direct_titles = {
        "teleferik davasi": "Teleferik davası / hukuki süreç hassasiyeti",
        "hizmet asfalt": "Asfalt / yol hizmeti şikayetleri",
        "bayrak personel": "Bayrak, personel ve kurumsal görünürlük",
        "cocuk aile": "Çocuk, aile ve sosyal etkinlikler",
        "mali disiplin": "Mali disiplin / borç açıklamaları",
        "spor etkinlik": "Spor ve etkinlik görünürlüğü",
        "buyuksehir ulasim": "Büyükşehir / ulaşım gündemi",
        "genel": "Genel yorum gündemi",
        "yorum": "Genel yorum gündemi",
    }

    if text in direct_titles:
        return direct_titles[text]

    # Sonra metnin içindeki kelimelere göre doğal başlık üret.
    if any(term in text for term in ["teleferik", "facia", "mahkeme", "sorusturma", "soruşturma", "iddianame", "yargi", "yargı", "hukuk", "tutuklama"]):
        return "Teleferik davası / hukuki süreç hassasiyeti"

    if any(term in text for term in ["asfalt", "yol", "kaldirim", "kaldırım", "cukur", "çukur", "bozuk yol", "duaci", "duacı"]):
        return "Asfalt / yol hizmeti şikayetleri"

    if any(term in text for term in ["temizlik", "cop", "çöp", "park", "mahalle", "saha", "hizmet", "şikayet", "sikayet"]):
        return "Mahalle hizmetleri / vatandaş şikayetleri"

    if any(term in text for term in ["ulasim", "ulaşım", "otobus", "otobüs", "durak", "buyuksehir", "büyükşehir"]):
        return "Büyükşehir / ulaşım gündemi"

    if any(term in text for term in ["borc", "borç", "mali", "butce", "bütçe", "tasarruf"]):
        return "Mali disiplin / borç açıklamaları"

    if any(term in text for term in ["cocuk", "çocuk", "aile", "23 nisan", "senlik", "şenlik", "festival"]):
        return "Çocuk, aile ve sosyal etkinlikler"

    if any(term in text for term in ["spor", "drag", "turnuva", "musabaka", "müsabaka"]):
        return "Spor ve etkinlik görünürlüğü"

    if any(term in text for term in ["bayrak", "personel", "odul", "ödül", "kurumsal"]):
        return "Bayrak, personel ve kurumsal görünürlük"

    if any(term in text for term in ["siyasi", "rakip", "ak parti", "chp", "ocak", "dava arkadas", "dava arkadaş", "dava buyuk", "dava büyük"]):
        return "Siyasi görünürlük / rakip çevre takibi"

    # Hiçbir kategoriye girmezse ham metni biraz temizleyip göster.
    words = [w for w in text.split() if len(w) > 2 and w not in STOPWORDS]
    if not words:
        return "Genel yorum gündemi"

    cleaned = " ".join(words[:5])

    replacements = {
        "ogrenci": "öğrenci",
        "ulasim": "ulaşım",
        "buyuksehir": "büyükşehir",
        "cocuk": "çocuk",
        "sikayet": "şikayet",
        "borc": "borç",
        "cop": "çöp",
        "duaci": "duacı",
    }

    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)

    return " ".join([w.capitalize() for w in cleaned.split()])

def president_x_reply_topic_summary_html(replies):
    if not replies:
        return """
        <div class="card">
            Başkan X yanıtlarında konu analizi yapılacak veri bulunamadı.
            <br><small>Başkan X yanıtları geldikçe tekrar eden konu başlıkları burada kart olarak görünecek.</small>
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
            topic = "Genel yorum gündemi"

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
        status_color = "#b45309"
        status_bg = "#fff7ed"
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

    cards_html = ""

    for item in topics:
        sample_text = item.get("sample_text", "")
        if len(sample_text) > 220:
            sample_text = sample_text[:220] + "..."

        max_risk = safe_score_value(item.get("max_risk", 0))
        risk_count = int(item.get("risk_count", 0))
        count = int(item.get("count", 0))

        if risk_count >= 1 or max_risk >= 6:
            badge_color = "#b45309"
            badge_bg = "#fff7ed"
            badge_text = "Riskli konu"
        elif count >= 2:
            badge_color = "#2563eb"
            badge_bg = "#eff6ff"
            badge_text = "Tekrar eden konu"
        else:
            badge_color = "#475569"
            badge_bg = "#f8fafc"
            badge_text = "Standart takip"

        cards_html += f"""
        <div class="card" style="
            border-left: 5px solid {badge_color};
            margin: 14px 0;
        ">
            <div style="
                display:flex;
                justify-content:space-between;
                gap:10px;
                align-items:flex-start;
                flex-wrap:wrap;
                margin-bottom:8px;
            ">
                <div>
                    <b>{esc(item.get("topic", ""))}</b>
                    <br><small>Yanıt sayısı: {count} • Riskli yanıt: {risk_count}</small>
                </div>

                <div style="
                    background:{badge_bg};
                    color:{badge_color};
                    border:1px solid {badge_color};
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    {esc(badge_text)}
                </div>
            </div>

            <div style="
                display:flex;
                gap:8px;
                flex-wrap:wrap;
                margin:10px 0;
            ">
                <span style="
                    background:#f8fafc;
                    border:1px solid #cbd5e1;
                    color:#334155;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    En yüksek risk: {max_risk}/10
                </span>

                <span style="
                    background:#f8fafc;
                    border:1px solid #cbd5e1;
                    color:#334155;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    Örnek hesap: {esc(item.get("sample_account", ""))}
                </span>
            </div>

            <p style="margin:8px 0;">
                <b>Örnek yanıt:</b> {esc(sample_text)}
            </p>

            <div style="margin-top:10px;">
                {social_link(item.get("sample_link", ""))}
            </div>
        </div>
        """

    if not cards_html:
        cards_html = """
        <div class="card">
            Konu özeti üretilemedi.
            <br><small>Başkan X yanıtları çoğaldıkça tekrar eden konu kartları burada görünecek.</small>
        </div>
        """

    return f"""
    <div class="card">
        <span style="
            display:inline-block;
            background:{status_bg};
            color:{status_color};
            border:1px solid {status_color};
            border-radius:999px;
            padding:7px 11px;
            font-size:13px;
            font-weight:700;
        ">
            {esc(status_text)}
        </span>

        <p style="margin:12px 0 0 0;">
            <b>İlk aksiyon:</b> {esc(action_text)}
        </p>
    </div>

    {cards_html}
    """

def append_weekly_x_summary(social, president_replies):
    import csv
    from datetime import datetime

    file_path = ROOT / "data" / "weekly" / "weekly_x_summary.csv"
    today = datetime.now().strftime("%Y-%m-%d")

    def is_x_item(item):
        platform_norm = normalize_text(item.get("platform", ""))
        source_norm = normalize_text(item.get("source_type", ""))
        return (
            "twitter" in platform_norm
            or platform_norm == "x"
            or platform_norm.startswith("x ")
            or "x" in source_norm
        )

    x_items = [s for s in social if is_x_item(s)]

    total_x = len(x_items)
    risk_x = len([
        s for s in x_items
        if safe_score_value(s.get("risk_score", 0)) >= 6
    ])

    total_replies = len(president_replies)
    risk_replies = len([
        r for r in president_replies
        if safe_score_value(r.get("risk_score", 0)) >= 6
    ])

    # En çok görünen X konusunu bul
    topic_count = {}

    for item in x_items:
        topic = item.get("topic", "") or item.get("risk_note", "") or "genel"
        topic = str(topic or "").strip()
        if not topic:
            topic = "genel"
        topic_count[topic] = topic_count.get(topic, 0) + 1

    # X kaydı yoksa Başkan X yanıtlarındaki konulara bak
    if not topic_count:
        for r in president_replies:
            topic = r.get("post_topic", "") or "genel"
            topic = str(topic or "").strip()
            if not topic:
                topic = "genel"
            topic_count[topic] = topic_count.get(topic, 0) + 1

    top_topic = max(topic_count, key=topic_count.get) if topic_count else "genel"

    fieldnames = [
        "date",
        "total_x",
        "risk_x",
        "total_replies",
        "risk_replies",
        "top_topic",
    ]

    new_row = {
        "date": today,
        "total_x": total_x,
        "risk_x": risk_x,
        "total_replies": total_replies,
        "risk_replies": risk_replies,
        "top_topic": top_topic,
    }

    file_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    # Eski kayıtları oku; bugünün eski satırlarını alma.
    # Böylece aynı gün tekrar tekrar satır birikmez.
    if file_path.exists():
        try:
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row_date = str(row.get("date", "") or "").strip()
                    if row_date and row_date != today:
                        rows.append({
                            key: row.get(key, "")
                            for key in fieldnames
                        })
        except Exception as e:
            print(f"Haftalık X özeti okunamadı, yeniden oluşturulacak: {e}")
            rows = []

    rows.append(new_row)

    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Haftalık X özeti güncellendi: {today}")

def weekly_x_summary_html():
    import csv

    file_path = ROOT / "data" / "weekly" / "weekly_x_summary.csv"

    if not file_path.exists():
        return "<div class='card'><p class='small'>Haftalık X verisi bulunamadı.</p></div>"

    try:
        with open(file_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            return "<div class='card'><p class='small'>Haftalık X verisi boş.</p></div>"

        last = rows[-1]
        
        clean_topic = clean_topic_title(last.get("top_topic", ""))

        return f"""
<div class="card">
<p><b>Toplam X:</b> {last.get("total_x", 0)} • 
<b>Riskli X:</b> {last.get("risk_x", 0)} • 
<b>Başkan Yanıt:</b> {last.get("total_replies", 0)} • 
<b>Riskli Yanıt:</b> {last.get("risk_replies", 0)}</p>

<p><b>En Çok Konu:</b> {esc(clean_topic)}</p>
</div>
"""
    except:
        return "<div class='card'><p class='small'>Haftalık veri okunamadı.</p></div>"

def build_news_quality_html(news, undated_news=None, dashboard_day=None):
    undated_news = undated_news or []

    def to_float_local(value, default=0):
        try:
            return float(str(value or "0").replace(",", ".").strip())
        except:
            return default

    if dashboard_day is None:
        now_tr = dt.datetime.utcnow() + dt.timedelta(hours=3)
        dashboard_day = (now_tr.date() - dt.timedelta(days=1)).isoformat()

    today_news = [
        item for item in news
        if same_day(item.get("parsed_date", item.get("date", "")), dashboard_day)
    ]

    risky_news = [
        item for item in news
        if to_float_local(item.get("risk", 0)) >= 6
    ]

    positive_news = [
        item for item in news
        if normalize_text(item.get("tone", "")) == "olumlu"
    ]

    neutral_news = [
        item for item in news
        if normalize_text(item.get("tone", "")) in ["notr", "nötr"]
    ]

    def metric_card(label, value, note="", color="#334155", bg="#f8fafc"):
        return f"""
        <div style="
            background:{bg};
            border:1px solid {color};
            border-radius:14px;
            padding:12px;
            min-height:82px;
        ">
            <div style="font-size:12px;font-weight:700;color:{color};margin-bottom:6px;">
                {esc(label)}
            </div>
            <div style="font-size:24px;font-weight:800;color:#0f172a;line-height:1;">
                {esc(str(value))}
            </div>
            <div style="font-size:12px;color:#64748b;margin-top:6px;line-height:1.35;">
                {esc(note)}
            </div>
        </div>
        """

    def news_detail_card(item):
        title = item.get("title", "")
        summary = item.get("summary", "")
        if len(summary) > 260:
            summary = summary[:260] + "..."

        risk = to_float_local(item.get("risk", 0))
        opportunity = to_float_local(item.get("opportunity", 0))
        tone = item.get("tone", "")
        topic = clean_topic_title(item.get("topic", ""))
        keyword = item.get("keyword", "")
        parsed_date = item.get("parsed_date", "")
        date_text = parsed_date or item.get("date", "")
        link = str(item.get("link", "") or "").strip()

        if risk >= 7:
            badge_text = "Yüksek risk"
            badge_color = "#b91c1c"
            badge_bg = "#fef2f2"
        elif risk >= 4:
            badge_text = "Takip edilecek"
            badge_color = "#b45309"
            badge_bg = "#fff7ed"
        else:
            badge_text = "Standart takip"
            badge_color = "#2563eb"
            badge_bg = "#eff6ff"

        link_html = ""
        if link:
            link_html = f"""
            <a href="{esc(link)}" target="_blank" style="
                display:inline-block;
                margin-top:8px;
                padding:7px 10px;
                border-radius:10px;
                background:#0f172a;
                color:white;
                text-decoration:none;
                font-size:12px;
                font-weight:700;
            ">Haberi Aç</a>
            """

        return f"""
        <div style="
            background:#ffffff;
            border:1px solid #cbd5e1;
            border-radius:14px;
            padding:12px;
            margin:10px 0;
        ">
            <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;">
                <div style="font-size:15px;font-weight:800;color:#0f172a;line-height:1.35;">
                    {esc(title)}
                </div>
                <div style="
                    white-space:nowrap;
                    background:{badge_bg};
                    color:{badge_color};
                    border:1px solid {badge_color};
                    border-radius:999px;
                    padding:4px 8px;
                    font-size:11px;
                    font-weight:800;
                ">
                    {esc(badge_text)}
                </div>
            </div>

            <div style="font-size:12px;color:#64748b;margin-top:6px;line-height:1.45;">
                Tarih: {esc(date_text)} • Ton: {esc(tone)} • Risk: {esc(str(risk))}/10 • Fırsat: {esc(str(opportunity))}/10
            </div>

            <div style="font-size:12px;color:#64748b;margin-top:4px;line-height:1.45;">
                Konu: {esc(topic)} • Anahtar kelime: {esc(keyword)}
            </div>

            <div style="font-size:13px;color:#334155;margin-top:8px;line-height:1.45;">
                {esc(summary)}
            </div>

            {link_html}
        </div>
        """

    sample_news = sorted(
        news,
        key=lambda item: to_float_local(item.get("risk", 0)),
        reverse=True
    )[:8]

    sample_news_html = "".join([news_detail_card(item) for item in sample_news])
    if not sample_news_html:
        sample_news_html = """
        <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:14px;padding:12px;color:#475569;">
            Haber kaydı bulunamadı. Haber kaynakları, RSS veya filtreler kontrol edilmeli.
        </div>
        """

    return f"""
    <div style="display:flex;flex-direction:column;gap:14px;">

        <div style="
            background:#eff6ff;
            border:1px solid #2563eb;
            border-radius:16px;
            padding:14px;
        ">
            <div style="font-size:14px;font-weight:800;color:#1d4ed8;margin-bottom:6px;">
                Haber filtre kalite kontrolü
            </div>
            <div style="font-size:13px;color:#475569;line-height:1.45;">
                Bu bölüm başkan raporunu uzatmadan, ekip/operatör tarafında haberlerin gerçekten Kepez / Mesut Kocagöz / Antalya bağlamında olup olmadığını kontrol etmek için eklenmiştir.
            </div>
        </div>

        <div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:8px;">Haber Sayıları</div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;">
                {metric_card("Raporlanan haber", len(news), "Son 7 gün filtresinden geçen haber")}
                {metric_card("Özet günü haber", len(today_news), f"{dashboard_day} tarihli haber")}
                {metric_card("Riskli haber", len(risky_news), "Risk skoru 6 ve üzeri")}
                {metric_card("Olumlu haber", len(positive_news), "Olumlu tonlu haber")}
                {metric_card("Nötr haber", len(neutral_news), "Nötr tonlu haber")}
                {metric_card("Tarihi okunamayan", len(undated_news), "Ana rapora alınmayan haber")}
            </div>
        </div>

        <div>
            <div style="font-size:15px;font-weight:800;color:#0f172a;margin-bottom:8px;">
                En Riskli / Örnek Haberler
            </div>
            {sample_news_html}
        </div>

        <div style="
            background:#f8fafc;
            border:1px solid #cbd5e1;
            border-radius:14px;
            padding:12px;
            font-size:13px;
            color:#475569;
            line-height:1.5;
        ">
            <strong>Operatör kontrol notu:</strong>
            Bu listede alakasız il, eski haber, tekrar eden haber veya Kepez/Mesut bağlamı zayıf haber görülürse haber filtresi sıkılaştırılmalı. Başkan raporunda sadece özet ve karar göstergesi kalmalı; detay kontrol ekip raporunda yapılmalı.
        </div>

    </div>
    """

def build_team_report(news, social, early_warning, crisis_plan, crisis_status, report_time, undated_news=None):
    now_tr = dt.datetime.utcnow() + dt.timedelta(hours=3)
    today = now_tr.date().isoformat()
    dashboard_day = (now_tr.date() - dt.timedelta(days=1)).isoformat()

    def safe_float(value, default=0):
        try:
            return float(str(value or "0").replace(",", ".").strip())
        except:
            return default

    alert_logs = read_alert_log(20)
    team_actions = read_team_actions(20)
    crisis_log = read_crisis_log()
    president_replies = read_president_x_replies()
    president_posts = read_president_x_posts()
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
    data_flow_quality = build_data_flow_quality_html(
        news,
        social,
        president_posts,
        president_replies,
        youtube_summary,
        undated_news,
    )
    
    news_quality_html = build_news_quality_html(
        news,
        undated_news,
        dashboard_day,
    )
    
    x_summary_html = x_social_summary_html(social, president_replies)
    service_complaint_followup = x_service_complaint_followup_html(social)
    weekly_summary = weekly_x_summary_html()
    president_replies_detail = president_x_replies_detail_html(president_replies)
    president_post_classification = president_x_post_classification_html(president_posts)
    president_reply_topics = president_x_reply_topic_summary_html(president_replies)
    unmapped_x_accounts = unmapped_x_accounts_html(social)
    
    risky_social = sorted(
    [
        item for item in social
        if not is_official_pr_or_service_item(item)
    ],
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

    risky_social_content = ""

    for item in risky_social:
        content = item.get("content", "") or item.get("text", "") or item.get("action_note", "")
        if len(content) > 240:
            content = content[:240] + "..."

        risk_value = safe_score_value(item.get("account_adjusted_risk_score", item.get("risk_score", 0)))
        tone = item.get("tone", "") or item.get("sentiment", "")
        account = item.get("account", "")
        platform = item.get("platform", "")
        topic = clean_topic_title(item.get("topic", ""))

        if risk_value >= 8:
            badge_color = "#b91c1c"
            badge_bg = "#fef2f2"
            badge_text = "Yüksek risk"
        elif risk_value >= 6:
            badge_color = "#b45309"
            badge_bg = "#fff7ed"
            badge_text = "Takip gerektirir"
        else:
            badge_color = "#475569"
            badge_bg = "#f8fafc"
            badge_text = "Standart takip"

        risky_social_content += f"""
        <div class="card" style="border-left: 5px solid {badge_color}; margin: 14px 0;">
            <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start; flex-wrap:wrap; margin-bottom:8px;">
                <div>
                    <b>{esc(topic)}</b>
                    <br><small>{esc(item.get("date", ""))} • {esc(platform)} • {esc(account)}</small>
                </div>

                <div style="background:{badge_bg}; color:{badge_color}; border:1px solid {badge_color}; border-radius:999px; padding:5px 9px; font-size:12px; font-weight:700;">
                    {esc(badge_text)}
                </div>
            </div>

            <p style="margin:8px 0;">{esc(content)}</p>

            <div style="display:flex; gap:8px; flex-wrap:wrap; margin:10px 0;">
                <span style="background:#f8fafc; border:1px solid #cbd5e1; color:#334155; border-radius:999px; padding:5px 9px; font-size:12px; font-weight:700;">
                    Risk: {risk_value}/10
                </span>
                <span style="background:#f8fafc; border:1px solid #cbd5e1; color:#334155; border-radius:999px; padding:5px 9px; font-size:12px; font-weight:700;">
                    Ton: {esc(tone)}
                </span>
            </div>

            <p style="margin:8px 0;"><b>Aksiyon notu:</b> {esc(item.get("action_note", ""))}</p>

            <div style="margin-top:10px;">
                {social_link(item.get("link", ""))}
            </div>
        </div>
        """

    if not risky_social_content:
        risky_social_content = """
        <div class="card">
            Riskli sosyal medya kaydı bulunamadı.
            <br><small>Şu an ekip kontrolü gerektiren yüksek riskli sosyal medya kaydı görünmüyor.</small>
        </div>
        """

    risky_reply_content = ""

    for item in risky_replies:
        reply_text = item.get("reply_text", "")
        if len(reply_text) > 240:
            reply_text = reply_text[:240] + "..."

        risk_value = safe_score_value(item.get("risk_score", 0))

        if risk_value >= 8:
            badge_color = "#b91c1c"
            badge_bg = "#fef2f2"
            badge_text = "Yüksek riskli yanıt"
        else:
            badge_color = "#b45309"
            badge_bg = "#fff7ed"
            badge_text = "Takip edilecek yanıt"

        risky_reply_content += f"""
        <div class="card" style="border-left: 5px solid {badge_color}; margin: 14px 0;">
            <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start; flex-wrap:wrap; margin-bottom:8px;">
                <div>
                    <b>{esc(item.get("reply_account", ""))}</b>
                    <br><small>{esc(item.get("reply_date", ""))}</small>
                </div>

                <div style="background:{badge_bg}; color:{badge_color}; border:1px solid {badge_color}; border-radius:999px; padding:5px 9px; font-size:12px; font-weight:700;">
                    {esc(badge_text)}
                </div>
            </div>

            <p style="margin:8px 0;">{esc(reply_text)}</p>

            <div style="display:flex; gap:8px; flex-wrap:wrap; margin:10px 0;">
                <span style="background:#f8fafc; border:1px solid #cbd5e1; color:#334155; border-radius:999px; padding:5px 9px; font-size:12px; font-weight:700;">
                    Risk: {risk_value}/10
                </span>
            </div>

            <p style="margin:8px 0;">
                <b>İlk değerlendirme:</b> Başkan X yanıtı ekip tarafından kontrol edilmeli; aynı konu tekrar ediyorsa konu başlığı ekip raporunda takip edilmeli.
            </p>

            <div style="margin-top:10px;">
                {social_link(item.get("reply_url", ""))}
            </div>
        </div>
        """

    if not risky_reply_content:
        risky_reply_content = """
        <div class="card">
            Riskli Başkan X yanıtı bulunamadı.
            <br><small>Başkan X yanıtlarında şu an ekip müdahalesi gerektiren yüksek risk görünmüyor.</small>
        </div>
        """

    alert_content = ""

    for item in alert_logs:
        risk_text = item.get("risk_level", "")
        decision_text = item.get("decision", "")
        title_text = item.get("crisis_title", "")
        mail_text = item.get("email_sent", "")
        note_text = item.get("note", "")

        risk_norm = normalize_text(risk_text)

        if "yuksek" in risk_norm or "yüksek" in risk_norm:
            badge_color = "#b91c1c"
            badge_bg = "#fef2f2"
            badge_text = "Yüksek risk alarmı"
        elif "orta" in risk_norm:
            badge_color = "#b45309"
            badge_bg = "#fff7ed"
            badge_text = "Orta risk alarmı"
        else:
            badge_color = "#0369a1"
            badge_bg = "#f0f9ff"
            badge_text = "Alarm kaydı"

        alert_content += f"""
        <div class="card" style="
            border-left: 5px solid {badge_color};
            margin: 14px 0;
        ">
            <div style="
                display:flex;
                justify-content:space-between;
                gap:10px;
                align-items:flex-start;
                flex-wrap:wrap;
                margin-bottom:8px;
            ">
                <div>
                    <b>{esc(title_text)}</b>
                    <br><small>{esc(item.get("date", ""))} • Saat: {esc(item.get("time", ""))}</small>
                </div>

                <div style="
                    background:{badge_bg};
                    color:{badge_color};
                    border:1px solid {badge_color};
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    {esc(badge_text)}
                </div>
            </div>

            <p style="margin:8px 0;">
                <b>Risk:</b> {esc(risk_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Karar:</b> {esc(decision_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Mail gönderildi mi?</b> {esc(mail_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Not:</b> {esc(note_text)}
            </p>
        </div>
        """

    if not alert_content:
        alert_content = """
        <div class="card">
            Henüz bildirim / alarm kaydı yok.
            <br><small>Yeni alarm kayıtları burada kart görünümünde listelenecek.</small>
        </div>
        """

    team_action_content = ""

    for item in team_actions:
        topic_text = item.get("alert_topic", "")
        action_text = item.get("action_taken", "")
        result_text = item.get("result", "")
        responsible_text = item.get("responsible", "")
        next_step_text = item.get("next_step", "")
        status_text = item.get("status", "")

        status_norm = normalize_text(status_text)

        if "tamam" in status_norm or "çözüldü" in status_norm or "cozuldu" in status_norm:
            badge_color = "#166534"
            badge_bg = "#f0fdf4"
            badge_text = "Tamamlandı"
        elif "bekle" in status_norm or "devam" in status_norm:
            badge_color = "#b45309"
            badge_bg = "#fff7ed"
            badge_text = "Takipte"
        elif "başkan" in status_norm or "baskan" in status_norm:
            badge_color = "#0369a1"
            badge_bg = "#f0f9ff"
            badge_text = "Başkan bilgisi"
        else:
            badge_color = "#16a34a"
            badge_bg = "#f0fdf4"
            badge_text = status_text or "Ekip aksiyonu"

        team_action_content += f"""
        <div class="card" style="
            border-left: 5px solid {badge_color};
            margin: 14px 0;
        ">
            <div style="
                display:flex;
                justify-content:space-between;
                gap:10px;
                align-items:flex-start;
                flex-wrap:wrap;
                margin-bottom:8px;
            ">
                <div>
                    <b>{esc(topic_text)}</b>
                    <br><small>{esc(item.get("date", ""))} • Saat: {esc(item.get("time", ""))}</small>
                </div>

                <div style="
                    background:{badge_bg};
                    color:{badge_color};
                    border:1px solid {badge_color};
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    {esc(badge_text)}
                </div>
            </div>

            <p style="margin:8px 0;">
                <b>Alınan aksiyon:</b> {esc(action_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Sonuç:</b> {esc(result_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Sorumlu:</b> {esc(responsible_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Sıradaki adım:</b> {esc(next_step_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Durum:</b> {esc(status_text)}
            </p>
        </div>
        """

    if not team_action_content:
        team_action_content = """
        <div class="card">
            Henüz ekip aksiyon kaydı yok.
            <br><small>Bildirim veya kriz sonrası ekip aksiyonu girildiğinde burada kart olarak görünecek.</small>
        </div>
        """

    crisis_log_content = ""

    for item in crisis_log:
        event_text = item.get("event", "")
        action_text = item.get("action", "")
        result_text = item.get("result", "")
        responsible_text = item.get("responsible", "")
        next_step_text = item.get("next_step", "")

        crisis_log_content += f"""
        <div class="card" style="
            border-left: 5px solid #d97706;
            margin: 14px 0;
        ">
            <div style="
                display:flex;
                justify-content:space-between;
                gap:10px;
                align-items:flex-start;
                flex-wrap:wrap;
                margin-bottom:8px;
            ">
                <div>
                    <b>{esc(event_text)}</b>
                    <br><small>Saat: {esc(item.get("time", ""))}</small>
                </div>

                <div style="
                    background:#fff7ed;
                    color:#b45309;
                    border:1px solid #b45309;
                    border-radius:999px;
                    padding:5px 9px;
                    font-size:12px;
                    font-weight:700;
                ">
                    Müdahale kaydı
                </div>
            </div>

            <p style="margin:8px 0;">
                <b>Yapılan işlem:</b> {esc(action_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Sonuç:</b> {esc(result_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Sorumlu:</b> {esc(responsible_text)}
            </p>

            <p style="margin:8px 0;">
                <b>Sıradaki adım:</b> {esc(next_step_text)}
            </p>
        </div>
        """

    if not crisis_log_content:
        crisis_log_content = """
        <div class="card">
            Henüz müdahale kaydı yok.
            <br><small>Kriz panelinden müdahale kaydı girildiğinde burada kart olarak görünecek.</small>
        </div>
        """

    # Accordion başlıkları için kısa özetler
    def is_x_summary_item(item):
        platform_norm = normalize_text(item.get("platform", ""))
        source_norm = normalize_text(item.get("source_type", ""))
        return (
            "twitter" in platform_norm
            or platform_norm == "x"
            or platform_norm.startswith("x ")
            or "x" in source_norm
        )

    x_items_for_summary = [item for item in social if is_x_summary_item(item)]

    risky_x_for_summary = [
        item for item in x_items_for_summary
        if safe_float(item.get("account_adjusted_risk_score", item.get("risk_score", 0))) >= 6
        and not is_official_pr_or_service_item(item)
    ]

    risky_reply_count_for_summary = len([
        item for item in president_replies
        if safe_float(item.get("risk_score", 0)) >= 6
    ])

    crisis_subtitle = f"{early_warning.get('decision', '')} • Risk: {crisis_plan.get('level', '')}"
    learning_subtitle = f"{learning_note.get('operator_status', '')} • {learning_note.get('repeated_topic', '')}"
    youtube_subtitle = f"{len(youtube_summary)} kaynak / kanal takipte"
    x_count_for_data_flow = len([x for x in social if is_x_platform(x)])
    youtube_count_for_data_flow = len([x for x in social if is_youtube_platform(x)])
    data_flow_subtitle = f"Haber {len(news)} • X {x_count_for_data_flow} • YouTube {youtube_count_for_data_flow} • YouTube kaynak {len(youtube_summary)}"
       
    today_news_for_quality = [
        item for item in news
        if same_day(item.get("parsed_date", item.get("date", "")), dashboard_day)
    ]

    risky_news_for_quality = [
        item for item in news
        if safe_float(item.get("risk", 0)) >= 6
    ]

    news_quality_subtitle = f"{len(news)} haber • Özet günü {len(today_news_for_quality)} • Riskli {len(risky_news_for_quality)} • Tarihi okunamayan {len(undated_news or [])}"
    weekly_subtitle = f"{len(x_items_for_summary)} X kaydı • {len(risky_x_for_summary)} riskli"
    x_social_subtitle = f"{len(x_items_for_summary)} kayıt • {len(risky_x_for_summary)} riskli/takip gerektiren kayıt"
    service_subtitle = "Vatandaş şikayeti, kurumsal cevap ve hizmet duyurusu ayrımı"
    president_post_subtitle = f"Son {min(len(president_posts), 10)} Başkan X gönderisi analiz edildi"
    president_reply_subtitle = f"{len(president_replies)} yanıt • {risky_reply_count_for_summary} riskli yanıt"
    president_topic_subtitle = "Başkan X yanıtlarında tekrar eden konular"
    unmapped_subtitle = "Hesap haritasına eklenmesi gereken X hesapları"
    alert_subtitle = f"Son {len(alert_logs)} bildirim / alarm kaydı"
    team_action_subtitle = f"Son {len(team_actions)} ekip aksiyon kaydı"
    risky_social_subtitle = f"En riskli {len(risky_social)} sosyal medya kaydı"
    risky_reply_subtitle = f"{len(risky_replies)} riskli Başkan X yanıtı"
    crisis_log_subtitle = f"{len(crisis_log)} müdahale kaydı"

    crisis_alarm_section = accordion_section(
        "🚨 Güncel Kriz / Alarm Özeti",
        "#b91c1c",
        "#fef2f2",
        f"""
        <div class="card">
            <p><b>Risk seviyesi:</b> {esc(crisis_plan.get("level", ""))}</p>
            <p><b>Kriz başlığı:</b> {esc(crisis_plan.get("risk_topic", ""))}</p>
            <p><b>Karar:</b> {esc(early_warning.get("decision", ""))}</p>
            <p><b>Durum:</b> {esc(crisis_status.get("status", ""))}</p>
            <p><b>İlk aksiyon:</b> {esc(early_warning.get("first_action", ""))}</p>
        </div>
        """,
        opened=True,
        subtitle=crisis_subtitle,

    )

    data_flow_section = accordion_section(
        " Veri Akışı / Filtre Kalite Kontrolü",
        "#0f766e",
        "#ecfdf5",
        data_flow_quality,
        opened=True,
        subtitle=data_flow_subtitle,
    )
    
    news_quality_section = accordion_section(
        " Haber Filtre Kalite Kontrolü / Haber Detayları",
        "#2563eb",
        "#eff6ff",
        news_quality_html,
        subtitle=news_quality_subtitle,
    )

    learning_section = accordion_section(
        " Günlük Sistem Öğrenme Notu",
        "#334155",
        "#f8fafc",
        f"""

Operatör kontrol durumu: {esc(learning_note.get("operator_status", ""))}
Veri sağlık notu: {esc(learning_note.get("data_health", ""))}

Operatör aksiyon önerisi: {esc(learning_note.get("operator_action", ""))}

Ana risk değerlendirmesi: {esc(learning_note.get("main_risk", ""))}

Tekrarlayan / öne çıkan konu: {esc(learning_note.get("repeated_topic", ""))}

Filtre notu: {esc(learning_note.get("filter_note", ""))}

Ekip aksiyon notu: {esc(learning_note.get("action_note", ""))}

Arşiv notu: {esc(learning_note.get("archive_note", ""))}
Bir sonraki küçük gelişim: {esc(learning_note.get("next_improvement", ""))}

""",
    opened=True,
    subtitle=learning_subtitle,
)
    
    youtube_section = accordion_section(
        "📺 YouTube Kanal Takibi",
        "#334155",
        "#f8fafc",
        f"""
        <div class="card">
            Yerel YouTube kanallarında kontrol edilen videolar ve yerel gündemle alakalı bulunan yorum sayıları.
        </div>
        {youtube_summary_html(youtube_summary)}
        """,
        subtitle=youtube_subtitle,

    )

    weekly_section = accordion_section(
        "📊 X Haftalık Durum",
        "#334155",
        "#f8fafc",
        
        weekly_summary,
        subtitle=weekly_subtitle,

    )

    x_social_section = accordion_section(
        "🦚 X Sosyal Ağ Özeti",
        "#334155",
        "#f8fafc",
        
        x_summary_html,
        subtitle=x_social_subtitle,

    )

    service_section = accordion_section(
        "🟠 Hizmet Şikayeti / Kurumsal Cevap Durumu",
        "#d97706",
        "#fffbeb",
        service_complaint_followup,
        opened=True,
        subtitle=service_subtitle,

    )

    president_post_section = accordion_section(
        "🧭 Başkan X Gönderi Sınıflandırması",
        "#334155",
        "#f8fafc",
        president_post_classification,
        subtitle=president_post_subtitle,

    )

    president_reply_detail_section = accordion_section(
        "💬 Başkan X Yanıt Detayı",
        "#334155",
        "#f8fafc",
        president_replies_detail,
        subtitle=president_reply_subtitle,

    )

    president_reply_topic_section = accordion_section(
        "🔁 Başkan X Tekrar Eden Yanıt Konuları",
        "#334155",
        "#f8fafc",
        president_reply_topics,
        subtitle=president_topic_subtitle,

    )

    unmapped_section = accordion_section(
        "🧭 Sınıflandırılacak X Hesapları",
        "#334155",
        "#f8fafc",
        unmapped_x_accounts,
        subtitle=unmapped_subtitle,

    )

    alert_section = accordion_section(
        "📣 Bildirim Geçmişi / Alarm Kayıtları",
        "#0369a1",
        "#f0f9ff",
        alert_content,
        subtitle=alert_subtitle,

    )

    team_action_section = accordion_section(
        "✅ Bekleyen / Alınan Ekip Aksiyonları",
        "#16a34a",
        "#f0fdf4",
        team_action_content,
        subtitle=team_action_subtitle,

    )

    risky_social_section = accordion_section(
        "⚠️ En Riskli Sosyal Medya Kayıtları",
        "#b91c1c",
        "#fef2f2",
        risky_social_content,
        subtitle=risky_social_subtitle,
        
    )

    risky_reply_section = accordion_section(
        "💬 Başkan X Riskli Yanıt Takibi",
        "#b45309",
        "#fff7ed",
        risky_reply_content,
        subtitle=risky_reply_subtitle,

    )

    crisis_log_section = accordion_section(
        "📝 Müdahale Kayıtları",
        "#d97706",
        "#fffbeb",
        crisis_log_content,
        subtitle=crisis_log_subtitle,

    )

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

{crisis_alarm_section}
{data_flow_section}
{news_quality_section}
{learning_section}
<div id="detay-youtube"></div>
{youtube_section}
{weekly_section}
{x_social_section}
{service_section}
{president_post_section}
{president_reply_detail_section}
{president_reply_topic_section}
{unmapped_section}
{alert_section}
{team_action_section}
{risky_social_section}
{risky_reply_section}
{crisis_log_section}
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

    # Günlük başkan raporu "dün ne oldu?" sorusuna cevap verir.
    # Bu yüzden özet günü her zaman bir önceki gündür.
    dashboard_day = (now_tr.date() - dt.timedelta(days=1)).isoformat()
    important, positive_news, risky_news = top_items(news)
    social_sum = social_summary(social)
    youtube_summary = read_youtube_summary()
    crisis_sum = build_auto_crisis_summary(news, social_sum)
    crisis_plan = crisis_action_plan(crisis_sum)
    crisis_status = read_crisis_status()
    
    active_raw = str(crisis_status.get("active", "")).strip().lower()
    active_label = "Aktif" if active_raw in ["yes", "evet", "true", "1", "aktif"] else "Pasif"
    early_warning = early_warning_decision(crisis_plan, crisis_status, crisis_sum)
    
    dashboard_news = [
        item for item in news
        if same_day(item.get("parsed_date", item.get("date", "")), dashboard_day)
    ]

    dashboard_social = [
        item for item in social
        if same_day(item.get("date", ""), dashboard_day)
    ]

    dashboard_social_sum = social_summary(dashboard_social)
    dashboard_crisis_sum = build_auto_crisis_summary(dashboard_news, dashboard_social_sum)
    dashboard_crisis_plan = crisis_action_plan(dashboard_crisis_sum)
    dashboard_early_warning = early_warning_decision(
        dashboard_crisis_plan,
        crisis_status,
        dashboard_crisis_sum
    )
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
    opportunity_sum = build_opportunity_summary(news, social, president_posts, dashboard_day)
    archive_alert_logs = read_alert_log()
    archive_team_actions = read_team_actions()
    archive_president_replies = read_president_x_replies()

    archive_learning_note = build_system_learning_note(
        dashboard_news,
        dashboard_social,
        archive_alert_logs,
        archive_team_actions,
        archive_president_replies,
        dashboard_crisis_plan,
        dashboard_early_warning
    )

    append_daily_decision_log(
        dashboard_day,
        report_time,
        dashboard_news,
        dashboard_social,
        dashboard_crisis_plan,
        dashboard_early_warning,
        opportunity_sum,
        archive_learning_note,
        archive_team_actions
    )
    
    dashboard_html = president_dashboard_panel(
        dashboard_day,
        report_time,
        dashboard_news,
        dashboard_social,
        president_posts,
        dashboard_crisis_plan,
        dashboard_early_warning,
        opportunity_sum,
        news,
    )
    
    try:
        header_display_day = dt.datetime.strptime(str(dashboard_day), "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        header_display_day = str(dashboard_day)

    header_risk_level = str(dashboard_crisis_plan.get("level", "") or "")
    header_risk_norm = normalize_text(header_risk_level)
    header_opportunity_score = safe_score_value(opportunity_sum.get("score", 0))

    if "yuksek" in header_risk_norm or "yüksek" in header_risk_norm:
        header_status = "⚠️ Yüksek Risk"
    elif "orta" in header_risk_norm:
        header_status = "🟠 Orta Risk"
    elif header_opportunity_score >= 6:
        header_status = "🌟 Fırsat"
    else:
        header_status = "Normal Takip"

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
    <h1>Kepez — {header_display_day} — {header_status}</h1>
    <p>Sayın Başkan Günlük Özeti • Güncelleme: {report_time}</p>
</header>

<main>

{dashboard_html}

{section_label(" Acil Durum ve Operasyon Hızlı Erişim", "#b91c1c", "#fef2f2")}

<div class="card" style="
    border-left:6px solid #b91c1c;
    background:#fff7f7;
    margin:14px 0;
">
    <h2 style="margin-top:0;color:#991b1b;">🚨 Kriz ve Operasyon Kısayolları</h2>
    <p style="color:#475569;font-weight:700;line-height:1.45;">
        Kriz paneli, acil eylem planı ve ekip operasyon raporu başkan ekranında hızlı erişim için açık bırakılmıştır.
        Detaylı haber, sosyal medya ve analiz akışı aşağıdaki “Detaylı Rapor Akışını Aç” bölümündedir.
    </p>
</div>
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

<details id="detay-rapor-akisi" style="
    margin:18px 0;
    border-radius:20px;
">
    <summary style="
        cursor:pointer;
        list-style:none;
        background:#f8fafc;
        border:1.5px solid #334155;
        color:#334155;
        border-radius:20px;
        padding:16px;
        font-size:18px;
        font-weight:900;
        box-shadow:0 6px 18px rgba(15,23,42,0.05);
    ">
        📂 Detaylı Rapor Akışını Aç
        <div style="
            font-size:13px;
            font-weight:700;
            color:#64748b;
            margin-top:6px;
            line-height:1.35;
        ">
            Haber listeleri, sosyal medya detayları, kriz aksiyon planı, YouTube ve Başkan X ayrıntıları bu bölümde yer alır.
        </div>
    </summary>

    <div style="
        margin-top:14px;
        padding:4px 0;
    ">

{report_main_menu()}

<div id="haberler"></div>
<div id="detay-haberler"></div>
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

<div id="detay-social"></div>
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

    </div>
</details>

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
    
    build_team_report(news, social, early_warning, crisis_plan, crisis_status, report_time, undated_news)
    
    send_early_warning_email(early_warning, crisis_plan, crisis_status, report_time)

def main():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    news, undated_news = fetch_news()
    print(f"Haber tarama tamamlandı. Raporlanan haber: {len(news)}, Tarihi okunamayan: {len(undated_news)}")
    fetch_x_social_posts()
    fetch_youtube_social_comments()
    fetch_president_x_posts()
    fetch_president_x_replies()
    social = read_social_data()
    president_replies = read_president_x_replies()
    append_weekly_x_summary(social, president_replies)
    

    save_dynamic_keywords(generate_dynamic_keywords(news, social))

    html = build_report(news, social, undated_news)
    # save_report(html)

if __name__ == "__main__":
    main()
