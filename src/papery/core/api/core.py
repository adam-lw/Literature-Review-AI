from typing import Any, Literal
from papery.core.api.dispatcher import get_dispatcher
import asyncio
from papery.core.logging.langfuse import lf_logger
import time

from loguru import logger


async def api_call(
    api_id: str,
    header: dict[str, Any],
    body: dict[str, Any] = {},
    endpoint: str = "/",
    task: Literal["GET", "POST"] = "GET",
) -> dict[str, Any]:
    """
    Inferface for calling APIs using dispatchers. Handles rate limiting, retry logic and logging in parallel
    for multi-agent systems and bulk API calls.

    Parameters
    ----------
    api_id: str
        The ID of the API to call, as specified in the dispatcher registry config.
    header: dict[str, Any]
        The header/parameters to send with the API call.
    body: dict[str, Any]
        The body to send with the API call.
    """
    dispatcher = get_dispatcher(api_id)

    # Filter None values in header to stop aiohttp from erroring
    header_filtered = {}
    for k, v in header.items():
        if v is not None:
            if isinstance(v, bool):
                header_filtered[k] = str(v)
            else:
                header_filtered[k] = v

    for attempt in range(dispatcher.max_retries + 1):
        # log a lightweight api request event (will only write if LANGFUSE_ENABLED)
        try:
            lf_logger.log_api_call(
                api_id,
                endpoint,
                header_filtered,
                response=None,
                duration_s=0.0,
                error=None,
            )
        except Exception:
            pass

        future = asyncio.get_running_loop().create_future()

        await dispatcher.add_to_queue(
            {"params": header_filtered, "json": body},
            endpoint=endpoint,
            future=future,
            task=task,
        )

        start = time.time()
        response: dict[str, Any] = await future
        duration = time.time() - start

        # Log the response/result
        try:
            lf_logger.log_api_call(
                api_id, endpoint, header_filtered, response, duration, error=None
            )
        except Exception:
            pass

        # check header and status to handle retrying if appropriate
        if response.get("code", 200) in [
            429,
            503,
        ]:  # rate limit or service unavailable
            sleep_time = response.get(
                "Retry-After", (attempt + 1) * dispatcher.backoff_factor
            )

            logger.warning(
                f"API call failed with status {response.get('code', 'unknown')}. Retrying in {sleep_time} seconds..."
            )
            await dispatcher.pause(sleep_time)
        else:
            logger.info(
                f"API call successful with status {response.get('code', 'unknown')}."
            )
            break

    return response
