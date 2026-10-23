"""Реализуйте две функции. Контракт и примеры: EVALUATION.md и tests/test_eval.py."""
import json
import math

FIELDS = ('n', 'correct', 'valid', 'errors', 'accuracy', 'format_rate')
SHA_KEYS = ('protocol_sha256', 'golden_sha256', 'baseline_spec_sha256')


def _reject_constant(name):
    raise ValueError(f'Нестрогий JSON: {name}')


def parse_answer(raw, choices):
    """Строгий разбор: JSON-объект ровно с одним полем answer из choices, иначе None."""
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw, parse_constant=_reject_constant)
    except ValueError:
        return None
    if not isinstance(value, dict) or set(value) != {'answer'}:
        return None
    answer = value['answer']
    return answer if isinstance(answer, str) and answer in choices else None


def _summary(items):
    n = len(items)
    correct = sum(item['correct'] for item in items)
    valid = sum(item['valid'] for item in items)
    errors = sum(item['error'] is not None for item in items)
    return dict(n=n, correct=correct, valid=valid, errors=errors,
                accuracy=correct / n, format_rate=valid / n)


def score(rows, outputs):
    """Верните overall, slices и per_item. Не удаляйте плохие ответы из знаменателя.

    Строгий ответ: JSON с единственным строковым полем answer из choices.
    outputs: [{id, raw, error, latency_seconds}, ...].
    В overall и каждом срезе: n, correct, valid, errors, accuracy, format_rate.
    В per_item: id, raw, parsed, valid, correct, error, slices.
    Несовпадающие/дублирующиеся id и пустой набор должны вызвать ValueError.
    """
    if not rows:
        raise ValueError('Пустой набор для оценки')
    row_ids = [row['id'] for row in rows]
    out_ids = [out['id'] for out in outputs]
    if len(set(row_ids)) != len(row_ids):
        raise ValueError('Дубли id в наборе')
    if len(set(out_ids)) != len(out_ids):
        raise ValueError('Дубли id в ответах')
    if set(row_ids) != set(out_ids):
        raise ValueError('id ответов не совпадают с id набора')
    by_id = {out['id']: out for out in outputs}
    per_item = []
    for row in rows:
        out = by_id[row['id']]
        error = out.get('error')
        raw = out.get('raw')
        # Ошибка генерации — нулевой результат, но строка остаётся в знаменателе.
        parsed = None if error is not None else parse_answer(raw, row['choices'])
        valid = parsed is not None
        per_item.append(dict(id=row['id'], raw=raw, parsed=parsed, valid=valid,
                             correct=valid and parsed == row['expected'],
                             error=None if error is None else str(error), slices=list(row['slices'])))
    names = sorted({s for item in per_item for s in item['slices']})
    slices = {name: _summary([item for item in per_item if name in item['slices']]) for name in names}
    return dict(overall=_summary(per_item), slices=slices, per_item=per_item)


def _count(value, what):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{what}: ожидается неотрицательное целое')
    return value


def _check_metrics(m, what):
    """Метрики конечны, counts согласованы, доли соответствуют counts."""
    if not isinstance(m, dict) or any(k not in m for k in FIELDS):
        raise ValueError(f'{what}: нет метрик {FIELDS}')
    n = _count(m['n'], f'{what}.n')
    if n == 0:
        raise ValueError(f'{what}: пустой набор')
    correct, valid, errors = (_count(m[k], f'{what}.{k}') for k in ('correct', 'valid', 'errors'))
    if not correct <= valid <= n or errors > n or valid + errors > n:
        raise ValueError(f'{what}: counts несовместимы')
    for key, count in (('accuracy', correct), ('format_rate', valid)):
        value = m[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{what}.{key}: missing/NaN/inf')
        if not math.isclose(value, count / n, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f'{what}.{key} не соответствует counts')
    return m


def _check_report(report, what, min_n, min_slices):
    """Полный отчёт: метрики overall/срезов согласованы с per_item."""
    if not isinstance(report, dict) or report.get('status') != 'complete':
        raise ValueError(f'{what}: отчёт неполный')
    if not isinstance(report.get('model'), dict) or not report['model']:
        raise ValueError(f'{what}: не указана модель')
    overall = _check_metrics(report.get('overall'), f'{what}.overall')
    if overall['n'] < min_n:
        raise ValueError(f'{what}: в наборе {overall["n"]} < {min_n} примеров')
    items = report.get('per_item')
    if not isinstance(items, list) or len(items) != overall['n']:
        raise ValueError(f'{what}: per_item не соответствует n')
    ids = [item['id'] for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f'{what}: дубли id в per_item')
    if _recount(items) != {k: overall[k] for k in ('n', 'correct', 'valid', 'errors')}:
        raise ValueError(f'{what}.overall не соответствует per_item')
    slices = report.get('slices')
    if not isinstance(slices, dict) or len(slices) < min_slices:
        raise ValueError(f'{what}: нужно минимум {min_slices} среза')
    if set(slices) != {s for item in items for s in item['slices']}:
        raise ValueError(f'{what}: имена срезов не соответствуют per_item')
    for name, m in slices.items():
        _check_metrics(m, f'{what}.slices.{name}')
        members = [item for item in items if name in item['slices']]
        if _recount(members) != {k: m[k] for k in ('n', 'correct', 'valid', 'errors')}:
            raise ValueError(f'{what}.slices.{name} не соответствует per_item')
    return report


def _recount(items):
    for item in items:
        if not isinstance(item['valid'], bool) or not isinstance(item['correct'], bool):
            raise ValueError('per_item: valid/correct должны быть bool')
        if item['correct'] and not item['valid']:
            raise ValueError('per_item: correct без valid')
    return dict(n=len(items), correct=sum(i['correct'] for i in items), valid=sum(i['valid'] for i in items),
                errors=sum(i['error'] is not None for i in items))


def quality_gate(baseline, candidate, critical_slices):
    """Верните {passed: True, ...} или вызовите ValueError с причиной отказа.

    Проверьте совместимость протокола/набора/baseline, метрики и counts,
    все id и срезы, общую accuracy/format_rate, критические срезы и behavior.
    Missing, NaN, пустой набор и ошибки генерации означают отказ.
    Пороги задаются до измерения; учебный допуск регрессии равен нулю.
    """
    try:
        return _gate(baseline, candidate, critical_slices)
    except (KeyError, TypeError, AttributeError) as exc:
        # Отсутствующее поле или неверный тип — тоже отказ, а не падение обвязки.
        raise ValueError(f'Некорректный отчёт: {type(exc).__name__}: {exc}') from exc


def _gate(baseline, candidate, critical_slices):
    # 1. Совместимость: один протокол, один golden, один baseline.
    for key in SHA_KEYS:
        values = [r.get(key) for r in (baseline, candidate)]
        if any(not isinstance(v, str) or not v for v in values) or values[0] != values[1]:
            raise ValueError(f'Несовместимые отчёты: {key}')
    # 2. Полнота и согласованность метрик, одинаковые id, срезы и размеры групп.
    base = _check_report(baseline, 'baseline', 50, 3)
    cand = _check_report(candidate, 'candidate', 50, 3)
    if [i['id'] for i in base['per_item']] != [i['id'] for i in cand['per_item']]:
        raise ValueError('id в отчётах baseline и candidate различаются')
    if {k: v['n'] for k, v in base['slices'].items()} != {k: v['n'] for k, v in cand['slices'].items()}:
        raise ValueError('Срезы или размеры групп различаются')
    if not isinstance(critical_slices, (list, tuple)) or not critical_slices:
        raise ValueError('Не заданы критические срезы')
    missing = [s for s in critical_slices if s not in base['slices']]
    if missing:
        raise ValueError(f'Критический срез отсутствует: {missing}')
    # 3. Ошибки генерации и регрессии; допуск ухудшения равен нулю, сравнение по counts.
    for role, report in (('baseline', base), ('candidate', cand)):
        if report['overall']['errors']:
            raise ValueError(f'{role}: ошибки генерации ({report["overall"]["errors"]})')
    b, c = base['overall'], cand['overall']
    if c['correct'] < b['correct']:
        raise ValueError(f'Регрессия accuracy: {c["accuracy"]:.4f} < {b["accuracy"]:.4f}')
    if c['valid'] < b['valid']:
        raise ValueError(f'Регрессия format_rate: {c["format_rate"]:.4f} < {b["format_rate"]:.4f}')
    slices = {}
    for name in critical_slices:
        bs, cs = base['slices'][name], cand['slices'][name]
        if cs['correct'] < bs['correct']:
            raise ValueError(f'Регрессия критического среза {name}: {cs["accuracy"]:.4f} < {bs["accuracy"]:.4f}')
        slices[name] = dict(n=bs['n'], baseline=bs['accuracy'], candidate=cs['accuracy'])
    # 4. Все обязательные behavioral-кейсы кандидата проходят, их минимум три.
    behavior = cand.get('behavioral')
    if not isinstance(behavior, dict):
        raise ValueError('Нет behavioral-отчёта кандидата')
    bo = _check_metrics(behavior.get('overall'), 'behavioral.overall')
    if bo['n'] < 3:
        raise ValueError('Behavioral: минимум три кейса')
    if isinstance(behavior.get('per_item'), list) and _recount(behavior['per_item']) != {
            k: bo[k] for k in ('n', 'correct', 'valid', 'errors')}:
        raise ValueError('Behavioral overall не соответствует per_item')
    if bo['errors'] or bo['correct'] != bo['n']:
        failed = [i['id'] for i in behavior.get('per_item', []) if not i['correct']]
        raise ValueError(f'Behavioral не пройден: {bo["correct"]}/{bo["n"]} {failed}')
    return dict(passed=True, critical_slices=list(critical_slices),
                baseline=dict(model=base['model'], accuracy=b['accuracy'], format_rate=b['format_rate'], n=b['n']),
                candidate=dict(model=cand['model'], accuracy=c['accuracy'], format_rate=c['format_rate'], n=c['n']),
                delta=dict(accuracy=c['accuracy'] - b['accuracy'], format_rate=c['format_rate'] - b['format_rate']),
                critical=slices, behavioral=dict(n=bo['n'], correct=bo['correct']),
                **{key: cand[key] for key in SHA_KEYS})
