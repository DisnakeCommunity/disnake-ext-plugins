import typing

from disnake.ext import commands, plugins

# As shown in extras.py, extras are useful to to store per-plugin
# data. However, by default `.extras` is an untyped dict, which makes
# interacting with it less convenient and degrades editor hints quality.
# Same applies when you're using a custom `Bot` class that has additional
# properties over the base one: each access to such property will require
# you to unnecessarily "prove" to type checker that this property exists.
# To mitigate these issues, `Plugin` is generic over both `.bot`'s and
# `.extras`' types, which can be specialized to allow type-safe access.

# To enable type safety for `.extras`, we create a type for the data we
# will store there. See `TypedDict`'s documentation for more.

class MyExtras(typing.TypedDict, total=False):
    foo: typing.Literal["bar"]
    bar: typing.Literal["foo"]

# Then, when creating `Plugin` instance, specify types using the
# square bracket notation.
# Bot type is specified first. You can use the default `plugins.AnyBot`
# (in cases when you don't need any custom property access), or a
# concrete `Bot`-like type, including your own `Bot` subclasses.
# Extras type is specified after it. Be careful that the initial `extras=`
# are not validated due to type system limitations.

typed_plugin = plugins.Plugin[plugins.AnyBot, MyExtras](extras={"foo": "bar"})

# If your IDE of choice supports type checking (or if you have an
# extension/plugin for it that does), it should highlight that the
# type of `typed_plugin.extras` is `MyExtras`. You can also try changing
# the bot type.
if typing.TYPE_CHECKING:
    import typing_extensions

    typing_extensions.reveal_type(typed_plugin.extras)
    typing_extensions.reveal_type(typed_plugin.bot)

# Any access or modifications of `.extras` or usage of custom `Bot`
# properties will now be validated by your type-checker.


@typed_plugin.command()
async def what_is_what(ctx: commands.Context[commands.Bot]):
    await ctx.reply(str(typed_plugin.extras))


@typed_plugin.command("on_message")
async def swap_foobar(ctx: commands.Context[commands.Bot]):
    if typed_plugin.extras.get("foo"):
        # Try adding another key/value pair here
        typed_plugin.extras = {"bar": "foo"}
    else:
        typed_plugin.extras = {"foo": "bar"}

    await ctx.reply("Done!")


setup, teardown = typed_plugin.create_extension_handlers()
