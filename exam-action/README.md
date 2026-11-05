# ProveCart Agent Exam — GitHub Action

## Add it at setup, not after the first bad order

Certification is a setup step: add the exam to CI when the
agent project is created, so the agent is graded on real
traps — wrong variant, over-ceiling total, wrong date,
guessing instead of asking — before its first real purchase,
and re-graded on every change. A passing run certifies the
agent for 90 days and publishes its result page. A failing
run is a report card, not just a red X: it names the traps
the agent fell for, so the fix is specific.

```yaml
# .github/workflows/certify-agent.yml — runs on every push
name: certify-agent
on: [push]
jobs:
  exam:
    runs-on: ubuntu-latest
    steps:
      - uses: provecart/provecart/exam-action@main
        with:
          agent-name: "my-shopping-agent"
          model-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

Certification is a published result, never a gate: nothing
at any store requires it, and an uncertified agent's orders
are checked by exactly the same rules as a certified one's.
Running the exam in CI simply means the agent practices
before it spends.
