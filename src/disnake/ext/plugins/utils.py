"""Utilities for plguins."""

import asyncio
import logging
import pathlib
import typing as t

_LOGGER = logging.getLogger(__name__)

# asyncio.Task isn't subscriptable in py 3.8, so we do this "workaround" to
# make it subscriptable and compatible with inspect.signature etc.
# This probably isn't necessary but everything for our users, eh?

if t.TYPE_CHECKING:
    Task = asyncio.Task
else:
    T = t.TypeVar("T")
    Task = t._alias(asyncio.Task, T)  # noqa: SLF001

__all__: t.Sequence[str] = ("safe_task",)


_tasks: t.Set["Task[t.Any]"] = set()


def safe_task(
    coroutine: t.Coroutine[t.Any, t.Any, t.Any],
) -> "Task[t.Any]":
    """Create an asyncio background task without risk of it being GC'd."""
    task = asyncio.create_task(coroutine)

    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    return task


# We don't want to use stdlib files (typing) or disnake.ext.plugins to name the plugin.
_INVALID: t.Final[t.Sequence[pathlib.Path]] = (
    pathlib.Path(t.__file__).parent.resolve(),
    pathlib.Path(__file__).parent.resolve(),
)


def _is_valid_path(path: str) -> bool:
    to_check = pathlib.Path(path).resolve()
    for invalid_path in _INVALID:
        if invalid_path == to_check or invalid_path in to_check.parents:
            return False

    return True


def get_source_module_name() -> str:
    """Get current frame from exception traceback."""
    # We ignore ruff here because we need to raise and immediately catch an
    # exception to figure out our stack level.
    try:
        raise Exception  # noqa: TRY002, TRY301
    except Exception as exc:  # noqa: BLE001
        tb = exc.__traceback__

    if not tb:
        # No traceback, therefore can't access frames and infer plugin name...
        _LOGGER.warning("Failed to infer file name, defaulting to 'plugin'.")
        return "plugin"

    # Navigate all frames for one with a valid path.
    # Note that we explicitly filter out:
    # - the stdlib typing module; if the generic parameter is specified, this
    #   will be encountered before the target module.
    # - this file; we don't want to just return "plugin" if possible.
    frame = tb.tb_frame
    while frame := frame.f_back:
        if _is_valid_path(frame.f_code.co_filename):
            break

    else:
        _LOGGER.warning("Failed to infer file name, defaulting to 'plugin'.")
        return "plugin"

    module_name = frame.f_locals["__name__"]
    _LOGGER.debug("Module name resolved to %r", module_name)
    return module_name
