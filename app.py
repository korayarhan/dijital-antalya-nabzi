import csv
import os
import datetime as dt
import html
import re
import urllib.parse
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "keywords.txt"
SOCIAL_CSV = ROOT / "data" / "manual_social" / "social_manual.csv"
CRISIS_CSV = ROOT / "data" / "manual_crisis" / "crisis_status.csv"
CRISIS_LOG_CSV = ROOT / "data" / "manual_crisis" / "crisis_log.csv"
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


def read_social_data():
    if not SOCIAL_CSV.exists():
        return []
    rows = []
    with SOCIAL_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            likes = to_float(row.get("likes"))
            comments = to_float(row.get("comments"))
            shares = to_float(row.get("shares"))
            views = to_float(row.get("views"))
            good = to_float(row.get("good_comments"))
            neutral = to_float(row.get("neutral_comments"))
            bad = to_float(row.get("bad_comments"))
            like_rate = (likes / views * 100) if views else 0
            engagement_rate = ((likes + comments + shares) / views * 100) if views else 0
            total = good + neutral + bad
            bad_ratio = bad / total if total else 0
            good_ratio = good / total if total else 0
            row.update({
                "likes": likes, "comments": comments, "shares": shares, "views": views,
                "good_comments": good, "neutral_comments": neutral, "bad_comments": bad,
                "like_rate": like_rate, "engagement_rate": engagement_rate,
                "risk_score": min(10, round(bad_ratio * 8 + (2 if row.get("tone") == "Kötü" else 0), 1)),
                "opportunity_score": min(10, round(good_ratio * 8 + (2 if like_rate > 5 else 0), 1)),
            })
            rows.append(row)
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
                    "responsible": str(row.get("responsible", "") or "").strip(),
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


def news_card(item):
    return f"""
    <div class="item">
        <h3>{esc(item["title"])}</h3>
        <p class="muted">Anahtar kelime: {esc(item["keyword"])}</p>
        <p><span class="pill {item["tone"].lower()}">{esc(item["tone"])}</span><span class="pill">Risk: {item["risk"]}/10</span><span class="pill">Fırsat: {item["opportunity"]}/10</span></p>
        <p>{esc(item.get("summary", ""))[:240]}</p>
        <p><a href="{esc(item["link"])}" target="_blank">Haberi aç</a></p>
    </div>
    """


def social_link(link):
    link = str(link or "").strip()
    if not link:
        return ""
    if "example.com" in link:
        return '<p class="muted"><b>Link:</b> Manuel sosyal medya verisi</p>'
    return f'<p><a href="{esc(link)}" target="_blank">Paylaşımı aç</a></p>'


def social_card(title, item):
    if not item:
        return f'<div class="item"><h3>{esc(title)}</h3><p class="muted">Henüz sosyal medya verisi girilmedi.</p></div>'
    return f"""
    <div class="item">
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


def build_report(news, social, undated_news=None):
    undated_news = undated_news or []
    now_tr = dt.datetime.utcnow() + dt.timedelta(hours=3)
    today = now_tr.date().isoformat()
    report_time = now_tr.strftime("%H:%M")
    important, positive_news, risky_news = top_items(news)
    social_sum = social_summary(social)
    crisis_plan = crisis_action_plan(social_sum)
    crisis_status = read_crisis_status()
    
    active_raw = str(crisis_status.get("active", "")).strip().lower()
    active_label = "Aktif" if active_raw in ["yes", "evet", "true", "1", "aktif"] else "Pasif"
    
    crisis_log = read_crisis_log()

    crisis_log_html = ""
    for item in crisis_log:
        crisis_log_html += f"""
    <div style="padding:12px; border-radius:12px; background:#ffffff; border:1px solid #e2e8f0; margin-bottom:10px;">
      <div style="font-weight:bold; color:#991b1b;">{esc(item.get("time", ""))} - {esc(item.get("event", ""))}</div>
      <div><b>Aksiyon:</b> {esc(item.get("action", ""))}</div>
      <div><b>Sorumlu:</b> {esc(item.get("responsible", ""))}</div>
      <div><b>Not:</b> {esc(item.get("note", ""))}</div>
    </div>
    """

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
        <tr><td>{esc(item.get("date"))}</td><td>{esc(item.get("platform"))}</td><td>{esc(item.get("topic"))}</td><td>{esc(item.get("tone"))}</td><td>%{item["like_rate"]:.2f}</td><td>{item["risk_score"]}/10</td><td>{item["opportunity_score"]}/10</td></tr>
        """
    if not social_rows:
        social_rows = "<tr><td colspan='7'>Henüz manuel sosyal medya verisi girilmedi.</td></tr>"
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
<div style="margin:18px 0; padding:14px; border:2px solid #dc2626; border-radius:14px; background:#fff7ed;">
  <a href="crisis_panel.html" style="font-size:18px; font-weight:bold; color:#991b1b; text-decoration:none;">
    🚨 Acil Eylem Planı / Kriz Panelini Aç
  </a>
  <div style="margin-top:6px; color:#7f1d1d;">
    Risk seviyesi: {esc(crisis_plan.get("level", ""))} • Durum: {esc(crisis_status.get("status", ""))} • Son güncelleme: {report_time}
  </div>
</div>
</header>

<main>
<div class="card notice">
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

<div class="card"><h2>2. Bugünün En Önemli 3 Başlığı</h2>{important_html}</div>
<div class="card"><h2>3. Öne Çıkan Olumlu Haberler</h2>{positive_html}</div>
<div class="card"><h2>4. Riskli / İzlenmesi Gereken Haberler</h2>{risky_html}</div>

<div class="card">
 <h2>4.1 Tarihi Okunamayan Ama Takip Edilmesi Gereken Haberler</h2>
 <p class="muted">Bu bölümdeki haberler Kepez / Antalya / Mesut Kocagöz filtresinden geçmiştir; ancak haber tarihi sistem tarafından okunamadığı için ana günlük gündeme doğrudan dahil edilmemiştir.</p>
 {undated_html}
</div>

<div class="card">
 <h2>5. Sosyal Medya Etkileşim Analizi</h2>
    <div class="kpis">
        <div class="kpi"><b>{int(social_sum["total_likes"])}</b><span>Toplam beğeni</span></div>
        <div class="kpi"><b>{int(social_sum["total_comments"])}</b><span>Toplam yorum</span></div>
        <div class="kpi"><b>%{social_sum["like_rate"]:.2f}</b><span>Beğenme oranı</span></div>
        <div class="kpi"><b>%{social_sum["engagement_rate"]:.2f}</b><span>Etkileşim oranı</span></div>
    </div>
    
        <div class="item">
            <h3>Sayın Başkan İçin Sosyal Medya Özeti</h3>
            <p><b>Genel ton:</b> {esc(social_sum.get("social_mood", ""))}</p>
            <p><b>Öne çıkan konu:</b> {esc(social_sum.get("main_topic", ""))}</p>
            <p><b>Risk yorumu:</b> {esc(social_sum.get("risk_text", ""))}</p>
            <p><b>Fırsat yorumu:</b> {esc(social_sum.get("opportunity_text", ""))}</p>
            <p><b>İlk aksiyon önerisi:</b> {esc(social_sum.get("action_text", ""))}</p>
        </div>
        
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

<div class="card">
    <h2>10. Manuel Sosyal Medya Kayıtları</h2>
    <table>
        <tr><th>Tarih</th><th>Platform</th><th>Konu</th><th>Ton</th><th>Beğenme</th><th>Risk</th><th>Fırsat</th></tr>
        {social_rows}
    </table>
</div>

<div class="card">
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

    crisis_news_html = "".join(news_card(x) for x in risky_news[:3]) or "<div class='card'>Krizle ilişkili riskli haber bulunamadı.</div>"

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

    <div class="card soft">
      <h2>🕒 Kriz Zaman Çizelgesi / Olay Akışı</h2>
      <p class="small">Bu bölüm kriz boyunca yapılan işlemleri, alınan aksiyonları ve sorumlu kişileri takip etmek için kullanılır.</p>
      {crisis_log_html}
    </div>

    <div class="card danger">
      <h2>Sayın Başkan İçin İlk Uyarı</h2>
      <p><b>Şu an yapılmaması gereken:</b><br>{esc(crisis_plan.get("what_not_to_do", ""))}</p>
      <p><b>İlk doğru hamle:</b><br>{esc(crisis_plan.get("first_30", ""))}</p>
      <p><b>Sayın Başkan konuşmalı mı?</b><br>{esc(crisis_plan.get("speaker_decision", crisis_plan.get("speaker", "")))}</p>
    </div>

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

    <div class="card">
      <h2>Son Riskli Haberler</h2>
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

def main():
    os.makedirs("reports", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    news, undated_news = fetch_news()
    social = read_social_data()

    save_dynamic_keywords(generate_dynamic_keywords(news, social))

    html = build_report(news, social, undated_news)
    # save_report(html)

if __name__ == "__main__":
    main()
