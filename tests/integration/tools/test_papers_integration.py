#!/usr/bin/env python3
"""
Integration tests for HF Papers Tool
Tests with real HF and arXiv APIs — all endpoints are public, no auth required.
"""
import asyncio
import sys

sys.path.insert(0, ".")

from agent.tools.papers_tool import hf_papers_handler

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_test(msg):
    print(f"{BLUE}[TEST]{RESET} {msg}")


def print_success(msg):
    print(f"{GREEN}✓{RESET} {msg}")


def print_warning(msg):
    print(f"{YELLOW}⚠{RESET} {msg}")


def print_error(msg):
    print(f"{RED}✗{RESET} {msg}")


def print_snippet(output, length=600):
    """Print a snippet of raw test output."""
    out = output[:length].replace("\n", "\\n")
    if len(output) > length:
        out += "..."
    print(f"{YELLOW}[RAW OUTPUT SNIPPET]{RESET} {out}")


passed = 0
failed = 0


async def run_tool(args: dict) -> tuple[str, bool]:
    """Call the handler and return (output, success)."""
    return await hf_papers_handler(args)


async def check(name: str, args: dict, *, expect_success: bool = True, expect_in: list[str] | None = None) -> str:
    """Run a tool call, validate, and track pass/fail.
    Prints a snippet of raw output of each test."""
    global passed, failed
    print_test(name)
    output, success = await run_tool(args)
    print_snippet(output)

    if success != expect_success:
        print_error(f"Expected success={expect_success}, got {success}")
        print(f"   Output: {output[:300]}")
        failed += 1
        return output

    if expect_in:
        missing = [s for s in expect_in if s.lower() not in output.lower()]
        if missing:
            print_error(f"Missing expected strings: {missing}")
            print(f"   Output: {output[:300]}")
            failed += 1
            return output

    print_success(f"OK ({len(output)} chars)")
    passed += 1
    return output


# ---------------------------------------------------------------------------
# Test suites
# ---------------------------------------------------------------------------


async def test_paper_discovery():
    print(f"\n{YELLOW}{'=' * 70}{RESET}")
    print(f"{YELLOW}Test Suite 1: Paper Discovery{RESET}")
    print(f"{YELLOW}{'=' * 70}{RESET}\n")

    # Trending papers
    output = await check(
        "trending (limit=3)",
        {"operation": "trending", "limit": 3},
        expect_in=["Trending Papers"],
    )

    # Trending with keyword filter
    await check(
        "trending with query='language'",
        {"operation": "trending", "query": "language", "limit": 5},
    )

    # Search
    await check(
        "search 'direct preference optimization'",
        {"operation": "search", "query": "direct preference optimization", "limit": 3},
        expect_in=["preference"],
    )

    # Paper details (DPO paper)
    await check(
        "paper_details for 2305.18290 (DPO paper)",
        {"operation": "paper_details", "arxiv_id": "2305.18290"},
        expect_in=["2305.18290", "Direct Preference"],
    )


async def test_read_paper():
    print(f"\n{YELLOW}{'=' * 70}{RESET}")
    print(f"{YELLOW}Test Suite 2: Read Paper{RESET}")
    print(f"{YELLOW}{'=' * 70}{RESET}\n")

    # Read paper TOC (no section specified)
    output = await check(
        "read_paper TOC for 2305.18290",
        {"operation": "read_paper", "arxiv_id": "2305.18290"},
        expect_in=["Sections", "Abstract"],
    )

    # Read specific section by number
    await check(
        "read_paper section='4' (DPO paper)",
        {"operation": "read_paper", "arxiv_id": "2305.18290", "section": "4"},
    )

    # Read specific section by name
    await check(
        "read_paper section='Experiments'",
        {"operation": "read_paper", "arxiv_id": "2305.18290", "section": "Experiments"},
    )

    # Fallback for a paper that might not have HTML
    # Using a very old paper ID — may or may not have HTML
    await check(
        "read_paper fallback (old paper 1706.03762 — Attention Is All You Need)",
        {"operation": "read_paper", "arxiv_id": "1706.03762"},
        expect_in=["Attention"],
    )


async def test_linked_resources():
    print(f"\n{YELLOW}{'=' * 70}{RESET}")
    print(f"{YELLOW}Test Suite 3: Linked Resources{RESET}")
    print(f"{YELLOW}{'=' * 70}{RESET}\n")

    # Find datasets linked to DPO paper
    await check(
        "find_datasets for 2305.18290",
        {"operation": "find_datasets", "arxiv_id": "2305.18290", "limit": 5},
    )

    # Find models linked to DPO paper
    await check(
        "find_models for 2305.18290",
        {"operation": "find_models", "arxiv_id": "2305.18290", "limit": 5},
    )

    # Find collections
    await check(
        "find_collections for 2305.18290",
        {"operation": "find_collections", "arxiv_id": "2305.18290"},
    )

    # Find all resources (parallel fan-out)
    await check(
        "find_all_resources for 2305.18290",
        {"operation": "find_all_resources", "arxiv_id": "2305.18290"},
        expect_in=["Datasets", "Models", "Collections"],
    )


async def test_edge_cases():
    print(f"\n{YELLOW}{'=' * 70}{RESET}")
    print(f"{YELLOW}Test Suite 4: Edge Cases{RESET}")
    print(f"{YELLOW}{'=' * 70}{RESET}\n")

    # Search with no results
    await check(
        "search gibberish query",
        {"operation": "search", "query": "xyzzyplugh_nonexistent_9999"},
        expect_in=["No papers found"],
    )

    # Missing required param
    await check(
        "search without query → error",
        {"operation": "search"},
        expect_success=False,
        expect_in=["required"],
    )

    # Missing arxiv_id
    await check(
        "find_datasets without arxiv_id → error",
        {"operation": "find_datasets"},
        expect_success=False,
        expect_in=["required"],
    )

    # Invalid arxiv_id
    await check(
        "paper_details with nonexistent ID",
        {"operation": "paper_details", "arxiv_id": "0000.00000"},
        expect_success=False,
    )

    # Invalid operation
    await check(
        "invalid operation → error",
        {"operation": "nonexistent_op"},
        expect_success=False,
        expect_in=["Unknown operation"],
    )

    # read_paper with nonexistent section
    await check(
        "read_paper with bad section name",
        {"operation": "read_paper", "arxiv_id": "2305.18290", "section": "Nonexistent Section XYZ"},
        expect_success=False,
        expect_in=["not found"],
    )


async def main():
    print("=" * 70)
    print(f"{BLUE}HF Papers Tool — Integration Tests{RESET}")
    print("=" * 70)
    print(f"{BLUE}All APIs are public, no authentication required.{RESET}\n")

    try:
        await test_paper_discovery()
        await test_read_paper()
        await test_linked_resources()
        await test_edge_cases()
    except Exception as e:
        print_error(f"Test suite crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Summary
    print(f"\n{'=' * 70}")
    total = passed + failed
    if failed == 0:
        print(f"{GREEN}✓ All {total} tests passed!{RESET}")
    else:
        print(f"{RED}✗ {failed}/{total} tests failed{RESET}")
        print(f"{GREEN}✓ {passed}/{total} tests passed{RESET}")

    print(f"{'=' * 70}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
