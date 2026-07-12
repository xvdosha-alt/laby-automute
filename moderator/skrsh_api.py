import base64
import uuid
from datetime import date, datetime

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
EPOCH = date(2020, 1, 1)


def encode_days(value: date | None = None) -> str:
    if value is None:
        value = date.today()
    days_diff = abs((value - EPOCH).days)
    base = len(CHARS)
    quotient = days_diff // base
    remainder = days_diff - quotient * base
    return CHARS[quotient] + CHARS[remainder]


def build_short_url(free_id: str, short_base: str = "https://skr.sh") -> str:
    return f"{short_base.rstrip('/')}/s{encode_days()}{free_id}"


def build_screenshot_id(free_id: str, value: date | None = None) -> str:
    if value is None:
        value = date.today()
    return f"{value.strftime('%d%m%y')}/{free_id}"


def build_upload_filename() -> str:
    return f"Скриншот {datetime.now().strftime('%d-%m-%Y %H%M%S')}"


def encode_filename(filename: str) -> str:
    return base64.b64encode(filename.encode("utf-8")).decode("ascii")


def make_app_id() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"
