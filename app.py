import datetime as dt
import html
import urllib.parse
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "keywords.txt"
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

POSITIVE_WORDS = [
    "hizmet", "asfalt", "açılış", "ödül", "teşekkür", "çocuk",
    "şenlik", "proje", "destek", "spor", "başarı", "tamamlandı"
]

RISK_WORDS = [
    "dava", "facia", "kaza", "tepki", "şikayet", "kriz",
    "eleştiri", "borç", "iddia", "tartışma", "soruşturma"
]


def read_keywords():
    if not CONFIG.exists():
        return []
    return [
        x.strip()
        for x in CONFIG.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


def classify(text):
    t = text.lower()
    positive = sum(1 for w in POSITIVE_WORDS if w in t)
    risk = sum(1 for w in RISK_WORDS if w in t)

    if risk > positive:
        tone = "Riskli"
    elif positive > risk:
        tone = "Olumlu"
    else:
        tone = "Nötr"

    return tone, min(10, risk * 3), min(10, positive * 2)


def google_news_url(keyword):
    q = urllib.parse.quote_plus(keyword)
    return f"https://news.google.com/rss/search?q={q}&hl=tr&gl=TR&ceid=TR:tr"


def fetch_news():
    rows = []
    seen = set()

    for keyword in read_keywords():
        feed = feedparser.parse(google_news_url(keyword))

        for item in feed.entries[:8]:
            title = getattr(item, "title", "")
            link = getattr(item, "link", "")
            date = getattr(item, "published", "")

            if not title or title in seen:
                continue

            seen.add(title)
            tone, risk, opportunity = classify(title)

            rows.append({
                "keyword": keyword,
                "title": title,
                "link": link,
                "date": date,
                "tone": tone,
                "risk": risk,
                "opportunity": opportunity,
            })

    return rows


def esc(x):
    return html.escape(str(x or ""))


def build_report(news):
    today = dt.date.today().isoformat()

    positive_count = sum(1 for x in news if x["tone"] == "Olumlu")
    risk_count = sum(1 for x in news if x["tone"] == "Riskli")
    neutral_count = sum(1 for x in news if x["tone"] == "Nötr")

    items = ""
    for n in news[:25]:
        items += f"""
        <div class="item">
            <h3>{esc(n["title"])}</h3>
            <p><b>Anahtar kelime:</b> {esc(n["keyword"])}</p>
            <p><b>Ton:</b> {esc(n["tone"])} | <b>Risk:</b> {n["risk"]}/10 | <b>Fırsat:</b> {n["opportunity"]}/10</p>
            <p><a href="{esc(n["link"])}" target="_blank">Haberi aç</a></p>
        </div>
        """

    html_doc = f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Yerel Liderlik AI Günlük Raporu</title>
<style>
body {{
    margin:0;
    background:#f6f3ee;
    color:#1f2933;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
}}
header {{
    background:linear-gradient(135deg,#2f3a45,#5d4c38);
    color:white;
    padding:22px 16px;
}}
main {{
    padding:16px;
    max-width:900px;
    margin:auto;
}}
.card,.item {{
    background:white;
    border:1px solid #e5ded4;
    border-radius:18px;
    padding:16px;
    margin-bottom:14px;
    box-shadow:0 8px 22px rgba(0,0,0,.06);
}}
h1 {{font-size:23px;margin:0 0 6px}}
h2 {{font-size:19px}}
h3 {{font-size:15px;margin-bottom:6px}}
.kpis {{
    display:grid;
    grid-template-columns:repeat(2,1fr);
    gap:10px;
}}
.kpi {{
    background:#fbfaf8;
    border:1px solid #e5ded4;
    border-radius:16px;
    padding:14px;
}}
.kpi b {{
    display:block;
    font-size:24px;
}}
a {{
    color:#2f3a45;
    font-weight:700;
}}
</style>
</head>
<body>
<header>
<h1>Yerel Liderlik AI Günlük Raporu</h1>
<p>Takip edilen isim: <b>Mesut Kocagöz</b> • Bölge: <b>Antalya / Kepez</b> • Tarih: <b>{today}</b></p>
</header>

<main>
<div class="card">
<h2>Genel Özet</h2>
<div class="kpis">
<div class="kpi"><b>{len(news)}</b><span>Toplam haber</span></div>
<div class="kpi"><b>{positive_count}</b><span>Olumlu</span></div>
<div class="kpi"><b>{neutral_count}</b><span>Nötr</span></div>
<div class="kpi"><b>{risk_count}</b><span>Riskli</span></div>
</div>
<p>Bu rapor Google News RSS üzerinden anahtar kelime bazlı otomatik tarama ile hazırlanmıştır.</p>
</div>

<div class="card">
<h2>Stratejik Kısa Yorum</h2>
<p>Olumlu haberler hizmet, etkinlik ve görünürlük açısından fırsat üretir. Riskli başlıklar ise ayrıca takip edilmeli ve büyümeden not alınmalıdır.</p>
</div>

<div class="card">
<h2>Otomatik Haber Taraması</h2>
{items if items else "<p>Haber bulunamadı.</p>"}
</div>
</main>
</body>
</html>"""

    out = REPORTS / "daily_report.html"
    out.write_text(html_doc, encoding="utf-8")
    print(f"Rapor hazır: {out}")


def main():
    news = fetch_news()
    build_report(news)


if __name__ == "__main__":
    main()
