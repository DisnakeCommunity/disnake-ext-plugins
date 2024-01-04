import typing as t

from disnake.ext import commands, plugins

# `PluginKey`s provide a type-safe approach for interacting with
# `Plugin.extras`, similar to aiohttp's `AppKey`s. This file is a
# refactor of `extras.py` that uses `PluginKey`s instead of plain
# strings, so it is advised to read `extras.py` first if you're not
# familiar with extras yet.

# Since we have two keys, "foo" and "bar", we define two `PluginKey`s
# for them, with appropriate type arguments.

foo_key = plugins.PluginKey[t.Literal["bar"]]("foo_key")
bar_key = plugins.PluginKey[t.Literal["foo"]]("bar_key")

# Be careful, as due to type system limitations the initial
# `extras=...` cannot be type-validated.

extras_plugin = plugins.Plugin(extras={"foo": "bar"})


@extras_plugin.command()
async def what_is_what(ctx: commands.Context[commands.Bot]):
    await ctx.reply(str(extras_plugin.extras))


# To get type-checking benefits, use square bracket notation on
# `Plugin, as if it was a `dict`. Note, however, that only
# `plugin[key]`, `plugin[key] = ...`, `del plugin[key]` and
# `plugin.get()` are implemented, and `Plugin` is not a "real" `dict`.


@extras_plugin.listener("on_message")
async def swap_foobar(ctx: commands.Context[commands.Bot]):
    if extras_plugin.get(foo_key):
        del extras_plugin[foo_key]
        extras_plugin[bar_key] = "foo"
    else:
        del extras_plugin[bar_key]
        extras_plugin[foo_key] = "bar"

    await ctx.reply("Done!")


setup, teardown = extras_plugin.create_extension_handlers()
