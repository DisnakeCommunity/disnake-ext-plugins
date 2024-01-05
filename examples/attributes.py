import disnake
from disnake.ext import plugins

# Parameters specified inside the plugin metadata's `command_attrs`,
# `message_command_attrs`, `slash_command_attrs`, and `user_command_attrs`
# will automatically be provided to the decorators of prefix commands,
# message commands, slash commands and user commands, respectively.


plugin = plugins.Plugin(slash_command_attrs={"guild_ids": [1234]})


# This slash command will automatically receive the `guild_ids = [1234]`
# defined inside the plugin's metadata.


@plugin.slash_command()
async def my_command(inter: disnake.CommandInteraction):
    ...


# This slash command overwrites the guild_ids provided by the metadata.
# It will not be available inside the guild with id 1234, but instead
# only inside the guild with id 5678.


@plugin.slash_command(guild_ids=[5678])
async def my_other_command(inter: disnake.CommandInteraction):
    ...


# You can also manually define and pass attribute "bundles". This is regular
# python "unpack" syntax, so you can't pass the same parameter both in the bundle
# and as a parameter. Additionally, annotating bundle's type will ensure that you
# don't accidentally make a typo or pass an extraneous parameter.

attrs: plugins.AppCommandAttrs = {"auto_sync": False}

# This command will not be automatically synced and will be only avail
@plugin.slash_command(**attrs)
async def another_command(inter: disnake.CommandInteraction):
    ...


setup, teardown = plugin.create_extension_handlers()
