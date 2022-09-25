from __future__ import annotations

import asyncio
import dataclasses
import logging
import pathlib
import sys
import typing as t

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

Coro = t.Coroutine[t.Any, t.Any, T]
EmptyAsync = t.Callable[[], Coro[None]]
SetupFunc = t.Callable[[commands.Bot], None]

AnyCommand = commands.Command[t.Any, t.Any, t.Any]
AnyGroup = commands.Group[t.Any, t.Any, t.Any]

CoroFunc = t.Callable[..., Coro[t.Any]]
CoroFuncT = t.TypeVar("CoroFuncT", bound=CoroFunc)
CoroDecorator = t.Callable[[CoroFunc], T]

LocalizedOptional = t.Union[t.Optional[str], disnake.Localized[t.Optional[str]]]
PermissionsOptional = t.Optional[t.Union[disnake.Permissions, int]]


class CommandParams(t.TypedDict, total=False):
    name: str
    help: str
    brief: str
    usage: str
    aliases: t.Union[t.List[str], t.Tuple[str]]
    enabled: bool
    description: str
    hidden: bool
    ignore_extra: bool
    cooldown_after_parsing: bool
    extras: t.Dict[str, t.Any]


class AppCommandParams(t.TypedDict, total=False):
    name: LocalizedOptional
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


class Plugin:

    __slots__ = (
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

    metadata: PluginMetadata

    # Mostly just here to easily run async code at (un)load time while we wait
    # for disnake's async refactor. I will probably leave these in for lower
    # disnake versions, but they may be removed someday.
    _pre_load_hooks: t.List[t.Callable[[], Coro[None]]]
    _post_load_hooks: t.List[t.Callable[[], Coro[None]]]
    _pre_unload_hooks: t.List[t.Callable[[], Coro[None]]]
    _post_unload_hooks: t.List[t.Callable[[], Coro[None]]]

    def __init__(self, metadata: t.Optional[PluginMetadata] = None):
        self.metadata = metadata or PluginMetadata(name=_get_source_module_name())

        self._commands: t.Dict[str, commands.Command[Plugin, t.Any, t.Any]] = {}  # type: ignore
        self._message_commands: t.Dict[str, commands.InvokableMessageCommand] = {}
        self._slash_commands: t.Dict[str, commands.InvokableSlashCommand] = {}
        self._user_commands: t.Dict[str, commands.InvokableUserCommand] = {}

        self._listeners: t.Dict[str, t.MutableSequence[CoroFunc]] = {}

        self._pre_load_hooks = []
        self._post_load_hooks = []
        self._pre_unload_hooks = []
        self._post_unload_hooks = []

    @classmethod
    def with_metadata(
        cls,
        *,
        name: t.Optional[str] = None,
        category: t.Optional[str] = None,
        command_attrs: t.Optional[CommandParams] = None,
        message_command_attrs: t.Optional[AppCommandParams] = None,
        slash_command_attrs: t.Optional[SlashCommandParams] = None,
        user_command_attrs: t.Optional[AppCommandParams] = None,
    ) -> Plugin:
        return cls(
            PluginMetadata(
                name=name or _get_source_module_name(),
                category=category,
                command_attrs=command_attrs or {},
                message_command_attrs=message_command_attrs or {},
                slash_command_attrs=slash_command_attrs or {},
                user_command_attrs=user_command_attrs or {},
            )
        )

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def category(self) -> t.Optional[str]:
        return self.metadata.category

    @property
    def commands(self) -> t.Sequence[commands.Command[Plugin, t.Any, t.Any]]:  # type: ignore
        return tuple(self._commands.values())

    @property
    def slash_commands(self) -> t.Sequence[commands.InvokableSlashCommand]:
        return tuple(self._slash_commands.values())

    @property
    def user_commands(self) -> t.Sequence[commands.InvokableUserCommand]:
        return tuple(self._user_commands.values())

    @property
    def message_commands(self) -> t.Sequence[commands.InvokableMessageCommand]:
        return tuple(self._message_commands.values())

    def apply_attrs(self, attrs: t.Mapping[str, t.Any], **kwargs: t.Any) -> t.Dict[str, t.Any]:
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
        attributes = self.apply_attrs(self.metadata.command_attrs, name=name, **kwargs)

        if cls is None:
            cls = t.cast(t.Type[AnyCommand], attributes.pop("cls", AnyCommand))

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> AnyCommand:
            if not asyncio.iscoroutinefunction(callback):
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")

            if attributes["name"] is None:
                attributes["name"] = callback.__name__

            command = cls(callback, **attributes)
            self._commands[command.qualified_name] = command

            return command

        return decorator

    def group(
        self,
        name: t.Optional[str] = None,
        *,
        cls: t.Optional[t.Type[commands.Group[t.Any, t.Any, t.Any]]],
        **kwargs: t.Any,
    ) -> CoroDecorator[AnyGroup]:
        attributes = self.apply_attrs(self.metadata.command_attrs, name=name, **kwargs)

        if cls is None:
            cls = t.cast(t.Type[AnyGroup], attributes.pop("cls", AnyGroup))

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> AnyGroup:
            if not asyncio.iscoroutinefunction(callback):
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")

            if attributes["name"] is None:
                attributes["name"] = callback.__name__

            command = cls(callback, **attributes)
            self._commands[command.qualified_name] = command  # type: ignore

            return command

        return decorator

    # Application commands

    def slash_command(
        self,
        *,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: PermissionsOptional = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        connectors: t.Optional[t.Dict[str, str]] = None,
        auto_sync: t.Optional[bool] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> CoroDecorator[commands.InvokableSlashCommand]:
        attributes = self.apply_attrs(
            self.metadata.slash_command_attrs,
            name=name,
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

            command = commands.InvokableSlashCommand(callback, **attributes)
            self._slash_commands[command.qualified_name] = command

            return command

        return decorator

    def user_command(
        self,
        *,
        name: LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: PermissionsOptional = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        auto_sync: t.Optional[bool] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> CoroDecorator[commands.InvokableUserCommand]:
        attributes = self.apply_attrs(
            self.metadata.user_command_attrs,
            name=name,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> commands.InvokableUserCommand:
            if not asyncio.iscoroutinefunction(callback):
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")

            command = commands.InvokableUserCommand(callback, **attributes)
            self._user_commands[command.qualified_name] = command

            return command

        return decorator

    def message_command(
        self,
        *,
        name: LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: PermissionsOptional = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        auto_sync: t.Optional[bool] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> CoroDecorator[commands.InvokableMessageCommand]:
        attributes = self.apply_attrs(
            self.metadata.user_command_attrs,
            name=name,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> commands.InvokableMessageCommand:
            if not asyncio.iscoroutinefunction(callback):
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")

            command = commands.InvokableMessageCommand(callback, **attributes)
            self._message_commands[command.qualified_name] = command

            return command

        return decorator

    # Listeners

    def add_listeners(self, *callbacks: CoroFunc, event: t.Optional[str] = None) -> None:
        for callback in callbacks:
            key = callback.__name__ if event is None else event
            self._listeners.setdefault(key, []).append(callback)

    def listener(self, event: t.Optional[str] = None) -> t.Callable[[CoroFuncT], CoroFuncT]:
        def decorator(callback: CoroFuncT) -> CoroFuncT:
            self.add_listeners(callback, event=event)
            return callback

        return decorator

    # Plugin (un)loading...

    async def load(self, bot: commands.Bot) -> None:
        await asyncio.gather(hook() for hook in self._pre_load_hooks)

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

        await asyncio.gather(hook() for hook in self._post_load_hooks)
        LOGGER.info(f"Successfully loaded plugin `{self.metadata.name}`")

    async def unload(self, bot: commands.Bot) -> None:
        await asyncio.gather(hook() for hook in self._pre_unload_hooks)

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

        await asyncio.gather(hook() for hook in self._post_unload_hooks)
        LOGGER.info(f"Successfully unloaded plugin `{self.metadata.name}`")

    def load_hook(self, post: bool = False) -> t.Callable[[EmptyAsync], EmptyAsync]:
        hooks = self._post_load_hooks if post else self._pre_load_hooks

        def wrapper(callback: EmptyAsync) -> EmptyAsync:
            hooks.append(callback)
            return callback

        return wrapper

    def unload_hook(self, post: bool = False) -> t.Callable[[EmptyAsync], EmptyAsync]:
        hooks = self._post_unload_hooks if post else self._pre_unload_hooks

        def wrapper(callback: EmptyAsync) -> EmptyAsync:
            hooks.append(callback)
            return callback

        return wrapper

    def create_extension_handlers(self) -> t.Tuple[SetupFunc, SetupFunc]:
        def setup(bot: commands.Bot) -> None:
            asyncio.create_task(self.load(bot))

        def teardown(bot: commands.Bot) -> None:
            asyncio.create_task(self.unload(bot))

        return setup, teardown
