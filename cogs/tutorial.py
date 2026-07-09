import disnake
from disnake.ext import commands

from services.translation import get_user_language, t


BRAND_COLOR = disnake.Color.from_rgb(190, 145, 70)

MEMBER_TUTORIAL_PAGES = [
    "start",
    "language",
    "register",
    "roles",
    "add_alt",
    "stats",
    "dragon",
    "access",
    "update_access",
    "lookup",
    "bubble",
    "time",
    "weekend",
    "battlegrounds",
    "update_name",
    "help",
]

ADMIN_TUTORIAL_PAGES = [
    "start",
    "permissions",
    "roles",
    "logistics_council",
    "logs_autorole",
    "member_onboarding",
    "battlegrounds",
    "polls",
    "roster_overview",
    "roster_import",
    "roster_updates",
    "roster_expiry_exports",
    "troubleshooting",
]


def page_index(page_id, pages):
    if page_id in pages:
        return pages.index(page_id)
    return 0


def build_tutorial_embed(language_code, page_id, pages, prefix):
    index = page_index(page_id, pages)
    page_prefix = f"{prefix}.{page_id}"
    embed = disnake.Embed(
        title=t(f"{page_prefix}.title", language_code),
        description=t(f"{page_prefix}.description", language_code),
        color=BRAND_COLOR,
    )

    for section in ("goal", "steps", "example", "tips"):
        value = t(f"{page_prefix}.{section}", language_code)
        if value and value != f"{page_prefix}.{section}":
            embed.add_field(
                name=t(f"tutorial.section.{section}", language_code),
                value=value,
                inline=False,
            )

    embed.set_footer(
        text=t(
            "tutorial.footer",
            language_code,
            current=index + 1,
            total=len(pages),
        )
    )
    return embed


class TutorialTopicSelect(disnake.ui.Select):
    def __init__(self, language_code, current_page, pages, prefix):
        self.pages = pages
        self.prefix = prefix
        options = [
            disnake.SelectOption(
                label=t(f"{prefix}.nav.{page_id}", language_code),
                value=page_id,
                default=page_id == current_page,
            )
            for page_id in pages
        ]
        placeholder_key = f"{prefix}.select_placeholder"
        placeholder = t(placeholder_key, language_code)
        if placeholder == placeholder_key:
            placeholder = t("tutorial.select_placeholder", language_code)

        super().__init__(
            placeholder=placeholder,
            options=options,
            row=0,
        )
        self.language_code = language_code

    async def callback(self, inter: disnake.MessageInteraction):
        page_id = self.values[0]
        await inter.response.edit_message(
            embed=build_tutorial_embed(self.language_code, page_id, self.pages, self.prefix),
            view=TutorialView(self.language_code, page_id, self.pages, self.prefix),
        )


class TutorialView(disnake.ui.View):
    def __init__(self, language_code, current_page, pages, prefix):
        super().__init__(timeout=600)
        self.language_code = language_code
        self.current_page = current_page
        self.pages = pages
        self.prefix = prefix
        self.add_item(TutorialTopicSelect(language_code, current_page, pages, prefix))

        index = page_index(current_page, pages)
        self.previous_page.disabled = index == 0
        self.next_page.disabled = index == len(pages) - 1
        self.previous_page.label = t("tutorial.button.previous", language_code)
        self.next_page.label = t("tutorial.button.next", language_code)
        self.done.label = t("tutorial.button.done", language_code)

    async def go_to_page(self, inter, page_id):
        await inter.response.edit_message(
            embed=build_tutorial_embed(self.language_code, page_id, self.pages, self.prefix),
            view=TutorialView(self.language_code, page_id, self.pages, self.prefix),
        )

    @disnake.ui.button(label="Back", style=disnake.ButtonStyle.secondary, row=1)
    async def previous_page(self, button, inter):
        index = max(0, page_index(self.current_page, self.pages) - 1)
        await self.go_to_page(inter, self.pages[index])

    @disnake.ui.button(label="Next", style=disnake.ButtonStyle.primary, row=1)
    async def next_page(self, button, inter):
        index = min(len(self.pages) - 1, page_index(self.current_page, self.pages) + 1)
        await self.go_to_page(inter, self.pages[index])

    @disnake.ui.button(label="Done", style=disnake.ButtonStyle.success, row=1)
    async def done(self, button, inter):
        await inter.response.edit_message(
            content=t(f"{self.prefix}.done", self.language_code),
            embed=None,
            view=None,
        )


class Tutorial(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="tutorial", description="Open the guided Steward tutorial")
    async def tutorial(
        self,
        inter: disnake.ApplicationCommandInteraction,
        topic: str = commands.Param(
            default=None,
            description="Optional tutorial topic",
        ),
    ):
        await inter.response.defer(ephemeral=True)
        language_code = get_user_language(inter.guild.id, inter.author.id)
        page_id = topic.lower().strip() if topic else "start"
        if page_id not in MEMBER_TUTORIAL_PAGES:
            page_id = "start"

        await inter.edit_original_message(
            embed=build_tutorial_embed(language_code, page_id, MEMBER_TUTORIAL_PAGES, "tutorial"),
            view=TutorialView(language_code, page_id, MEMBER_TUTORIAL_PAGES, "tutorial"),
        )

    @tutorial.autocomplete("topic")
    async def tutorial_topic_autocomplete(self, inter, string: str):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        query = string.lower()
        return [
            disnake.OptionChoice(
                name=t(f"tutorial.nav.{page_id}", language_code),
                value=page_id,
            )
            for page_id in MEMBER_TUTORIAL_PAGES
            if query in page_id or query in t(f"tutorial.nav.{page_id}", language_code).lower()
        ][:25]

    @commands.slash_command(name="tutorial_admin", description="Open the Steward admin setup tutorial")
    async def tutorial_admin(
        self,
        inter: disnake.ApplicationCommandInteraction,
        topic: str = commands.Param(
            default=None,
            description="Optional admin tutorial topic",
        ),
    ):
        await inter.response.defer(ephemeral=True)
        language_code = get_user_language(inter.guild.id, inter.author.id)
        page_id = topic.lower().strip() if topic else "start"
        if page_id not in ADMIN_TUTORIAL_PAGES:
            page_id = "start"

        await inter.edit_original_message(
            embed=build_tutorial_embed(language_code, page_id, ADMIN_TUTORIAL_PAGES, "admin_tutorial"),
            view=TutorialView(language_code, page_id, ADMIN_TUTORIAL_PAGES, "admin_tutorial"),
        )

    @tutorial_admin.autocomplete("topic")
    async def admin_tutorial_topic_autocomplete(self, inter, string: str):
        language_code = get_user_language(inter.guild.id, inter.author.id)
        query = string.lower()
        return [
            disnake.OptionChoice(
                name=t(f"admin_tutorial.nav.{page_id}", language_code),
                value=page_id,
            )
            for page_id in ADMIN_TUTORIAL_PAGES
            if query in page_id or query in t(f"admin_tutorial.nav.{page_id}", language_code).lower()
        ][:25]


def setup(bot):
    bot.add_cog(Tutorial(bot))
