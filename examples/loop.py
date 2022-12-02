from disnake.ext import plugins, tasks

# Sometimes, we want to use loops in our plugins. This is easily done.
# We can simply create a loop as per usual, then use
# `plugins.Plugin.register_loop` to register it to the plugin.
# this signals the plugin to automatically start and stop the loop when
# the plugin is loaded or unloaded.

plugin = plugins.Plugin()


@plugin.register_loop()
@tasks.loop(seconds=3)
async def simple_loop():
    print("Looping!")


# Sometimes, we need our loops to make api requests. In these situations,
# it is vital to ensure the bot has started before we can actually make
# any requests. Naturally, just starting a loop on plugin load is therefore
# not always desirable. To that end, the `register_loop` decorator provides
# the `wait_until_ready` keyword-argument, which adds a `before_loop`
# callback that waits for the bot to be ready.

# Keep in mind that this option is therefore incompatible with any
# `before_loop` callbacks you may want to add yourself!


@plugin.register_loop(wait_until_ready=True)
@tasks.loop(seconds=3)
async def loop_that_makes_api_requests():
    print(await plugin.bot.fetch_channel(958140996619730955))


# This is equivalent to


@plugin.register_loop()
@tasks.loop(seconds=3)
async def loop_that_makes_api_requests_alternative():
    print(await plugin.bot.fetch_channel(958140996619730955))


@loop_that_makes_api_requests_alternative.before_loop
async def wait_until_ready():
    await plugin.bot.wait_until_ready()


setup, teardown = plugin.create_extension_handlers()
