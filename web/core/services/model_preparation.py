"""Signed confirmation of the model contract displayed by the service page."""

from django.core import signing

from src.model_operations import model_preparation_binding


SALT = "data-tools-model-preparation"


def preparation_confirmation() -> str:
    """Issue a short-lived confirmation bound to server configuration."""

    return signing.dumps(model_preparation_binding(), salt=SALT)


def confirmed_preparation_binding(data) -> str:
    """Require explicit consent and the unchanged signed contract."""

    if data.get("confirmation") != "prepare":
        raise ValueError("Bitte die Vorbereitung der konfigurierten Modelle ausdrücklich bestätigen.")
    try:
        expected = signing.loads(str(data.get("preparation_binding") or ""), salt=SALT, max_age=900)
    except signing.BadSignature:
        raise ValueError("Bestätigung fehlt oder ist abgelaufen. Seite neu laden und erneut bestätigen.") from None
    try:
        actual = model_preparation_binding()
    except (OSError, RuntimeError):
        raise ValueError("Modellkonfiguration kann nicht bestätigt werden. Konfiguration prüfen.") from None
    if not isinstance(expected, str) or expected != actual:
        raise ValueError("Modellkonfiguration wurde geändert. Seite neu laden und erneut bestätigen.")
    return expected
