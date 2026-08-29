import json
from dataclasses import dataclass, field
from typing import Any

from literature_ai.agent_service.agent.memory.core import MemoryObject


@dataclass
class ScopingMemoryObject(MemoryObject):
    """
    Memory object holding the scoping agent's final specification.

    `specification` is the raw JSON object the scoping agent emits as its
    sole handoff artifact (see `config/core/agent/prompts/agent_types/
    scoping.md`) - research questions, review definition, inclusion/
    exclusion criteria, topical relevance, search terms, open items, and
    scope risk note. Stored as-is rather than mirrored into typed fields,
    since it's an opaque handoff artifact for downstream agents to read,
    not something this layer manipulates field-by-field.
    """

    specification: dict[str, Any] = field(default_factory=dict)

    def get_summary(self) -> str:
        return (
            f"{self.id}: the finalized scoping specification for this "
            "literature review. Call `retrieve_scope` to view the full "
            "specification, or `update_scope` with a complete replacement "
            "specification (as a JSON string) to change it."
        )

    def format_specification(self) -> str:
        """Renders the stored scope specification as pretty-printed JSON for an LLM to read."""
        if not self.specification:
            return "No scoping specification has been recorded yet."
        return json.dumps(self.specification, indent=2)

    def update_scope(self, specification: str) -> str:
        """
        Replaces the stored specification wholesale with the given JSON
        string. `specification` is opaque, handoff-artifact data (see class
        docstring) - there is no field-level update, so the caller must
        resend the complete specification, not a partial patch.
        """
        try:
            parsed = json.loads(specification)
        except json.JSONDecodeError as exc:
            return f"Invalid JSON, specification was not updated: {exc}"

        self.specification = parsed
        return "Scoping specification updated."
