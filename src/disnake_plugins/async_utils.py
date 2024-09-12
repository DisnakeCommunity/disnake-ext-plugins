"""Utilities for asyncio patterns."""

import asyncio
import typing

# asyncio.Task isn't subscriptable in py 3.8, so we do this "workaround" to
# make it subscriptable and compatible with inspect.signature etc.
# This probably isn't necessary but everything for our users, eh?

if typing.TYPE_CHECKING:
    Task = asyncio.Task
else:
    T = typing.TypeVar("T")
    Task = typing._alias(asyncio.Task, T)  # noqa: SLF001

__all__: typing.Sequence[str] = ("safe_task",)


_tasks: typing.Set["Task[typing.Any]"] = set()


def safe_task(
    coroutine: typing.Coroutine[typing.Any, typing.Any, typing.Any],
) -> "Task[typing.Any]":
    """Create an asyncio background task without risk of it being GC'd."""
    task = asyncio.create_task(coroutine)

    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return task
