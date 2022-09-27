from __future__ import annotations

import asyncio
import dataclasses
import logging
import pathlib
import sys
import typing as t

from typing_extensions import Self

import disnake
from disnake.ext import commands

__all__ = ("Plugin",)

LOGGER = logging.getLogger(__name__)

T = t.TypeVar("T")

if sys.version_info <= (3, 9):
    import typing_extensions

    P = typing_extensions.ParamSpec("P")
else:
    P = t.ParamSpec("P")

BotT = t.TypeVar(
    "BotT",
    bound=t.Union[
        commands.Bot,
        commands.AutoShardedBot,
        commands.InteractionBot,
        commands.AutoShardedInteractionBot,
    ],
)

Coro = t.Coroutine[t.Any, t.Any, T]
EmptyAsync = t.Callable[[], Coro[None]]
SetupFunc = t.Callable[[BotT], None]

AnyCommand = commands.Command[t.Any, t.Any, t.Any]
AnyGroup = commands.Group[t.Any, t.Any, t.Any]

CoroFunc = t.Callable[..., Coro[t.Any]]
CoroFuncT = t.TypeVar("CoroFuncT", bound=CoroFunc)
CoroDecorator = t.Callable[[CoroFunc], T]

LocalizedOptional = t.Union[t.Optional[str], disnake.Localized[t.Optional[str]]]
PermissionsOptional = t.Optional[t.Union[disnake.Permissions, int]]


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
    name: str
    category: t.Optional[str] = None

    command_attrs: CommandParams = dataclasses.field(default_factory=CommandParams)
    slash_command_attrs: SlashCommandParams = dataclasses.field(default_factory=SlashCommandParams)
    message_command_attrs: AppCommandParams = dataclasses.field(default_factory=AppCommandParams)
    user_command_attrs: AppCommandParams = dataclasses.field(default_factory=AppCommandParams)


def _get_source_module_name() -> str:
    return pathlib.Path(logging.currentframe().f_code.co_filename).stem


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
    command_attrs: Dict[:class:`str`, Any]
        A dict of parameters to apply to each prefix command in this plugin.
    message_command_attrs: Dict[:class:`str`, Any]
        A dict of parameters to apply to each message command in this plugin.
    slash_command_attrs: Dict[:class:`str`, Any]
        A dict of parameters to apply to each slash command in this plugin.
    user_command_attrs: Dict[:class:`str`, Any]
        A dict of parameters to apply to each user command in this plugin.
    """

    __slots__ = (
        "bot",
        "metadata",
        "_commands",
        "_slash_commands",
        "_message_commands",
        "_listeners",
        "_user_commands",
        "_pre_load_hooks",
        "_post_load_hooks",
        "_pre_unload_hooks",
        "_post_unload_hooks",
    )

    bot: BotT
    """The bot on which this plugin is registered. This will only be available
    after calling :meth:`.load`.
    """

    metadata: PluginMetadata
    """The metadata assigned to the plugin."""

    @t.overload
    def __init__(
        self: Plugin[commands.Bot],
        *,
        name: t.Optional[str] = None,
        category: t.Optional[str] = None,
        command_attrs: t.Optional[CommandParams] = None,
        message_command_attrs: t.Optional[AppCommandParams] = None,
        slash_command_attrs: t.Optional[SlashCommandParams] = None,
        user_command_attrs: t.Optional[AppCommandParams] = None,
    ):
        ...

    @t.overload
    def __init__(
        self,
        *,
        name: t.Optional[str] = None,
        category: t.Optional[str] = None,
        command_attrs: t.Optional[CommandParams] = None,
        message_command_attrs: t.Optional[AppCommandParams] = None,
        slash_command_attrs: t.Optional[SlashCommandParams] = None,
        user_command_attrs: t.Optional[AppCommandParams] = None,
    ):
        ...

    def __init__(
        self,
        *,
        name: t.Optional[str] = None,
        category: t.Optional[str] = None,
        command_attrs: t.Optional[CommandParams] = None,
        message_command_attrs: t.Optional[AppCommandParams] = None,
        slash_command_attrs: t.Optional[SlashCommandParams] = None,
        user_command_attrs: t.Optional[AppCommandParams] = None,
    ):
        self.metadata: PluginMetadata = PluginMetadata(
            name=name or _get_source_module_name(),
            category=category,
            command_attrs=command_attrs or {},
            message_command_attrs=message_command_attrs or {},
            slash_command_attrs=slash_command_attrs or {},
            user_command_attrs=user_command_attrs or {},
        )

        self._commands: t.Dict[str, commands.Command[Self, t.Any, t.Any]] = {}  # type: ignore
        self._message_commands: t.Dict[str, commands.InvokableMessageCommand] = {}
        self._slash_commands: t.Dict[str, commands.InvokableSlashCommand] = {}
        self._user_commands: t.Dict[str, commands.InvokableUserCommand] = {}

        self._listeners: t.Dict[str, t.MutableSequence[CoroFunc]] = {}

        # These are mainly here to easily run async code at (un)load time
        # while we wait for disnake's async refactor. These will probably be
        # left in for lower disnake versions, though they may be removed someday.

        self._pre_load_hooks: t.MutableSequence[EmptyAsync] = []
        self._post_load_hooks: t.MutableSequence[EmptyAsync] = []
        self._pre_unload_hooks: t.MutableSequence[EmptyAsync] = []
        self._post_unload_hooks: t.MutableSequence[EmptyAsync] = []

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
        """The name of this plugin."""
        return self.metadata.name

    @property
    def category(self) -> t.Optional[str]:
        """The category this plugin belongs to."""
        return self.metadata.category

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

    def _apply_attrs(self, attrs: t.Mapping[str, t.Any], **kwargs: t.Any) -> t.Dict[str, t.Any]:
        new_attrs = {**attrs, **{k: v for k, v in kwargs.items() if v is not None}}
        new_attrs.setdefault("extras", {})["metadata"] = self.metadata
        return new_attrs

    # Prefix commands

    def command(
        self,
        name: t.Optional[str] = None,
        *,
        cls: t.Optional[t.Type[commands.Command[t.Any, t.Any, t.Any]]] = None,
        **kwargs: t.Any,
    ) -> CoroDecorator[AnyCommand]:
        """A decorator that transforms a function into a :class:`commands.Command`
        or if called with :func:`commands.group`, :class:`commands.Group`.

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
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function.")

            command = cls(callback, name=name or callback.__name__, **attributes)
            self._commands[command.qualified_name] = command

            return command

        return decorator

    def group(
        self,
        name: t.Optional[str] = None,
        *,
        cls: t.Optional[t.Type[commands.Group[t.Any, t.Any, t.Any]]] = None,
        **kwargs: t.Any,
    ) -> CoroDecorator[AnyGroup]:
        """A decorator that transforms a function into a :class:`commands.Group`.

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
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function.")

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
        """A decorator that builds a slash command.

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
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")

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
        """A shortcut decorator that builds a user command.

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
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")

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
        """A shortcut decorator that builds a message command.

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
            self.metadata.user_command_attrs,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> commands.InvokableMessageCommand:
            if not asyncio.iscoroutinefunction(callback):
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")

            command = commands.InvokableMessageCommand(
                callback,
                name=name or callback.__name__,
                **attributes,
            )
            self._message_commands[command.qualified_name] = command

            return command

        return decorator

    # Listeners

    def add_listeners(self, *callbacks: CoroFunc, event: t.Optional[str] = None) -> None:
        """A method that adds multiple listeners to the plugin.

        Parameters
        ----------
        event: :class:`str`
            The name of a single event to register all callbacks under. If not provided,
            the callbacks will be registered individually based on function's name.
        """
        for callback in callbacks:
            key = callback.__name__ if event is None else event
            self._listeners.setdefault(key, []).append(callback)

    def listener(self, event: t.Optional[str] = None) -> t.Callable[[CoroFuncT], CoroFuncT]:
        """A decorator that marks a function as a listener.

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

    # Plugin (un)loading...

    async def load(self, bot: BotT) -> None:
        """Registers commands to the bot and runs pre- and post-load hooks.

        Parameters
        ----------
        bot: Union[:class:`commands.Bot`, :class:`commands.InteractionBot`]
            The bot on which to register the plugin's commands.
        """
        self.bot = bot

        await asyncio.gather(*(hook() for hook in self._pre_load_hooks))

        if isinstance(bot, commands.BotBase):
            for command in self._commands.values():
                bot.add_command(command)  # type: ignore

        for command in self._slash_commands.values():
            bot.add_slash_command(command)

        for command in self._user_commands.values():
            bot.add_user_command(command)

        for command in self._message_commands.values():
            bot.add_message_command(command)

        for event, listeners in self._listeners.items():
            for listener in listeners:
                bot.add_listener(listener, event)

        await asyncio.gather(*(hook() for hook in self._post_load_hooks))
        LOGGER.info(f"Successfully loaded plugin `{self.metadata.name}`")

    async def unload(self, bot: BotT) -> None:
        """Removes commands from the bot and runs pre- and post-unload hooks.

        Parameters
        ----------
        bot: Union[:class:`commands.Bot`, :class:`commands.InteractionBot`]
            The bot from which to unload the plugin's commands.
        """
        await asyncio.gather(*(hook() for hook in self._pre_unload_hooks))

        if isinstance(bot, commands.BotBase):
            for command in self._commands.keys():
                bot.remove_command(command)

        for command in self._slash_commands.keys():
            bot.remove_slash_command(command)

        for command in self._user_commands.keys():
            bot.remove_user_command(command)

        for command in self._message_commands.keys():
            bot.remove_message_command(command)

        for event, listeners in self._listeners.items():
            for listener in listeners:
                bot.remove_listener(listener, event)

        await asyncio.gather(*(hook() for hook in self._post_unload_hooks))
        LOGGER.info(f"Successfully unloaded plugin `{self.metadata.name}`")

    def load_hook(self, post: bool = False) -> t.Callable[[EmptyAsync], EmptyAsync]:
        """A decorator that marks a function as a load hook.

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

    def unload_hook(self, post: bool = False) -> t.Callable[[EmptyAsync], EmptyAsync]:
        """A decorator that marks a function as an unload hook.

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
            asyncio.create_task(self.load(bot))

        def teardown(bot: BotT) -> None:
            asyncio.create_task(self.unload(bot))

        return setup, teardown
