"""
disnake-ext-plugins
~~~~~~~~~~~~~~~~~~~~~~
An extension for disnake providing a robust alternative to cogs,
not reliant on inheritance.
:copyright: (c) 2022-present Chromosomologist.
:license: MIT, see LICENSE for more details.
"""

__version__ = "0.1.0"


from .context import GlobalContext, LocalContext
from .plugin import Plugin

__all__ = ("Plugin", "GlobalContext", "LocalContext")
