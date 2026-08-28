import re
import secrets
import unicodedata


def slugify(value: str, max_length: int = 120) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    slug = slug[:max_length].rstrip("-")
    return slug or f"item-{secrets.token_hex(4)}"
