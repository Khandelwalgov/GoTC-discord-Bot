import disnake
from disnake.ext import commands

from services.translation import (
    LANGUAGE_CHOICES,
    SUPPORTED_LANGUAGES,
    get_user_language,
    language_code_from_native,
    language_native_name,
    set_user_language,
    t,
)


BRAND_COLOR = disnake.Color.from_rgb(190, 145, 70)


class LanguageSelect(disnake.ui.Select):
    def __init__(self, current_language):
        options = [
            disnake.SelectOption(
                label=info["native"],
                value=code,
                default=code == current_language,
            )
            for code, info in SUPPORTED_LANGUAGES.items()
        ]
        super().__init__(
            placeholder=t("language.select_placeholder", current_language),
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        language_code = self.values[0]
        set_user_language(inter.guild.id, inter.author.id, language_code)
        await inter.response.edit_message(
            embed=language_set_embed(language_code),
            view=None,
        )


class LanguageView(disnake.ui.View):
    def __init__(self, current_language):
        super().__init__(timeout=120)
        self.add_item(LanguageSelect(current_language))


def language_set_embed(language_code):
    embed = disnake.Embed(
        title=t("language.saved_title", language_code, language=language_native_name(language_code)),
        description=t("language.saved_description", language_code),
        color=BRAND_COLOR,
    )
    embed.add_field(
        name=t("language.coverage_title", language_code),
        value=t("language.coverage_body", language_code),
        inline=False,
    )
    embed.add_field(
        name=t("language.next_title", language_code),
        value=t("language.next_body", language_code),
        inline=False,
    )
    return embed


class Language(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="language", description="Choose your Steward language")
    async def language(
        self,
        inter: disnake.ApplicationCommandInteraction,
        language: str = commands.Param(
            default=None,
            choices=LANGUAGE_CHOICES,
            description="Choose your language",
        ),
    ):
        await inter.response.defer(ephemeral=True)
        current_language = get_user_language(inter.guild.id, inter.author.id)

        if language:
            language_code = language_code_from_native(language)
            if not language_code:
                return await inter.edit_original_message(
                    content=t("language.unsupported", current_language)
                )
            set_user_language(inter.guild.id, inter.author.id, language_code)
            return await inter.edit_original_message(embed=language_set_embed(language_code))

        embed = disnake.Embed(
            title=t("language.select_title", current_language),
            description=t("language.select_description", current_language),
            color=BRAND_COLOR,
        )
        embed.add_field(
            name=t("language.current_title", current_language),
            value=language_native_name(current_language),
            inline=False,
        )
        await inter.edit_original_message(
            embed=embed,
            view=LanguageView(current_language),
        )


def setup(bot):
    bot.add_cog(Language(bot))
