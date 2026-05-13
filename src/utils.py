import html
import re


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


def to_float(x):
    try:
        return float(str(x or "0").replace(",", "."))
    except ValueError:
        return 0.0


def safe_score_value(value, default=0):
    try:
        return float(str(value or default).replace(",", ".").strip())
    except:
        return default


def same_day(value, today):
    value = str(value or "").strip()
    return value.startswith(today) or today in value


def clean_topic_title(raw_topic):
    text = normalize_text(raw_topic)

    if not text:
        return "Genel yorum gündemi"

    text = text.replace("_", " ").replace("-", " ")

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

    if any(term in text for term in [
        "teleferik", "facia", "mahkeme", "sorusturma", "soruşturma",
        "iddianame", "yargi", "yargı", "hukuk", "tutuklama"
    ]):
        return "Teleferik davası / hukuki süreç hassasiyeti"

    if any(term in text for term in [
        "asfalt", "yol", "kaldirim", "kaldırım", "cukur", "çukur",
        "bozuk yol", "duaci", "duacı"
    ]):
        return "Asfalt / yol hizmeti şikayetleri"

    if any(term in text for term in [
        "temizlik", "cop", "çöp", "park", "mahalle", "saha",
        "hizmet", "şikayet", "sikayet"
    ]):
        return "Mahalle hizmetleri / vatandaş şikayetleri"

    if any(term in text for term in [
        "ulasim", "ulaşım", "otobus", "otobüs", "durak",
        "buyuksehir", "büyükşehir"
    ]):
        return "Büyükşehir / ulaşım gündemi"

    if any(term in text for term in ["borc", "borç", "mali", "butce", "bütçe", "tasarruf"]):
        return "Mali disiplin / borç açıklamaları"

    if any(term in text for term in ["cocuk", "çocuk", "aile", "23 nisan", "senlik", "şenlik", "festival"]):
        return "Çocuk, aile ve sosyal etkinlikler"

    if any(term in text for term in ["spor", "drag", "turnuva", "musabaka", "müsabaka"]):
        return "Spor ve etkinlik görünürlüğü"

    if any(term in text for term in ["bayrak", "personel", "odul", "ödül", "kurumsal"]):
        return "Bayrak, personel ve kurumsal görünürlük"

    if any(term in text for term in [
        "siyasi", "rakip", "ak parti", "chp", "ocak",
        "dava arkadas", "dava arkadaş", "dava buyuk", "dava büyük"
    ]):
        return "Siyasi görünürlük / rakip çevre takibi"

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


def contains_any(text, terms):
    text = normalize_text(text)
    return any(normalize_text(term) in text for term in terms)