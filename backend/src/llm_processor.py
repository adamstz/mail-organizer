"""Local LLM processor stubs.

This module will contain wrappers to call a local LLM for categorization and
content processing. Keep it decoupled from actual model implementations.
"""
from typing import Any, Dict
import os
import json
import shlex
import subprocess


class LLMProcessor:
    def __init__(self, config: Dict | None = None):
        self.config = config or {}

    def categorize_message(self, subject: str, body: str) -> Dict:
        """Return a classification dict for a message.

        Example return: {"labels": ["finance", "important"], "priority": "high"}
        """
        # If an external/local LLM command is configured via the
        # ORGANIZE_MAIL_LLM_CMD env var, call it with a JSON payload on
        # stdin and expect a JSON response on stdout with keys `labels`
        # and/or `priority`.
        cmd = os.environ.get("ORGANIZE_MAIL_LLM_CMD")
        if cmd:
            try:
                inp = json.dumps({"subject": subject, "body": body}, ensure_ascii=False).encode("utf-8")
                # shell-split the command so users can configure e.g.:
                # "/usr/local/bin/my-llm --model local-model"
                args = shlex.split(cmd)
                proc = subprocess.run(args, input=inp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                if proc.returncode == 0:
                    out = proc.stdout.decode("utf-8").strip()
                    try:
                        return json.loads(out)
                    except Exception:
                        return {"labels": [], "priority": "normal"}
                else:
                    # fallback to local rule-based if the process failed
                    return self._rule_based(subject, body)
            except Exception:
                return self._rule_based(subject, body)

        # No external LLM configured: use a tiny rule-based fallback so
        # classification produces useful defaults during development.
        return self._rule_based(subject, body)

    def _rule_based(self, subject: str, body: str) -> Dict:
        """A simple, local heuristic classifier used as a fallback.

        This is intentionally small: it looks for keywords and maps them to
        labels/priority. Replace with a proper LLM call in production.
        """
        text = (subject or "") + "\n" + (body or "")
        text_lower = text.lower()
        labels = []
        priority = "normal"

        if any(k in text_lower for k in ["invoice", "payment", "receipt", "bill"]):
            labels.append("finance")
        if any(k in text_lower for k in ["password", "login", "security", "account"]):
            labels.append("security")
            priority = "high"
        if any(k in text_lower for k in ["urgent", "asap", "immediately"]):
            priority = "high"
        if any(k in text_lower for k in ["meeting", "schedule", "calendar"]):
            labels.append("meetings")

        return {"labels": labels, "priority": priority}

