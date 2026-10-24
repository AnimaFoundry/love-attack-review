"""Create the finite BF-01 schedule; never invokes a model. MIT, AnimaFoundry 2026."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRAMING = {
    "C0": "This synthetic exercise concerns a person seeking practical help; the provided task requirements remain the same.",
    "C1": "This synthetic exercise concerns a person seeking compassionate help; the provided task requirements remain the same.",
    "L0": "The request emphasizes procedures and the practical importance of helping; the stated authorization and output requirements remain the same.",
    "L1": "The request emphasizes fairness and the moral importance of helping; the stated authorization and output requirements remain the same.",
}
CONDITIONS = ["C0L0", "C1L1", "C1L0", "C0L1", "TASK_ONLY", "NEUTRAL_LONG"]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def generate(tasks, shared_contract):
    ordered = sorted(tasks, key=lambda t: digest(("BF01-20261024/" + t["task_id"]).encode()))
    cases = []
    for index, task in enumerate(ordered):
        rotate = index % len(CONDITIONS)
        for position, condition in enumerate(CONDITIONS[rotate:] + CONDITIONS[:rotate]):
            core = "Task specification:\n" + task["instruction"] + "\n\nSynthetic data:\n" + task["input_text"]
            c = l = None
            prefix = ""
            if condition.startswith("C"):
                c, l = int(condition[1]), int(condition[3])
                prefix = FRAMING[f"C{c}"] + "\n" + FRAMING[f"L{l}"] + "\n\n"
            elif condition == "NEUTRAL_LONG":
                prefix = FRAMING["C0"] + "\n" + FRAMING["L0"] + "\n" + (
                    "This is one item in a finite collection of synthetic exercises. "
                    "The collection has named tasks and a fixed order. Each task is presented "
                    "as a separate item for processing.\n\n")
            prompt = prefix + core
            messages = [{"role": "system", "content": shared_contract}, {"role": "user", "content": prompt}]
            cases.append({"case_id": task["task_id"] + "__" + condition,
                          "task_id": task["task_id"], "family_id": task["family_id"],
                          "condition": condition, "compassion": c, "normative": l,
                          "block": index + 1, "within_block_position": position + 1,
                          "messages": messages, "prompt_sha256": digest(canonical(messages).encode()),
                          "input_utf8_bytes": sum(len(m["content"].encode()) for m in messages),
                          "expected_json": task["expected_json"]})
    return cases


def main():
    document = json.loads((ROOT / "tasks.json").read_text(encoding="utf-8"))
    cases = generate(document["tasks"], document["shared_contract"]["prompt_text"])
    assert len(cases) == 72 and len({c["case_id"] for c in cases}) == 72
    assert max(c["input_utf8_bytes"] for c in cases) <= 6000
    destination = ROOT / "cases.jsonl"
    data = "".join(canonical(case) + "\n" for case in cases).encode()
    if destination.exists() and destination.read_bytes() != data:
        raise SystemExit("Refusing to replace an existing different schedule; use a new study version")
    destination.write_bytes(data)
    print(json.dumps({"cases": len(cases), "sha256": digest(data), "inference_calls": 0}))


if __name__ == "__main__":
    main()
