import csv
import datetime as dt
import html
import re
import urllib.parse
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "keywords.txt"
SOCIAL_CSV = ROOT / "data" / "manual_social" / "social_manual.csv"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

POSITIVE_WORDS = [
    "hizmet", "asfalt", "açılış", "ödül", "teşekkür", "çocuk",
    "şenlik", "proje", "destek", "spor", "başarı", "tamamlandı",
    "coşku", "yatırım", "park", "festival", "yardım", "duyarlılık",
    "bayrak", "personel", "mahalle"
]

RISK_WORDS = [
    "dava", "facia", "kaza", "tepki", "şikayet", "kriz",
    "eleştiri", "borç", "iddia", "tartışma", "soruşturma",
    "yargı", "protesto", "usulsüz", "ceza", "gündem oldu"
]


def esc(x):
    return html.escape(str(x or ""))


def clean_text(text):
    text = html.unescape(str(text or ""))
    text = re.sub(r"<.*?>", "", text)
    text = text.replace("\xa0", " ")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def read_keywords():
    if not CONFIG.exists():
        return []
    return [
        x.strip()
        for x in CONFIG.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


def classify(text):
    t = str(text or "").lower()
    positive = sum(1 for w in POSITIVE_WORDS if w in t)
    risk = sum(1 for w in RISK_WORDS if w in t)

    if risk > positive:
        tone = "Riskli"
    elif positive > risk:
        tone = "Olumlu"
    else:
        tone = "Nötr"

    risk_score = min(10, risk * 3 + (2 if tone == "Riskli" else 0))
    opportunity_score = min(10, positive * 2 + (2 if tone == "Olumlu" else 0))

    return tone, risk_score, opportunity_score


def google_news_url(keyword):
    q = urllib.parse.quote_plus(keyword)
    return f"https://news.google.com/rss/search?q={q}&hl=tr&gl=TR&ceid=TR:tr"


def fetch_news():
    rows = []
    seen_titles = set()

    for keyword in read_keywords():
        feed = feedparser.parse(google_news_url(keyword))

        for item in feed.entries[:10]:
            title = clean_text(getattr(item, "title", ""))
            link = getattr(item, "link", "")
            date = getattr(item, "published", "")
            summary = clean_text(getattr(item, "summary", ""))

            if not title:
                continue

            short_title_key = re.sub(r"\s+", " ", title.lower())[:90]
            if short_title_key in seen_titles:
                continue

            seen_titles.add(short_title_key)
            tone, risk, opportunity = classify(title + " " + summary)

            rows.append({
                "keyword": keyword,
                "title": title,
                "link": link,
                "date": date,
                "summary": summary,
                "tone": tone,
                "risk": risk,
                "opportunity": opportunity,
            })

    return rows


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

            total_comment_tone = good + neutral + bad
            bad_ratio = bad / total_comment_tone if total_comment_tone else 0
            good_ratio = good / total_comment_tone if total_comment_tone else 0

            risk_score = min(10, round(bad_ratio * 8 + (2 if row.get("tone") == "Kötü" else 0), 1))
            opportunity_score = min(10, round(good_ratio * 8 + (2 if like_rate > 5 else 0), 1))

            row.update({
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "views": views,
                "good_comments": good,
                "neutral_comments": neutral,
                "bad_comments": bad,
                "like_rate": like_rate,
                "engagement_rate": engagement_rate,
                "risk_score": risk_score,
                "opportunity_score": opportunity_score,
            })

            rows.append(row)

    return rows


def topic_key(title):
    t = str(title or "").lower()

    if "teleferik" in t or "facia" in t or "dava" in t:
        return "teleferik_davasi"
    if "asfalt" in t or "duacı" in t or "yol" in t:
        return "hizmet_asfalt"
    if "bayrak" in t or "personel" in t or "ödül" in t:
        return "bayrak_personel"
    if "23 nisan" in t or "çocuk" in t or "şenlik" in t:
        return "cocuk_aile"
    if "borç" in t or "mali" in t:
        return "mali_disiplin"
    if "drag" in t or "spor" in t:
        return "spor_etkinlik"

    words = re.sub(r"[^a-zA-ZğüşöçıİĞÜŞÖÇ0-9 ]", "", t).split()
    return "_".join(words[:4])


def unique_by_topic(items, limit):
    result = []
    used = set()

    for item in items:
        key = topic_key(item.get("title", ""))
        if key in used:
            continue
        used.add(key)
        result.append(item)

        if len(result) >= limit:
            break

    return result


def top_items(news):
    positive_candidates = sorted(
        [x for x in news if x["tone"] == "Olumlu"],
        key=lambda x: x["opportunity"],
        reverse=True
    )

    service_candidates = sorted(
        [
            x for x in news
            if any(k in str(x.get("title", "")).lower() for k in ["asfalt", "duacı", "hizmet", "mahalle", "yol", "park"])
        ],
        key=lambda x: x["opportunity"],
        reverse=True
    )

    risk_candidates = sorted(
        [x for x in news if x["tone"] == "Riskli"],
        key=lambda x: x["risk"],
        reverse=True
    )

    positive = unique_by_topic(positive_candidates, 5)
    risky = unique_by_topic(risk_candidates, 5)

    important = []

    if positive_candidates:
        important.append(positive_candidates[0])

    if service_candidates:
        service_item = service_candidates[0]
        if service_item not in important:
            important.append(service_item)

    if risk_candidates:
        risk_item = risk_candidates[0]
        if risk_item not in important:
            important.append(risk_item)

    if len(important) < 3:
        remaining = sorted(
            news,
            key=lambda x: x["risk"] + x["opportunity"],
            reverse=True
        )

        for item in remaining:
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

    best_like = max(social, key=lambda x: x["like_rate"], default=None)
    most_comments = max(social, key=lambda x: x["comments"], default=None)
    risky = max(social, key=lambda x: x["risk_score"], default=None)
    opportunity = max(social, key=lambda x: x["opportunity_score"], default=None)

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
    }


def bar(label, value, color_class):
    value = max(0, min(100, float(value or 0)))
    return f"""
    <div class="bar-row">
        <div class="bar-label">
            <span>{esc(label)}</span>
            <b>%{value:.1f}</b>
        </div>
        <div class="bar">
            <div class="{color_class}" style="width:{value:.1f}%"></div>
        </div>
    </div>
    """


def news_card(item):
    return f"""
    <div class="item">
        <h3>{esc(item["title"])}</h3>
        <p class="muted">Anahtar kelime: {esc(item["keyword"])}</p>
        <p>
            <span class="pill {item["tone"].lower()}">{esc(item["tone"])}</span>
            <span class="pill">Risk: {item["risk"]}/10</span>
            <span class="pill">Fırsat: {item["opportunity"]}/10</span>
        </p>
        <p>{esc(item.get("summary", ""))[:220]}</p>
        <p><a href="{esc(item["link"])}" target="_blank">Haberi aç</a></p>
    </div>
    """


def social_card(title, item):
    if not item:
        return f"""
        <div class="item">
            <h3>{esc(title)}</h3>
            <p class="muted">Henüz sosyal medya verisi girilmedi.</p>
        </div>
        """

    return f"""
    <div class="item">
        <h3>{esc(title)}</h3>
        <p><b>{esc(item.get("topic"))}</b></p>
        <p class="muted">{esc(item.get("platform"))} • {esc(item.get("date"))}</p>
        <p>
            Beğeni: <b>{int(item["likes"])}</b> •
            Yorum: <b>{int(item["comments"])}</b> •
            Paylaşım: <b>{int(item["shares"])}</b> •
            Görüntülenme: <b>{int(item["views"])}</b>
        </p>
        <p>
            Beğenme oranı: <b>%{item["like_rate"]:.2f}</b> •
            Etkileşim oranı: <b>%{item["engagement_rate"]:.2f}</b>
        </p>
        <p>
            Risk: <b>{item["risk_score"]}/10</b> •
            Fırsat: <b>{item["opportunity_score"]}/10</b>
        </p>
        <p>{esc(item.get("notes"))}</p>
        <p class="risk-note">{esc(item.get("risk_note"))}</p>
        <p><a href="{esc(item.get("link"))}" target="_blank">Paylaşımı aç</a></p>
    </div>
    """


def build_report(news, social):
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

    social_rows = ""
    for item in social:
        social_rows += f"""
        <tr>
            <td>{esc(item.get("date"))}</td>
            <td>{esc(item.get("platform"))}</td>
            <td>{esc(item.get("topic"))}</td>
            <td>{esc(item.get("tone"))}</td>
            <td>%{item["like_rate"]:.2f}</td>
            <td>{item["risk_score"]}/10</td>
            <td>{item["opportunity_score"]}/10</td>
        </tr>
        """

    if not social_rows:
        social_rows = "<tr><td colspan='7'>Henüz manuel sosyal medya verisi girilmedi.</td></tr>"

    tomorrow_keywords = ", ".join(read_keywords()[:10])

    html_doc = f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yerel Liderlik AI Günlük Raporu</title>
<style>
:root {{
    --bg:#f6f3ee;
    --card:#ffffff;
    --ink:#1f2933;
    --muted:#6b7280;
    --line:#e5ded4;
    --accent:#8b6f47;
    --dark:#2f3a45;
    --good:#177245;
    --bad:#a33a2b;
    --neutral:#7a6f64;
    --warn:#b7791f;
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
    background:linear-gradient(135deg,#2f3a45,#5d4c38);
    color:white;
    padding:24px 16px;
}}
header h1 {{
    margin:0 0 6px;
    font-size:23px;
    letter-spacing:-.3px;
}}
header p {{
    margin:0;
    opacity:.92;
    font-size:14px;
}}
main {{
    padding:16px;
    max-width:980px;
    margin:auto;
}}
.card,.item {{
    background:var(--card);
    border:1px solid var(--line);
    border-radius:18px;
    padding:16px;
    margin-bottom:14px;
    box-shadow:0 8px 22px rgba(31,41,51,.06);
}}
h2 {{
    font-size:19px;
    margin:4px 0 12px;
}}
h3 {{
    font-size:15px;
    margin:0 0 8px;
}}
.muted {{
    color:var(--muted);
    font-size:13px;
}}
.kpis {{
    display:grid;
    grid-template-columns:repeat(2,1fr);
    gap:10px;
    margin:10px 0;
}}
@media(min-width:760px) {{
    .kpis {{ grid-template-columns:repeat(4,1fr); }}
    .grid {{ grid-template-columns:1fr 1fr; }}
}}
.kpi {{
    background:#fbfaf8;
    border:1px solid var(--line);
    border-radius:16px;
    padding:14px;
}}
.kpi b {{
    display:block;
    font-size:24px;
}}
.kpi span {{
    color:var(--muted);
    font-size:12px;
    font-weight:700;
}}
.grid {{
    display:grid;
    gap:12px;
}}
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
.pill.olumlu {{
    background:#e8f5ee;
    color:var(--good);
}}
.pill.riskli {{
    background:#fdeceb;
    color:var(--bad);
}}
.pill.nötr {{
    background:#f1eee8;
    color:var(--neutral);
}}
.bar-row {{
    margin:10px 0;
}}
.bar-label {{
    display:flex;
    justify-content:space-between;
    font-size:13px;
    margin-bottom:5px;
}}
.bar {{
    height:11px;
    background:#ebe4dc;
    border-radius:999px;
    overflow:hidden;
}}
.bar div {{
    height:100%;
}}
.bar .good {{ background:var(--good); }}
.bar .neutral {{ background:var(--neutral); }}
.bar .bad {{ background:var(--bad); }}
.bar .accent {{ background:var(--accent); }}
table {{
    width:100%;
    border-collapse:collapse;
    font-size:13px;
    background:white;
    border-radius:14px;
    overflow:hidden;
}}
th,td {{
    padding:9px;
    border-bottom:1px solid var(--line);
    text-align:left;
    vertical-align:top;
}}
th {{
    background:#fbfaf8;
}}
a {{
    color:#2f3a45;
    font-weight:800;
}}
.risk-note {{
    color:var(--bad);
}}
.notice {{
    border-left:5px solid var(--accent);
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

<div class="card">
    <h2>2. Bugünün En Önemli 3 Başlığı</h2>
    {important_html}
</div>

<div class="card">
    <h2>3. Öne Çıkan Olumlu Haberler</h2>
    {positive_html}
</div>

<div class="card">
    <h2>4. Riskli / İzlenmesi Gereken Haberler</h2>
    {risky_html}
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
        <tr>
            <th>Tarih</th>
            <th>Platform</th>
            <th>Konu</th>
            <th>Ton</th>
            <th>Beğenme</th>
            <th>Risk</th>
            <th>Fırsat</th>
        </tr>
        {social_rows}
    </table>
</div>

<div class="card">
    <h2>11. Kriz Erken Uyarı</h2>
    <p>Bugün riskli haber sayısı <b>{risk_count}</b>. Sosyal medyada kötü yorum oranı <b>%{bad_pct:.1f}</b>.</p>
    <p>Teleferik, dava, borç, şikayet ve hizmet aksaması içeren başlıklar ayrıca izlenmelidir.</p>
</div>

<div class="card">
    <h2>12. Stratejik Yorum</h2>
    <p>Bugünkü raporda hizmet, mahalle çalışması, çocuk/aile teması ve değer odaklı içerikler olumlu algı üretme potansiyeli taşır. Riskli başlıklarda ise savunmacı dil yerine sakin, bilgi veren ve hukuki sürece saygılı bir dil tercih edilmelidir.</p>
</div>

<div class="card">
    <h2>13. Bugün Ne Yapılmalı?</h2>
    <ul>
        <li>En yüksek beğenme oranı alan paylaşımın dili tekrar kullanılmalı.</li>
        <li>Olumlu haberler sade, insan hikayesi içeren kısa sosyal medya içeriklerine çevrilmeli.</li>
        <li>Riskli başlıklarda yorumlar izlenmeli; gereksiz polemiğe girilmemeli.</li>
        <li>Mahalle bazlı hizmet başlıkları görselle desteklenmeli.</li>
    </ul>
</div>

<div class="card">
    <h2>14. Yarın Takip Edilecek Başlıklar</h2>
    <p>{esc(tomorrow_keywords)}</p>
</div>

</main>
</body>
</html>
"""

    out = REPORTS / "daily_report.html"
    out.write_text(html_doc, encoding="utf-8")
    print(f"Rapor hazır: {out}")


def main():
    news = fetch_news()
    social = read_social_data()
    build_report(news, social)


if __name__ == "__main__":
    main()
