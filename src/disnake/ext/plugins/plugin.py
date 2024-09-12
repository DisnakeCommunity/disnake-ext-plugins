"""Module defining the main Plugin class."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import typing as t
import warnings

import disnake
from disnake.ext import commands

from . import async_utils

if t.TYPE_CHECKING:
    from typing_extensions import ParamSpec, Self

    from disnake.ext import tasks

    P = ParamSpec("P")


__all__ = ("Plugin", "PluginMetadata", "get_parent_plugin", "PluginKey")

LOGGER = logging.getLogger(__name__)
_INVALID: t.Final[t.Sequence[str]] = (t.__file__, __file__)

T = t.TypeVar("T")
U = t.TypeVar("U")


AnyBot = t.Union[
    commands.Bot,
    commands.AutoShardedBot,
    commands.InteractionBot,
    commands.AutoShardedInteractionBot,
]

BotT = t.TypeVar("BotT", bound=AnyBot)

Coro = t.Coroutine[t.Any, t.Any, T]
MaybeCoro = t.Union[Coro[T], T]
EmptyAsync = t.Callable[[], Coro[None]]
SetupFunc = t.Callable[[BotT], None]

AnyCommand = commands.Command[t.Any, t.Any, t.Any]
AnyGroup = commands.Group[t.Any, t.Any, t.Any]

CoroFunc = t.Callable[..., Coro[t.Any]]
CoroFuncT = t.TypeVar("CoroFuncT", bound=CoroFunc)
CoroDecorator = t.Callable[[CoroFunc], T]

LocalizedOptional = t.Union[t.Optional[str], disnake.Localized[t.Optional[str]]]
PermissionsOptional = t.Optional[t.Union[disnake.Permissions, int]]

LoopT = t.TypeVar("LoopT", bound="tasks.Loop[t.Any]")

PrefixCommandCheck = t.Callable[[commands.Context[t.Any]], MaybeCoro[bool]]
AppCommandCheck = t.Callable[[disnake.CommandInteraction], MaybeCoro[bool]]

PrefixCommandCheckT = t.TypeVar("PrefixCommandCheckT", bound=PrefixCommandCheck)
AppCommandCheckT = t.TypeVar("AppCommandCheckT", bound=AppCommandCheck)


class PluginKey(str, t.Generic[T]):
    """A :class:`str` subclass for type-safe access to :attr:`Plugin.extras`."""

    __slots__ = ()

    def __repr__(self) -> str:
        return f"<PluginKey name={str(self)!r}>"


class CheckAware(t.Protocol):
    checks: t.List[t.Callable[..., MaybeCoro[bool]]]


class CommandParams(t.TypedDict, total=False):
    help: str
    brief: str
    usage: str
    enabled: bool
    description: str
    hidden: bool
    ignore_extra: bool
    cooldown_after_parsing: bool
    extras: t.Dict[str, t.Any]


class AppCommandParams(t.TypedDict, total=False):
    auto_sync: bool
    dm_permission: bool
    default_member_permissions: PermissionsOptional
    guild_ids: t.Sequence[int]
    extras: t.Dict[str, t.Any]


class SlashCommandParams(AppCommandParams, total=False):
    description: LocalizedOptional
    connectors: t.Dict[str, str]


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

    command_attrs: CommandParams = dataclasses.field(default_factory=CommandParams)
    """Parameters to apply to each prefix command in this plugin."""
    slash_command_attrs: SlashCommandParams = dataclasses.field(default_factory=SlashCommandParams)
    """Parameters to apply to each slash command in this plugin."""
    message_command_attrs: AppCommandParams = dataclasses.field(default_factory=AppCommandParams)
    """Parameters to apply to each message command in this plugin."""
    user_command_attrs: AppCommandParams = dataclasses.field(default_factory=AppCommandParams)
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


class ExtrasAware(t.Protocol):
    extras: t.Dict[str, t.Any]


def get_parent_plugin(obj: ExtrasAware) -> Plugin[AnyBot]:
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


def _get_source_module_name() -> str:
    """Get current frame from exception traceback."""
    # We ignore ruff here because we need to raise and immediately catch an
    # exception to figure out our stack level.
    try:
        raise Exception  # noqa: TRY002, TRY301
    except Exception as exc:  # noqa: BLE001
        tb = exc.__traceback__

    if not tb:
        # No traceback, therefore can't access frames and infer plugin name...
        LOGGER.warning("Failed to infer file name, defaulting to 'plugin'.")
        return "plugin"

    # Navigate all frames for one with a valid path.
    # Note that we explicitly filter out:
    # - the stdlib typing module; if the generic parameter is specified, this
    #   will be encountered before the target module.
    # - this file; we don't want to just return "plugin" if possible.
    frame = tb.tb_frame
    while frame := frame.f_back:
        if frame.f_code.co_filename not in _INVALID:
            break

    else:
        LOGGER.warning("Failed to infer file name, defaulting to 'plugin'.")
        return "plugin"

    module_name = frame.f_locals["__name__"]
    LOGGER.debug("Module name resolved to %r", module_name)
    return module_name


class Plugin(t.Generic[BotT]):
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
        "metadata",
        "logger",
        "_bot",
        "_commands",
        "_slash_commands",
        "_message_commands",
        "_user_commands",
        "_command_checks",
        "_slash_command_checks",
        "_message_command_checks",
        "_user_command_checks",
        "_listeners",
        "_loops",
        "_pre_load_hooks",
        "_post_load_hooks",
        "_pre_unload_hooks",
        "_post_unload_hooks",
    )

    metadata: PluginMetadata
    """The metadata assigned to the plugin."""

    logger: logging.Logger
    """The logger associated with this plugin."""

    @t.overload
    def __init__(
        self: Plugin[commands.Bot],
        *,
        name: t.Optional[str] = None,
        command_attrs: t.Optional[CommandParams] = None,
        message_command_attrs: t.Optional[AppCommandParams] = None,
        slash_command_attrs: t.Optional[SlashCommandParams] = None,
        user_command_attrs: t.Optional[AppCommandParams] = None,
        logger: t.Union[logging.Logger, str, None] = None,
        **extras: t.Any,  # noqa: ANN401
    ) -> None:
        ...

    @t.overload
    def __init__(
        self,
        *,
        name: t.Optional[str] = None,
        command_attrs: t.Optional[CommandParams] = None,
        message_command_attrs: t.Optional[AppCommandParams] = None,
        slash_command_attrs: t.Optional[SlashCommandParams] = None,
        user_command_attrs: t.Optional[AppCommandParams] = None,
        logger: t.Union[logging.Logger, str, None] = None,
        **extras: t.Any,  # noqa: ANN401
    ) -> None:
        ...

    def __init__(
        self,
        *,
        name: t.Optional[str] = None,
        command_attrs: t.Optional[CommandParams] = None,
        message_command_attrs: t.Optional[AppCommandParams] = None,
        slash_command_attrs: t.Optional[SlashCommandParams] = None,
        user_command_attrs: t.Optional[AppCommandParams] = None,
        logger: t.Union[logging.Logger, str, None] = None,
        **extras: t.Any,
    ) -> None:
        self.metadata: PluginMetadata = PluginMetadata(
            name=name or _get_source_module_name(),
            command_attrs=command_attrs or {},
            message_command_attrs=message_command_attrs or {},
            slash_command_attrs=slash_command_attrs or {},
            user_command_attrs=user_command_attrs or {},
            extras=extras,
        )

        if logger is not None:
            if isinstance(logger, str):
                logger = logging.getLogger(logger)

        else:
            logger = LOGGER

        self.logger = logger

        self._commands: t.Dict[str, commands.Command[Self, t.Any, t.Any]] = {}  # type: ignore
        self._message_commands: t.Dict[str, commands.InvokableMessageCommand] = {}
        self._slash_commands: t.Dict[str, commands.InvokableSlashCommand] = {}
        self._user_commands: t.Dict[str, commands.InvokableUserCommand] = {}

        self._command_checks: t.MutableSequence[PrefixCommandCheck] = []
        self._slash_command_checks: t.MutableSequence[AppCommandCheck] = []
        self._message_command_checks: t.MutableSequence[AppCommandCheck] = []
        self._user_command_checks: t.MutableSequence[AppCommandCheck] = []

        self._listeners: t.Dict[str, t.MutableSequence[CoroFunc]] = {}
        self._loops: t.List[tasks.Loop[t.Any]] = []

        # These are mainly here to easily run async code at (un)load time
        # while we wait for disnake's async refactor. These will probably be
        # left in for lower disnake versions, though they may be removed someday.

        self._pre_load_hooks: t.MutableSequence[EmptyAsync] = []
        self._post_load_hooks: t.MutableSequence[EmptyAsync] = []
        self._pre_unload_hooks: t.MutableSequence[EmptyAsync] = []
        self._post_unload_hooks: t.MutableSequence[EmptyAsync] = []

        self._bot: t.Optional[BotT] = None

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
    def bot(self) -> BotT:
        """The bot on which this plugin is registered.

        This will only be available after calling :meth:`.load`.
        """
        if not self._bot:
            msg = "Cannot access the bot on a plugin that has not yet been loaded."
            raise RuntimeError(msg)
        return self._bot

    @property
    def name(self) -> str:
        """The name of this plugin."""
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
        """A dict of extra metadata for this plugin.

        .. versionadded:: 0.2.4
        """
        return self.metadata.extras

    @extras.setter
    def extras(self, value: t.Dict[str, t.Any]) -> None:
        self.metadata.extras = value

    # mutmap api

    def __getitem__(self, key: PluginKey[T]) -> T:
        return self.extras[key]

    def __setitem__(self, key: PluginKey[T], value: T) -> None:
        self.extras[key] = value

    def __delitem__(self, key: PluginKey[t.Any]) -> None:
        del self.extras[key]

    def get(self, key: PluginKey[T], default: U = None) -> t.Union[T, U]:
        """Type-safe method of calling ``plugin.extras.get`` directly."""
        return self.extras.get(key, default)

    # end mutmap api

    @property
    def commands(self) -> t.Sequence[commands.Command[Self, t.Any, t.Any]]:  # type: ignore
        """All prefix commands registered in this plugin."""
        return tuple(self._commands.values())

    @property
    def slash_commands(self) -> t.Sequence[commands.InvokableSlashCommand]:
        """All slash commands registered in this plugin."""
        return tuple(self._slash_commands.values())

    @property
    def user_commands(self) -> t.Sequence[commands.InvokableUserCommand]:
        """All user commands registered in this plugin."""
        return tuple(self._user_commands.values())

    @property
    def message_commands(self) -> t.Sequence[commands.InvokableMessageCommand]:
        """All message commands registered in this plugin."""
        return tuple(self._message_commands.values())

    @property
    def loops(self) -> t.Sequence[tasks.Loop[t.Any]]:
        """All loops registered to this plugin."""
        return tuple(self._loops)

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
    ) -> CoroDecorator[AnyCommand]:
        """Transform a function into a :class:`commands.Command`.

        By default the ``help`` attribute is received automatically from the
        docstring of the function and is cleaned up with the use of
        ``inspect.cleandoc``. If the docstring is ``bytes``, then it is decoded
        into :class:`str` using utf-8 encoding.

        All checks added using the :func:`commands.check` & co. decorators are
        added into the function. There is no way to supply your own checks
        through this decorator.

        Parameters
        ----------
        name: :class:`str`
            The name to create the command with. By default this uses the
            function name unchanged.
        cls:
            The class to construct with. By default this is
            :class:`commands.Command`. You usually do not change this.
        **kwargs:
            Keyword arguments to pass into the construction of the class denoted
            by ``cls``.

        Returns
        -------
        Callable[..., :class:`commands.Command`]
            A decorator that converts the provided method into a
            :class:`commands.Command` or a derivative, and returns it.

        Raises
        ------
        TypeError
            The function is not a coroutine or is already a command.

        """
        attributes = self._apply_attrs(self.metadata.command_attrs, **kwargs)

        if cls is None:
            cls = t.cast(t.Type[AnyCommand], attributes.pop("cls", AnyCommand))

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> AnyCommand:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = cls(callback, name=name or callback.__name__, **attributes)
            self._commands[command.qualified_name] = command

            return command

        return decorator

    def group(
        self,
        name: t.Optional[str] = None,
        *,
        cls: t.Optional[t.Type[commands.Group[t.Any, t.Any, t.Any]]] = None,
        **kwargs: t.Any,  # noqa: ANN401
    ) -> CoroDecorator[AnyGroup]:
        """Transform a function into a :class:`commands.Group`.

        This is similar to the :func:`commands.command` decorator but the
        ``cls`` parameter is set to :class:`Group` by default.

        Parameters
        ----------
        name: :class:`str`
            The name to create the group with. By default this uses the
            function name unchanged.
        cls:
            The class to construct with. By default this is
            :class:`commands.Group`. You usually do not change this.
        **kwargs:
            Keyword arguments to pass into the construction of the class denoted
            by ``cls``.

        Returns
        -------
        Callable[..., :class:`commands.Group`]
            A decorator that converts the provided method into a
            :class:`commands.Group` or a derivative, and returns it.

        Raises
        ------
        TypeError
            The function is not a coroutine or is already a command.

        """
        attributes = self._apply_attrs(self.metadata.command_attrs, **kwargs)

        if cls is None:
            cls = t.cast(t.Type[AnyGroup], attributes.pop("cls", AnyGroup))

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> AnyGroup:
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
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: PermissionsOptional = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        connectors: t.Optional[t.Dict[str, str]] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> CoroDecorator[commands.InvokableSlashCommand]:
        """Transform a function into a slash command.

        Parameters
        ----------
        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``.
        name: Optional[Union[:class:`str`, :class:`disnake.Localized`]]
            The name of the slash command (defaults to function name).
        description: Optional[Union[:class:`str`, :class:`disnake.Localized`]]
            The description of the slash command. It will be visible in Discord.
        dm_permission: :class:`bool`
            Whether this command can be used in DMs.
            Defaults to ``True``.
        default_member_permissions: Optional[Union[:class:`disnake.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`disnake.ApplicationCommand.default_member_permissions` for details.
        guild_ids: List[:class:`int`]
            If specified, the client will register the command in these guilds.
            Otherwise, this command will be registered globally.
        connectors: Dict[:class:`str`, :class:`str`]
            Binds function names to option names. If the name
            of an option already matches the corresponding function param,
            you don't have to specify the connectors. Connectors template:
            ``{"option-name": "param_name", ...}``.
            If you're using :ref:`param_syntax`, you don't need to specify this.
        extras: Dict[:class:`str`, Any]
            A dict of user provided extras to attach to the command.

            .. note::
                This object may be copied by the library.

        Returns
        -------
        Callable[..., :class:`commands.InvokableSlashCommand`]
            A decorator that converts the provided method into a
            :class:`commands.InvokableSlashCommand` and returns it.

        """
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

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> commands.InvokableSlashCommand:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = commands.InvokableSlashCommand(
                callback,
                name=name or callback.__name__,
                **attributes,
            )
            self._slash_commands[command.qualified_name] = command

            return command

        return decorator

    def user_command(
        self,
        *,
        name: LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: PermissionsOptional = None,
        auto_sync: t.Optional[bool] = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> CoroDecorator[commands.InvokableUserCommand]:
        """Transform a function into a user command.

        Parameters
        ----------
        name: Optional[Union[:class:`str`, :class:`disnake.Localized`]]
            The name of the user command (defaults to the function name).
        dm_permission: :class:`bool`
            Whether this command can be used in DMs.
            Defaults to ``True``.
        default_member_permissions: Optional[Union[:class:`disnake.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`disnake.ApplicationCommand.default_member_permissions` for details.
        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``.
        guild_ids: Sequence[:class:`int`]
            If specified, the client will register the command in these guilds.
            Otherwise, this command will be registered globally.
        extras: Dict[:class:`str`, Any]
            A dict of user provided extras to attach to the command.

            .. note::
                This object may be copied by the library.

        Returns
        -------
        Callable[..., :class:`commands.InvokableUserCommand`]
            A decorator that converts the provided method into a
            :class:`commands.InvokableUserCommand` and returns it.

        """
        attributes = self._apply_attrs(
            self.metadata.user_command_attrs,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> commands.InvokableUserCommand:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = commands.InvokableUserCommand(
                callback,
                name=name or callback.__name__,
                **attributes,
            )
            self._user_commands[command.qualified_name] = command

            return command

        return decorator

    def message_command(
        self,
        *,
        name: LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: PermissionsOptional = None,
        auto_sync: t.Optional[bool] = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> CoroDecorator[commands.InvokableMessageCommand]:
        """Transform a function into a message command.

        Parameters
        ----------
        name: Optional[Union[:class:`str`, :class:`disnake.Localized`]]
            The name of the message command (defaults to the function name).
        dm_permission: :class:`bool`
            Whether this command can be used in DMs.
            Defaults to ``True``.
        default_member_permissions: Optional[Union[:class:`disnake.Permissions`, :class:`int`]]
            The default required permissions for this command.
            See :attr:`disnake.ApplicationCommand.default_member_permissions` for details.
        auto_sync: :class:`bool`
            Whether to automatically register the command. Defaults to ``True``.
        guild_ids: Sequence[:class:`int`]
            If specified, the client will register the command in these guilds.
            Otherwise, this command will be registered globally.
        extras: Dict[:class:`str`, Any]
            A dict of user provided extras to attach to the command.

            .. note::
                This object may be copied by the library.

        Returns
        -------
        Callable[..., :class:`commands.InvokableMessageCommand`]
            A decorator that converts the provided method into an
            :class:`commands.InvokableMessageCommand` and then returns it.

        """
        attributes = self._apply_attrs(
            self.metadata.message_command_attrs,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> commands.InvokableMessageCommand:
            if not asyncio.iscoroutinefunction(callback):
                msg = f"<{callback.__qualname__}> must be a coroutine function."
                raise TypeError(msg)

            command = commands.InvokableMessageCommand(
                callback,
                name=name or callback.__name__,
                **attributes,
            )
            self._message_commands[command.qualified_name] = command

            return command

        return decorator

    # Checks

    def command_check(self, predicate: PrefixCommandCheckT) -> PrefixCommandCheckT:
        """Add a `commands.check` to all prefix commands on this plugin."""
        self._command_checks.append(predicate)
        return predicate

    def slash_command_check(self, predicate: AppCommandCheckT) -> AppCommandCheckT:
        """Add a `commands.check` to all slash commands on this plugin."""
        self._slash_command_checks.append(predicate)
        return predicate

    def message_command_check(self, predicate: AppCommandCheckT) -> AppCommandCheckT:
        """Add a `commands.check` to all message commands on this plugin."""
        self._message_command_checks.append(predicate)
        return predicate

    def user_command_check(self, predicate: AppCommandCheckT) -> AppCommandCheckT:
        """Add a `commands.check` to all user commands on this plugin."""
        self._user_command_checks.append(predicate)
        return predicate

    # Listeners

    def add_listeners(
        self,
        *callbacks: CoroFunc,
        event: t.Optional[t.Union[str, disnake.Event]] = None,
    ) -> None:
        """Add multiple listeners to the plugin.

        Parameters
        ----------
        *callbacks: Callable[..., Any]
            The callbacks to add as listeners for this plugin.
        event: :class:`str`
            The name of a single event to register all callbacks under. If not provided,
            the callbacks will be registered individually based on function's name.

        """
        for callback in callbacks:
            if event is None:
                key = callback.__name__
            elif isinstance(event, disnake.Event):
                key = f"on_{event.value}"
            else:
                key = event
            self._listeners.setdefault(key, []).append(callback)

    def listener(
        self,
        event: t.Optional[t.Union[str, disnake.Event]] = None,
    ) -> t.Callable[[CoroFuncT], CoroFuncT]:
        """Register a function as a listener on this plugin.

        This is the plugin equivalent of :meth:`commands.Bot.listen`.

        Parameters
        ----------
        event: :class:`str`
            The name of the event being listened to. If not provided, it
            defaults to the function's name.

        """

        def decorator(callback: CoroFuncT) -> CoroFuncT:
            self.add_listeners(callback, event=event)
            return callback

        return decorator

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
        checks: t.Sequence[t.Union[PrefixCommandCheck, AppCommandCheck]],
        command: CheckAware,
    ) -> None:
        """Handle updating checks with plugin-wide checks.

        This method is intended for internal use.

        To remain consistent with the behaviour of e.g. commands.Cog.cog_check,
        plugin-wide checks are **prepended** to the commands' local checks.
        """
        if checks:
            command.checks = [*checks, *command.checks]

    async def load(self, bot: BotT) -> None:
        """Register commands to the bot and run pre- and post-load hooks.

        Parameters
        ----------
        bot: Union[:class:`commands.Bot`, :class:`commands.InteractionBot`]
            The bot on which to register the plugin's commands.

        """
        self._bot = bot

        await asyncio.gather(*(hook() for hook in self._pre_load_hooks))

        if isinstance(bot, commands.BotBase):
            for command in self._commands.values():
                bot.add_command(command)  # type: ignore
                self._prepend_plugin_checks(self._command_checks, command)

        for command in self._slash_commands.values():
            bot.add_slash_command(command)
            self._prepend_plugin_checks(self._slash_command_checks, command)

        for command in self._user_commands.values():
            bot.add_user_command(command)
            self._prepend_plugin_checks(self._user_command_checks, command)

        for command in self._message_commands.values():
            bot.add_message_command(command)
            self._prepend_plugin_checks(self._message_command_checks, command)

        for event, listeners in self._listeners.items():
            for listener in listeners:
                bot.add_listener(listener, event)

        for loop in self._loops:
            loop.start()

        await asyncio.gather(*(hook() for hook in self._post_load_hooks))

        bot._schedule_delayed_command_sync()  # noqa: SLF001

        self.logger.info("Successfully loaded plugin %r", self.metadata.name)

    async def unload(self, bot: BotT) -> None:
        """Remove commands from the bot and run pre- and post-unload hooks.

        Parameters
        ----------
        bot: Union[:class:`commands.Bot`, :class:`commands.InteractionBot`]
            The bot from which to unload the plugin's commands.

        """
        await asyncio.gather(*(hook() for hook in self._pre_unload_hooks))

        if isinstance(bot, commands.BotBase):
            for command in self._commands:
                bot.remove_command(command)

        for command in self._slash_commands:
            bot.remove_slash_command(command)

        for command in self._user_commands:
            bot.remove_user_command(command)

        for command in self._message_commands:
            bot.remove_message_command(command)

        for event, listeners in self._listeners.items():
            for listener in listeners:
                bot.remove_listener(listener, event)

        for loop in self._loops:
            loop.cancel()

        await asyncio.gather(*(hook() for hook in self._post_unload_hooks))

        bot._schedule_delayed_command_sync()  # noqa: SLF001

        self.logger.info("Successfully unloaded plugin %r", self.metadata.name)

    def load_hook(self, *, post: bool = False) -> t.Callable[[EmptyAsync], EmptyAsync]:
        """Mark a function as a load hook.

        .. versionchanged:: 0.2.4
            Argument `post` is now keyword-only.

        Parameters
        ----------
        post: :class:`bool`
            Whether the hook is a post-load or pre-load hook.

        """
        hooks = self._post_load_hooks if post else self._pre_load_hooks

        def wrapper(callback: EmptyAsync) -> EmptyAsync:
            hooks.append(callback)
            return callback

        return wrapper

    def unload_hook(self, *, post: bool = False) -> t.Callable[[EmptyAsync], EmptyAsync]:
        """Mark a function as an unload hook.

        .. versionchanged:: 0.2.4
            Argument `post` is now keyword-only.

        Parameters
        ----------
        post: :class:`bool`
            Whether the hook is a post-unload or pre-unload hook.

        """
        hooks = self._post_unload_hooks if post else self._pre_unload_hooks

        def wrapper(callback: EmptyAsync) -> EmptyAsync:
            hooks.append(callback)
            return callback

        return wrapper

    def create_extension_handlers(self) -> t.Tuple[SetupFunc[BotT], SetupFunc[BotT]]:
        """Create basic setup and teardown handlers for an extension.

        Simply put, these functions ensure :meth:`.load` and :meth:`.unload`
        are called when the plugin is loaded or unloaded, respectively.
        """

        def setup(bot: BotT) -> None:
            async_utils.safe_task(self.load(bot))

        def teardown(bot: BotT) -> None:
            async_utils.safe_task(self.unload(bot))

        return setup, teardown
