from disnake.ext import commands, plugins

# Sometimes you would want to attach some extra info to your plugin and grab
# it back later in another command. For this, the so-called extras exist.
# They don"t serve any actual purpose and are purely for use by the user.

extras_plugin = plugins.Plugin(extras={"foo": "bar"})


# Afterwards we can easily access this data.


@extras_plugin.command()
async def what_is_what(ctx: commands.Context[commands.Bot]):
    await ctx.reply(str(extras_plugin.extras))


# Likewise you can change this data at runtime.


@extras_plugin.command()
async def swap_foobar(ctx: commands.Context[commands.Bot]):
    if extras_plugin.extras.get("foo"):
        extras_plugin.extras = {"bar": "foo"}
    else:
        extras_plugin.extras = {"foo": "bar"}

    await ctx.reply("Done!")


setup, teardown = extras_plugin.create_extension_handlers()
