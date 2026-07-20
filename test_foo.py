import pytest
import asyncio
from textwrap import dedent


@pytest.mark.asyncio
async def test_basic():
    assert asyncio.get_running_loop()


def test_sync():
    assert False


@pytest.mark.asyncio
async def test_assert_false():
    assert False

class Test:
    loop: asyncio.AbstractEventLoop | None = None
    
    @pytest.mark.asyncio(loop_scope="session")
    async def test_remember_loop(self):
        Test.loop = asyncio.get_running_loop()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_get_loop(self):
        assert Test.loop is not asyncio.get_running_loop()

    @pytest.mark.asyncio(loop_scope="session")
    async def test_get_loop_session(self):
        assert Test.loop is asyncio.get_running_loop()
