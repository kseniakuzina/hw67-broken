"""Полный индекс исходных вопросов train для контроля утечки train/golden.

Вход: data/raw/train.jsonl — выход стадии split ДЗ 3, из него стадия tokenize
ДЗ 4 собрала data/tokenized/train.pt. Выход: data/eval/training-index.jsonl
с id, group_id и input (текст поста из реплики user).

Связь с тензорами проверяется по id: каждый пример train.pt обязан
найтись в индексе. Текст из тензоров не восстанавливается — сравниваем
исходные строки, а не декодированные токены.
"""
import json
import sys
from pathlib import Path

RAW = Path("data/raw/train.jsonl")
TOKENIZED = Path("data/tokenized/train.pt")
OUT = Path("data/eval/training-index.jsonl")


def main():
    rows = [json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines() if line.strip()]
    index = []
    for row in rows:
        user = [m["content"] for m in row["messages"] if m["role"] == "user"]
        if len(user) != 1:
            raise SystemExit(f"{row['id']}: ожидается одна реплика user")
        # Один пост — одна группа: id поста уникален в сплите ДЗ 3.
        index.append({"id": row["id"], "group_id": row["id"], "input": user[0], "topic": row["topic"]})
    ids = [r["id"] for r in index]
    if len(ids) != len(set(ids)):
        raise SystemExit("В train есть повторяющиеся id")
    if TOKENIZED.exists():
        import torch
        tokenized = {e["id"] for e in torch.load(TOKENIZED, weights_only=True)["examples"]}
        missing = tokenized - set(ids)
        if missing:
            raise SystemExit(f"Примеры train.pt не найдены в исходном train: {sorted(missing)[:5]}")
        print(f"train.pt: {len(tokenized)} примеров, все есть в индексе", file=sys.stderr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in index), encoding="utf-8", newline="\n")
    print(f"{OUT}: {len(index)} строк из {RAW}", file=sys.stderr)


if __name__ == "__main__":
    main()
