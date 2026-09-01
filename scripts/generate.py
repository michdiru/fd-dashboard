#!/usr/bin/env python3
"""Запускает пересчёт дашборда с расширенными метриками."""
import sys

from generate_core import main


def run():
    if len(sys.argv) == 2:
        main(sys.argv[1])
    elif len(sys.argv) == 4 and sys.argv[2] == "--month":
        main(sys.argv[1], sys.argv[3])
    else:
        sys.exit("Использование: python3 scripts/generate.py <папка> [--month ГГГГ-ММ]")

if __name__ == "__main__":
    run()
