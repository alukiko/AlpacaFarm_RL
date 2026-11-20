"""Build the report and defense slides for the frozen local-judge experiment."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

import build_artifacts as view


def measured(result: dict) -> str:
    return f"{result['errors']}/{result['n']} · {view.pct(result['error_rate'])}"


def percentage_points(value: float) -> str:
    return f"{100 * value:+.2f}".replace("-", "−").replace(".", ",") + " п.п."


def build_report() -> None:
    for name in ("body", "bullet"):
        view.STYLE[name].fontSize = 10.5
        view.STYLE[name].leading = 16
        view.STYLE[name].spaceAfter = 8
    view.STYLE["small"].fontSize = 8.8
    view.STYLE["small"].leading = 13
    view.STYLE["section"].fontSize = 14
    view.STYLE["section"].leading = 19
    view.STYLE["title"].fontSize = 20.5
    view.STYLE["title"].leading = 27
    view.STYLE["callout"].fontSize = 11
    view.STYLE["callout"].leading = 17
    for name in ("table", "table_head"):
        view.STYLE[name].fontSize = 9.2
        view.STYLE[name].leading = 13

    summary = view.SUMMARY
    local = summary["local_judge"]
    model = local["judge"]
    word = local["word_length_on_same_pairs"]
    char = local["character_length_on_same_pairs"]
    first = local["position_1_on_same_pairs"]
    delta = local["paired_judge_minus_length"]
    agreement = local["human_agreement_subgroups"]
    swapped = local["order_swap"]
    repeated = local["same_order_repeat"]

    report = SimpleDocTemplate(
        str(view.DOCS / "report.pdf"), pagesize=A4,
        leftMargin=50, rightMargin=50, topMargin=52, bottomMargin=52,
        title="К06 — проверка локального судьи на AlpacaFarm",
        author="Команда К06",
    )
    p, bullet = view.p, view.bullet
    story = [
        p("Проверка локального LLM-судьи на AlpacaFarm", "title"),
        p("Команда К06 · исследовательский отчёт · 20 ноября 2026", "small"),
        view.callout(
            f"Локальная Qwen3 4B разошлась с большинством людей в "
            f"{model['errors']} из {model['n']} пар ({view.pct(model['error_rate'])}). "
            f"При перестановке ответов решение сменилось в "
            f"{swapped['changed_choices']} из {swapped['n']} случаев."
        ),
        p("Исследовательский вопрос", "section"),
        p(
            "Насколько локальный содержательный LLM-судья совпадает с человеческим "
            "предпочтением при сравнении двух ответов, превосходит ли он простое "
            "правило длины и где принимает нестабильные решения? Эталон здесь — "
            "большинство аннотаторов, а не доказательство фактической правильности."
        ),
        p("Почему выбран локальный судья", "section"),
        p(
            "В согласованной карточке команда планировала сравнение с опубликованным "
            "alpaca_eval_gpt4. При точном сопоставлении инструкции и обоих полных "
            "ответов найдено лишь 4 надёжные общие пары из 648. Этого недостаточно "
            "для запланированного пилота на 200 парах. Поэтому опубликованному "
            "GPT-4 не приписываются результаты на этом наборе; вместо него на тех "
            "же человеческих парах запущена доступная локальная модель."
        ),
        p("Данные и выборка", "section"),
        bullet("2 596 отдельных человеческих аннотаций объединены в 648 пар по инструкции и полным текстам двух ответов; обратный порядок учитывается."),
        bullet("498 пар имеют ровно четыре голоса и большинство 4:0 или 3:1. 147 ничьих 2:2 и 3 пары с 5–6 голосами исключены из основной метрики."),
        bullet("Для локального судьи взяты первые 200 пригодных пар после сортировки по SHA-256 идентификатору пары, без отбора по результату модели или направлению метки."),
        p("Оценщик и протокол", "section"),
        p(
            "Qwen3 4B Instruct 2507 Q4_K_M через локальный Ollama: один запрос "
            "на пару, инструкция и два ответа, критерии корректности, релевантности "
            "и полезности, JSON-выбор 1 или 2. Температура 0, seed 42, контекст "
            "4096, предел 24 выходных токена, num_gpu=0. Порядок ответа "
            "детерминированно сбалансирован по ID; выбор всегда возвращается к "
            "исходной нумерации пары. Все 200 ответов модели распознаны."
        ),
        PageBreak(),
        p("Основное сравнение на одних и тех же 200 парах", "title"),
        p(
            "Метрика — доля несовпадений с большинством людей. Для каждой доли "
            "указан двусторонний 95% интервал Уилсона; единица наблюдения — пара. "
            "При одинаковой длине слов правило длины воздерживается, и это "
            "считается несовпадением."
        ),
        view.data_table(
            ["Оценщик", "Несовпадения", "95% ДИ Уилсона"],
            [
                ["Локальная Qwen3", measured(model), view.interval(model["error_wilson_95"])],
                ["Длина в словах", measured(word), view.interval(word["error_wilson_95"])],
                ["Длина в символах", measured(char), view.interval(char["error_wilson_95"])],
                ["Всегда ответ 1", measured(first), view.interval(first["error_wilson_95"])],
                ["Случайный выбор", "ожидаемо 50%", "—"],
            ], [165, 170, 160],
        ),
        Spacer(1, 16),
        view.bars([
            ("Qwen3", model["error_rate"], view.pct(model["error_rate"])),
            ("Слова", word["error_rate"], view.pct(word["error_rate"])),
            ("Символы", char["error_rate"], view.pct(char["error_rate"])),
            ("Ответ 1", first["error_rate"], view.pct(first["error_rate"])),
        ]),
        p("Парное сравнение с правилом слов", "section"),
        p(
            f"Разность долей ошибок «Qwen3 минус слова» равна "
            f"{percentage_points(delta['judge_minus_length_error_rate'])} "
            f"(95% парный бутстрэп: "
            f"[{percentage_points(delta['bootstrap_95'][0])}; "
            f"{percentage_points(delta['bootstrap_95'][1])}]; "
            f"{delta['resamples']} повторных выборок, фиксированный seed). "
            "Интервал включает ноль: на этих данных нельзя уверенно утверждать, "
            "что модель лучше правила слов. Правило символов тоже близко к модели."
        ),
        p("Критерий пилота и полный срез", "section"),
        p(
            f"Точечная ошибка модели {view.pct(model['error_rate'])} выше "
            "ориентира карточки проекта — 30%. На всех 498 пригодных парах "
            f"правило слов имеет {measured(summary['main_evaluator'])} "
            "несовпадений; это отдельный полный срез, его нельзя напрямую "
            "сопоставлять с моделью на 200 парах."
        ),
        PageBreak(),
        p("Две проверки слабых мест судьи", "title"),
        p("1 · Согласие людей", "section"),
        p(
            "Гипотеза: при менее однозначном человеческом предпочтении судье "
            "труднее совпасть с большинством. На парном срезе модели ошибка "
            f"составила {measured(agreement['4:0'])} при согласии 4:0 и "
            f"{measured(agreement['3:1'])} при 3:1. Разница описательная: "
            "согласие людей связано со сложностью примера, но не доказывает её причину."
        ),
        view.bars([
            ("Согласие 4:0", agreement["4:0"]["error_rate"], view.pct(agreement["4:0"]["error_rate"])),
            ("Согласие 3:1", agreement["3:1"]["error_rate"], view.pct(agreement["3:1"]["error_rate"])),
        ]),
        p("2 · Порядок предъявления ответов", "section"),
        p(
            "Для первых 50 пар ответы поменяли местами, затем выбор модели "
            "вернули к исходной нумерации. Контроль: те же 50 пар повторно "
            "запустили без изменения порядка и с теми же настройками."
        ),
        view.data_table(
            ["Повтор относительно исходного", "Смена решения", "Доля"],
            [
                ["Обратный порядок", f"{swapped['changed_choices']}/{swapped['n']}", view.pct(swapped["change_rate"])],
                ["Тот же порядок", f"{repeated['changed_choices']}/{repeated['n']}", view.pct(repeated["change_rate"])],
            ], [265, 115, 115],
        ),
        Spacer(1, 12),
        view.bars([
            ("Перестановка", swapped["change_rate"], view.pct(swapped["change_rate"])),
            ("Повтор", repeated["change_rate"], view.pct(repeated["change_rate"])),
        ]),
        p(
            f"Исходная ошибка на этих 50 парах — "
            f"{measured(swapped['original_order_error'])}; "
            f"после перестановки — {measured(swapped['reversed_order_error'])}. "
            "Частые индивидуальные смены почти скрыты итоговой долей ошибок. "
            "Один повтор на одном срезе не характеризует все задачи и модели."
        ),
        p("Дополнительная проверка правила длины", "section"),
        p(
            "Добавление 64 нейтральных слов к исходно проигравшему ответу "
            "сменило выбор правила слов в 83/100 исходно верных пар. Новые "
            "человеческие метки изменённых ответов не собирались, поэтому "
            "это чувствительность эвристики, а не измеренная ошибка качества."
        ),
        PageBreak(),
        p("Выводы и воспроизводимость", "title"),
        p("Что следует из результатов", "section"),
        bullet("Локальный содержательный судья ошибся в 35,50% из 200 пар. Преимущество перед правилом слов на этих парах не подтверждено парным интервалом."),
        bullet("При согласии людей 3:1 доля несовпадений выше, чем при 4:0. На 50 проверенных парах перестановка ответов меняла решение в 48%, а повтор исходного порядка — в 0%."),
        bullet("Следующий эксперимент: заранее зафиксировать более широкий срез, усреднять два порядка или добавить независимую шкалу содержательной оценки и проверить её на тех же парах."),
        p("Ограничения", "section"),
        p(
            "Человеческое большинство — прокси предпочтений, не эталон "
            "фактической истины, безопасности или пользы. Одна локальная модель "
            "и 200 выбранных пар не представляют все генераторы и задачи. "
            "Общие инструкции и аннотаторы могут нарушать независимость пар, "
            "которую предполагают интервалы Уилсона и бутстрэп. Для проверки "
            "порядка использованы первые 50 пар и по одному запуску каждого "
            "варианта. Опубликованный GPT-4 не оценён на основном срезе."
        ),
        p("Как воспроизвести", "section"),
        p(
            "Исходные JSON, хеши SHA-256, код, построчные решения модели и CSV "
            "хранятся в репозитории. Из его корня: "
            "<font name='DejaVu-Bold'>python scripts/run_analysis.py</font>, затем "
            "<font name='DejaVu-Bold'>python scripts/check_submission.py</font>. "
            "Контрольный анализ использует замороженные решения и не вызывает "
            "Ollama или сетевые сервисы; ограничение менее 10 минут проверяется "
            "автоматически. Исходный сбор 200 решений занял 607 секунд "
            "CPU-инференса и проходит отдельно от контроля. Для новой "
            "генерации решений нужен локальный Ollama "
            "и <font name='DejaVu-Bold'>scripts/run_local_judge.py</font>. "
            "Наблюдавшийся рабочий набор модели — около 5,24 ГБ, GPU и платные "
            "API не использовались."
        ),
        p("Источники", "section"),
        p("1. Tatsu Lab. AlpacaEval, код и документация: https://github.com/tatsu-lab/alpaca_eval", "small"),
        p("2. Tatsu Lab. Данные human cross-annotations и alpaca_eval_gpt4: https://huggingface.co/datasets/tatsu-lab/alpaca_eval", "small"),
        p("3. Команда К06. Карточка проекта, данные, код и результаты: https://github.com/alukiko/AlpacaFarm_RL", "small"),
    ]
    report.build(story, onFirstPage=view.report_footer, onLaterPages=view.report_footer)


def build_slides() -> None:
    summary = view.SUMMARY
    local = summary["local_judge"]
    model = local["judge"]
    word = local["word_length_on_same_pairs"]
    char = local["character_length_on_same_pairs"]
    first = local["position_1_on_same_pairs"]
    agreement = local["human_agreement_subgroups"]
    swapped = local["order_swap"]
    repeated = local["same_order_repeat"]
    light = colors.HexColor("#D7E5EE")
    aqua = colors.HexColor("#82D8D6")
    pdf = canvas.Canvas(str(view.DOCS / "defense.pdf"), pagesize=(960, 540))
    pdf.setTitle("К06 — защита исследования локального судьи")
    pdf.setAuthor("Команда К06")

    view.slide_base(pdf, 1, "Исследовательский проект", "Можно ли доверять локальному LLM-судье?")
    view.slide_text(pdf, "Проверка на человеческих предпочтениях AlpacaFarm", 58, 366, 830, 21, color=light)
    view.slide_text(pdf, view.pct(model["error_rate"]), 58, 273, 540, 62, color=aqua, bold=True)
    view.slide_text(pdf, "несовпадений с большинством людей · 200 пар", 60, 174, 820, 21, color=view.WHITE)
    pdf.showPage()

    view.slide_base(pdf, 2, "Данные", "Почему мы запустили своего судью")
    view.panel(pdf, 56, 202, 260, 197, "2 596", "человеческих аннотаций по парам ответов")
    view.panel(pdf, 350, 202, 260, 197, "498", "пар с большинством 4:0 или 3:1")
    view.panel(pdf, 644, 202, 260, 197, "200", "одинаковых пар для модели и базовых методов")
    view.slide_text(pdf, "Опубликованный GPT-4: только 4 надёжные общие пары после точного сопоставления.",
                    58, 150, 840, 16, color=light)
    pdf.showPage()

    view.slide_base(pdf, 3, "Метод", "Локальная Qwen3 4B на CPU")
    view.panel(pdf, 56, 205, 260, 191, "Вход", "Инструкция и два полных ответа; порядок сбалансирован по ID")
    view.panel(pdf, 350, 205, 260, 191, "Выход", "JSON: выбрать 1 или 2; температура 0; seed 42")
    view.panel(pdf, 644, 205, 260, 191, "Эталон", "Большинство четырёх людей, если есть результат 4:0 или 3:1")
    view.slide_text(pdf, "Все 200 решений распознаны; num_gpu=0; замороженные JSONL дают короткий контрольный прогон.",
                    58, 155, 840, 15.5, color=light)
    pdf.showPage()

    view.slide_base(pdf, 4, "Основной результат", "Модель и простые правила на одних 200 парах")
    view.slide_bar(pdf, 325, "Qwen3", model["error_rate"], measured(model), view.ORANGE)
    view.slide_bar(pdf, 270, "Длина в словах", word["error_rate"], measured(word))
    view.slide_bar(pdf, 215, "Длина в символах", char["error_rate"], measured(char))
    view.slide_bar(pdf, 160, "Всегда ответ 1", first["error_rate"], measured(first))
    view.slide_text(pdf, "Qwen3 − слова: −5 п.п.; парный 95% бутстрэп [−14; +4,5] п.п. — ноль внутри.",
                    58, 110, 840, 15, color=light)
    pdf.showPage()

    view.slide_base(pdf, 5, "Слабое место 1", "Меньше согласия людей — больше расхождений")
    view.panel(pdf, 56, 182, 410, 220, "Люди 4:0", f"Модель ошиблась в {measured(agreement['4:0'])} случаев")
    view.panel(pdf, 494, 182, 410, 220, "Люди 3:1", f"Модель ошиблась в {measured(agreement['3:1'])} случаев", view.ORANGE)
    view.slide_text(pdf, "Это описательный срез: согласие людей не измеряет причину ошибки модели.",
                    58, 134, 840, 16, color=light)
    pdf.showPage()

    view.slide_base(pdf, 6, "Слабое место 2", "Порядок ответов меняет выбор модели")
    view.panel(pdf, 56, 174, 410, 224, "Переставили ответы", f"Решение сменилось в {swapped['changed_choices']}/{swapped['n']} пар — {view.pct(swapped['change_rate'])}", view.ORANGE)
    view.panel(pdf, 494, 174, 410, 224, "Повторили тот же порядок", f"Решение сменилось в {repeated['changed_choices']}/{repeated['n']} пар — {view.pct(repeated['change_rate'])}")
    view.slide_text(pdf, "Ошибка на этих 50 парах: 12/50 до перестановки и 16/50 после неё.",
                    58, 130, 840, 16, color=light)
    pdf.showPage()

    view.slide_base(pdf, 7, "Вывод", "Нужно проверять содержательность и устойчивость")
    view.panel(pdf, 56, 180, 410, 217, "Что установлено", "35,5% ошибок; преимущество над правилом слов не подтверждено парным интервалом")
    view.panel(pdf, 494, 180, 410, 217, "Что сделать дальше", "Проверить более широкий срез и оба порядка ответа; улучшить критерии оценки")
    view.slide_text(pdf, "Код, исходные данные, замороженные решения, CSV и отчёт — в GitHub команды К06.",
                    58, 132, 840, 15, color=light)
    pdf.showPage()
    pdf.save()
