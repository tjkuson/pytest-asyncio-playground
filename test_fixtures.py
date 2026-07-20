import pytest
from pytest import ScopeName
# from pytest import StashKey
from conftest import _event_loop_manager_stash_key, _get_scope
import inspect
import asyncio


def async_fixture(*, scope: ScopeName):
    def outer(func):
        sig = inspect.signature(func)
        @pytest.fixture(name=func.__name__, scope=scope)
        def inner(request):
            test_params = {}
            for param_name in sig.parameters:
                test_params[param_name] = request.getfixturevalue(param_name)

            loop_manager = request.config.stash[_event_loop_manager_stash_key]
            # TODO: what if fixture and test have different scopes?
            loop_scope = _get_scope(request._pyfuncitem)
            runner = loop_manager.get_runner(loop_scope)
            # if inspect.iscoroutinefunction(func):
                
            return runner.run(func(**test_params))
        return inner
    return outer
    
loop: asyncio.AbstractEventLoop

@async_fixture(scope="module")
async def fix(request, tmpdir_factory):
    print(tmpdir_factory)
    global loop
    loop = asyncio.get_running_loop()
    print(f"fix (before): {loop=}")
    def finalizer():
        print(f"fix (after): {asyncio.get_running_loop()=}")
    request.addfinalizer(finalizer)
    return 1

@pytest.mark.asyncio(loop_scope="module")
async def test_a(fix):
    global loop
    assert loop is asyncio.get_running_loop()
    assert fix == 1

# Should fail, because of loop_scope mismatch!
@pytest.mark.asyncio(loop_scope="function")
async def test_b(request, fix):
    global loop
    assert loop is asyncio.get_running_loop()
    assert fix == 1

