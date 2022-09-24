import contextvars

import aiohttp

import disnake
from disnake.ext import plugins

plugin = plugins.Plugin()


# Sometimes, it is desirable to attach extra behaviour to loading and unloading
# plugins. This can generally be achieved through the `setup` and `teardown`
# hooks. However, before disnake undergoes its inevitable async refactor to
# remain compatible with python 3.11, it can be slightly cumbersome to do so.
# For this purpose, plugins provide load and unload hooks, which are async
# callables that will be called when the plugin is loaded.

# Note: a contextvar is used here to transfer the clientsession through the plugin.


plugin_session: contextvars.ContextVar[aiohttp.ClientSession] = contextvars.ContextVar("session")


@plugin.load_hook()
async def create_session():
    session = aiohttp.ClientSession()
    plugin_session.set(session)


# We make sure to close the clientsession when the plugin is unloaded...


@plugin.unload_hook()
async def close_session():
    session = plugin_session.get()
    await session.close()


# Now we can use this in our commands...


@plugin.slash_command()
async def make_request(inter: disnake.CommandInteraction):
    session = plugin_session.get()
    async with session.get("...") as response:
        data = await response.text()

    await inter.response.send_message(data)  # type: ignore


setup, teardown = plugin.create_extension_handlers()
