import aiohttp
from asyncio import Future
from aiohttp import ClientResponse
from typing import Any


async def http_get_task(request, future: Future, endpoint: str):
    async with aiohttp.ClientSession() as c:
        async with c.get(endpoint, **request) as response:
            to_return = await _handle_response(response)
    future.set_result(to_return)


async def http_post_task(request, future: Future, endpoint: str):
    async with aiohttp.ClientSession() as c:
        async with c.post(endpoint, **request) as response:
            to_return = await _handle_response(response)
    future.set_result(to_return)


async def _handle_response(response: ClientResponse) -> dict[str, Any]:
    response_json = await response.json()
    print(f"Response json: {str(response_json)[0:500]}...")
    print(f"Response json type: {type(response_json)}")
    if isinstance(response_json, dict) and "code" not in response_json.keys():
        to_return = response_json
        to_return["code"] = response.status
    elif not isinstance(response_json, dict):
        to_return = {"code": response.status, "data": response_json}
    else:
        to_return = response_json
        to_return["code"] = int(to_return["code"])
    print(f"To return: {str(to_return)[0:500]}...")
    return to_return
