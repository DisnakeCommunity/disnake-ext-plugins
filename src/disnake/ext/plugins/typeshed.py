"""Module that houses all typing related to plugins."""

from __future__ import annotations

import typing as t

import disnake
import typing_extensions
from disnake.ext import commands

if t.TYPE_CHECKING:
    from disnake.ext import tasks

T = t.TypeVar("T")
P = typing_extensions.ParamSpec("P")

AnyBot = t.Union[
    commands.Bot,
    commands.AutoShardedBot,
    commands.InteractionBot,
    commands.AutoShardedInteractionBot,
]
BotT = typing_extensions.TypeVar("BotT", bound=AnyBot, default=AnyBot)
PluginT = typing_extensions.TypeVar(
    "PluginT",
    bound="PluginProtocol[t.Any]",
    default="PluginProtocol[AnyBot]",
)

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

TypeT_co = t.TypeVar("TypeT_co", commands.SubCommandGroup, commands.SubCommand, covariant=True)


class ExtrasAware(t.Protocol):
    """A protocol that matches any object that implements extras."""

    extras: t.Dict[str, t.Any]


class CheckAware(t.Protocol):
    """A protocol that matches any object that implements checks."""

    checks: t.List[t.Callable[..., MaybeCoro[bool]]]


class CommandParams(t.TypedDict, total=False):
    """A :class:`TypedDict` with all the parameters to a :class:`commands.Command`."""

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
    """A :class:`TypedDict` with all the parameters to any kind of application command."""

    auto_sync: bool
    dm_permission: bool
    default_member_permissions: PermissionsOptional
    guild_ids: t.Sequence[int]
    extras: t.Dict[str, t.Any]


class SlashCommandParams(AppCommandParams, total=False):
    """A :class:`TypedDict` with all the parameters to a :class:`commands.InvokableSlashCommand`."""

    description: LocalizedOptional
    connectors: t.Dict[str, str]


class PluginProtocol(t.Protocol[BotT]):
    """Protocol for Plugin-like classes."""

    @property
    def bot(self) -> BotT:
        """The bot to which this plugin is registered."""
        ...

    @property
    def name(self) -> str:
        """The name of this sub plugin."""
        ...

    @property
    def extras(self) -> t.Dict[str, t.Any]:
        """A dict of extra metadata for this plugin.

        .. versionadded:: 0.2.4
        """
        ...

    @property
    def commands(self) -> t.Sequence[commands.Command[PluginProtocol[BotT], t.Any, t.Any]]:  # type: ignore
        """All prefix commands registered in this plugin."""
        ...

    @property
    def slash_commands(self) -> t.Sequence[commands.InvokableSlashCommand]:
        """All slash commands registered in this plugin."""
        ...

    @property
    def user_commands(self) -> t.Sequence[commands.InvokableUserCommand]:
        """All user commands registered in this plugin."""
        ...

    @property
    def message_commands(self) -> t.Sequence[commands.InvokableMessageCommand]:
        """All message commands registered in this plugin."""
        ...

    @property
    def loops(self) -> t.Sequence[tasks.Loop[t.Any]]:
        """All loops registered to this plugin."""
        ...

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
        ...

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
        ...

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
        ...

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
        ...

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
        ...

    # Checks

    def command_check(self, predicate: PrefixCommandCheckT) -> PrefixCommandCheckT:
        """Add a `commands.check` to all prefix commands on this plugin."""
        ...

    def slash_command_check(self, predicate: AppCommandCheckT) -> AppCommandCheckT:
        """Add a `commands.check` to all slash commands on this plugin."""
        ...

    def message_command_check(self, predicate: AppCommandCheckT) -> AppCommandCheckT:
        """Add a `commands.check` to all message commands on this plugin."""
        ...

    def user_command_check(self, predicate: AppCommandCheckT) -> AppCommandCheckT:
        """Add a `commands.check` to all user commands on this plugin."""
        ...

    # Listeners

    def add_listeners(self, *callbacks: CoroFunc, event: t.Optional[str] = None) -> None:
        """Add multiple listeners to the plugin.

        Parameters
        ----------
        *callbacks: Callable[..., Any]
            The callbacks to add as listeners for this plugin.
        event: :class:`str`
            The name of a single event to register all callbacks under. If not provided,
            the callbacks will be registered individually based on function's name.
        """
        ...

    def listener(self, event: t.Optional[str] = None) -> t.Callable[[CoroFuncT], CoroFuncT]:
        """Register a function as a listener on this plugin.

        This is the plugin equivalent of :meth:`commands.Bot.listen`.

        Parameters
        ----------
        event: :class:`str`
            The name of the event being listened to. If not provided, it
            defaults to the function's name.
        """
        ...

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
        ...
