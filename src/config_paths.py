import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONFIG = ROOT / "config" / "keywords.txt"

SOCIAL_CSV = ROOT / "data" / "manual_social" / "social_manual.csv"
AUTO_SOCIAL_CSV = ROOT / "data" / "auto_social" / "social_auto.csv"
PRESIDENT_X_CSV = ROOT / "data" / "auto_social" / "president_x_posts.csv"
PRESIDENT_X_REPLIES_CSV = ROOT / "data" / "auto_social" / "president_x_replies.csv"
YOUTUBE_SOCIAL_CSV = ROOT / "data" / "auto_social" / "youtube_social.csv"
INSTAGRAM_SOCIAL_CSV = ROOT / "data" / "auto_social" / "instagram_social.csv"
YOUTUBE_SUMMARY_CSV = ROOT / "data" / "auto_social" / "youtube_summary.csv"

YOUTUBE_WATCH_CSV = ROOT / "data" / "social_watch" / "youtube_watch.csv"
ACCOUNTS_MAP_CSV = ROOT / "data" / "social_watch" / "accounts_map.csv"
INSTAGRAM_ACCOUNTS_MAP_CSV = ROOT / "data" / "social_watch" / "instagram_accounts_map.csv"
WATCH_KEYWORDS_CSV = ROOT / "data" / "social_watch" / "watch_keywords.csv"

CRISIS_CSV = ROOT / "data" / "manual_crisis" / "crisis_status.csv"
CRISIS_LOG_CSV = ROOT / "data" / "manual_crisis" / "crisis_log.csv"

ALERT_LOG_CSV = ROOT / "data" / "alerts" / "alert_log.csv"
TEAM_ACTIONS_CSV = ROOT / "data" / "team_actions" / "team_actions.csv"
DEMO_SOCIAL_ACCOUNTS_CSV = ROOT / "data" / "demo" / "demo_social_accounts.csv"

ARCHIVE_DIR = ROOT / "data" / "archive"
X_DATA_DIR = ROOT / "data" / "x"
X_API_HEALTH_CSV = X_DATA_DIR / "x_api_health.csv"
DAILY_DECISION_LOG_CSV = ARCHIVE_DIR / "daily_decision_log.csv"

DYNAMIC_KEYWORDS = ROOT / "data" / "dynamic_keywords.txt"
REPORTS = ROOT / "reports"

PRESIDENT_X_USERNAME = "mesutkocagoztr"

RUN_VERSION = (dt.datetime.utcnow() + dt.timedelta(hours=3)).strftime("%Y%m%d%H%M%S")

REPORTS.mkdir(exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
X_DATA_DIR.mkdir(parents=True, exist_ok=True)