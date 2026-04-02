"""Property tests for README.md structural correctness.

These tests validate that the monorepo root README.md conforms to the
structural requirements defined in the World-Class README & Contributor Hub spec.
Each test maps to a specific correctness property from the design document.
"""

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

README_PATH = Path(__file__).resolve().parent.parent.parent.parent / "README.md"


def _readme_text() -> str:
    """Return the full README content."""
    return README_PATH.read_text(encoding="utf-8")


def _readme_lines() -> list[str]:
    """Return README lines (preserving blanks)."""
    return _readme_text().splitlines()


def _h2_headings() -> list[str]:
    """Extract all ## headings (full text after '## ')."""
    return [
        line.removeprefix("## ").strip()
        for line in _readme_lines()
        if line.startswith("## ")
    ]


def _heading_text_without_emoji(heading: str) -> str:
    """Strip emoji/unicode symbols from a heading, returning only ASCII-ish text."""
    # Keep only word chars, spaces, hyphens, dots, slashes
    return re.sub(r"[^\w\s\-./]", "", heading).strip()


def _section_content(section_prefix: str) -> str:
    """Return the content between a ## heading matching *section_prefix* and the next ## heading."""
    lines = _readme_lines()
    capturing = False
    result: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if capturing:
                break
            text = _heading_text_without_emoji(line.removeprefix("## ").strip())
            if text.lower().startswith(section_prefix.lower()):
                capturing = True
                continue
        if capturing:
            result.append(line)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Property 1: README section ordering
# ---------------------------------------------------------------------------

REQUIRED_SECTION_ORDER = [
    "Quick Start",
    "Local Battle Arena",
    "Environment Configuration",
    "Connect Your Own Agents",
    "Leaderboard",
    "Developing with Kiro",
    "Contributing",
    "License",
]


def test_readme_section_ordering():
    """Property 1: README section ordering.

    Parse ## headings from README.md, verify required order:
    Quick Start < Local Battle Arena < Environment Configuration <
    Connect Your Own Agents < Leaderboard < Developing with Kiro <
    Contributing < License.

    **Validates: Requirements 1.1**
    """
    headings = _h2_headings()
    # Strip emoji to get plain text for matching
    plain_headings = [_heading_text_without_emoji(h) for h in headings]

    # Find the index of each required section in the heading list
    indices: list[int] = []
    for required in REQUIRED_SECTION_ORDER:
        found_idx = None
        for i, ph in enumerate(plain_headings):
            if required.lower() in ph.lower():
                found_idx = i
                break
        assert found_idx is not None, (
            f"Required section '{required}' not found in README headings: {plain_headings}"
        )
        indices.append(found_idx)

    # Verify strictly increasing order
    for i in range(len(indices) - 1):
        assert indices[i] < indices[i + 1], (
            f"Section '{REQUIRED_SECTION_ORDER[i]}' (index {indices[i]}) "
            f"must appear before '{REQUIRED_SECTION_ORDER[i + 1]}' (index {indices[i + 1]})"
        )


# ---------------------------------------------------------------------------
# Property 2: Quick start code blocks use bash
# ---------------------------------------------------------------------------


def test_quick_start_code_blocks_use_bash():
    """Property 2: Quick start code blocks use bash language identifier.

    Extract all fenced code blocks from the Quick Start section.
    Verify each has the ``bash`` language identifier.

    **Validates: Requirements 2.3**
    """
    qs_content = _section_content("Quick Start")
    assert qs_content, "Quick Start section not found or empty"

    # Find all fenced code block openers (``` followed by optional language)
    code_block_pattern = re.compile(r"^```(\w*)", re.MULTILINE)
    openers = code_block_pattern.findall(qs_content)

    # Filter to only opening fences (non-empty language or the start of a block)
    # We pair openers: every odd ``` is a closer. So take every other match.
    # Actually, just find lines starting with ``` that have a language tag or are openers.
    lines = qs_content.splitlines()
    languages: list[str] = []
    inside_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") and not inside_block:
            lang = stripped[3:].strip()
            languages.append(lang)
            inside_block = True
        elif stripped.startswith("```") and inside_block:
            inside_block = False

    assert len(languages) > 0, "No code blocks found in Quick Start section"
    for lang in languages:
        assert lang == "bash", (
            f"Quick Start code block has language '{lang}', expected 'bash'"
        )


# ---------------------------------------------------------------------------
# Property 3: Scenario schema documentation completeness
# ---------------------------------------------------------------------------

ARENA_SCENARIO_FIELDS = [
    "id", "name", "description", "agents", "toggles",
    "negotiation_params", "outcome_receipt",
]


@pytest.mark.parametrize("field", ARENA_SCENARIO_FIELDS)
def test_scenario_schema_field_documented(field: str):
    """Property 3: Scenario schema documentation completeness.

    For each required ArenaScenario field, verify the Connect Your Own Agents
    section mentions it.

    **Validates: Requirements 5.2**
    """
    section = _section_content("Connect Your Own Agents")
    assert section, "Connect Your Own Agents section not found or empty"
    assert field in section, (
        f"ArenaScenario field '{field}' not documented in Connect Your Own Agents section"
    )


# ---------------------------------------------------------------------------
# Property 4: Agent schema documentation completeness
# ---------------------------------------------------------------------------

AGENT_DEFINITION_FIELDS = [
    "role", "name", "type", "persona_prompt", "goals", "budget",
    "tone", "output_fields", "model_id", "fallback_model_id",
]


@pytest.mark.parametrize("field", AGENT_DEFINITION_FIELDS)
def test_agent_schema_field_documented(field: str):
    """Property 4: Agent schema documentation completeness.

    For each required AgentDefinition field, verify the agent connection
    section mentions it.

    **Validates: Requirements 5.3**
    """
    section = _section_content("Connect Your Own Agents")
    assert section, "Connect Your Own Agents section not found or empty"
    assert field in section, (
        f"AgentDefinition field '{field}' not documented in Connect Your Own Agents section"
    )


# ---------------------------------------------------------------------------
# Property 5: Example scenario JSON validates against schema
# ---------------------------------------------------------------------------


def test_example_scenario_json_validates():
    """Property 5: Example scenario JSON validates against schema.

    Extract JSON code blocks from the Connect Your Own Agents section,
    parse with the ArenaScenario Pydantic model, assert no validation errors.

    **Validates: Requirements 5.4**
    """
    from app.scenarios.models import ArenaScenario

    section = _section_content("Connect Your Own Agents")
    assert section, "Connect Your Own Agents section not found or empty"

    # Extract JSON code blocks
    json_blocks: list[str] = []
    lines = section.splitlines()
    inside_json = False
    current_block: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```json") and not inside_json:
            inside_json = True
            current_block = []
        elif stripped.startswith("```") and inside_json:
            inside_json = False
            json_blocks.append("\n".join(current_block))
        elif inside_json:
            current_block.append(line)

    assert len(json_blocks) > 0, (
        "No JSON code blocks found in Connect Your Own Agents section"
    )

    # Try to parse each JSON block as ArenaScenario — at least one must succeed
    validated = 0
    errors: list[str] = []
    for block in json_blocks:
        try:
            data = json.loads(block)
            ArenaScenario(**data)
            validated += 1
        except Exception as exc:
            errors.append(str(exc))

    assert validated > 0, (
        f"No JSON block validated as ArenaScenario. Errors: {errors}"
    )


# ---------------------------------------------------------------------------
# Property 8: Section headings contain emoji markers
# ---------------------------------------------------------------------------


def test_section_headings_contain_emoji():
    """Property 8: README section headings contain emoji markers.

    For each ## heading in README, verify it contains at least one
    emoji/Unicode symbol character (ord > 0x2000).

    **Validates: Requirements 10.2**
    """
    headings = _h2_headings()
    assert len(headings) > 0, "No ## headings found in README"

    for heading in headings:
        has_emoji = any(ord(ch) > 0x2000 for ch in heading)
        assert has_emoji, (
            f"Heading '## {heading}' does not contain an emoji/Unicode symbol marker"
        )


# ---------------------------------------------------------------------------
# Property 9: TOC links resolve to actual headings
# ---------------------------------------------------------------------------


def _github_anchor(heading: str) -> str:
    """Generate a GitHub-compatible anchor from a heading string.

    GitHub's algorithm: lowercase, strip characters that aren't alphanumeric,
    spaces, or hyphens, replace spaces with hyphens, collapse multiple hyphens.
    Emoji characters are stripped.
    """
    # Remove emoji / high-unicode characters
    cleaned = "".join(ch for ch in heading if ord(ch) < 0x2000 or ch in "-_ ")
    # Lowercase
    cleaned = cleaned.lower()
    # Keep only alphanumeric, spaces, hyphens
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    # Replace spaces with hyphens
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    # Collapse multiple hyphens
    cleaned = re.sub(r"-+", "-", cleaned)
    # Strip leading/trailing hyphens
    cleaned = cleaned.strip("-")
    return cleaned


def test_toc_links_resolve():
    """Property 9: Table of contents links resolve to actual headings.

    For each anchor link in the TOC section, verify a corresponding heading
    exists whose GitHub-generated anchor matches.

    **Validates: Requirements 10.3**
    """
    text = _readme_text()
    lines = _readme_lines()

    # Find TOC section: between "## 📑 Table of Contents" and next "---" or "## "
    toc_lines: list[str] = []
    in_toc = False
    for line in lines:
        if line.startswith("## ") and "Table of Contents" in line:
            in_toc = True
            continue
        if in_toc:
            if line.startswith("## ") or line.strip() == "---":
                break
            toc_lines.append(line)

    assert toc_lines, "Table of Contents section not found"

    # Extract anchor links from TOC: pattern [text](#anchor)
    anchor_pattern = re.compile(r"\[.*?\]\(#(.*?)\)")
    toc_anchors: list[str] = []
    for line in toc_lines:
        toc_anchors.extend(anchor_pattern.findall(line))

    assert len(toc_anchors) > 0, "No anchor links found in Table of Contents"

    # Build set of all heading anchors in the document
    headings = _h2_headings()
    heading_anchors = {_github_anchor(h) for h in headings}

    # Also generate anchors with leading dash stripped (GitHub sometimes does this)
    heading_anchors_no_leading_dash = {a.lstrip("-") for a in heading_anchors}

    for toc_anchor in toc_anchors:
        clean_toc = toc_anchor.lstrip("-")
        assert (
            toc_anchor in heading_anchors
            or clean_toc in heading_anchors
            or clean_toc in heading_anchors_no_leading_dash
        ), (
            f"TOC anchor '#{toc_anchor}' does not resolve to any heading. "
            f"Available anchors: {sorted(heading_anchors)}"
        )


# ---------------------------------------------------------------------------
# Property 10: README line count under 800
# ---------------------------------------------------------------------------


def test_readme_line_count_under_800():
    """Property 10: README line count under 800.

    Count total lines in README.md, assert strictly less than 800.

    **Validates: Requirements 10.5**
    """
    line_count = len(_readme_lines())
    assert line_count < 800, (
        f"README has {line_count} lines, must be strictly under 800"
    )


# ---------------------------------------------------------------------------
# Property 11: Kiro directory documentation completeness
# ---------------------------------------------------------------------------

KIRO_REQUIRED_ELEMENTS = [
    "steering/",
    "specs/",
    "hooks/",
    "tech.md",
    "styling.md",
    "testing.md",
    "deployment.md",
    "product.md",
]


@pytest.mark.parametrize("element", KIRO_REQUIRED_ELEMENTS)
def test_kiro_directory_element_documented(element: str):
    """Property 11: Kiro directory documentation completeness.

    For each required .kiro/ element, verify the Developing with Kiro
    section mentions it.

    **Validates: Requirements 12.2, 12.3**
    """
    section = _section_content("Developing with Kiro")
    assert section, "Developing with Kiro section not found or empty"

    # For directory entries like "steering/", also match without trailing slash
    search_term = element.rstrip("/")
    assert search_term in section, (
        f"Kiro element '{element}' not documented in Developing with Kiro section"
    )
