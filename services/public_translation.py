import disnake
from firebase_admin import firestore

from database import db
from services.translation import selected_user_language, t


TRANSLATE_BUTTON_ID = "steward_translate_message"


def guild_ref(guild_id):
    return db.collection("guilds").document(str(guild_id))


def translatable_ref(guild_id, message_id):
    return guild_ref(guild_id).collection("translatable_messages").document(str(message_id))


def register_translatable_message(guild_id, message, message_type, payload=None):
    translatable_ref(guild_id, message.id).set(
        {
            "message_id": str(message.id),
            "channel_id": str(message.channel.id),
            "type": message_type,
            "payload": payload or {},
            "created_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )


class TranslateButton(disnake.ui.Button):
    def __init__(self, row=4):
        super().__init__(
            label="Translate",
            style=disnake.ButtonStyle.secondary,
            custom_id=TRANSLATE_BUTTON_ID,
            row=row,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        await send_translated_copy(inter)


def add_translate_button(view, row=4):
    if not any(getattr(item, "custom_id", None) == TRANSLATE_BUTTON_ID for item in view.children):
        view.add_item(TranslateButton(row=row))
    return view


async def send_translated_copy(inter):
    language_code = selected_user_language(inter.guild.id, inter.author.id)
    if not language_code:
        return await inter.response.send_message(
            t("translate.no_language", "en"),
            ephemeral=True,
        )

    doc = translatable_ref(inter.guild.id, inter.message.id).get()
    if not doc.exists:
        return await inter.response.send_message(
            t("translate.not_available", language_code),
            ephemeral=True,
        )

    embed = build_translated_embed(inter.guild.id, inter.message.id, doc.to_dict() or {}, language_code)
    if not embed:
        return await inter.response.send_message(
            t("translate.not_available", language_code),
            ephemeral=True,
        )

    await inter.response.send_message(
        content=t("translate.copy_notice", language_code),
        embed=embed,
        ephemeral=True,
    )


def build_translated_embed(guild_id, message_id, record, language_code):
    message_type = record.get("type")
    payload = record.get("payload", {}) or {}

    if message_type == "static_embed":
        return build_static_embed(payload, language_code)
    if message_type == "poll":
        return build_poll_embed(guild_id, message_id, language_code)
    if message_type == "bg_event":
        return build_bg_event_embed(guild_id, message_id, language_code)
    return None


def color_from_payload(payload, default=0xBE9146):
    return disnake.Color(int(payload.get("color", default)))


def build_static_embed(payload, language_code):
    embed = disnake.Embed(
        title=t(payload.get("title_key", ""), language_code),
        description=t(payload.get("description_key", ""), language_code),
        color=color_from_payload(payload),
    )
    for field in payload.get("fields", []) or []:
        embed.add_field(
            name=t(field.get("name_key", ""), language_code),
            value=t(field.get("value_key", ""), language_code),
            inline=field.get("inline", False),
        )
    footer_key = payload.get("footer_key")
    if footer_key:
        embed.set_footer(text=t(footer_key, language_code))
    return embed


def build_poll_embed(guild_id, message_id, language_code):
    poll_doc = guild_ref(guild_id).collection("polls").document(str(message_id)).get()
    if not poll_doc.exists:
        return None

    poll_data = poll_doc.to_dict() or {}
    question = poll_data.get("question", "Council Poll")
    options = poll_data.get("options", [])
    votes = poll_data.get("votes", {}) or {}
    closed = poll_data.get("status") == "closed"

    counts = {option: 0 for option in options}
    for choice in votes.values():
        if choice in counts:
            counts[choice] += 1

    title_key = "public.poll.title_closed" if closed else "public.poll.title_open"
    lines = [
        t("public.poll.option_line", language_code, option=option, count=counts.get(option, 0))
        for option in options
    ]
    embed = disnake.Embed(
        title=t(title_key, language_code, question=question),
        description="\n".join(lines) or t("public.poll.no_options", language_code),
        color=disnake.Color.dark_gray() if closed else disnake.Color.blue(),
    )

    if closed and counts:
        top_score = max(counts.values())
        winners = [option for option, count in counts.items() if count == top_score]
        embed.add_field(
            name=t("public.poll.winner", language_code),
            value=", ".join(winners),
            inline=False,
        )
    footer_key = "public.poll.footer_closed" if closed else "public.poll.footer_open"
    embed.set_footer(text=t(footer_key, language_code, total=len(votes)))
    return embed


def build_bg_event_embed(guild_id, message_id, language_code):
    event_doc = guild_ref(guild_id).collection("battleground_events").document(str(message_id)).get()
    if not event_doc.exists:
        return None

    event_data = event_doc.to_dict() or {}
    event_type = event_data.get("type", "Battleground")
    type_key = {
        "Titans of the North": "public.bg.type_titans",
        "The Great Ranging": "public.bg.type_ranging",
    }.get(event_type)
    translated_type = t(type_key, language_code) if type_key else event_type

    unix = int(event_data.get("starts_at_unix", 0))
    participants = event_data.get("participants", []) or []
    roster = "\n".join(f"- <@{user_id}>" for user_id in participants)

    embed = disnake.Embed(
        title=t("public.bg.title", language_code, type=translated_type),
        description=t("public.bg.description", language_code, unix=unix),
        color=disnake.Color(0xBE9146),
    )
    embed.add_field(
        name=t("public.bg.signed_up", language_code, count=len(participants)),
        value=roster or t("public.bg.no_signups", language_code),
        inline=False,
    )
    embed.set_footer(text=t("public.bg.footer", language_code))
    return embed
