from disnake.ext import commands

# Since plugin loading supports asynchronous hooks, it needs to be done slightly
# differently from normal cog loading (which is sync and cuts some corners).
# Basically, we need to have a running loop by the time we load plugins. The
# easiest way to achieve this is through an async main function. To this end,
# we use asyncio to run the function.

import asyncio


async def main():

    bot = commands.Bot()

    # Plugins are still normal disnake extensions, so the usual
    # `bot.load_extension` and `bot.load_extensions` methods work as per usual!
    bot.load_extensions("exts")

    # This starts the bot in much the same way as `bot.run` does, except in
    # an async context.
    await bot.start("TOKEN")


# Now all that's left is to just run the main function:
asyncio.run(main())


# As you may have noticed, this is pretty much the exact same as a normal main
# file, except the main body where you create your bot and load your plugins
# is now inside an async main function.
