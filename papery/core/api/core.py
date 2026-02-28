from typing import Any, Literal
from papery.core.api.dispatcher import get_dispatcher
import asyncio
from papery.core.telemetry.langfuse import lf_logger
import time

from loguru import logger


async def api_call(
    params: dict[str, Any],
    json: dict[str, Any],
    api_id: str,
    endpoint: str = "/",
    task: Literal["GET", "POST"] = "GET",
    verbosity: int = 0,
) -> dict[str, Any]:
    dispatcher = get_dispatcher(api_id)

    for i in range(dispatcher.get_max_retries()):
        # Filter None values to stop aiohttp from erroring
        params_filtered = {}
        for k, v in params.items():
            if v is not None:
                if isinstance(v, bool):
                    params_filtered[k] = str(v)
                else:
                    params_filtered[k] = v

        tries = 0
        while tries < dispatcher.get_max_retries():
            # log a lightweight api request event (will only write if LANGFUSE_ENABLED)
            try:
                lf_logger.log_api_call(
                    api_id,
                    endpoint,
                    params_filtered,
                    response=None,
                    duration_s=0.0,
                    error=None,
                )
            except Exception:
                pass

            future = asyncio.get_running_loop().create_future()

            await dispatcher.add_to_queue(
                {"params": params_filtered, "json": json},
                endpoint=endpoint,
                future=future,
                task=task,
            )

            start = time.time()
            response = await future
            duration = time.time() - start

            # Log the response/result
            try:
                lf_logger.log_api_call(
                    api_id, endpoint, params_filtered, response, duration, error=None
                )
            except Exception:
                pass

            # check header and status to handle retrying if appropriate
            if response.get("code", 200) in [
                429,
                503,
            ]:  # rate limit or service unavailable
                sleep_time = response.get(
                    "Retry-After", (tries + 1) * dispatcher.backoff_factor
                )

                logger.warning(
                    f"API call failed with status {response.get('code', 'unknown')}. Retrying in {sleep_time} seconds..."
                )
                await dispatcher.pause(sleep_time)
                tries += 1
            else:
                logger.info(
                    f"API call successful with status {response.get('code', 'unknown')}."
                )
                break

        return response
