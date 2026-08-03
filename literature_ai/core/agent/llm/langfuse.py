from literature_ai.core.agent.llm.core import LLM
import time
from literature_ai.core.agent.logging.langfuse import lf_logger


class LangfuseLLM(LLM):
    """
    Wrapper around an LLM class which logs calls to Langfuse logger.
    """

    def __init__(self, llm: LLM):
        self._llm = llm

    async def call(self, messages: list[dict[str, str]]) -> str:
        start = time.time()
        err = None
        resp = None
        try:
            resp = await self._llm.call(messages)
            return resp
        except Exception as e:
            err = e
            raise
        finally:
            duration = time.time() - start
            try:
                short_resp = (
                    resp
                    if isinstance(resp, str) and len(resp) < 5000
                    else str(resp)[:5000]
                )
            except Exception:
                short_resp = None
            try:
                lf_logger.log_llm_call(
                    getattr(self._llm, "model", "unknown"),
                    messages,
                    short_resp,
                    duration,
                    err,
                )
            except Exception:
                # never surface logging errors
                pass
