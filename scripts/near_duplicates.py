"""Поиск близких train-постов для каждого golden-примера (сходство Жаккара по словам).

Дополняет точную проверку contract.validate_golden: показывает кандидатов
в смысловые перефразы для ручного разбора. Высокое сходство — повод
посмотреть пару глазами, низкое не доказывает отсутствие утечки.
"""
import json
import re
from pathlib import Path

THRESHOLD = 0.5
WORD = re.compile(r"\w+")


def words(text):
    match = re.search(r"«(.*)»", text, re.S)
    return set(WORD.findall((match.group(1) if match else text).casefold()))


def main():
    config = json.loads(Path("evaluation/params.json").read_text(encoding="utf-8"))
    load = lambda key: [json.loads(l) for l in Path(config[key]).read_text(encoding="utf-8").splitlines() if l.strip()]
    train = [(r["id"], words(r["input"])) for r in load("training_index")]
    report = []
    for row in load("golden") + load("behavioral"):
        g = words(row["input"])
        best = max(((len(g & t) / len(g | t), tid) for tid, t in train if t), default=(0.0, None))
        report.append({"id": row["id"], "nearest_train_id": best[1], "jaccard": round(best[0], 3)})
    report.sort(key=lambda r: -r["jaccard"])
    flagged = [r for r in report if r["jaccard"] >= THRESHOLD]
    out = {"threshold": THRESHOLD, "n_checked": len(report), "n_flagged": len(flagged),
           "max_jaccard": report[0]["jaccard"], "top": report[:10]}
    Path("metrics").mkdir(exist_ok=True)
    Path("metrics/leakage-near.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if flagged:
        raise SystemExit(f"Близкие к train примеры: {[r['id'] for r in flagged]} — разберите вручную")


if __name__ == "__main__":
    main()
