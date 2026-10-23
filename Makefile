# Windows: Python по умолчанию читает файлы в cp1251; весь проект в UTF-8.
export PYTHONUTF8 = 1
export PYTHONIOENCODING = utf-8

.PHONY: install up down sweep promote predict check check-storage
install:
	uv sync --frozen
up:
	docker compose -p mlops-hw6 up --build -d --wait
down:
	docker compose -p mlops-hw6 down
sweep:
	uv run python -m src.sweep
promote:
	uv run python -m evaluation.cli promote
predict:
	uv run python -m src.predict --uri models:/my-qwen-adapter@champion --prompt "по моему опыту лучший способ найти первых клиентов писать в личку по 30 сообщений в день работает железно"
check:
	bash tests/check.sh
check-storage:
	uv run python tests/check_storage.py

index:
	uv run python -m scripts.make_training_index
eval-sets:
	uv run python scripts/build_eval_sets.py

.PHONY: index eval-sets report candidate baseline-init evaluate eval check-eval check-negative check-all baseline-update predict-candidate
report:
	uv run python -m src.report
candidate:
	uv run python -m evaluation.cli candidate
baseline-init:
	uv run python -m evaluation.cli baseline-init
evaluate:
	uv run python -m evaluation.cli evaluate
eval:
	uv run python -m evaluation.cli gate
check-eval:
	uv run python -m unittest discover -s tests -p 'test_*.py' -v
check-negative:
	uv run python -m evaluation.cli negative
check-all: check check-eval
baseline-update:
	uv run python -m evaluation.cli baseline-update
predict-candidate:
	uv run python -m src.predict --uri models:/my-qwen-adapter@candidate --prompt "Выберите правильный вариант."
