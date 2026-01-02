import pathlib
import re

PROMPT_RE = re.compile(r"^\(venv\)\s+\S+@\S+:.+\$\s*$")

def test_no_terminal_prompts_accidentally_committed():
    """
    Guardrail: prevent accidental pasting of shell prompts into Python source.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    offenders = []
    for p in repo_root.rglob("*.py"):
        # skip virtualenv and migrations noise
        if "/venv/" in str(p) or "/migrations/" in str(p):
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            if PROMPT_RE.match(line.strip()):
                offenders.append(f"{p}:{i}: {line}")
    assert not offenders, "Terminal prompts found in source:\n" + "\n".join(offenders)
