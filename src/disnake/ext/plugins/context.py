from __future__ import annotations

import typing as t

from . import utilities

__all__ = ("GlobalContext",)


class _Undefined:
    def __bool__(self):
        return False


Undefined: _Undefined = _Undefined()

T = t.TypeVar("T")
DefaultT = t.TypeVar("DefaultT")

UndefinedOr = t.Union[_Undefined, T]


class GlobalContext(t.Generic[T]):

    __instances__: t.ClassVar[t.MutableMapping[str, GlobalContext[t.Any]]] = {}
    key: str
    value: T
    default: UndefinedOr[T]

    def __new__(cls, key: str, default: UndefinedOr[T] = Undefined) -> GlobalContext[T]:
        if self := cls.__instances__.get(key):
            return self

        self = super().__new__(cls)
        self.key = key
        self.value = t.cast(T, Undefined)
        self.default = default

        cls.__instances__[key] = self
        return self

    def set(self, obj: T) -> None:
        self.value = obj

    @t.overload
    def get(self) -> T:
        ...

    @t.overload
    def get(self, default: DefaultT) -> t.Union[T, DefaultT]:
        ...

    def get(self, default: t.Union[_Undefined, DefaultT] = Undefined) -> t.Union[T, DefaultT]:
        if self.value is Undefined:

            resolved_default = default or self.default
            if resolved_default is Undefined:
                raise ValueError("")

            return resolved_default
        return self.value


class LocalContext(GlobalContext[T]):
    def __new__(cls, key: str, default: UndefinedOr[T] = Undefined) -> GlobalContext[T]:
        key = f"{utilities.get_source_module_name()}:{key}"
        return super().__new__(cls, key, default)
