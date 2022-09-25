import logging
import pathlib

__all__ = ("get_source_module_name",)


def get_source_module_name() -> str:
    return pathlib.Path(logging.currentframe().f_code.co_filename).stem
