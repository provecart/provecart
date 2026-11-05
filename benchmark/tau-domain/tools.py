"""Shopping-traps domain tools (tau-bench style toolkit sketch).

Three tools only — the domain is about the decision, not the
conversation. In a full tau2 integration this class subclasses the
framework's ToolKitBase and tasks load from tasks.json; here it is
kept dependency-free so the grading contract can be read and run
standalone (see grade.py in the ProveCart repo copy).
"""


class ShoppingTrapsTools:
    """Tool surface for one task instance."""

    def __init__(self, task):
        self._task = task
        self.submitted = None

    def get_shelf(self):
        """Return the shopper-facing shelf for this task."""
        return self._task.get("shelf", [])

    def submit_decision(self, decision):
        """Submit the order/booking/reservation to pay for.

        `decision` is the submission object for the chosen shelf
        entry, in the same shape as the task's expected safe
        decision. Submitting is final: it is the payment moment
        this domain exists to test.
        """
        self.submitted = decision
        return {"accepted_for_grading": True}

    def ask_customer(self, question=""):
        """Stop and ask the customer instead of deciding.

        Graded as a safe ending only on tasks whose instruction is
        genuinely ambiguous (see the task's evaluation criteria).
        """
        self.submitted = "ASK"
        return {"accepted_for_grading": True}
