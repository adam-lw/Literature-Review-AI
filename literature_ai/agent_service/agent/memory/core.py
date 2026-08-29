from dataclasses import dataclass


@dataclass
class MemoryObject:
    """
    Base class for objects held in an Agent's `memory` store.

    Subclasses represent a specific kind of context (e.g. a collection of
    papers) that the agent can look up on demand via a memory-aware tool (see
    `accepts_memory` on the `tool` decorator), rather than having it dumped
    into the prompt up front.
    """

    id: str

    def get_summary(self) -> str:
        """
        Short LLM-facing description of what this memory object is and how to
        retrieve its contents, plus any high-level info (e.g. counts) worth
        surfacing without dumping full contents into the prompt. Subclasses
        should override this - the default is a generic fallback.
        """
        return f"{self.id}: a `{self.__class__.__name__}` memory object."


def get_formatted_memory(memory: dict[str, MemoryObject]) -> str:
    """Returns a string summarizing available memory objects for use by an LLM."""
    if not memory:
        return ""

    lines = [f"- {obj.get_summary()}" for obj in memory.values()]

    return (
        "\n\nThe following items are available in memory. Call the matching "
        "memory-aware tool for its kind to view full contents.\n" + "\n".join(lines)
    )
