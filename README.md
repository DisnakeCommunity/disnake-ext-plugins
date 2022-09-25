disnake-ext-plugins
===================

An extension for disnake that serves as a robust replacement for cogs.
No more pointless inheritance, no more singleton classes serving as little more
than a namespace, and no more unexpected behaviour when you get anywhere near
the inner workings of your extensions.

Key Features
------------
- Smoothly integrates with [disnake](https://github.com/DisnakeDev/disnake),
- Manage your extensions without inheritance,
- Minimum boilerplate, maximum control.

Installing
----------
**Python 3.8 or higher is required**

To install the extension, run the following command in your command prompt/shell:

``` sh
# Linux/macOS
python3 -m pip install -U git+https://github.com/DisnakeCommunity/disnake-ext-plugins

# Windows
py -3 -m pip install -U git+https://github.com/DisnakeCommunity/disnake-ext-plugins
```
It will be installed to your existing [disnake](https://github.com/DisnakeDev/disnake) installation as an extension. From there, it can be imported as:

```py
from disnake.ext import plugins
```

Example
-------
```py
import disnake
from disnake.ext import commands, plugin


plugin = plugins.Plugin()


@plugin.slash_command()
async def my_command(inter: disnake.CommandInteraction):
    await inter.response.send_message("Woo!")


setup, teardown = plugin.create_extension_handlers()
```
Further examples can be found in [the examples directory](https://github.com/Chromosomologist/disnake-ext-plugins/tree/master/examples).

To-Do
-----
- PyPI release,
- Provide some clean entrypoint for global variables, perhaps custom `ContextVar`s?
- Perhaps some mechanism to register submodules to a plugin, allowing to batch-reload related files.

Contributing
------------
Any contributions are welcome, feel free to open an issue or submit a pull request if you'd like to see something added. Contribution guidelines will come soon.
