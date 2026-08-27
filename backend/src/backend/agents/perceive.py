"""Layer 7.1 "perceive" step (Section 5.7)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PerceivedCase:
    presenting_complaint: str
    history: str
    examination_findings: str

    @property
    def case_text(self) -> str:
        return f"{self.presenting_complaint} {self.history} {self.examination_findings}"


def perceive(presenting_complaint: str, history: str, examination_findings: str) -> PerceivedCase:
    return PerceivedCase(
        presenting_complaint=presenting_complaint.strip(),
        history=history.strip(),
        examination_findings=examination_findings.strip(),
    )
