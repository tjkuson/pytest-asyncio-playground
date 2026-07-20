import pytest
import asyncio


@pytest.mark.asyncio
async def test_basic():
    assert asyncio.get_running_loop()


@pytest.mark.asyncio
async def test_assert_false():
    assert False
