import disnake
from disnake.ext import commands, plugins

# Create a basic plugin...
# Without providing any extra data, a plugin will be instantiated with only a
# name. This name will default to the file in which the plugin was created.
# In this case, a plugin named "basic" would be created.

basic_plugin = plugins.Plugin()


# Next, we register a command on the plugin.
# This is very similar to creating commands normally, but we now use the
# `@Plugin.command()` decorator to register the command on the plugin.


@basic_plugin.command()
async def my_command(ctx: commands.Context[commands.Bot]):
    await ctx.reply("hi!")


# Similarly, we can register slash, user, and message commands.
# Plugins also support listeners as per usual:


@basic_plugin.listener("on_message")
async def my_listener(msg: disnake.Message):
    ...


# Just like any other type of disnake extension, if we wish to load this from
# the main file using `Bot.load_extension()`, we need to define `setup` and
# `teardown` functions. Plugins provide a simple way of making these functions:


setup, teardown = basic_plugin.create_extension_handlers()


# This will simply call `basic_plugin.load()` in setup and `basic_plugin.unload()`
# in teardown, though wrapped inside asyncio tasks, as these functions are async.
