import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def test_every_domain_generation_call_has_an_explicit_output_limit() -> None:
    missing: list[str] = []
    call_count = 0

    for path in APP_ROOT.rglob("*.py"):
        if path.name == "model_gateway.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"complete", "complete_for_profile"}:
                continue
            call_count += 1
            if not any(keyword.arg == "max_tokens" for keyword in node.keywords):
                relative = path.relative_to(APP_ROOT.parent.parent)
                missing.append(f"{relative}:{node.lineno}")

    assert call_count >= 20, "LLM call inventory unexpectedly shrank; review the scanner scope."
    assert not missing, f"Generation calls without max_tokens: {', '.join(missing)}"
