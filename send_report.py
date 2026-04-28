import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_HTML = ROOT / "reports" / "daily_report.html"
REPORT_PDF = ROOT / "reports" / "daily_report.pdf"


def send_email():
    mail_user = os.environ.get("MAIL_USER")
    mail_pass = os.environ.get("MAIL_PASS")
    mail_to = os.environ.get("MAIL_TO")

    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not mail_user or not mail_pass or not mail_to:
        raise RuntimeError("MAIL_USER, MAIL_PASS veya MAIL_TO GitHub Secrets içinde eksik.")

    if not REPORT_PDF.exists():
        raise FileNotFoundError("PDF raporu bulunamadı: reports/daily_report.pdf")

    msg = EmailMessage()
    msg["Subject"] = "Yerel Liderlik AI Günlük Raporu"
    msg["From"] = mail_user
    msg["To"] = mail_to

    msg.set_content(
        """Merhaba,

Yerel Liderlik AI Takip Sistemi günlük raporu ekte PDF olarak yer almaktadır.

Web rapor linki:
https://korayarhan.github.io/dijital-antalya-nabzi/reports/daily_report.html

Bu mail GitHub Actions tarafından otomatik gönderilmiştir.
"""
    )

    pdf_data = REPORT_PDF.read_bytes()
    msg.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename="yerel_liderlik_ai_gunluk_raporu.pdf"
    )

    with smtplib.SMTP(smtp_server, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(mail_user, mail_pass)
        smtp.send_message(msg)

    print("Mail başarıyla gönderildi.")


if __name__ == "__main__":
    send_email()
