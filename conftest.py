from __future__ import annotations
import asyncio
import warnings
from asyncio import AbstractEventLoopPolicy, Runner, AbstractEventLoop
import contextlib

from collections.abc import Callable, Iterator
import enum
from typing import Any, Self

import pytest


# --- public API -------------------------------------------------------


def fixture(
    fixture_function: Any = None,
    loop_scope: Any = None,  # TODO: implement this
    **kwargs: Any,
) -> Callable:
    return pytest.fixture(fixture_function, **kwargs)


def is_async_test(item: pytest.Item) -> bool:
    raise NotImplementedError


# --- internals --------------------------------------------------------


class Mode(str, enum.Enum):
    AUTO = "auto"
    STRICT = "strict"

    @classmethod
    def from_config(cls, config: pytest.Config) -> Self:
        val = config.getoption("asyncio_mode")
        if val is None:
            val = config.getini("asyncio_mode")
        try:
            return Mode(val)
        except ValueError as exc:
            modes = ", ".join(m.value for m in Mode)
            msg = f"{val!r} is not a valid asyncio_mode. Valid modes: {modes}."
            raise pytest.UsageError(msg) from exc


def _resolve_asyncio_marker(item: pytest.Function) -> pytest.Mark | None:
    marker = item.get_closest_marker("asyncio")
    if marker is not None:
        return marker
    if Mode.from_config(item.config) == Mode.AUTO:
        item.add_marker("asyncio")
        return item.get_closest_marker("asyncio")
    return None


def _get_event_loop_policy() -> AbstractEventLoopPolicy:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return asyncio.get_event_loop_policy()


def _set_event_loop_policy(policy: AbstractEventLoopPolicy) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(policy)


@contextlib.contextmanager
def _temporary_event_loop_policy(
    policy: AbstractEventLoopPolicy,
) -> Iterator[None]:
    old_loop_policy = _get_event_loop_policy()
    _set_event_loop_policy(policy)
    try:
        yield
    finally:
        _set_event_loop_policy(old_loop_policy)


def _set_event_loop(loop: AbstractEventLoop | None) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop(loop)


@contextlib.contextmanager
def _scoped_runner(
    _asyncio_loop_factory,
) -> Iterator[Runner]:
    runner = Runner(
        loop_factory=_asyncio_loop_factory,
    )
    with runner:
        yield runner


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> object | None:
    testfunction = pyfuncitem.obj

    from _pytest.compat import is_async_function

    if not is_async_function(testfunction):
        return

    funcargs = pyfuncitem.funcargs
    testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
    with _scoped_runner(_asyncio_loop_factory=asyncio.new_event_loop) as runner:
        result = runner.run(testfunction(**testargs))
    return True
