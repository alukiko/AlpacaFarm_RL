"""Shared PDF drawing helpers and the command to build current deliverables.

Run after `python scripts/run_analysis.py`. Requires reportlab; the analysis
itself has no third-party Python dependencies. Length-only builders are kept
for the earlier exploratory study; the command builds the local-judge report.
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SUMMARY = json.loads((ROOT / "results/summary.json").read_text(encoding="utf-8"))

NAVY = colors.HexColor("#13233A")
INK = colors.HexColor("#213149")
MUTED = colors.HexColor("#52647C")
TEAL = colors.HexColor("#087F8C")
PALE = colors.HexColor("#E9F4F4")
GRAY = colors.HexColor("#F3F5F8")
ORANGE = colors.HexColor("#D97835")
WHITE = colors.white


def register_fonts() -> None:
    candidates = [
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/ttf-dejavu"),
    ]
    for folder in candidates:
        regular = folder / "DejaVuSans.ttf"
        bold = folder / "DejaVuSans-Bold.ttf"
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont("DejaVu", str(regular)))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold)))
            pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold")
            return
    raise FileNotFoundError("Install DejaVu Sans to rebuild the PDFs")


def pct(value: float) -> str:
    return f"{100 * value:.2f}%".replace(".", ",")


def interval(values: list[float]) -> str:
    return f"{pct(values[0])}–{pct(values[1])}"


STYLE = {
    "title": ParagraphStyle(
        "title", fontName="DejaVu-Bold", fontSize=18, leading=24,
        textColor=NAVY, spaceAfter=10,
    ),
    "section": ParagraphStyle(
        "section", fontName="DejaVu-Bold", fontSize=12.5, leading=17,
        textColor=TEAL, spaceBefore=12, spaceAfter=6,
    ),
    "body": ParagraphStyle(
        "body", fontName="DejaVu", fontSize=9.1, leading=14,
        textColor=INK, spaceAfter=7,
    ),
    "small": ParagraphStyle(
        "small", fontName="DejaVu", fontSize=8, leading=12,
        textColor=MUTED, spaceAfter=5,
    ),
    "bullet": ParagraphStyle(
        "bullet", fontName="DejaVu", fontSize=9.1, leading=14,
        textColor=INK, leftIndent=14, firstLineIndent=-10, spaceAfter=6,
    ),
    "callout": ParagraphStyle(
        "callout", fontName="DejaVu-Bold", fontSize=10.2, leading=16,
        textColor=NAVY,
    ),
    "table_head": ParagraphStyle(
        "table_head", fontName="DejaVu-Bold", fontSize=8.2, leading=11,
        textColor=WHITE,
    ),
    "table": ParagraphStyle(
        "table", fontName="DejaVu", fontSize=8.2, leading=11,
        textColor=INK,
    ),
}


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLE[style])


def bullet(text: str) -> Paragraph:
    return p("•  " + text, "bullet")


def callout(text: str) -> Table:
    table = Table([[p(text, "callout")]], colWidths=[495])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B8D8D9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return table


def data_table(headers: list[str], rows: list[list[str]], widths: list[int]) -> Table:
    cells = [[p(value, "table_head") for value in headers]]
    cells += [[p(str(value), "table") for value in row] for row in rows]
    table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GRAY]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#CCD5DE")),
    ]))
    return table


def bars(items: list[tuple[str, float, str]], width: int = 495) -> Drawing:
    height = 29 * len(items) + 9
    drawing = Drawing(width, height)
    for index, (label, rate, display) in enumerate(items):
        y = height - 25 - index * 29
        drawing.add(String(0, y + 4, label, fontName="DejaVu", fontSize=8.6, fillColor=INK))
        drawing.add(Rect(185, y, 230, 12, fillColor=GRAY, strokeColor=None))
        drawing.add(Rect(185, y, 230 * rate / 0.60, 12, fillColor=TEAL, strokeColor=None))
        drawing.add(String(425, y + 3, display, fontName="DejaVu-Bold", fontSize=8.8, fillColor=NAVY))
    return drawing


def report_footer(pdf: canvas.Canvas, doc: SimpleDocTemplate) -> None:
    pdf.saveState()
    width, _ = A4
    pdf.setStrokeColor(colors.HexColor("#D8E0E8"))
    pdf.line(48, 38, width - 48, 38)
    pdf.setFont("DejaVu", 7.5)
    pdf.setFillColor(MUTED)
    pdf.drawString(48, 25, "К06 · AlpacaFarm · 20.11.2026")
    pdf.drawRightString(width - 48, 25, str(doc.page))
    pdf.restoreState()


def build_length_report() -> None:
    main = SUMMARY["main_evaluator"]
    char = SUMMARY["character_length_comparator"]
    base = SUMMARY["constant_position_1_baseline"]
    overlap = SUMMARY["overlap_audit"]
    report = SimpleDocTemplate(
        str(DOCS / "report.pdf"), pagesize=A4,
        leftMargin=50, rightMargin=50, topMargin=46, bottomMargin=52,
        title="К06 — аудит оценщика предпочтений на AlpacaFarm",
        author="Команда К06",
    )
    story = []

    # 1. Question, dataset, and decision to use the approved fallback.
    story += [
        p("Аудит оценщика предпочтений на AlpacaFarm", "title"),
        p("К06 · отчёт о пилотном исследовании · 20 ноября 2026", "small"),
        callout(
            f"Правило «выбери более длинный ответ» не совпало с большинством "
            f"людей в {main['errors']} из {main['n']} пар: {pct(main['error_rate'])} "
            f"(95% ДИ {interval(main['error_wilson_95'])})."
        ),
        p("Исследовательский вопрос", "section"),
        p(
            "Насколько надёжно простое автоматическое правило выбора более длинного "
            "по числу слов ответа воспроизводит большинство человеческих предпочтений "
            "в AlpacaFarm и в каких условиях оно даёт сбой? Это резервный вариант "
            "согласованной карточки проекта: опубликованного GPT-4-судью нельзя "
            "корректно оценить без совпадающих пар ответов."
        ),
        p("Данные", "section"),
        data_table(
            ["Единица данных", "Число", "Роль в анализе"],
            [
                ["Аннотации людей", "2 596", "Исходные записи"],
                ["Уникальные пары", "648", "Группировка по инструкции и двум ответам"],
                ["4:0 / 3:1", "201 / 297", "498 пар с большинством — основная выборка"],
                ["2:2", "147", "Разногласия без большинства"],
                ["5–6 голосов", "3", "Исключены из основной метрики"],
            ], [176, 57, 262],
        ),
        p("Проверка опубликованного судьи", "section"),
        p(
            f"Сопоставление по полной инструкции и двум полным ответам, включая "
            f"перестановку A/B, обнаружило {overlap['exact_match_pairs']} точных пары. "
            f"Ещё {overlap['whitespace_only_match_pairs']} пара совпала только после "
            f"нормализации пробелов, но была неоднозначной. Надёжно сопоставлены "
            f"{overlap['reliable_unique_pairs']} пары — меньше минимума 200. "
            "Поэтому точность GPT-4 здесь не заявляется."
        ),
        PageBreak(),
    ]

    # 2. Reproducible method and primary comparison.
    story += [
        p("Метод и основной результат", "title"),
        bullet("Четыре оценки одной пары объединены по инструкции и полным текстам ответов. При обратном порядке ответы и голоса переориентируются."),
        bullet("Эталон — большинство 4:0 или 3:1. Это прокси предпочтений, а не доказательство фактической верности."),
        bullet("Основной оценщик выбирает ответ с большим числом слов, разделённых пробельными символами. Равенство длин — воздержание и несовпадение."),
        bullet("Базовые сравнения: всегда первый ответ, выбор по числу символов; для случайного выбора ожидаемая ошибка 50%. Все методы оценены на одинаковых 498 парах."),
        bullet("Для каждой доли ошибок показан двусторонний 95% интервал Уилсона; единица наблюдения — пара ответов."),
        p("Доля несовпадений с большинством людей", "section"),
        data_table(
            ["Оценщик", "Ошибка", "95% ДИ Уилсона"],
            [
                ["Слова (основной)", f"{main['errors']}/{main['n']} · {pct(main['error_rate'])}", interval(main["error_wilson_95"])],
                ["Символы", f"{char['errors']}/{char['n']} · {pct(char['error_rate'])}", interval(char["error_wilson_95"])],
                ["Всегда ответ 1", f"{base['errors']}/{base['n']} · {pct(base['error_rate'])}", interval(base["error_wilson_95"])],
                ["Случайный выбор", "ожидаемо 50%", "—"],
            ], [175, 170, 150],
        ),
        Spacer(1, 16),
        bars([
            ("Слова", main["error_rate"], pct(main["error_rate"])),
            ("Символы", char["error_rate"], pct(char["error_rate"])),
            ("Ответ 1", base["error_rate"], pct(base["error_rate"])),
        ]),
        p(
            "Правило слов немного лучше выбора первой позиции, но хуже близкого "
            "по сложности правила символов. Согласованный пилотный порог не более "
            "30% несовпадений не достигнут. Интервалы относятся к долям внутри "
            "данного среза, а не исправляют возможную нерепрезентативность AlpacaFarm."
        ),
        PageBreak(),
    ]

    # 3. Two explicit weakness checks.
    agreement = SUMMARY["human_agreement_subgroups"]
    small = SUMMARY["word_gap_at_most_30"]
    large = SUMMARY["word_gap_over_30"]
    padding = SUMMARY["padding_probe"]
    story += [
        p("Проверки слабых мест", "title"),
        p("Проверка 1 · человеческое согласие и разница длин", "section"),
        p(
            "Гипотеза: простая эвристика хуже работает там, где длина ответов "
            "близка, а человеческие предпочтения менее однозначны. Процедура: "
            "сравнить ошибки на группах 4:0 против 3:1 и при разнице не более "
            "30 слов против разницы свыше 30 слов. Порог 30 — описательный "
            "срез, выбранный для анализа, а не заранее подтверждённый критерий."
        ),
        bars([
            ("Согласие 4:0", agreement["4:0"]["error_rate"], pct(agreement["4:0"]["error_rate"])),
            ("Согласие 3:1", agreement["3:1"]["error_rate"], pct(agreement["3:1"]["error_rate"])),
            ("Разница ≤30 слов", small["error_rate"], pct(small["error_rate"])),
            ("Разница >30 слов", large["error_rate"], pct(large["error_rate"])),
        ]),
        p(
            f"На 4:0 — {agreement['4:0']['errors']}/{agreement['4:0']['n']} ошибок; "
            f"на 3:1 — {agreement['3:1']['errors']}/{agreement['3:1']['n']}. "
            f"При разнице ≤30 слов — {small['errors']}/{small['n']}; "
            f"при большей — {large['errors']}/{large['n']}. "
            "Это ассоциации: сложность ответа, его качество и длина могут быть связаны."
        ),
        p("Проверка 2 · дописывание нейтрального текста", "section"),
        p(
            "Гипотеза: можно изменить решение оценщика, увеличив объём исходно "
            "проигравшего ответа без целевой работы над его содержанием. Взяты "
            "первые 100 изначально правильно оценённых пар по SHA-256 ID; "
            "к проигравшему ответу добавлено 64 слова «additional context». "
            f"Решение сменилось относительно исходной человеческой метки "
            f"в {padding['flips_relative_to_original_labels']}/{padding['n']} случаях "
            f"({pct(padding['flip_rate'])}; 95% ДИ {interval(padding['flip_wilson_95'])}). "
            "Медиана минимального числа слов для смены решения — "
            f"{str(padding['median_minimum_words_to_reverse']).replace('.', ',')}."
        ),
        callout(
            "Новые человеческие оценки изменённых ответов не собирались. "
            "Следовательно, 83% — частота смены решения относительно старой метки, "
            "а не подтверждённая ошибка качества на новых ответах."
        ),
        PageBreak(),
    ]

    # 4. Interpretation, limitations, sources and reproducibility.
    story += [
        p("Выводы и воспроизводимость", "title"),
        p("Интерпретация", "section"),
        bullet("Доля ошибок правила слов 42,97% (95% ДИ 38,69–47,36%); пилотный порог 30% не достигнут."),
        bullet("Близость длин — выраженный слабый срез: ошибка 50,00% при разнице до 30 слов. На таких парах правило практически не даёт полезного сигнала относительно случайного выбора."),
        bullet("Дописанный нейтральный текст часто меняет решение правила. Эта проверка показывает уязвимость прокси-метрики к увеличению объёма, но требует новой человеческой разметки для вывода о фактическом ухудшении качества."),
        p("Ограничения и возможное улучшение", "section"),
        p(
            "Большинство людей не является универсальным эталоном истинности; "
            "четыре аннотатора могут систематически ошибаться вместе. В выборке "
            "нет независимой проверки фактов, безопасности или полезности ответов. "
            "Срезы по длине выбраны для исследования, а не причинного вывода. "
            "Интервалы Уилсона считают пары независимыми; общие инструкции "
            "и аннотаторы могут сделать интервалы слишком узкими. "
            "Для следующего шага нужно повторно разметить изменённые ответы и "
            "сопоставить содержательный судейский метод с теми же самыми парами. "
            "Если модель недоступна на CPU в заданном бюджете, следует "
            "использовать явную ручную шкалу качества на небольшом ядре."
        ),
        p("Воспроизводимость", "section"),
        p(
            "Исходные JSON, их SHA-256, код, результаты по каждой паре и тест "
            "дописывания сохранены в репозитории. Команда запуска: "
            "<font name='DejaVu-Bold'>python scripts/run_analysis.py</font>. "
            "Тесты: <font name='DejaVu-Bold'>python -m unittest discover -s tests -v</font>. "
            "Проверка комплекта: <font name='DejaVu-Bold'>python scripts/check_submission.py</font>. "
            "Контрольный прогон на CPU занимает около секунды; платные API, "
            "обучение моделей и GPU не используются."
        ),
        p("Источники", "section"),
        p("1. Tatsu Lab. AlpacaEval: официальный код и описание аннотаций. https://github.com/tatsu-lab/alpaca_eval", "small"),
        p("2. Tatsu Lab. AlpacaEval dataset, human cross-annotations и alpaca_eval_gpt4. https://huggingface.co/datasets/tatsu-lab/alpaca_eval", "small"),
        p("3. Согласованная карточка проекта К06 и данные эксперимента: репозиторий alukiko/AlpacaFarm_RL.", "small"),
    ]
    report.build(story, onFirstPage=report_footer, onLaterPages=report_footer)


def slide_text(pdf: canvas.Canvas, text: str, x: float, y_top: float,
               width: float, font_size: float = 21, leading: float | None = None,
               color: colors.Color = WHITE, bold: bool = False) -> float:
    style = ParagraphStyle(
        "slide", fontName="DejaVu-Bold" if bold else "DejaVu",
        fontSize=font_size, leading=leading or font_size * 1.35,
        textColor=color, alignment=TA_LEFT,
    )
    item = Paragraph(text, style)
    _, height = item.wrap(width, 500)
    item.drawOn(pdf, x, y_top - height)
    return height


def slide_base(pdf: canvas.Canvas, number: int, eyebrow: str, title: str) -> None:
    pdf.setFillColor(NAVY)
    pdf.rect(0, 0, 960, 540, fill=1, stroke=0)
    pdf.setFillColor(TEAL)
    pdf.rect(0, 0, 12, 540, fill=1, stroke=0)
    slide_text(pdf, eyebrow.upper(), 54, 500, 800, 11, color=colors.HexColor("#82D8D6"), bold=True)
    slide_text(pdf, title, 54, 462, 850, 27, color=WHITE, bold=True)
    pdf.setFillColor(colors.HexColor("#496078"))
    pdf.line(54, 42, 906, 42)
    pdf.setFont("DejaVu", 10)
    pdf.setFillColor(colors.HexColor("#C8D7E4"))
    pdf.drawString(54, 22, "К06 · AlpacaFarm · 20.11.2026")
    pdf.drawRightString(906, 22, f"{number} / 7")


def panel(pdf: canvas.Canvas, x: float, y: float, width: float, height: float,
          title: str, body: str, accent: colors.Color = TEAL) -> None:
    pdf.setFillColor(colors.HexColor("#213852"))
    pdf.roundRect(x, y, width, height, 12, fill=1, stroke=0)
    pdf.setFillColor(accent)
    pdf.roundRect(x + 18, y + height - 28, 6, 11, 3, fill=1, stroke=0)
    slide_text(pdf, title, x + 35, y + height - 14, width - 55, 18, color=WHITE, bold=True)
    slide_text(pdf, body, x + 22, y + height - 59, width - 44, 16.5,
               color=colors.HexColor("#D7E5EE"))


def slide_bar(pdf: canvas.Canvas, y: float, label: str, value: float,
              display: str, color: colors.Color = TEAL) -> None:
    slide_text(pdf, label, 58, y + 17, 278, 15, color=WHITE)
    pdf.setFillColor(colors.HexColor("#324760"))
    pdf.roundRect(345, y, 390, 22, 5, fill=1, stroke=0)
    pdf.setFillColor(color)
    pdf.roundRect(345, y, 390 * value / 0.6, 22, 5, fill=1, stroke=0)
    slide_text(pdf, display, 754, y + 20, 155, 15, color=WHITE, bold=True)


def build_length_slides() -> None:
    main = SUMMARY["main_evaluator"]
    char = SUMMARY["character_length_comparator"]
    base = SUMMARY["constant_position_1_baseline"]
    small = SUMMARY["word_gap_at_most_30"]
    large = SUMMARY["word_gap_over_30"]
    padding = SUMMARY["padding_probe"]
    pdf = canvas.Canvas(str(DOCS / "defense.pdf"), pagesize=(960, 540))
    pdf.setTitle("К06 — защита исследования AlpacaFarm")
    pdf.setAuthor("Команда К06")

    slide_base(pdf, 1, "Исследовательский проект", "Можно ли доверять оценщику по длине ответа?")
    slide_text(pdf, "Проверка на человеческих предпочтениях AlpacaFarm", 58, 366, 820, 22,
               color=colors.HexColor("#C8D7E4"))
    slide_text(pdf, "42,97%", 58, 270, 500, 62, color=colors.HexColor("#82D8D6"), bold=True)
    slide_text(pdf, "несовпадений с большинством людей на 498 парах", 59, 172, 790, 21,
               color=WHITE)
    pdf.showPage()

    slide_base(pdf, 2, "Данные", "Пары ответов и четыре оценки на каждую")
    panel(pdf, 56, 194, 260, 208, "2 596", "отдельных человеческих аннотаций")
    panel(pdf, 350, 194, 260, 208, "648", "уникальных пар после группировки полных текстов")
    panel(pdf, 644, 194, 260, 208, "498", "пар 4:0 или 3:1 для основной метрики")
    slide_text(pdf, "147 пар 2:2 без большинства; 3 пары с 5–6 оценками исключены.",
               58, 156, 840, 16, color=colors.HexColor("#D7E5EE"))
    pdf.showPage()

    slide_base(pdf, 3, "Проверка исходной гипотезы", "Опубликованный GPT-4 нельзя сравнить напрямую")
    panel(pdf, 56, 178, 410, 222, "4 пары", "надёжно совпали по инструкции и двум полным ответам, включая проверку перестановки A/B")
    panel(pdf, 494, 178, 410, 222, "Нужно ≥200", "сопоставленных пар для пилота по согласованной карточке; опубликованный судья не покрывает этот срез", ORANGE)
    slide_text(pdf, "Используем предусмотренный резервный вопрос: надёжность правила длины.",
               58, 140, 840, 16, color=WHITE, bold=True)
    pdf.showPage()

    slide_base(pdf, 4, "Метод", "Что означает «ошибка оценщика»")
    panel(pdf, 56, 215, 260, 184, "Эталон", "Большинство людей 4:0 или 3:1; это прокси предпочтения")
    panel(pdf, 350, 215, 260, 184, "Оценщик", "Выбирает ответ с большим числом слов; равная длина — ошибка")
    panel(pdf, 644, 215, 260, 184, "Сравнение", "Первая позиция, число символов, случайный выбор")
    slide_text(pdf, "Метрика: доля несовпадений + 95% доверительный интервал Уилсона.",
               58, 169, 840, 17, color=WHITE)
    pdf.showPage()

    slide_base(pdf, 5, "Основной результат", "Правило слов не проходит порог 30% ошибок")
    slide_bar(pdf, 323, "Слова · основной", main["error_rate"], pct(main["error_rate"]), ORANGE)
    slide_bar(pdf, 263, "Символы", char["error_rate"], pct(char["error_rate"]))
    slide_bar(pdf, 203, "Всегда ответ 1", base["error_rate"], pct(base["error_rate"]))
    slide_text(pdf, f"214/498 ошибок; 95% ДИ {interval(main['error_wilson_95'])}.",
               58, 138, 820, 17, color=WHITE)
    pdf.showPage()

    slide_base(pdf, 6, "Две проверки слабых мест", "Малая разница длин и многословие")
    panel(pdf, 56, 160, 410, 237, "Разница ≤30 слов",
          f"Ошибка {pct(small['error_rate'])} ({small['errors']}/{small['n']}). "
          f"При разнице >30 слов — {pct(large['error_rate'])}. "
          "Срез описательный, не причинный.")
    panel(pdf, 494, 160, 410, 237, "+64 нейтральных слова",
          f"Выбор сменился на {padding['flips_relative_to_original_labels']} из "
          f"{padding['n']} исходно верных пар. Изменённые ответы людьми заново не оценены.", ORANGE)
    slide_text(pdf, "Результат показывает управляемость прокси-метрики объёмом текста.",
               58, 120, 840, 16, color=WHITE, bold=True)
    pdf.showPage()

    slide_base(pdf, 7, "Вывод", "Длина ответа — слабый заменитель качества")
    panel(pdf, 56, 183, 410, 213, "Наблюдение", "42,97% ошибок; близкие по длине ответы особенно трудны для правила")
    panel(pdf, 494, 183, 410, 213, "Следующий шаг", "Разметить изменённые ответы и проверить содержательного судью на тех же парах")
    slide_text(pdf, "Исходные JSON, код, CSV по парам, отчёт и проверки — в GitHub команды К06.",
               58, 139, 840, 15, color=colors.HexColor("#D7E5EE"))
    pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    from build_judge_artifacts import build_report as build_judge_report
    from build_judge_artifacts import build_slides as build_judge_slides

    register_fonts()
    build_judge_report()
    build_judge_slides()
    print("Built docs/report.pdf and docs/defense.pdf")
