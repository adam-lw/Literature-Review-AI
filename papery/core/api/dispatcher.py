from typing import Optional, Literal, Any
import asyncio
from papery.core.api.tasks import http_get_task, http_post_task
from papery.core.utils import load_dict, get_project_root
import time
import collections

from loguru import logger

DISPATCHER_REGISTRY_CONFIG_PATH = (
    get_project_root() / "config" / "core" / "dispatchers.yaml"
)

dispatcher_states = Literal["RUNNING", "STOPPED", "PAUSED"]


class Dispatcher:
    state: dispatcher_states

    def __init__(
        self,
        *,
        api_id: str,
        url: str,
        max_retries: int = 5,
        backoff_factor: float = 2.0,
        rpm: Optional[int] = None,
        delay_per_request: Optional[float] = None,
    ):
        self.api_id = api_id
        self.url = url
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.rpm = rpm
        self.delay_per_request = delay_per_request

        self.queue = asyncio.Queue()
        self.state: dispatcher_states = "STOPPED"
        self.requests_60s: list[float] = []

        print(f"Initialised dispatcher {api_id}")

    async def start(self):
        """
        Starts running the dispatcher
        """
        print(f"Started dispatcher {self.api_id}")
        self.state = "RUNNING"
        while self.state == "RUNNING":
            item = await self.queue.get()
            try:
                # Unpack queue item
                request, endpoint, future, task = item
            except Exception as e:
                logger.error(f"Error unpacking queue item: {e}")
                continue

            if self.rpm is not None:
                # Prune requests made >60s ago
                now = time.time()
                collections.deque(
                    self.requests_60s, maxlen=self.rpm
                )  # keep list from growing indefinitely

                # If we've hit the RPM limit, wait until we can make a request
                if len(self.requests_60s) >= self.rpm:
                    queue_wait = (self.requests_60s[0] + 60) - now
                    queue_wait = 0 if queue_wait < 0 else queue_wait
                    logger.info(
                        "Hit RPM limit, resuming in %.2f seconds..." % queue_wait
                    )
                    await asyncio.sleep(queue_wait)

            # If time since last request is below delay_per_request, wait the remaining time
            if (
                self.requests_60s
                and self.delay_per_request
                and (time.time() - self.requests_60s[-1]) < self.delay_per_request
            ):
                sleep_time = self.delay_per_request - (
                    time.time() - self.requests_60s[-1]
                )
                await asyncio.sleep(sleep_time)

            print(f"Dispatcher {self.api_id} processing queue item...")
            if task == "GET":
                task = http_get_task(
                    request=request, endpoint=self.url + endpoint, future=future
                )
            elif task == "POST":
                task = http_post_task(
                    request=request, endpoint=self.url + endpoint, future=future
                )

            asyncio.create_task(task)
            self.requests_60s.append(time.time())
            collections.deque(self.requests_60s, maxlen=self.rpm)

    async def add_to_queue(
        self, request: Any, endpoint: str, future: asyncio.Future, task: str
    ):
        logger.info(f"Adding to queue: {request}")
        await self.queue.put((request, endpoint, future, task))
        logger.info(f"Queue size is now {self.queue.qsize()}")

    def get_api_id(self) -> str:
        return self.api_id

    def get_max_retries(self) -> int:
        return self.max_retries

    async def pause(self, time: float) -> None:
        """
        Pauses the dispatcher for a given amount of time (in seconds).
        During this time, the dispatcher will not process any items from the queue.

        This can be used to implement backoff across all callers when the API asks us to slow down.
        """
        if self.state == "RUNNING":
            self.state = "PAUSED"
            await asyncio.sleep(time)
            self.state = "RUNNING"


class DispatcherRegistry:
    _dispatchers: dict[str, Dispatcher] = {}

    def __init__(self):
        # load available dispatchers from file
        dispatcher_meta = load_dict(DISPATCHER_REGISTRY_CONFIG_PATH)

        # Initialise dispatchers
        self._dispatchers = {
            k: Dispatcher(api_id=k, **v) for k, v in dispatcher_meta.items()
        }

    def register(self, dispatcher: Dispatcher):
        api_id = dispatcher.get_api_id()
        if api_id in self._dispatchers.keys():
            raise ValueError(f"Dispatcher with api_id {api_id} is already registered.")

        self._dispatchers[api_id] = dispatcher

    def get_dispatcher(self, api_id: str):
        if api_id not in self._dispatchers.keys():
            raise ValueError(f"api_id {api_id} not found.")

        disp = self._dispatchers[api_id]

        if disp.state == "STOPPED":
            print(f"Starting dispatcher {api_id}...")
            disp.state = "RUNNING"
            asyncio.create_task(disp.start())

        return disp


_dispatcher_registry: DispatcherRegistry = DispatcherRegistry()


def get_dispatcher(api_id: str):
    return _dispatcher_registry.get_dispatcher(api_id)
