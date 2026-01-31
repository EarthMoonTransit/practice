from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fpdf import FPDF

from . import db

FONT_CANDIDATES = [
    Path(__file__).resolve().parent / "assets" / "DejaVuSans.ttf",
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
]


def _select_font(pdf: FPDF) -> str:
    for font_path in FONT_CANDIDATES:
        if font_path.exists():
            pdf.add_font("Unicode", "", str(font_path), uni=True)
            return "Unicode"
    return "Helvetica"


def _add_table(pdf: FPDF, font_name: str, rows: List[Dict[str, str]]) -> None:
    pdf.set_font(font_name, size=11)
    col_widths = [10, 55, 25, 40, 25]
    headers = ["ID", "Файл", "Кол-во", "Дата", "Время, мс"]

    for header, width in zip(headers, col_widths):
        pdf.cell(width, 7, header, border=1)
    pdf.ln()

    for row in rows:
        values = [
            str(row.get("id", "")),
            str(row.get("filename", ""))[:30],
            str(row.get("total_count", "")),
            str(row.get("created_at", "")),
            str(row.get("processing_ms", "")),
        ]
        for value, width in zip(values, col_widths):
            pdf.cell(width, 6, value, border=1)
        pdf.ln()

    pdf.ln(2)


def generate_report(output_path: Path) -> Path:
    db.init_db()
    summary = db.get_summary()
    counts_by_class = db.get_counts_by_class()
    recent = db.fetch_recent(limit=10)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    font_name = _select_font(pdf)
    pdf.set_font(font_name, size=18)
    pdf.cell(0, 10, "Отчёт: результаты подсчёта фруктов", ln=1)
    pdf.set_font(font_name, size=11)
    pdf.cell(0, 6, f"Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1)
    pdf.ln(2)

    pdf.set_font(font_name, size=13)
    pdf.cell(0, 8, "Сводные результаты", ln=1)
    pdf.set_font(font_name, size=11)
    pdf.multi_cell(
        0,
        6,
        "Всего обработанных изображений: {total}\n"
        "Общее количество обнаруженных фруктов: {fruits}\n"
        "Среднее количество фруктов на изображение: {avg:.2f}\n"
        "По классам: {classes}\n"
        "[Вставить скриншот: пример результата детектирования на изображении]".format(
            total=summary.get("total_requests", 0),
            fruits=summary.get("total_fruits", 0),
            avg=summary.get("avg_per_request", 0),
            classes=", ".join(f"{name}: {count}" for name, count in counts_by_class.items())
            if counts_by_class
            else "Нет данных",
        ),
    )
    pdf.ln(2)

    pdf.set_font(font_name, size=13)
    pdf.cell(0, 8, "Последние результаты", ln=1)
    _add_table(pdf, font_name, recent)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    return output_path
