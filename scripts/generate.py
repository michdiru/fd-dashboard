#!/usr/bin/env python3
"""Пересчёт данных дашборда ФД из ежедневной выгрузки A&A.

Использование:
    python3 scripts/generate.py <папка с выгрузкой>

Читает real*/st* CSV-файлы (UTF-16LE, табуляция — см. DATA_SPEC.md),
историю прошлого года из data/history_2025.csv и планы из data/plans.json,
пишет data.js в корень репозитория.

Отчётный период: с 1-го числа месяца последней транзакции по дату последней
транзакции в выгрузке (а не «по сегодня»: выгрузка A&A может отставать на
день-два, и сравнение с прошлым годом должно идти по одинаковым окнам).
"""
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEPTS = ["ТЗ", "ГП", "БК", "ДЦ", "Мероприятия ФД", "Массаж", "СМ"]
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


def title_name(raw):
    """АХТЯЛТДИНОВ И. Р. -> Ахтялтдинов И. Р. (дефисы и инициалы сохраняются)."""
    def cap(w):
        return "-".join(p[:1].upper() + p[1:].lower() if len(p) > 2 else p.upper()
                        for p in w.split("-"))
    return " ".join(cap(w) if len(w) > 2 else w.upper() for w in raw.split())


def read_rows(path):
    with open(path, encoding="utf-16") as f:
        rd = csv.reader(f, delimiter="\t")
        hdr = next(rd)
        idx = {h: i for i, h in enumerate(hdr)}
        for r in rd:
            if r and len(r) >= len([h for h in hdr if h]):
                yield idx, r


def main(export_dir):
    real_files = sorted(glob.glob(os.path.join(export_dir, "real*.csv")))
    st_files = sorted(glob.glob(os.path.join(export_dir, "st*.csv")))
    if not real_files:
        sys.exit(f"В {export_dir} нет файлов real*.csv")

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

    txns = []  # (dept, dt, summa, is_pt)
    for key, n in global_cnt.items():
        section, _res, _fio, _price, _qty, summa, name, datevalue = key
        try:
            dt = datetime.strptime(datevalue.strip(), "%d.%m.%Y %H:%M:%S")
        except ValueError:
            continue
        dep = canon_section(section)
        if dep is None:
            continue
        is_pt = "персональн" in name.lower()
        for _ in range(n):
            txns.append((dep, dt, num(summa), is_pt))

    end = max(t[1] for t in txns)
    start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    real = defaultdict(float)
    pt = defaultdict(int)
    for dep, dt, summa, is_pt in txns:
        if start <= dt <= end.replace(hour=23, minute=59, second=59):
            real[dep] += summa
            if is_pt:
                pt[dep] += 1

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
            except (KeyError, ValueError):
                continue
            sales = int(num(r[idx["Qnt"]]))
            st[dep] += q
            st_sales[dep] += sales
            t = trainers[dep][title_name(r[idx["ResourceName"]])]
            t[0] += q
            t[1] += sales

    # --- планы ---
    with open(os.path.join(ROOT, "data", "plans.json"), encoding="utf-8") as f:
        plans = json.load(f)
    plan_real = plans["реализация"]
    plan_st = plans["СТ"]

    def pct(fact, plan):
        return round(fact / plan * 100) if plan else None

    def conv_pct(st_cnt, sales_cnt):
        return round(sales_cnt / st_cnt * 100) if st_cnt else None

    departments = []
    for dep in DEPTS:
        departments.append({
            "name": dep,
            "pt": pt.get(dep, 0),
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
    totals = {
        "pt": sum(pt.values()),
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
    if len(sys.argv) != 2:
        sys.exit("Использование: python3 scripts/generate.py <папка с выгрузкой>")
    main(sys.argv[1])
