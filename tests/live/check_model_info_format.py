import asyncio, sys, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PY = sys.executable
MAIN = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "main.py")

async def main():
    async with stdio_client(StdioServerParameters(command=PY, args=[MAIN])) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("get_revit_model_info", {})
            txt = " ".join(getattr(c, "text", "") for c in res.content)
            assert "ERROR DETAILS" not in txt, "false error header present:\n" + txt[:300]
            assert "total_elements" in txt, "expected model data missing"
            print("MODEL_INFO_OK")

asyncio.run(main())
