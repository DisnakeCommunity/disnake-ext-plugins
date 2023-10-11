"""Module containing slash command placeholder objects."""

import abc
import typing as t

import disnake
from disnake.ext import commands

from . import typeshed

__all__: t.Sequence[str] = ("SubCommandPlaceholder", "SubCommandGroupPlaceholder")

# Copium as we can't do super().__init__ with a Protocol.
def _shared_init(
    self: "CommandPlaceholderABC[t.Any]",
    func: typeshed.CoroFunc,
    parent_name: str,
    /,
    *,
    name: typeshed.LocalizedOptional,
    **kwargs: t.Any,  # noqa: ANN401
) -> None:
    self._func = func
    self.parent_name = parent_name.strip()

    # This is how disnake does it so we follow suit.
    name_loc = disnake.Localized._cast(name, required=False)  # noqa: SLF001
    self._name = name_loc.string or func.__name__

    # This will be None until `set_parent` is called.
    self._command = None

    # These will be passed to the sub_command(_group) decorator.
    self._kwargs = kwargs


class CommandPlaceholderABC(abc.ABC, t.Generic[typeshed.TypeT_co]):
    """Base class for command placeholders.

    This is essentially only used internally as a shared logic container for
    :class:`SubCommandGroupPlaceholder` and :class:`SubCommandPlaceholder`,
    and should generally not need to be used externally.
    """

    __slots__: t.Sequence[str] = ("_command", "_func", "_kwargs", "_name", "parent_name")

    _command: t.Optional[typeshed.TypeT_co]
    _func: typeshed.CoroFunc
    _kwargs: t.Dict[str, t.Any]
    _name: str

    @t.overload
    @abc.abstractmethod
    def set_parent(
        self: "CommandPlaceholderABC[commands.SubCommand]",
        parent: t.Union[commands.InvokableSlashCommand, commands.SubCommandGroup],
    ) -> None:
        ...

    @t.overload
    @abc.abstractmethod
    def set_parent(
        self: "CommandPlaceholderABC[commands.SubCommandGroup]",
        parent: commands.InvokableSlashCommand,
    ) -> None:
        ...

    @abc.abstractmethod
    def set_parent(
        self,
        parent: t.Union[commands.InvokableSlashCommand, commands.SubCommandGroup],
    ) -> None:
        raise NotImplementedError

    @property
    def command(self) -> typeshed.TypeT_co:
        if self._command:
            return self._command

        msg = (
            "Cannot access attributes of a placeholder SubCommand(Group)"
            " without first setting its parent command."
        )
        raise RuntimeError(msg)

    @property
    def name(self) -> str:
        return self._name

    @property
    def qualified_name(self) -> str:
        return f"{self.parent_name} {self._name}"

    @property
    def docstring(self) -> str:
        return self.docstring

    @property
    def root_parent(self) -> commands.InvokableSlashCommand:
        return self.command.root_parent


class SubCommandPlaceholder(CommandPlaceholderABC[commands.SubCommand]):
    """A placeholder for a slash subcommand.

    This class allows to define a subcommand in a different file than the
    parent command.

    Most of the attributes on this class cannot be used until a parent is set
    using :meth:`.set_parent`. This is done automatically when the Plugin to
    which this placeholder is registered is loaded into the bot.

    This class should generally not be instantiated directly. Instead, create
    instances of this class through :meth:`SubPlugin.external_sub_command`.
    """

    __slots__: t.Sequence[str] = ("_deferred_autocompleters",)

    _deferred_autocompleters: t.Dict[str, t.Callable[..., t.Any]]

    def __init__(
        self,
        func: typeshed.CoroFunc,
        parent_name: str,
        /,
        *,
        name: typeshed.LocalizedOptional = None,
        **kwargs: t.Any,  # noqa: ANN401
    ) -> None:
        _shared_init(self, func, parent_name, name=name, **kwargs)
        self._deferred_autocompleters = {}

    def set_parent(
        self,
        parent: t.Union[commands.InvokableSlashCommand, commands.SubCommandGroup],
    ) -> None:
        """Set the parent command of this subcommand placeholder.

        This finalises the :class:`disnake.SubCommand` and makes it available
        through :obj:`.command`. After doing this, all properties that proxy to
        the underlying command become available.

        Parameters
        ----------
        parent:
            The parent command that this subcommand was a placeholder for.
        """
        self._command = parent.sub_command(**self._kwargs)(self._func)  # type: ignore

        if not self._deferred_autocompleters:
            return

        # Populate autocompleters...
        options = {option.name: option for option in self.body.options}

        for option_name, autocompleter in self._deferred_autocompleters.items():
            if option_name not in options:
                msg = f"Option {option_name!r} doesn't exist in '{self.qualified_name}'."
                raise ValueError(msg)

            self._command.autocompleters[option_name] = autocompleter
            options[option_name].autocomplete = True

    # TODO: If people ask for this, make fiels like description available
    #       before setting the parent command.
    @property
    def description(self) -> str:
        """The description of this subcommand.

        This is only available after setting a parent command using
        :meth:`.set_parent`.
        """
        return self.command.description

    @property
    def connectors(self) -> t.Dict[str, str]:
        """The connectors of this subcommand.

        This is only available after setting a parent command using
        :meth:`.set_parent`.
        """
        return self.command.connectors

    @property
    def autocompleters(self) -> t.Dict[str, t.Any]:
        """The autocompleters of this subcommand.

        This is only available after setting a parent command using
        :meth:`.set_parent`.
        """
        return self.command.autocompleters

    @property
    def parent(self) -> t.Union[commands.InvokableSlashCommand, commands.SubCommandGroup]:
        """The parent of this subcommand.

        This is only available after setting a parent command using
        :meth:`.set_parent`.
        """
        return self.command.parent

    @property
    def parents(
        self,
    ) -> t.Union[
        t.Tuple[commands.InvokableSlashCommand],
        t.Tuple[commands.SubCommandGroup, commands.InvokableSlashCommand],
    ]:
        """The parents of this subcommand.

        This is only available after setting a parent command using
        :meth:`.set_parent`.
        """
        return self.command.parents

    @property
    def body(self) -> disnake.Option:
        """The underlying representation of this subcommand.

        This is only available after setting a parent command using
        :meth:`.set_parent`.
        """
        return self.command.body

    # TODO: Maybe use ParamSpec here.
    async def invoke(
        self,
        inter: disnake.CommandInteraction,
        *args: t.Any,  # noqa: ANN401
        **kwargs: t.Any,  # noqa: ANN401
    ) -> None:
        """Invoke the slash command, running its callback and any converters.

        Parameters
        ----------
        inter:
            The interaction with which to run the command.
        *args:
            The positional arguments required to run the callback.
        **kwargs:
            The keyword arguments required to run the callback.
        """
        await self.command.invoke(inter, *args, **kwargs)  # pyright: ignore

    def autocomplete(
        self,
        option_name: str,
    ) -> t.Callable[[typeshed.CoroFuncT], typeshed.CoroFuncT]:
        """Register an autocomplete function for the specified option.

        Parameters
        ----------
        option_name:
            The name of the option for which to add an autocomplete. This has
            to match the name of an option on this subcommand.

        Returns
        -------
        Callable[[Callable], Callable]
            A decorator that adds the wrapped function as an autocomplete
            function to this subcommand.
        """
        if self._command:
            return self._command.autocomplete(option_name)  # pyright: ignore

        def decorator(func: typeshed.CoroFuncT) -> typeshed.CoroFuncT:
            self._deferred_autocompleters[option_name] = func
            return func

        return decorator


class SubCommandGroupPlaceholder(CommandPlaceholderABC[commands.SubCommandGroup]):
    """A placeholder for a slash subcommand group.

    This class allows to define a subcommand group in a different file than the
    parent command.

    Most of the attributes on this class cannot be used until a parent is set
    using :meth:`.set_parent`. This is done automatically when the Plugin to
    which this placeholder is registered is loaded into the bot.

    This class should generally not be instantiated directly. Instead, create
    instances of this class through :meth:`SubPlugin.external_sub_command_group`.
    """

    __slots__: t.Sequence[str] = ("_subcommand_placeholders",)

    _subcommand_placeholders: t.List[SubCommandPlaceholder]

    def __init__(
        self,
        func: typeshed.CoroFunc,
        parent_name: str,
        /,
        *,
        name: typeshed.LocalizedOptional = None,
        **kwargs: t.Any,  # noqa: ANN401
    ) -> None:
        _shared_init(self, func, parent_name, name=name, **kwargs)
        self._subcommand_placeholders = []

    def set_parent(self, parent: commands.InvokableSlashCommand) -> None:
        """Set the parent command of this subcommand group placeholder.

        This finalises the :class:`disnake.SubCommandGroup` and makes it
        available through :obj:`.command`. After doing this, all properties
        that proxy to the underlying command become available.

        Parameters
        ----------
        parent:
            The parent command that this subcommand was a placeholder for.
        """
        self._command = parent.sub_command_group(**self._kwargs)(self._func)  # type: ignore

        for subcommand in self._subcommand_placeholders:
            subcommand.set_parent(self._command)

    @property
    def parent(self) -> commands.InvokableSlashCommand:
        """The parent of this subcommand group.

        This is only available after setting a parent command using
        :meth:`.set_parent`.
        """
        return self.command.parent

    @property
    def parents(self) -> t.Tuple[commands.InvokableSlashCommand]:
        """The parents of this subcommand group.

        This is only available after setting a parent command using
        :meth:`.set_parent`.
        """
        return self.command.parents

    def sub_command(
        self,
        name: typeshed.LocalizedOptional = None,
        description: typeshed.LocalizedOptional = None,
        options: t.Optional[t.List[disnake.Option]] = None,
        connectors: t.Optional[t.Dict[str, str]] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
        **kwargs: t.Any,  # noqa: ANN401
    ) -> t.Callable[[typeshed.CoroFunc], SubCommandPlaceholder]:
        """Wrap a callable to create a subcommand in this group.

        As the parent command may not yet exist, this decorator returns a
        placeholder object. The placeholder object has properties proxying to
        the parent command that become available as soon as :meth:`set_parent`
        is called. This is done automatically when the plugin to which this
        group is registered is loaded into the bot.

        Parameters
        ----------
        parent_name:
            The name of the parent :class:`InvokableSlashCommand` or
            :class:`SubCommandGroup` to which this subcommand should be
            registered.
        name:
            The name of this subcommand. If not provided, this will use the
            name of the decorated function.
        description:
            The description of this command. If not provided, this will use the
            docstring of the decorated function.
        connectors:
            A mapping of option names to function parameter names, mainly for
            internal processes.
        extras:
            Any extras that are to be stored on the subcommand.

        Returns
        -------
        Callable[..., :class:`SubCommandPlaceholder`]
            A decorator that converts the provided method into a
            :class:`SubCommandGroupPlaceholder` and returns it.
        """

        def create_placeholder(func: typeshed.CoroFunc) -> SubCommandPlaceholder:
            placeholder = SubCommandPlaceholder(
                func,
                self.qualified_name,
                name=name,
                description=description,
                options=options,
                connectors=connectors,
                extras=extras,
                **kwargs,
            )
            self._subcommand_placeholders.append(placeholder)
            return placeholder

        if self._command:

            def create_and_bind_placeholder(func: typeshed.CoroFunc) -> SubCommandPlaceholder:
                placeholder = create_placeholder(func)
                placeholder.set_parent(self.command)
                return placeholder

            return create_and_bind_placeholder

        return create_placeholder
