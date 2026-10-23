# Доступ к данным и воспроизведение

## Что под DVC

| файл | как получен |
|---|---|
| `data/raw/train.jsonl`, `data/raw/val.jsonl` | выход стадии split ДЗ 3 (тот же файл, что в ДЗ 4) — `dvc add` |
| `data/tokenized/train.pt`, `data/tokenized/val.pt` | выход стадии tokenize ДЗ 4 — `dvc add` |
| `data/eval/training-index.jsonl` | стадия `training_index` (`scripts/make_training_index.py`): все 3747 постов train; проверяет, что все 3731 id из `train.pt` есть в индексе |
| `data/eval/golden.jsonl`, `data/eval/behavioral.jsonl` | стадия `eval_sets` (`scripts/build_eval_sets.py`): вручную написанные посты, метка и источник — в самом скрипте и в поле `source` |
| `metrics/leakage-near.json` | стадия `leakage` (`scripts/near_duplicates.py`): ближайший train-пост для каждого golden |

Хеши — в `*.dvc` и `dvc.lock`. Remote по умолчанию — локальный каталог
`../dvc-storage` (рядом с репозиторием). Он прикладывается к сдаче архивом;
распакуйте его рядом с репозиторием и выполните:

```bash
uvx dvc pull          # или: pip install dvc && dvc pull
uvx dvc status        # Data and pipelines are up to date.
```

Набор оценки маленький и не содержит секретов, поэтому `data/eval/*.jsonl`
дополнительно приложены к архиву сдачи как обычные файлы.

## Воспроизведение

```bash
uv sync --frozen
uvx dvc pull
make check-eval        # 24 теста оценки, без модели
make up                # MLflow на http://127.0.0.1:5006 (Docker)
make sweep report candidate
make baseline-init     # только если нет evaluation/baseline.json
make evaluate eval     # eval сейчас завершается отказом гейта — это итог
make check-negative check-storage check-all
```

Windows: команды выполнялись в Git Bash с GNU make; Makefile сам включает
`PYTHONUTF8=1`.
