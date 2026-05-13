import html
import re


def esc(value):
    """
    HTML içinde güvenli yazı basmak için kullanılır.
    0 değerini boş göstermemek için None ayrı kontrol edilir.
    """
    if value is None:
        return ""
    return html.escape(str(value))


def clean_text(text):
    """
    HTML etiketlerini ve fazla boşlukları temizler.
    """
    text = html.unescape(str(text or ""))
    text = re.sub(r"<.*?>", "", text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text(text):
    """
    Karşılaştırma ve filtreleme için metni sadeleştirir.
    """
    text = str(text or "").lower().replace("ı", "i")
    text = re.sub(r"[^a-zA-ZğüşöçıİĞÜŞÖÇ0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def to_float(value, default=0.0):
    """
    Sayı alanlarını güvenli float'a çevirir.
    """
    try:
        return float(str(value or default).replace(",", ".").strip())
    except Exception:
        return default


def safe_score_value(value, default=0.0):
    """
    Risk/fırsat/etkileşim skorlarını güvenli sayıya çevirir.
    """
    try:
        return float(str(value or default).replace(",", ".").strip())
    except Exception:
        return default


def contains_any(text, terms):
    """
    Normalize edilmiş metin içinde verilen terimlerden biri var mı kontrol eder.
    """
    normalized = normalize_text(text)
    return any(normalize_text(term) in normalized for term in terms)


def same_day(value, target_day):
    """
    Tarih alanı hedef günle aynı mı kontrol eder.
    """
    value = str(value or "").strip()
    target_day = str(target_day or "").strip()
    return value.startswith(target_day) or target_day in value