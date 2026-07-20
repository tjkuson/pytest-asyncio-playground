import pytest

@pytest.mark.asyncio(loop_scope="module")
async def test1():
    pass

class Test:
    @pytest.mark.asyncio(loop_scope="class")
    async def test2(self):
        pass

    @pytest.mark.asyncio(loop_scope="function")
    async def test3(self):
        pass

    @pytest.mark.asyncio(loop_scope="class")
    async def test4(self):
        pass

@pytest.mark.asyncio(loop_scope="module")
async def test5():
    pass

class Test2:
    @pytest.mark.asyncio(loop_scope="class")
    async def test6(self):
        pass

    @pytest.mark.asyncio(loop_scope="module")
    async def test7(self):
        pass

    @pytest.mark.asyncio(loop_scope="class")
    async def test8(self):
        pass
