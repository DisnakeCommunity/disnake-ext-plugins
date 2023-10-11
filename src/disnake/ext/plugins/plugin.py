"""Module defining the main Plugin class."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import typing as t
import warnings

from disnake.ext import commands
from typing_extensions import Self

from . import typeshed, utils

if t.TYPE_CHECKING:
    from disnake.ext import tasks


__all__ = ("Plugin", "SubPlugin", "PluginMetadata", "get_parent_plugin")

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class PluginMetadata:
    """Represents metadata for a :class:`Plugin`.

    Parameters
    ----------
    name: :class:`str`
        Plugin's name.
    category: Optional[:class:`str`]
        The category this plugin belongs to. Does not serve any actual purpose,
        but may be useful in organising plugins.

        .. deprecated:: 0.2.4
            Use :attr:`.extras` instead.
    extras: Dict[:class:`str`, :class:`str`]
        A dict of extra metadata for a plugin.

        .. versionadded:: 0.2.4
    command_attrs: CommandParams
        Parameters to apply to each prefix command in this plugin.
    slash_command_attrs: SlashCommandParams
        Parameters to apply to each slash command in this plugin.
    message_command_attrs: AppCommandParams
        Parameters to apply to each message command in this plugin.
    user_command_attrs: AppCommandParams
        Parameters to apply to each user command in this plugin.
    """

    name: str
    """Plugin's name"""
    extras: t.Dict[str, t.Any]
    """A dict of extra metadata for a plugin."""

    command_attrs: typeshed.CommandParams = dataclasses.field(
        default_factory=typeshed.CommandParams,
    )
    """Parameters to apply to each prefix command in this plugin."""
    slash_command_attrs: typeshed.SlashCommandParams = dataclasses.field(
        default_factory=typeshed.SlashCommandParams,
    )
    """Parameters to apply to each slash command in this plugin."""
    message_command_attrs: typeshed.AppCommandParams = dataclasses.field(
        default_factory=typeshed.AppCommandParams,
    )
    """Parameters to apply to each message command in this plugin."""
    user_command_attrs: typeshed.AppCommandParams = dataclasses.field(
        default_factory=typeshed.AppCommandParams,
    )
    """Parameters to apply to each user command in this plugin."""

    @property
    def category(self) -> t.Optional[str]:
        """The category this plugin belongs to.

        This does not serve any actual purpose but may be useful in organising plugins.

        .. deprecated:: 0.2.4
            Use :attr:`.extras` instead.
        """
        warnings.warn(
            "Accessing `PluginMetadata.category` is deprecated. "
            "Use `PluginMetadata.extras` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.extras.get("category")

    @category.setter
    def category(self, value: t.Optional[str]) -> None:
        warnings.warn(
            "Setting `PluginMetadata.category` is deprecated. Use `PluginMetadata.extras` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.extras["category"] = value


def get_parent_plugin(obj: typeshed.ExtrasAware) -> Plugin[typeshed.AnyBot]:
    """Get the plugin to which the provided object is registered.

    This only works with objects that support an ``extras`` attribute.

    Parameters
    ----------
    obj: ExtrasAware
        Any object that supports an ``extras`` attribute, which should be a dict
        with ``str`` keys.

    Returns
    -------
    Plugin:
        The plugin to which the object is registered.

    Raises
    ------
    LookupError:
        The object is not registered to any plugin.
    """
    if plugin := obj.extras.get("plugin"):
        return plugin

    msg = f"Object {type(obj).__name__!r} does not belong to a Plugin."
    raise LookupError(msg)


@dataclasses.dataclass
class PluginStorage(t.Generic[typeshed.PluginT]):
    commands: t.Dict[str, commands.Command[typeshed.PluginT, t.Any, t.Any]] = dataclasses.field(default_factory=dict)  # type: ignore
    message_commands: t.Dict[str, commands.InvokableMessageCommand] = dataclasses.field(default_factory=dict)
    slash_commands: t.Dict[str, commands.InvokableSlashCommand] = dataclasses.field(default_factory=dict)
    user_commands: t.Dict[str, commands.InvokableUserCommand] = dataclasses.field(default_factory=dict)

    command_checks: t.List[typeshed.PrefixCommandCheck] = dataclasses.field(default_factory=list)
    slash_command_checks: t.List[typeshed.AppCommandCheck] = dataclasses.field(default_factory=list)
    message_command_checks: t.List[typeshed.AppCommandCheck] = dataclasses.field(default_factory=list)
    user_command_checks: t.List[typeshed.AppCommandCheck] = dataclasses.field(default_factory=list)

    loops: t.List[tasks.Loop[t.Any]] = dataclasses.field(default_factory=list)

    listeners: t.Dict[str, t.List[typeshed.CoroFunc]] = dataclasses.field(default_factory=dict)

    def update(self, other: PluginStorage[typeshed.PluginT]) -> None:
        """Update this PluginStorage with another, merging their container dicts and lists."""
        self.commands.update(other.commands)
        self.message_commands.update(other.message_commands)
        self.slash_commands.update(other.slash_commands)
        self.user_commands.update(other.user_commands)

        self.command_checks.extend(other.command_checks)
        self.slash_command_checks.extend(other.slash_command_checks)
        self.message_command_checks.extend(other.message_command_checks)
        self.user_command_checks.extend(other.user_command_checks)

        self.loops.extend(other.loops)

        for event, callbacks in other.listeners.items():
            if event not in self.listeners:
                self.listeners[event] = callbacks
            else:
                self.listeners[event].extend(callbacks)


# The PluginBase holds the logic to register commands etc. to the plugin.
# Since this is relevant for both actual plugins and sub plugins, this is a
# separate base class that can be inherited by both.

class PluginBase(typeshed.PluginProtocol[typeshed.BotT]):
    __slots__ = (
        "metadata",
        "_storage",
    )

    metadata: PluginMetadata
    """The metadata assigned to the plugin."""

    def __init__(
        self,
        *,
        name: t.Optional[str] = None,
        command_attrs: t.Optional[typeshed.CommandParams] = None,
        message_command_attrs: t.Optional[typeshed.AppCommandParams] = None,
        slash_command_attrs: t.Optional[typeshed.SlashCommandParams] = None,
        user_command_attrs: t.Optional[typeshed.AppCommandParams] = None,
        **extras: t.Any,  # noqa: ANN401
    ) -> None:
        self.metadata: PluginMetadata = PluginMetadata(
            name=name or utils.get_source_module_name(),
            command_attrs=command_attrs or {},
            message_command_attrs=message_command_attrs or {},
            slash_command_attrs=slash_command_attrs or {},
            user_command_attrs=user_command_attrs or {},
            extras=extras,
        )

        self._storage: PluginStorage[Self] = PluginStorage[Self]()

    @property
    def bot(self) -> typeshed.BotT:
        raise NotImplementedError

    @classmethod
    def with_metadata(cls, metadata: PluginMetadata) -> Self:
        """Create a Plugin with pre-existing metadata.

        Parameters
        ----------
        metadata: Optional[:class:`PluginMetadata`]
            The metadata to supply to the plugin.

        Returns
        -------
        :class:`Plugin`
            The newly created plugin. In a child class, this would instead
            return an instance of that child class.
        """
        self = cls()
        self.metadata = metadata
        return self

    @property
    def name(self) -> str:
        # << docstring inherited from typeshed.PluginProtocol>>
        return self.metadata.name

    @property
    def category(self) -> t.Optional[str]:
        """The category this plugin belongs to.

        .. deprecated:: 0.2.4
            Use :attr:`.extras` instead.
        """
        warnings.warn(
            "Accessing `Plugin.category` is deprecated. Use `Plugin.extras` instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        return self.extras.get("category")

    @property
    def extras(self) -> t.Dict[str, t.Any]:
        # << docstring inherited from typeshed.PluginProtocol>>
        return self.metadata.extras

    @extras.setter
    def extras(self, value: t.Dict[str, t.Any]) -> None:
        self.metadata.extras = value

    @property
    def commands(self) -> t.Sequence[commands.Command[Self, t.Any, t.Any]]:  # type: ignore
        # << docstring inherited from typeshed.PluginProtocol>>
        return tuple(self._storage.commands.values())

    @property
    def slash_commands(self) -> t.Sequence[commands.InvokableSlashCommand]:
        # << docstring inherited from typeshed.PluginProtocol>>
        return tuple(self._storage.slash_commands.values())

    @property
    def user_commands(self) -> t.Sequence[commands.InvokableUserCommand]:
        # << docstring inherited from typeshed.PluginProtocol>>
        return tuple(self._storage.user_commands.values())

    @property
    def message_commands(self) -> t.Sequence[commands.InvokableMessageCommand]:
        # << docstring inherited from typeshed.PluginProtocol>>
        return tuple(self._storage.message_commands.values())

    @property
    def loops(self) -> t.Sequence[tasks.Loop[t.Any]]:
        # << docstring inherited from typeshed.PluginProtocol>>
        return tuple(self._storage.loops)

    def _apply_attrs(
        self,
        attrs: t.Mapping[str, t.Any],
        **kwargs: t.Any,  # noqa: ANN401
    ) -> t.Dict[str, t.Any]:
        new_attrs = {**attrs, **{k: v for k, v in kwargs.items() if v is not None}}

        # Ensure keys are set, but don't override any in case they are already in use.
        extras = new_attrs.setdefault("extras", {})
        extras.setdefault("plugin", self)
        extras.setdefault("metadata", self.metadata)  # Backward compatibility, may remove later.

        return new_attrs

    # Prefix commands

    def command(
        self,
        name: t.Optional[str] = None,
        *,
        cls: t.Optional[t.Type[commands.Command[t.Any, t.Any, t.Any]]] = None,
        **kwargs: t.Any,  # noqa: ANN401
    ) -> typeshed.CoroDecorator[typeshed.AnyCommand]:
        # << docstring inherited from typeshed.PluginProtocol>>
        attributes = self._apply_attrs(self.metadata.command_attrs, **kwargs)

        if cls is None:
            cls = t.cast(t.Type[typeshed.AnyCommand], attributes.pop("cls", commands.Command))

        def decorator(callback: t.Callable[..., typeshed.Coro[t.Any]]) -> typeshed.AnyCommand:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = cls(callback, name=name or callback.__name__, **attributes)
            self._storage.commands[command.qualified_name] = command

            return command

        return decorator

    def group(
        self,
        name: t.Optional[str] = None,
        *,
        cls: t.Optional[t.Type[commands.Group[t.Any, t.Any, t.Any]]] = None,
        **kwargs: t.Any,  # noqa: ANN401
    ) -> typeshed.CoroDecorator[typeshed.AnyGroup]:
        # << docstring inherited from typeshed.PluginProtocol>>
        attributes = self._apply_attrs(self.metadata.command_attrs, **kwargs)

        if cls is None:
            cls = t.cast(t.Type[typeshed.AnyGroup], attributes.pop("cls", commands.Group))

        def decorator(callback: t.Callable[..., typeshed.Coro[t.Any]]) -> typeshed.AnyGroup:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = cls(callback, name=name or callback.__name__, **attributes)
            self._commands[command.qualified_name] = command  # type: ignore

            return command

        return decorator

    # Application commands

    def slash_command(
        self,
        *,
        auto_sync: t.Optional[bool] = None,
        name: typeshed.LocalizedOptional = None,
        description: typeshed.LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: typeshed.PermissionsOptional = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        connectors: t.Optional[t.Dict[str, str]] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> typeshed.CoroDecorator[commands.InvokableSlashCommand]:
        # << docstring inherited from typeshed.PluginProtocol>>
        attributes = self._apply_attrs(
            self.metadata.slash_command_attrs,
            description=description,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            connectors=connectors,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(
            callback: t.Callable[..., typeshed.Coro[t.Any]],
        ) -> commands.InvokableSlashCommand:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = commands.InvokableSlashCommand(
                callback,
                name=name or callback.__name__,
                **attributes,
            )
            self._storage.slash_commands[command.qualified_name] = command

            return command

        return decorator

    def user_command(
        self,
        *,
        name: typeshed.LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: typeshed.PermissionsOptional = None,
        auto_sync: t.Optional[bool] = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> typeshed.CoroDecorator[commands.InvokableUserCommand]:
        # << docstring inherited from typeshed.PluginProtocol>>
        attributes = self._apply_attrs(
            self.metadata.user_command_attrs,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(
            callback: t.Callable[..., typeshed.Coro[t.Any]],
        ) -> commands.InvokableUserCommand:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = commands.InvokableUserCommand(
                callback,
                name=name or callback.__name__,
                **attributes,
            )
            self._storage.user_commands[command.qualified_name] = command

            return command

        return decorator

    def message_command(
        self,
        *,
        name: typeshed.LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: typeshed.PermissionsOptional = None,
        auto_sync: t.Optional[bool] = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> typeshed.CoroDecorator[commands.InvokableMessageCommand]:
        # << docstring inherited from typeshed.PluginProtocol>>
        attributes = self._apply_attrs(
            self.metadata.user_command_attrs,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(
            callback: t.Callable[..., typeshed.Coro[t.Any]],
        ) -> commands.InvokableMessageCommand:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = commands.InvokableMessageCommand(
                callback,
                name=name or callback.__name__,
                **attributes,
            )
            self._storage.message_commands[command.qualified_name] = command

            return command

        return decorator

    # Checks

    def command_check(
        self,
        predicate: typeshed.PrefixCommandCheckT,
    ) -> typeshed.PrefixCommandCheckT:
        # << docstring inherited from typeshed.PluginProtocol>>
        self._storage.command_checks.append(predicate)
        return predicate

    def slash_command_check(
        self,
        predicate: typeshed.AppCommandCheckT,
    ) -> typeshed.AppCommandCheckT:
        # << docstring inherited from typeshed.PluginProtocol>>
        self._storage.slash_command_checks.append(predicate)
        return predicate

    def message_command_check(
        self,
        predicate: typeshed.AppCommandCheckT,
    ) -> typeshed.AppCommandCheckT:
        # << docstring inherited from typeshed.PluginProtocol>>
        self._storage.message_command_checks.append(predicate)
        return predicate

    def user_command_check(
        self,
        predicate: typeshed.AppCommandCheckT,
    ) -> typeshed.AppCommandCheckT:
        # << docstring inherited from typeshed.PluginProtocol>>
        self._storage.user_command_checks.append(predicate)
        return predicate

    # Listeners

    def add_listeners(
        self,
        *callbacks: typeshed.CoroFunc,
        event: t.Optional[str] = None,
    ) -> None:
        # << docstring inherited from typeshed.PluginProtocol>>
        for callback in callbacks:
            key = callback.__name__ if event is None else event
            self._storage.listeners.setdefault(key, []).append(callback)

    def listener(
        self,
        event: t.Optional[str] = None,
    ) -> t.Callable[[typeshed.CoroFuncT], typeshed.CoroFuncT]:
        # << docstring inherited from typeshed.PluginProtocol>>
        def decorator(callback: typeshed.CoroFuncT) -> typeshed.CoroFuncT:
            self.add_listeners(callback, event=event)
            return callback

        return decorator

    # Tasks

    def register_loop(
        self,
        *,
        wait_until_ready: bool = False,
    ) -> t.Callable[[typeshed.LoopT], typeshed.LoopT]:
        # << docstring inherited from typeshed.PluginProtocol>>
        def decorator(loop: typeshed.LoopT) -> typeshed.LoopT:
            if wait_until_ready:
                if loop._before_loop is not None:  # noqa: SLF001
                    msg = "This loop already has a `before_loop` callback registered."
                    raise TypeError(msg)

                async def _before_loop() -> None:
                    await self.bot.wait_until_ready()

                loop.before_loop(_before_loop)

            self._storage.loops.append(loop)
            return loop

        return decorator

    # Getters

    def get_command(self, name: str) -> t.Optional[commands.Command[Self, t.Any, t.Any]]:  # pyright: ignore
        part, _, name = name.strip().partition(" ")
        command = self._storage.commands.get(name)

        while name:
            if not isinstance(command, commands.GroupMixin):
                msg = (
                    f"Got name {name!r}, indicating a Group with a sub-Command, but"
                    f" command {part!r} is not a Group."
                )
                raise TypeError(msg)

            part, _, name = name.partition(" ")
            command: t.Optional[typeshed.AnyCommand] = command.get_command(name)

        return command

    def get_slash_command(self, name: str) -> t.Union[
        commands.InvokableSlashCommand,
        commands.SubCommandGroup,
        commands.SubCommand,
        None,
    ]:
        chain = name.strip().split()
        length = len(chain)

        slash = self._storage.slash_commands.get(chain[0])
        if not slash or length == 1:
            return slash

        if length == 2:  # noqa: PLR2004
            return slash.children.get(chain[1])

        if length == 3:  # noqa: PLR2004
            group = slash.children.get(chain[1])
            if isinstance(group, commands.SubCommandGroup):
                return group.children.get(chain[2])

        return None


# The actual Plugin implementation adds loading/unloading behaviour to the base.
# For the user's convenience, we also provide easy access to custom loggers.

class Plugin(PluginBase[typeshed.BotT]):
    """An extension manager similar to disnake's :class:`commands.Cog`.

    A plugin can hold commands and listeners, and supports being loaded through
    `bot.load_extension()` as per usual, and can similarly be unloaded and
    reloaded.

    Plugins can be constructed via :meth:`.with_metadata` to provide extra
    information to the plugin.

    Parameters
    ----------
    name: Optional[:class:`str`]
        The name of the plugin. Defaults to the module the plugin is created in.
    category: Optional[:class:`str`]
        The category this plugin belongs to. Does not serve any actual purpose,
        but may be useful in organising plugins.

        .. deprecated:: 0.2.4
            Use ``extras`` instead.
    command_attrs: Dict[:class:`str`, Any]
        A dict of parameters to apply to each prefix command in this plugin.
    message_command_attrs: Dict[:class:`str`, Any]
        A dict of parameters to apply to each message command in this plugin.
    slash_command_attrs: Dict[:class:`str`, Any]
        A dict of parameters to apply to each slash command in this plugin.
    user_command_attrs: Dict[:class:`str`, Any]
        A dict of parameters to apply to each user command in this plugin.
    logger: Optional[Union[:class:`logging.Logger`, :class:`str`]]
        The logger or its name to use when logging plugin events.
        If not specified, defaults to `disnake.ext.plugins.plugin`.
    **extras: Dict[:class:`str`, Any]
        A dict of extra metadata for this plugin.
    """

    __slots__ = (
        "logger",
        "_bot",
        "_pre_load_hooks",
        "_post_load_hooks",
        "_pre_unload_hooks",
        "_post_unload_hooks",
    )

    logger: logging.Logger
    """The logger associated with this plugin."""

    def __init__(
        self,
        *,
        name: t.Optional[str] = None,
        command_attrs: t.Optional[typeshed.CommandParams] = None,
        message_command_attrs: t.Optional[typeshed.AppCommandParams] = None,
        slash_command_attrs: t.Optional[typeshed.SlashCommandParams] = None,
        user_command_attrs: t.Optional[typeshed.AppCommandParams] = None,
        logger: t.Union[logging.Logger, str, None] = None,
        **extras: t.Any,  # noqa: ANN401
    ) -> None:
        super().__init__(
            name=name,
            command_attrs=command_attrs,
            message_command_attrs=message_command_attrs,
            slash_command_attrs=slash_command_attrs,
            user_command_attrs=user_command_attrs,
            **extras,
        )

        if logger is not None:
            if isinstance(logger, str):
                logger = logging.getLogger(logger)

        else:
            logger = LOGGER

        self.logger = logger

        # These are mainly here to easily run async code at (un)load time
        # while we wait for disnake's async refactor. These will probably be
        # left in for lower disnake versions, though they may be removed someday.

        self._pre_load_hooks: t.MutableSequence[typeshed.EmptyAsync] = []
        self._post_load_hooks: t.MutableSequence[typeshed.EmptyAsync] = []
        self._pre_unload_hooks: t.MutableSequence[typeshed.EmptyAsync] = []
        self._post_unload_hooks: t.MutableSequence[typeshed.EmptyAsync] = []

        self._bot: t.Optional[typeshed.BotT] = None

        self._sub_plugins: t.Set[SubPlugin[t.Any]] = set()
    @property
    def bot(self) -> typeshed.BotT:
        """The bot on which this plugin is registered.

        This will only be available after calling :meth:`.load` on the plugin.
        """
        if not self._bot:
            msg = "Cannot access the bot on a plugin that has not yet been loaded."
            raise RuntimeError(msg)
        return self._bot

    # Subplugin registration

    def register_sub_plugin(self, sub_plugin: SubPlugin[t.Any]) -> None:
        """Register a :class:`SubPlugin` to this plugin.

        This registers all commands, slash commands, listeners, loops, etc.
        that are registered on the sub-plugin to this Plugin.

        When this Plugin is unloaded, all sub-plugins are automatically
        unloaded along with it.

        Parameters
        ----------
        sub_plugin:
            The :class:`SubPlugin` that is to be registered.
        """
        self._sub_plugins.add(sub_plugin)
        self._storage.update(sub_plugin._storage)  # noqa: SLF001

        def decorator(callback: CoroFuncT) -> CoroFuncT:
            self.add_listeners(callback, event=event)
            return callback

        sub_plugin.bind(self)

    # Tasks

    def register_loop(self, *, wait_until_ready: bool = False) -> t.Callable[[LoopT], LoopT]:
        """Register a `tasks.Loop` to this plugin.

        Loops registered in this way will automatically start and stop as the
        plugin is loaded and unloaded, respectively.

        Parameters
        ----------
        wait_until_ready: :class:`bool`
            Whether or not to add a simple `before_loop` callback that waits
            until the bot is ready. This can be handy if you load plugins before
            you start the bot (which you should!) and make api requests with a
            loop.
            .. warn::
                This only works if the loop does not already have a `before_loop`
                callback registered.
        """

        def decorator(loop: LoopT) -> LoopT:
            if wait_until_ready:
                if loop._before_loop is not None:  # noqa: SLF001
                    msg = "This loop already has a `before_loop` callback registered."
                    raise TypeError(msg)

                async def _before_loop() -> None:
                    await self.bot.wait_until_ready()

                loop.before_loop(_before_loop)

            self._loops.append(loop)
            return loop

        return decorator

    # Plugin (un)loading...

    # TODO: Maybe make this a standalone function instead of a staticmethod.
    @staticmethod
    def _prepend_plugin_checks(
        checks: t.Sequence[t.Union[typeshed.PrefixCommandCheck, typeshed.AppCommandCheck]],
        command: typeshed.CheckAware,
    ) -> None:
        """Handle updating checks with plugin-wide checks.

        This method is intended for internal use.

        To remain consistent with the behaviour of e.g. commands.Cog.cog_check,
        plugin-wide checks are **prepended** to the commands' local checks.
        """
        if checks:
            command.checks = [*checks, *command.checks]

    async def load(self, bot: typeshed.BotT) -> None:
        """Register commands to the bot and run pre- and post-load hooks.

        Parameters
        ----------
        bot: Union[:class:`commands.Bot`, :class:`commands.InteractionBot`]
            The bot on which to register the plugin's commands.
        """
        self._bot = bot

        await asyncio.gather(*(hook() for hook in self._pre_load_hooks))

        if isinstance(bot, commands.BotBase):
            for command in self.commands:
                bot.add_command(command)  # type: ignore
                self._prepend_plugin_checks(self._storage.command_checks, command)

        for command in self.slash_commands:
            bot.add_slash_command(command)
            self._prepend_plugin_checks(self._storage.slash_command_checks, command)

        for command in self.user_commands:
            bot.add_user_command(command)
            self._prepend_plugin_checks(self._storage.user_command_checks, command)

        for command in self._storage.message_commands.values():
            bot.add_message_command(command)
            self._prepend_plugin_checks(self._storage.message_command_checks, command)

        for event, listeners in self._storage.listeners.items():
            for listener in listeners:
                bot.add_listener(listener, event)

        for loop in self.loops:
            loop.start()

        await asyncio.gather(*(hook() for hook in self._post_load_hooks))

        bot._schedule_delayed_command_sync()  # noqa: SLF001

        self.logger.info("Successfully loaded plugin %r", self.metadata.name)

    async def unload(self, bot: typeshed.BotT) -> None:
        """Remove commands from the bot and run pre- and post-unload hooks.

        Parameters
        ----------
        bot: Union[:class:`commands.Bot`, :class:`commands.InteractionBot`]
            The bot from which to unload the plugin's commands.
        """
        await asyncio.gather(*(hook() for hook in self._pre_unload_hooks))

        if isinstance(bot, commands.BotBase):
            for command in self._storage.commands:
                bot.remove_command(command)

        for command in self._storage.slash_commands:
            bot.remove_slash_command(command)

        for command in self._storage.user_commands:
            bot.remove_user_command(command)

        for command in self._storage.message_commands:
            bot.remove_message_command(command)

        for event, listeners in self._storage.listeners.items():
            for listener in listeners:
                bot.remove_listener(listener, event)

        for loop in self.loops:
            loop.cancel()

        await asyncio.gather(*(hook() for hook in self._post_unload_hooks))

        bot._schedule_delayed_command_sync()  # noqa: SLF001

        self.logger.info("Successfully unloaded plugin %r", self.metadata.name)

    def load_hook(
        self,
        *,
        post: bool = False,
    ) -> t.Callable[[typeshed.EmptyAsync], typeshed.EmptyAsync]:
        """Mark a function as a load hook.

        .. versionchanged:: 0.2.4
            Argument `post` is now keyword-only.

        Parameters
        ----------
        post: :class:`bool`
            Whether the hook is a post-load or pre-load hook.
        """
        hooks = self._post_load_hooks if post else self._pre_load_hooks

        def wrapper(callback: typeshed.EmptyAsync) -> typeshed.EmptyAsync:
            hooks.append(callback)
            return callback

        return wrapper

    def unload_hook(
        self,
        *,
        post: bool = False,
    ) -> t.Callable[[typeshed.EmptyAsync], typeshed.EmptyAsync]:
        """Mark a function as an unload hook.

        .. versionchanged:: 0.2.4
            Argument `post` is now keyword-only.

        Parameters
        ----------
        post: :class:`bool`
            Whether the hook is a post-unload or pre-unload hook.
        """
        hooks = self._post_unload_hooks if post else self._pre_unload_hooks

        def wrapper(callback: typeshed.EmptyAsync) -> typeshed.EmptyAsync:
            hooks.append(callback)
            return callback

        return wrapper

    def create_extension_handlers(
        self,
    ) -> t.Tuple[typeshed.SetupFunc[typeshed.BotT], typeshed.SetupFunc[typeshed.BotT]]:
        """Create basic setup and teardown handlers for an extension.

        Simply put, these functions ensure :meth:`.load` and :meth:`.unload`
        are called when the plugin is loaded or unloaded, respectively.
        """

        def setup(bot: typeshed.BotT) -> None:
            utils.safe_task(self.load(bot))

        def teardown(bot: typeshed.BotT) -> None:
            utils.safe_task(self.unload(bot))

        return setup, teardown


class SubPlugin(PluginBase[typeshed.BotT]):
    """Bean."""

    __slots__: t.Sequence[str] = (
        "_plugin",
        "_command_placeholders",
    )

    _plugin: t.Optional[Plugin[typeshed.BotT]]
    _command_placeholders: t.Dict[
        str,
        t.List[t.Union[placeholder.SubCommandPlaceholder, placeholder.SubCommandGroupPlaceholder]],
    ]

    def __init__(
        self,
        *,
        name: t.Optional[str] = None,
        command_attrs: t.Optional[typeshed.CommandParams] = None,
        message_command_attrs: t.Optional[typeshed.AppCommandParams] = None,
        slash_command_attrs: t.Optional[typeshed.SlashCommandParams] = None,
        user_command_attrs: t.Optional[typeshed.AppCommandParams] = None,
        **extras: t.Any,  # noqa: ANN401
    ) -> None:
        super().__init__(
            name=name,
            command_attrs=command_attrs,
            message_command_attrs=message_command_attrs,
            slash_command_attrs=slash_command_attrs,
            user_command_attrs=user_command_attrs,
            **extras,
        )
        self._plugin = None
        self._command_placeholders = {}

    def bind(self, plugin: Plugin[typeshed.BotT]) -> None:
        """Bind a main Plugin to this SubPlugin.

        This generally doesn't need to be called manually. Instead, use
        :meth:`Plugin.register_sub_plugin`, which will call this automatically.

        Arguments
        ---------
        plugin:
            The Plugin to bind to this SubPlugin.
        """
        if self._plugin:
            msg = f"This subplugin is already bound to a Plugin named {self._plugin.name!r}"
            raise RuntimeError(msg)

        self._plugin = plugin

    @property
    def plugin(self) -> Plugin[typeshed.BotT]:
        """The Plugin of which this is a SubPlugin.

        This is only available after the sub plugin was bound to a :class:`Plugin`.
        """
        if self._plugin:
            return self._plugin

        msg = f"The SubPlugin named {self.name!r} has not yet been bound to a Plugin."
        raise RuntimeError(msg)

    @property
    def bot(self) -> typeshed.BotT:
        """The Plugin of which this is a SubPlugin.

        This is only available after the sub plugin was bound to a :class:`Plugin`,
        and that plugin was loaded via :meth:`Plugin.load`.
        """
        return self.plugin.bot

    # TODO: Maybe allow setting a separate logger here?
    @property
    def logger(self) -> logging.Logger:
        """The logger of the Plugin of which this is a SubPlugin.

        This is only available after the sub plugin was bound to a :class:`Plugin`.
        """
        return self.plugin.logger

