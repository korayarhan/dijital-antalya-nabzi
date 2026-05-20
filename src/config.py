import os
from pathlib import Path

# Proje ana klasörü
ROOT = Path(__file__).resolve().parents[1]

# Ana klasörler
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

# Geriye uyumluluk için bazı eski isimler
REPORTS = REPORTS_DIR
REPORT_DIR = REPORTS_DIR

# Config / anahtar kelime dosyaları
KEYWORDS_FILE = CONFIG_DIR / "keywords.txt"
DYNAMIC_KEYWORDS_FILE = DATA_DIR / "dynamic_keywords.txt"

# Sosyal medya veri klasörleri
AUTO_SOCIAL_DIR = DATA_DIR / "auto_social"
X_DATA_DIR = AUTO_SOCIAL_DIR
MANUAL_SOCIAL_DIR = DATA_DIR / "manual_social"
SOCIAL_WATCH_DIR = DATA_DIR / "social_watch"

# Sosyal medya CSV dosyaları
MANUAL_SOCIAL_CSV = MANUAL_SOCIAL_DIR / "social_manual.csv"
SOCIAL_MANUAL_CSV = MANUAL_SOCIAL_CSV

SOCIAL_AUTO_CSV = AUTO_SOCIAL_DIR / "social_auto.csv"
AUTO_SOCIAL_CSV = SOCIAL_AUTO_CSV

PRESIDENT_X_POSTS_CSV = AUTO_SOCIAL_DIR / "president_x_posts.csv"
PRESIDENT_X_REPLIES_CSV = AUTO_SOCIAL_DIR / "president_x_replies.csv"
X_API_HEALTH_CSV = AUTO_SOCIAL_DIR / "x_api_health.csv"

YOUTUBE_SOCIAL_CSV = AUTO_SOCIAL_DIR / "youtube_social.csv"
YOUTUBE_SUMMARY_CSV = AUTO_SOCIAL_DIR / "youtube_summary.csv"

INSTAGRAM_SOCIAL_CSV = AUTO_SOCIAL_DIR / "instagram_social.csv"

# Sosyal izleme / hesap haritası
ACCOUNTS_MAP_CSV = SOCIAL_WATCH_DIR / "accounts_map.csv"
INSTAGRAM_ACCOUNTS_MAP_CSV = SOCIAL_WATCH_DIR / "instagram_accounts_map.csv"
YOUTUBE_WATCH_CSV = SOCIAL_WATCH_DIR / "youtube_watch.csv"
WATCH_KEYWORDS_CSV = SOCIAL_WATCH_DIR / "watch_keywords.csv"

# Kriz / alarm / ekip aksiyon dosyaları
MANUAL_CRISIS_DIR = DATA_DIR / "manual_crisis"
CRISIS_CSV = MANUAL_CRISIS_DIR / "crisis_status.csv"
CRISIS_LOG_CSV = MANUAL_CRISIS_DIR / "crisis_log.csv"

ALERTS_DIR = DATA_DIR / "alerts"
ALERT_LOG_CSV = ALERTS_DIR / "alert_log.csv"

TEAM_ACTIONS_DIR = DATA_DIR / "team_actions"
TEAM_ACTIONS_CSV = TEAM_ACTIONS_DIR / "team_actions.csv"

# Arşiv / hafıza
ARCHIVE_DIR = DATA_DIR / "archive"
DAILY_DECISION_LOG_CSV = ARCHIVE_DIR / "daily_decision_log.csv"

# Demo veri
DEMO_DIR = DATA_DIR / "demo"
DEMO_SOCIAL_ACCOUNTS_CSV = DEMO_DIR / "demo_social_accounts.csv"

# Rapor çıktıları
DAILY_REPORT_HTML = REPORTS_DIR / "daily_report.html"
TEAM_REPORT_HTML = REPORTS_DIR / "team_report.html"
CRISIS_PANEL_HTML = REPORTS_DIR / "crisis_panel.html"
VERSION_JSON = REPORTS_DIR / "version.json"

# Başkan X hesabı
PRESIDENT_X_USERNAME = os.getenv("PRESIDENT_X_USERNAME", "mesutkocagoztr")