from __future__ import annotations
import asyncio
import warnings
from asyncio import AbstractEventLoopPolicy, Runner, AbstractEventLoop
import contextlib

from collections.abc import Callable, Iterator
import enum
from typing import Any, Self

import pytest
from pytest import ScopeName, StashKey


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
    breakpoint()
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


class _EventLoopManager:
    def __init__(self):
        self._runner_by_scope: dict[ScopeName, Runner] = {}

    @contextlib.contextmanager
    def _scoped_runner(
        self,
        scope: ScopeName,
        _asyncio_loop_factory,
    ) -> Iterator[Runner]:
        runner = Runner(
            loop_factory=_asyncio_loop_factory,
        )
        with runner:
            yield runner

    def setup_loop(self, item: pytest.Item, nextitem: pytest.Item | None):
        current_scope = _get_scope(item)
        runner = self._runner_by_scope.get(current_scope)
        if runner is None:
            runner = asyncio.Runner()
            print(f"Created runner for scope {current_scope=}")
            self._runner_by_scope[current_scope] = runner

    def teardown_loop(self, item: pytest.Item, nextitem: pytest.Item | None):
        if nextitem is None:
            for scope, runner in reversed(self._runner_by_scope.items()):
                print(f"Destroyed runner for scope {scope=}")
                runner.close()
            self._runner_by_scope.clear()
            return
        current_scope = _get_scope(item)
        match current_scope:
            case 'function':
                self._runner_by_scope.pop(current_scope).close()
                print(f"Destroyed runner for scope {current_scope=}")
            case 'class':
                if nextitem.cls is not item.cls:
                    self._runner_by_scope.pop(current_scope).close()
                    print(f"Destroyed runner for scope {current_scope=}")
            case 'module':
                if nextitem.module is not item.module:
                    self._runner_by_scope.pop(current_scope).close()
                    print(f"Destroyed runner for scope {current_scope=}")
            case 'package':
                raise NotImplementedError()
            case 'session':
                if nextitem is None:
                    self._runner_by_scope.pop(current_scope).close()
                    print(f"Destroyed runner for scope {current_scope=}")

    def get_runner(self, scope: ScopeName) -> Runner:
        return self._runner_by_scope[scope]
                
    def shutdown(self):
        # assert not self._runner_by_scope
        pass


_event_loop_manager_stash_key = StashKey[_EventLoopManager]()

def pytest_configure(config: pytest.Config):
    config.stash[_event_loop_manager_stash_key] = _EventLoopManager()
    
def pytest_unconfigure(config: pytest.Config):
    loop_manager = config.stash[_event_loop_manager_stash_key]
    loop_manager.shutdown()
    del config.stash[_event_loop_manager_stash_key]


_runner: asyncio.Runner | None = None

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem: pytest.Item | None):
    testfunction = item.obj

    from _pytest.compat import is_async_function

    if not is_async_function(testfunction):
        yield
        return

    marker = _resolve_asyncio_marker(item)
    if not marker:
        yield
        return
    loop_manager: _EventLoopManager = item.config.stash[_event_loop_manager_stash_key]
    loop_manager.setup_loop(item, nextitem)
    yield
    loop_manager.teardown_loop(item, nextitem)
    

@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> object | None:
    testfunction = pyfuncitem.obj

    from _pytest.compat import is_async_function

    if not is_async_function(testfunction):
        return

    funcargs = pyfuncitem.funcargs
    testargs = {arg: funcargs[arg] for arg in pyfuncitem._fixtureinfo.argnames}
    loop_manager: _EventLoopManager = pyfuncitem.config.stash[_event_loop_manager_stash_key]
    scope = _get_scope(pyfuncitem)
    runner = loop_manager.get_runner(scope)
    runner.run(testfunction(**testargs))
    return True

def _get_scope(item: pytest.Item) -> ScopeName:
    marker = _resolve_asyncio_marker(item)
    assert marker
    return marker.kwargs.get("loop_scope", "function")
    
