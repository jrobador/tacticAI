"""Live smoke test against the real deployment. Run: python tests/agents/smoke_foundry.py"""
import time

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()
from tacticai.agents import foundry  # noqa: E402


class Answer(BaseModel):
    sum: int
    product: int
    explanation: str


def main():
    assert foundry.configured(), "FOUNDRY_* not set"
    print("a) plain:", foundry.run("Be brief.", "Say hi in 3 words.", timeout_s=30))

    log = foundry.ToolLog(cap=8)

    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    def mul(a: int, b: int) -> int:
        """Multiply two integers."""
        return a * b

    r = foundry.run("Use the tools for all arithmetic. Call independent tools in the same turn.",
                    "What is 17+25 and what is 6*7? Fill the schema.", tools=log.wrap_all([add, mul]),
                    response_format=Answer, timeout_s=60, max_tool_calls=4)
    print("b) structured+tools:", r)
    for e in log.entries:
        print("   ", e)

    t = time.time()
    # ponytail: output tokens come from a rough word count x1.33, not from API usage
    text = foundry.run("Write long, detailed answers.", "Explain how a high press works in football in about 450 words.",
                       timeout_s=90)
    dt = time.time() - t
    words = len(text.split())
    print(f"c) {words} words in {dt:.1f}s (~{words * 1.33 / dt:.0f} tokens/s incl. latency)")


if __name__ == "__main__":
    main()
