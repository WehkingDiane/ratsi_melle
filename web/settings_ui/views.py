"""Views for local UI settings."""

from __future__ import annotations

from django.shortcuts import render

from src.config.secrets import delete_api_key
from src.config.secrets import key_source
from src.config.secrets import set_api_key


_TOKEN_PROVIDERS = {
    "huggingface": {
        "label": "Hugging Face",
        "env_hint": "HF_TOKEN oder HUGGING_FACE_HUB_TOKEN",
    },
}


def index(request):
    messages: list[str] = []
    errors: list[str] = []

    if request.method == "POST":
        action = request.POST.get("action", "")
        provider_id = request.POST.get("provider_id", "")
        provider = _TOKEN_PROVIDERS.get(provider_id)
        if provider is None:
            errors.append("Unbekannter Token-Typ.")
        elif action == "save_token":
            token = request.POST.get("token", "").strip()
            if not token:
                errors.append("Bitte einen Token eingeben.")
            else:
                try:
                    set_api_key(provider_id, token)
                    messages.append(f"{provider['label']}-Token gespeichert.")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Token konnte nicht gespeichert werden: {exc}")
        elif action == "delete_token":
            delete_api_key(provider_id)
            messages.append(f"{provider['label']}-Token geloescht.")
        else:
            errors.append("Unbekannte Aktion.")

    token_sources = [
        {
            "provider_id": provider_id,
            "label": data["label"],
            "env_hint": data["env_hint"],
            "source": key_source(provider_id),
        }
        for provider_id, data in _TOKEN_PROVIDERS.items()
    ]
    return render(
        request,
        "settings_ui/index.html",
        {
            "active_nav": "settings",
            "messages": messages,
            "errors": errors,
            "token_sources": token_sources,
        },
    )
