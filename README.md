# AlpacaFarm_RL

TEAM_ID = 'К06'
DIRECTION = 'AlpacaFarm_RL'
DATASET = 'AlpacaFarm: человеческие и судейские аннотации'
CONFIG_AND_SLICE = 'перекрёстные аннотации людей'
LICENSE = 'CC BY-NC 4.0 (некоммерческое)'

RESEARCH_QUESTION = '[оценщик] на [срезе] ошибается относительно [эталона] в каких случаях?'
REFERENCE_OR_PROXY = '[эталонный исход или прокси; что он не покрывает]'
EVALUATOR = '[какой метод или метрика сейчас оценивает ответы]'
BASELINE = '[с чем сравним оценщик]'
ERROR_METRIC = '[что считаем; числитель и знаменатель]'
NUMERIC_CRITERION = '[порог и почему он содержателен; или: обсудить с куратором]'
ERROR_RISK = '[как оценщик может получить высокий балл ошибочно]'
SCOPE = '[что не входит в работу]'
NEXT_STEP = '[ближайшее действие по проекту]'
OWNER_AND_DUE = '[ответственный и срок]'
OPEN_QUESTION = '[что пока неясно и нужно спросить у команды/куратора]'

fields = {
    'TEAM_ID': TEAM_ID, 'DIRECTION': DIRECTION, 'DATASET': DATASET,
    'CONFIG_AND_SLICE': CONFIG_AND_SLICE, 'LICENSE': LICENSE,
    'RESEARCH_QUESTION': RESEARCH_QUESTION,
    'REFERENCE_OR_PROXY': REFERENCE_OR_PROXY,
    'EVALUATOR': EVALUATOR, 'BASELINE': BASELINE,
    'ERROR_METRIC': ERROR_METRIC, 'NUMERIC_CRITERION': NUMERIC_CRITERION,
    'ERROR_RISK': ERROR_RISK, 'SCOPE': SCOPE,
    'NEXT_STEP': NEXT_STEP, 'OWNER_AND_DUE': OWNER_AND_DUE,
    'OPEN_QUESTION': OPEN_QUESTION,
}
missing = [name for name, value in fields.items()
           if not value or value.startswith('[')]
if missing:
    print('Проверьте поля:', ', '.join(missing))
else:
    print('Все поля заполнены. Перенесите карточку в README команды.')

card = f"""# Карточка проекта {TEAM_ID} · {DIRECTION}

## Исследовательский вопрос
{RESEARCH_QUESTION}

## Данные и срез
{DATASET}; {CONFIG_AND_SLICE}; лицензия: {LICENSE}

## Эталон и метод
Эталонный исход или прокси: {REFERENCE_OR_PROXY}
Оцениваемый оценщик: {EVALUATOR}
Базовое сравнение: {BASELINE}

## Метрика и критерий
Метрика ошибки: {ERROR_METRIC}
Численный критерий успеха: {NUMERIC_CRITERION}

## Риск и границы
Возможная ошибка оценщика: {ERROR_RISK}
За границами проекта: {SCOPE}

## Следующий шаг
{NEXT_STEP}; ответственный и срок: {OWNER_AND_DUE}

## Что нужно уточнить
{OPEN_QUESTION}
"""
print(card)
