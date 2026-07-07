from database import db


LOGISTICS_ROLE_FIELD = "logistics_role"


def get_guild_config(guild_id):
    doc = db.collection("guilds").document(str(guild_id)).get()
    return doc.to_dict() if doc.exists else {}


def is_admin_member(member):
    permissions = getattr(member, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


def has_role_id(member, role_id):
    if not role_id:
        return False
    return any(role.id == int(role_id) for role in getattr(member, "roles", []))


def logistics_role_id(config):
    return config.get(LOGISTICS_ROLE_FIELD) or config.get("logistics_role_id")


def has_logistics_access(inter):
    if is_admin_member(inter.author):
        return True
    config = get_guild_config(inter.guild.id)
    return has_role_id(inter.author, logistics_role_id(config))


def logistics_denied_message():
    return "Only server administrators or the configured Logistics role can use this."
