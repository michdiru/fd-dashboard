#!/usr/bin/env python3
"""Запускает пересчёт и подключает расширенные метрики к старой странице."""
import os
import sys

from generate_core import main


def run():
    if len(sys.argv) == 2:
        main(sys.argv[1])
    elif len(sys.argv) == 4 and sys.argv[2] == "--month":
        main(sys.argv[1], sys.argv[3])
    else:
        sys.exit("Использование: python3 scripts/generate.py <папка> [--month ГГГГ-ММ]")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "data.js"), "a", encoding="utf-8") as f:
        f.write("document.write('<script src=\"metrics-overlay.js\"><\\/script>');\n")


if __name__ == "__main__":
    run()
