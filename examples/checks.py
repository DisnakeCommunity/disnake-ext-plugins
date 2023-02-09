import disnake
from disnake.ext import commands, plugins

Context = commands.Context[commands.Bot]


# Create a basic plugin...

plugin = plugins.Plugin()


# First, we define a local check...


async def local_check(ctx: Context):
    # Check if the message was sent in a channel with "foo" in its name...
    print("B")
    if isinstance(ctx.channel, disnake.DMChannel):
        return False

    return "foo" in ctx.channel.name.lower()  # type: ignore  # disnake.Thread typing bug :)


# Now, we add a check that applies to all prefix commands defined in this
# plugin. This is done using the `@plugin.command_check`-decorator. The same
# can be done for application commands using the `@plugin.slash_command_check`,
# `@plugin.message_command_check`, or `@plugin.user_command_check` for their
# respective command types.


@plugin.command_check
async def global_check_whoa(ctx: Context):
    # Check if the command author is the owner...
    print("A")
    return ctx.author.id == ctx.bot.owner_id


@commands.check(local_check)  # Don't forget to add the local check!
@plugin.command()
async def command_with_checks(ctx: Context):
    print("C")
    await ctx.send("did the check thing!")  # type: ignore


# Plugin-wide checks will run first, local checks afterwards. Besides that,
# checks run in the order they are defined/added to the command.

# In this case, a successful invocation of the command will print
# A
# B
# C

setup, teardown = plugin.create_extension_handlers()
