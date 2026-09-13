#!/usr/bin/env python3
"""Сверка документации, презентации и кода.

Запуск: ``python scripts/check_docs.py`` из каталога ``final-project``.
Проверки:

1. числовые факты презентации встречаются в README;
2. число автотестов в README и презентации совпадает с фактическим числом тестов;
3. число слайдов совпадает с картой «слайд → раздел README»;
4. каждая упомянутая ADR существует в ``docs/adr/``.

Код возврата 1, если хотя бы одна проверка не прошла: скрипт годится для CI.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DECK = ROOT / "presentation.html"
TESTS = ROOT / "backend" / "tests"
ADR = ROOT / "docs" / "adr"

FACT = re.compile(
    r"(?<![\w.])(?:≈\s*)?\d{1,3}(?:\s?\d{3})*(?:[,.]\d+)?\s*"
    r"(?:₽|%|×|млн|тыс|мин|секунд[аы]?|сек|ставк\w*|сессий|сессии|RPS|запросов|ГБ|лет|года|часов|месяцев)"
)
COUNT = re.compile(r"(\d+)\s*(?:автотест\w*|тест\w*|passed)")


def deck_text() -> str:
    raw = DECK.read_text(encoding="utf-8").split('<div class="stage" id="stage">')[1]
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def check_facts(problems: list[str]) -> None:
    readme = re.sub(r"\s+", "", README.read_text(encoding="utf-8"))
    for match in FACT.finditer(deck_text()):
        number = re.match(r"(?:≈\s*)?([\d\s,.]+)", match.group(0)).group(1)
        if re.sub(r"\s+", "", number) not in readme:
            problems.append(f"факт презентации не найден в README: {match.group(0).strip()}")


def check_test_count(problems: list[str]) -> None:
    actual = sum(
        len(re.findall(r"^def test_", path.read_text(encoding="utf-8"), re.M))
        for path in TESTS.glob("test_*.py")
    )
    for name, text in (("README", README.read_text(encoding="utf-8")), ("презентация", deck_text())):
        for value in {int(found) for found in COUNT.findall(text)}:
            if value != actual:
                problems.append(f"{name}: указано {value} тестов, в backend/tests — {actual}")


def check_slide_count(problems: list[str]) -> None:
    slides = DECK.read_text(encoding="utf-8").count('class="slide')
    numbers = [
        int(number)
        for row in re.findall(r"^\| (\d+(?:[–-]\d+)?) \|", README.read_text(encoding="utf-8"), re.M)
        for number in re.findall(r"\d+", row)
    ]
    if numbers and max(numbers) != slides:
        problems.append(f"слайдов в презентации {slides}, карта в README доходит до {max(numbers)}")


def check_adr(problems: list[str]) -> None:
    known = {path.name[:4] for path in ADR.glob("0*.md")}
    used = set(re.findall(r"ADR-(\d{4})", README.read_text(encoding="utf-8") + deck_text()))
    for number in sorted(used - known):
        problems.append(f"ADR-{number} упомянута, но файла в docs/adr нет")


def main() -> int:
    problems: list[str] = []
    check_facts(problems)
    check_test_count(problems)
    check_slide_count(problems)
    check_adr(problems)
    if problems:
        print("Расхождения документации:")
        for item in problems:
            print(" -", item)
        return 1
    print("Документация, презентация и код согласованы.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
