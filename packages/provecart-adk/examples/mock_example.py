"""Mock / offline example for provecart-adk.

Runs with no network and no API key. The default is MOCK mode: an
injected FakeProveCartClient answers the checks. Live mode is an
explicit opt-in: set PROVECART_LIVE=1 and pass your own real client
object where marked below; nothing live runs by default.

    python examples/mock_example.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from provecart_adk import FakeProveCartClient, ProveCartGuard, make_before_tool_callback


class FakeTool:
    def __init__(self, name):
        self.name = name


def main():
    if os.environ.get("PROVECART_LIVE") == "1":
        raise SystemExit(
            "Live mode is explicit opt-in: construct your real ProveCart "
            "client here and pass it to ProveCartGuard. This example ships "
            "with no live client and makes no network calls."
        )

    scenarios = [
        {"verdict": "MATCH", "corrections": [], "record_id": "rec_1", "max_attempts": 3},
        {"verdict": "BLOCK", "corrections": [{"action": "remove_item"}],
         "record_id": "rec_2", "max_attempts": 3},
        {"verdict": "REVIEW", "corrections": [], "record_id": "rec_3", "max_attempts": 3},
    ]
    args = {"mandate_id": "mandate_demo", "merchant": {"name": "Demo Shop"},
            "items": [{"name": "Demo item", "quantity": 1}], "total_price": 42}
    for response in scenarios:
        fake = FakeProveCartClient(response)
        callback = make_before_tool_callback(ProveCartGuard(fake))
        result = callback(tool=FakeTool("place_order"), args=args, tool_context=None)
        if result is None:
            print(f"{response['verdict']}: proceed - the purchase tool would run")
        else:
            print(f"{response['verdict']}: tool skipped - decision="
                  f"{result['provecart_decision']}, corrections={result['corrections']}")


if __name__ == "__main__":
    main()
