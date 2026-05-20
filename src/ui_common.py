import datetime as dt
import json

from src.config_paths import REPORTS, RUN_VERSION


def page_version():
    return RUN_VERSION


def write_pwa_version_file():
    version_file = REPORTS / "version.json"

    payload = {
        "version": page_version(),
        "updated_at": (dt.datetime.utcnow() + dt.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
    }

    version_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"PWA version dosyası hazır: {version_file}")


def pwa_head_tags():
    v = page_version()

    return f"""
<link rel="manifest" href="../manifest.json?v={v}">
<meta name="theme-color" content="#0f172a">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Yerel Lider AI">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="../neon_tech_crest_with_glowing_ai_symbol.png?v={v}">

<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">

<script>
(function () {{
    var pageVersion = "{v}";
    var refreshing = false;

    function reloadWithVersion(latestVersion) {{
        if (refreshing) return;

        var url = new URL(window.location.href);
        var urlVersion = url.searchParams.get("v");

        if (urlVersion === latestVersion && pageVersion === latestVersion) {{
            return;
        }}

        refreshing = true;
        url.searchParams.set("v", latestVersion);
        window.location.replace(url.pathname + url.search + url.hash);
    }}

    function checkLatestVersion() {{
        fetch("version.json?t=" + Date.now(), {{
            cache: "no-store"
        }})
        .then(function (response) {{
            if (!response.ok) return null;
            return response.json();
        }})
        .then(function (data) {{
            if (!data || !data.version) return;

            var latestVersion = String(data.version).trim();

            if (latestVersion && latestVersion !== pageVersion) {{
                reloadWithVersion(latestVersion);
            }}
        }})
        .catch(function () {{
            // Sessiz geç. İnternet yoksa veya dosya okunamazsa sayfa açık kalır.
        }});
    }}

    window.addEventListener("pageshow", function () {{
        setTimeout(checkLatestVersion, 400);
    }});

    document.addEventListener("visibilitychange", function () {{
        if (!document.hidden) {{
            setTimeout(checkLatestVersion, 400);
        }}
    }});

    window.addEventListener("focus", function () {{
        setTimeout(checkLatestVersion, 400);
    }});

    setInterval(function () {{
        if (!document.hidden) {{
            checkLatestVersion();
        }}
    }}, 60000);

    setTimeout(checkLatestVersion, 700);
}})();
</script>
"""


def top_nav_html(active=""):
    v = page_version()

    items = [
        ("Ana Ekran", f"index.html?v={v}", "home"),
        ("Sabah", f"briefing.html?v={v}", "briefing"),
        ("Canlı", f"daily_report.html?v={v}#platform-sosyal-nabiz", "live"),
        ("Tam Rapor", f"daily_report.html?v={v}#top", "daily"),
        ("Ekip", f"team_report.html?v={v}", "team"),
    ]

    buttons = []

    for label, href, key in items:
        active_class = " active" if active == key else ""
        buttons.append(
            f'<a class="top-nav-btn top-nav-{key}{active_class}" href="{href}">{label}</a>'
        )

    return f"""
<div class="top-nav-wrap">
    <div class="top-nav-scroll">
        {''.join(buttons)}
    </div>
</div>
"""


def top_nav_css():
    return """
<style>
.top-nav-wrap {
    position: sticky;
    top: 0;
    z-index: 999;
    background: rgba(13,15,20,0.96);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    padding: 10px 14px 8px;
}

.top-nav-scroll {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
}

.top-nav-scroll::-webkit-scrollbar {
    display: none;
}

.top-nav-btn {
    white-space: nowrap;
    text-decoration: none;
    color: #d1d5db;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 999px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 800;
}

.top-nav-home {
    background: rgba(59,130,246,0.15);
    border-color: rgba(59,130,246,0.35);
}

.top-nav-briefing {
    background: rgba(249,115,22,0.15);
    border-color: rgba(249,115,22,0.35);
}

.top-nav-live {
    background: rgba(16,185,129,0.15);
    border-color: rgba(16,185,129,0.35);
}

.top-nav-daily {
    background: rgba(59,130,246,0.15);
    border-color: rgba(59,130,246,0.35);
}

.top-nav-team {
    background: rgba(139,92,246,0.15);
    border-color: rgba(139,92,246,0.35);
}

.top-nav-btn.active {
    color: #ffffff;
    box-shadow:
        inset 0 0 0 1px rgba(255,255,255,0.20),
        0 0 18px rgba(255,255,255,0.06);
}

.top-nav-home.active {
    background: rgba(59,130,246,0.26);
    border-color: rgba(59,130,246,0.70);
}

.top-nav-briefing.active {
    background: rgba(249,115,22,0.26);
    border-color: rgba(249,115,22,0.70);
}

.top-nav-live.active {
    background: rgba(16,185,129,0.26);
    border-color: rgba(16,185,129,0.70);
}

.top-nav-daily.active {
    background: rgba(59,130,246,0.26);
    border-color: rgba(59,130,246,0.70);
}

.top-nav-team.active {
    background: rgba(139,92,246,0.26);
    border-color: rgba(139,92,246,0.70);
}

html {
    scroll-behavior: smooth;
}

#top,
#baskan-ozet,
#baskan-firsat,
#platform-sosyal-nabiz,
#detay-baskan-x,
#detay-haberler,
#detay-social,
#baskan-kriz {
    scroll-margin-top: 78px;
}

.back-to-top-btn {
    position: fixed;
    right: 14px;
    bottom: calc(18px + env(safe-area-inset-bottom));
    z-index: 1000;
    width: 46px;
    height: 46px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(15,23,42,0.94);
    color: #ffffff !important;
    text-decoration: none;
    border: 1px solid rgba(255,255,255,0.22);
    box-shadow: 0 14px 32px rgba(0,0,0,0.32);
    font-size: 24px;
    font-weight: 950;
}

.back-to-top-btn:active {
    transform: scale(0.96);
}

@media print {
    .back-to-top-btn {
        display: none !important;
    }
}
</style>
"""


def back_to_top_html():
    return """
<a class="back-to-top-btn" href="#top" aria-label="Sayfa başına dön" title="Yukarı çık">↑</a>
"""