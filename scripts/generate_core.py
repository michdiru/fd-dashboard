#!/usr/bin/env python3
"""Пересчёт данных дашборда ФД из ежедневной выгрузки A&A.

Использование:
    python3 scripts/generate.py <папка с выгрузкой> [--month ГГГГ-ММ]

Читает real*/st* CSV-файлы (UTF-16LE, табуляция — см. DATA_SPEC.md),
историю прошлого года из data/history_2025.csv и планы из data/plans.json,
пишет data.js в корень репозитория.

Для каждого департамента берётся самый новый real/st-файл в папке; старые копии
не смешиваются с актуальной. Готовые real-выгрузки A&A уже содержат итог отчёта:
в реализацию входят все их строки. ``DateValue`` нужен для подписи периода и сравнения с
прошлым годом, но не для повторной фильтрации строк.
На границе месяцев можно явно указать месяц подписи через ``--month``.
"""
import csv
import glob
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEPTS = ["ТЗ", "ГП", "БК", "ДЦ", "Мероприятия ФД", "Массаж", "СМ"]
ST_DEPTS = ["ТЗ", "ГП", "БК", "ДЦ", "Массаж", "СМ"]
REAL_COLUMNS = ["SectionName", "ResourceName", "FIO", "Price", "Qty", "Summa",
                "Name", "DateValue"]
ST_COLUMNS = ["ResourceName", "FIO", "ExQnt", "Qnt", "Cr", "DetailName", "GroupLevel"]
FILE_CODE = {"tz": "ТЗ", "gp": "ГП", "bk": "БК", "dc": "ДЦ",
             "mer": "Мероприятия ФД", "ms": "Массаж", "sm": "СМ"}
SECTION_MAP = {
    "тренажерный зал": "ТЗ", "общие услуги фд": "ТЗ",
    "аэробика": "ГП",
    "бойцовский клуб": "БК", "восточные единоборства": "БК",
    "детский центр": "ДЦ",
    "массаж": "Массаж",
    "спортивная медицина": "СМ",
}


def num(s):
    s = (s or "").replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    return float(s) if s else 0.0


def canon_section(sec):
    s = (sec or "").strip().lower()
    if "мероприятия" in s:
        return "Мероприятия ФД"
    return SECTION_MAP.get(s)


def dept_from_filename(path):
    m = re.search(r"(?:^|[\s_])(tz|gp|bk|dc|mer|ms|sm)\b", os.path.basename(path).lower())
    return FILE_CODE.get(m.group(1)) if m else None


def latest_files_by_department(paths):
    """По одному самому новому файлу на департамент.

    Основной признак — время изменения. При равенстве файл с суффиксом
    ``(1)``, ``(2)`` и т. д. считается более новой копией.
    """
    selected = {}
    for path in paths:
        dep = dept_from_filename(path)
        if dep is None:
            continue
        basename = os.path.basename(path)
        match = re.search(r"\((\d+)\)(?=\.csv$)", basename, re.IGNORECASE)
        copy_number = int(match.group(1)) if match else 0
        rank = (os.stat(path).st_mtime_ns, copy_number, basename.casefold())
        if dep not in selected or rank > selected[dep][0]:
            selected[dep] = (rank, path)
    return {dep: value[1] for dep, value in selected.items()}


def title_name(raw):
    """АХТЯЛТДИНОВ И. Р. -> Ахтялтдинов И. Р. (дефисы и инициалы сохраняются)."""
    def cap(w):
        return "-".join(p[:1].upper() + p[1:].lower() if len(p) > 2 else p.upper()
                        for p in w.split("-"))
    return " ".join(cap(w) if len(w) > 2 else w.upper() for w in raw.split())


def client_key(raw):
    """Стабильный обезличенный ключ клиента: ID из скобок или нормализованное ФИО."""
    normalized = unicodedata.normalize("NFKC", raw or "")
    normalized = " ".join(normalized.split()).casefold().replace("ё", "е")
    if not normalized:
        return None
    match = re.search(r"\((\d+)\)\s*$", normalized)
    if match:
        return "id:" + match.group(1)
    return "fio:" + normalized


def read_rows(path):
    with open(path, encoding="utf-16") as f:
        rd = csv.reader(f, delimiter="\t")
        try:
            hdr = next(rd)
        except StopIteration:
            sys.exit(f"Пустой файл: {os.path.basename(path)}")
        idx = {h: i for i, h in enumerate(hdr)}
        required = REAL_COLUMNS if os.path.basename(path).lower().startswith("real") else ST_COLUMNS
        missing = [column for column in required if column not in idx]
        if missing:
            sys.exit(f"В {os.path.basename(path)} нет колонок: {', '.join(missing)}")
        last_required_index = max(idx[column] for column in required)
        for line_number, r in enumerate(rd, start=2):
            if not r or not any(cell.strip() for cell in r):
                continue
            if len(r) <= last_required_index:
                sys.exit(f"Неполная строка {line_number} в {os.path.basename(path)}")
            yield idx, r


def main(export_dir, report_month=None):
    real_candidates = sorted(glob.glob(os.path.join(export_dir, "real*.csv")))
    st_candidates = sorted(glob.glob(os.path.join(export_dir, "st*.csv")))
    if not real_candidates:
        sys.exit(f"В {export_dir} нет файлов real*.csv")

    real_by_dep = latest_files_by_department(real_candidates)
    st_by_dep = latest_files_by_department(st_candidates)
    missing_real = [dep for dep in DEPTS if dep not in real_by_dep]
    missing_st = [dep for dep in ST_DEPTS if dep not in st_by_dep]
    if missing_real or missing_st:
        parts = []
        if missing_real:
            parts.append("нет real: " + ", ".join(missing_real))
        if missing_st:
            parts.append("нет st: " + ", ".join(missing_st))
        sys.exit("Неполная выгрузка (" + "; ".join(parts) + ")")
    real_files = [real_by_dep[dep] for dep in DEPTS]
    st_files = [st_by_dep[dep] for dep in ST_DEPTS]

    # Месяц из plans.json задаёт подпись периода и окно сравнения,
    # но не фильтрует строки готовой real-выгрузки.
    with open(os.path.join(ROOT, "data", "plans.json"), encoding="utf-8") as f:
        plans = json.load(f)
    plan_real = plans["реализация"]
    plan_st = plans["СТ"]
    effective_month = report_month or plans.get("месяц")

    # --- реализация ---
    # Выгрузка A&A иногда кладёт один и тот же блок транзакций в несколько
    # файлов (например, копия ТЗ внутри real_mer) — поэтому одинаковые строки
    # из РАЗНЫХ файлов учитываются один раз (берём максимум повторов по файлу,
    # чтобы не потерять честные повторные покупки внутри одного файла).
    from collections import Counter
    global_cnt = Counter()
    for p in real_files:
        file_cnt = Counter()
        for idx, r in read_rows(p):
            key = (r[idx["SectionName"]], r[idx["ResourceName"]], r[idx["FIO"]],
                   r[idx["Price"]], r[idx["Qty"]], r[idx["Summa"]],
                   r[idx["Name"]], r[idx["DateValue"]])
            file_cnt[key] += 1
        for key, n in file_cnt.items():
            global_cnt[key] = max(global_cnt[key], n)

    txns = []  # (dept, dt, summa, is_pt, client, studio_qty)
    for key, n in global_cnt.items():
        section, _res, fio, _price, _qty, summa, name, datevalue = key
        try:
            dt = datetime.strptime(datevalue.strip(), "%d.%m.%Y %H:%M:%S")
        except ValueError:
            sys.exit(f"Неверная DateValue в real-выгрузке: {datevalue!r}")
        dep = canon_section(section)
        if dep is None:
            continue
        is_pt = "персональн" in name.lower()
        is_studio = bool(re.search(r"секц|студи", name, re.IGNORECASE))
        client = client_key(fio)
        studio_qty = num(_qty) if is_studio else 0
        for _ in range(n):
            txns.append((dep, dt, num(summa), is_pt, client, studio_qty))

    if effective_month:
        try:
            start = datetime.strptime(effective_month, "%Y-%m")
        except ValueError:
            sys.exit("Месяц должен быть в формате ГГГГ-ММ, например 2026-08")
        month_txns = [t for t in txns if t[1].year == start.year and t[1].month == start.month]
        if not month_txns:
            sys.exit(f"В выгрузке нет транзакций за {effective_month}")
        end = max(t[1] for t in month_txns)
    else:
        end = max(t[1] for t in txns)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    real = defaultdict(float)
    pt = defaultdict(int)
    clients = defaultdict(set)
    pt_clients = defaultdict(set)
    studio = defaultdict(int)
    # A&A уже формирует real-файлы в границах нужного отчёта. Поэтому
    # суммируем всю выгрузку: повторный фильтр по DateValue отбрасывает часть
    # итога, который уже задан параметрами отчёта A&A.
    for dep, _dt, summa, is_pt, client, studio_qty in txns:
        real[dep] += summa
        if client:
            clients[dep].add(client)
        if is_pt:
            pt[dep] += 1
            if client:
                pt_clients[dep].add(client)
        studio[dep] += studio_qty

    # --- прошлый период: те же числа месяца годом ранее, из history CSV ---
    prev_start = start.replace(year=start.year - 1).date().isoformat()
    prev_end = end.replace(year=end.year - 1).date().isoformat()
    prev = defaultdict(float)
    with open(os.path.join(ROOT, "data", "history_2025.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if prev_start <= row["date"] <= prev_end:
                prev[row["department"]] += float(row["income"])

    # --- СТ по департаментам и тренерам ---
    st = defaultdict(int)
    st_sales = defaultdict(int)          # продажи после СТ (Qnt)
    trainers = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # dep -> name -> [СТ, продажи]
    for p in st_files:
        dep = dept_from_filename(p)
        if dep is None:
            continue
        for idx, r in read_rows(p):
            try:
                q = int(num(r[idx["ExQnt"]]))
                sales = int(num(r[idx["Qnt"]]))
            except ValueError:
                sys.exit(f"Неверное ExQnt/Qnt в {os.path.basename(p)}")
            st[dep] += q
            st_sales[dep] += sales
            t = trainers[dep][title_name(r[idx["ResourceName"]])]
            t[0] += q
            t[1] += sales

    def pct(fact, plan):
        return round(fact / plan * 100) if plan else None

    def conv_pct(st_cnt, sales_cnt):
        return round(sales_cnt / st_cnt * 100) if st_cnt else None

    departments = []
    for dep in DEPTS:
        departments.append({
            "name": dep,
            "pt": pt.get(dep, 0),
            "clients": len(clients[dep]),
            "pt_clients": len(pt_clients[dep]),
            "studio": int(round(studio.get(dep, 0))),
            "real": round(real.get(dep, 0.0), 2),
            "real_plan": plan_real.get(dep),
            "real_pct": pct(real.get(dep, 0.0), plan_real.get(dep)),
            "prev": round(prev.get(dep, 0.0), 2),
            "delta_pct": (round((real.get(dep, 0.0) - prev[dep]) / prev[dep] * 100, 1)
                          if prev.get(dep) else None),
            "st": st.get(dep) if dep in st else None,
            "st_plan": plan_st.get(dep),
            "st_pct": pct(st.get(dep, 0), plan_st.get(dep)) if dep in st else None,
            "st_sales": st_sales.get(dep) if dep in st else None,
            "st_sales_pct": conv_pct(st.get(dep, 0), st_sales.get(dep, 0)) if dep in st else None,
        })

    total_real = sum(real.values())
    total_prev = sum(prev.values())
    total_plan = sum(plan_real.values())
    all_clients = set().union(*(clients[dep] for dep in DEPTS))
    all_pt_clients = set().union(*(pt_clients[dep] for dep in DEPTS))
    totals = {
        "pt": sum(pt.values()),
        "clients": len(all_clients),
        "pt_clients": len(all_pt_clients),
        "studio": int(round(sum(studio.values()))),
        "real": round(total_real, 2),
        "real_plan": total_plan,
        "real_pct": pct(total_real, total_plan),
        "prev": round(total_prev, 2),
        "delta_pct": round((total_real - total_prev) / total_prev * 100, 1) if total_prev else None,
        "st": sum(st.values()),
        "st_plan": sum(plan_st.values()),
        "st_pct": pct(sum(st.values()), sum(plan_st.values())),
        "st_sales": sum(st_sales.values()),
        "st_sales_pct": conv_pct(sum(st.values()), sum(st_sales.values())),
    }

    trainer_panels = {
        dep: sorted(
            ({"name": n, "st": v[0], "sales": v[1],
              "sales_pct": conv_pct(v[0], v[1])} for n, v in trs.items()),
            key=lambda x: (-x["st"], -(x["sales_pct"] or 0), x["name"]),
        )
        for dep, trs in trainers.items()
    }

    data = {
        "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "period": {"from": start.strftime("%d.%m.%Y"), "to": end.strftime("%d.%m.%Y")},
        "prev_period": {"from": datetime.fromisoformat(prev_start).strftime("%d.%m.%Y"),
                        "to": datetime.fromisoformat(prev_end).strftime("%d.%m.%Y")},
        "totals": totals,
        "departments": departments,
        "trainers": trainer_panels,
    }

    out = os.path.join(ROOT, "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.DASH_DATA = ")
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"OK: {out}")
    print(f"Период {data['period']['from']}–{data['period']['to']}: "
          f"реализация {totals['real']/1e6:.3f} млн ({totals['real_pct']}%), "
          f"ПТ {totals['pt']}, СТ {totals['st']} ({totals['st_pct']}%)")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        main(sys.argv[1])
    elif len(sys.argv) == 4 and sys.argv[2] == "--month":
        main(sys.argv[1], sys.argv[3])
    else:
        sys.exit("Использование: python3 scripts/generate.py <папка> [--month ГГГГ-ММ]")
