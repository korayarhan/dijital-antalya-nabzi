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
    total_likes = sum(x["likes"] for x in social)
    total_comments = sum(x["comments"] for x in social)
    total_shares = sum(x["shares"] for x in social)
    total_views = sum(x["views"] for x in social)
    total_good = sum(x["good_comments"] for x in social)
    total_neutral = sum(x["neutral_comments"] for x in social)
    total_bad = sum(x["bad_comments"] for x in social)
    like_rate = (total_likes / total_views * 100) if total_views else 0
    engagement_rate = ((total_likes + total_comments + total_shares) / total_views * 100) if total_views else 0
    return {
        "total_likes": total_likes, "total_comments": total_comments,
        "total_shares": total_shares, "total_views": total_views,
        "total_good": total_good, "total_neutral": total_neutral, "total_bad": total_bad,
        "like_rate": like_rate, "engagement_rate": engagement_rate,
        "best_like": max(social, key=lambda x: x["like_rate"], default=None),
        "most_comments": max(social, key=lambda x: x["comments"], default=None),
        "risky": max(social, key=lambda x: x["risk_score"], default=None),
        "opportunity": max(social, key=lambda x: x["opportunity_score"], default=None),
    }


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
    today = dt.date.today().isoformat()
    important, positive_news, risky_news = top_items(news)
    social_sum = social_summary(social)

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
        strategy_focus = "Riskleri büyütmeden kontrol etmek, olumlu hizmet başlıklarını görünür tutmak ve başkan profilini güven veren bir çizgide korumak."
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
    <p>Takip edilen isim: <b>Mesut Kocagöz</b> • Bölge: <b>Antalya / Kepez</b> • Tarih: <b>{today}</b></p>
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

<p>Bugün iletişimde amaç sadece haber paylaşmak değil; Mesut Kocagöz algısını “sahada çalışan, gündemi takip eden, hizmeti önceleyen ve krizleri büyütmeden yöneten başkan” çizgisinde güçlendirmek olmalıdır.</p>

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
    
{esc(daily_language)}

Bugün kullanılabilecek ana mesaj şudur:

“Kepez’de önceliğimiz, vatandaşın günlük hayatına dokunan işleri sahada ve sürdürülebilir biçimde büyütmek. Hizmeti mahalle mahalle görünür hale getirmeye devam ediyoruz.”
</div>

<div class="card">
    <h2>12. Stratejik Yorum</h2>
    <div class="item"><h3>A) Bugün Öne Çıkarılacak Konu</h3><p>Bugün olumlu etki üretme potansiyeli en yüksek alan; hizmet, mahalle çalışması, çocuk/aile teması ve değer odaklı içeriklerdir. Özellikle vatandaşla temas eden, sahadan görüntü içeren ve insan hikayesi taşıyan paylaşımlar öne çıkarılmalıdır.</p></div>
    <div class="item"><h3>B) Dikkat Edilecek Risk</h3><p>Teleferik, dava, borç, şikayet ve hizmet aksaması içeren başlıklar kontrollü biçimde takip edilmelidir. Bu başlıklarda hızlı tepki yerine; sakin, belgeye dayalı ve hukuki sürece saygılı bir iletişim dili kullanılmalıdır.</p></div>
    <div class="item"><h3>C) Önerilen İletişim Dili</h3><p>Bugün önerilen dil; sert siyasi polemik değil, sade hizmet dili ve güven veren başkan profili olmalıdır. Mesajlar kısa, anlaşılır, mahalleye dokunan ve vatandaşın gündelik hayatına temas eden şekilde kurulmalıdır.</p></div>
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
