import json
from pathlib import Path

from firebase_admin import firestore

from database import db


DEFAULT_LANGUAGE = "en"

SUPPORTED_LANGUAGES = {
    "en": {"native": "English", "english": "English"},
    "de": {"native": "Deutsch", "english": "German"},
    "fr": {"native": "Français", "english": "French"},
    "es": {"native": "Español", "english": "Spanish"},
    "ru": {"native": "Русский", "english": "Russian"},
    "pt": {"native": "Português", "english": "Portuguese"},
    "it": {"native": "Italiano", "english": "Italian"},
    "tr": {"native": "Türkçe", "english": "Turkish"},
    "hi": {"native": "हिन्दी", "english": "Hindi"},
    "el": {"native": "Ελληνικά", "english": "Greek"},
}

LANGUAGE_CHOICES = [info["native"] for info in SUPPORTED_LANGUAGES.values()]

_LOCALES = {}


def guild_ref(guild_id):
    return db.collection("guilds").document(str(guild_id))


def language_pref_ref(guild_id, user_id):
    return guild_ref(guild_id).collection("language_preferences").document(str(user_id))


def language_code_from_native(native_name):
    for code, info in SUPPORTED_LANGUAGES.items():
        if info["native"] == native_name:
            return code
    return native_name if native_name in SUPPORTED_LANGUAGES else None


def language_native_name(language_code):
    return SUPPORTED_LANGUAGES.get(language_code, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])["native"]


def load_locale(language_code):
    language_code = language_code if language_code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    if language_code in _LOCALES:
        return _LOCALES[language_code]

    path = Path(__file__).resolve().parent.parent / "locales" / f"{language_code}.json"
    with path.open("r", encoding="utf-8") as locale_file:
        _LOCALES[language_code] = json.load(locale_file)
    return _LOCALES[language_code]


def selected_user_language(guild_id, user_id):
    doc = language_pref_ref(guild_id, user_id).get()
    if not doc.exists:
        return None
    language_code = (doc.to_dict() or {}).get("language")
    return language_code if language_code in SUPPORTED_LANGUAGES else None


def get_user_language(guild_id, user_id):
    selected = selected_user_language(guild_id, user_id)
    if selected:
        return selected

    # Backward/forward compatibility if language is later copied onto profiles.
    user_doc = guild_ref(guild_id).collection("users").document(str(user_id)).get()
    if user_doc.exists:
        language_code = (user_doc.to_dict() or {}).get("language")
        if language_code in SUPPORTED_LANGUAGES:
            return language_code

    guild_doc = guild_ref(guild_id).get()
    if guild_doc.exists:
        language_code = (guild_doc.to_dict() or {}).get("default_language")
        if language_code in SUPPORTED_LANGUAGES:
            return language_code

    return DEFAULT_LANGUAGE


def set_user_language(guild_id, user_id, language_code):
    if language_code not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language_code}")

    language_pref_ref(guild_id, user_id).set(
        {
            "language": language_code,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    user_ref = guild_ref(guild_id).collection("users").document(str(user_id))
    user_doc = user_ref.get()
    if user_doc.exists:
        user_ref.set(
            {
                "language": language_code,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )


class SafeFormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def t(key, language_code=DEFAULT_LANGUAGE, **kwargs):
    locale = load_locale(language_code)
    fallback = load_locale(DEFAULT_LANGUAGE)
    value = locale.get(key, fallback.get(key, key))
    if kwargs and isinstance(value, str):
        return value.format_map(SafeFormatDict(**kwargs))
    return value
