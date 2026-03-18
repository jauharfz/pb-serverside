"""
Blueprint: Laporan (FIXED)
───────────────────────────
GET /api/reports         → REQ-REPORT-001  (Admin only)
GET /api/reports/export  → REQ-REPORT-002  (Admin only)

FIX: date.today() → tanggal WIB hari ini
  HuggingFace berjalan UTC. date.today() mengembalikan tanggal UTC.
  v_kunjungan_harian.tanggal = DATE(waktu_masuk AT TIME ZONE 'Asia/Jakarta') → WIB.
  Mismatch ini menyebabkan laporan default hari ini kosong di pagi hari.
"""

import io
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request, send_file

from app.extensions import supabase
from app.middleware.auth import admin_only

reports_bp = Blueprint("reports", __name__)


def _today_wib() -> str:
    """Tanggal hari ini dalam timezone WIB (UTC+7), format YYYY-MM-DD."""
    return (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")


# ── GET /reports ──────────────────────────────────────────────────────────

@reports_bp.route("/reports", methods=["GET"])
@admin_only
def get_reports():
    # [FIX] Gunakan WIB bukan UTC sebagai default tanggal
    tanggal  = request.args.get("tanggal", _today_wib())
    event_id = request.args.get("event_id", "")

    try:
        query = (
            supabase.table("v_kunjungan_harian")
            .select("*")
            .eq("tanggal", tanggal)
            .order("waktu_masuk")
        )
        if event_id:
            query = query.eq("event_id", event_id)

        result = query.execute()
        detail = result.data or []

        nama_event      = detail[0].get("nama_event")  if detail else None
        actual_event_id = detail[0].get("event_id")    if detail else event_id or None

        total_member = sum(1 for r in detail if r.get("tipe_pengunjung") == "member")
        total_biasa  = sum(1 for r in detail if r.get("tipe_pengunjung") == "biasa")

        return jsonify({
            "status": "success",
            "data": {
                "tanggal":    tanggal,
                "event_id":   actual_event_id,
                "nama_event": nama_event,
                "ringkasan": {
                    "total_kunjungan": len(detail),
                    "total_member":    total_member,
                    "total_biasa":     total_biasa,
                },
                "detail": detail,
            },
        }), 200

    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── GET /reports/export ───────────────────────────────────────────────────

@reports_bp.route("/reports/export", methods=["GET"])
@admin_only
def export_report():
    fmt      = (request.args.get("format") or "").lower()
    tanggal  = (request.args.get("tanggal") or "").strip()
    event_id = request.args.get("event_id", "")

    _bad_param = jsonify({
        "status": "error",
        "message": "Parameter format harus berupa 'pdf' atau 'excel', dan tanggal harus format YYYY-MM-DD",
    }), 400

    if fmt not in ("pdf", "excel"):
        return _bad_param
    if not tanggal:
        return _bad_param
    try:
        datetime.strptime(tanggal, "%Y-%m-%d")
    except ValueError:
        return _bad_param

    try:
        query = (
            supabase.table("v_kunjungan_harian")
            .select("*")
            .eq("tanggal", tanggal)
            .order("waktu_masuk")
        )
        if event_id:
            query = query.eq("event_id", event_id)

        result     = query.execute()
        rows       = result.data or []
        nama_event = rows[0].get("nama_event", "-") if rows else "-"

        if fmt == "excel":
            data, filename = _generate_excel(rows, tanggal, nama_event)
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            data, filename = _generate_pdf(rows, tanggal, nama_event)
            mime = "application/pdf"

        return send_file(
            io.BytesIO(data),
            mimetype=mime,
            as_attachment=True,
            download_name=filename,
        )
    except Exception:
        return jsonify({"status": "error", "message": "Terjadi kesalahan pada server"}), 500


# ── Helpers ───────────────────────────────────────────────────────────────

def _fmt_ts(ts) -> str:
    if not ts:
        return "-"
    return str(ts)[:19].replace("T", " ")


def _generate_excel(rows, tanggal, nama_event):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Laporan {tanggal}"

    ws.merge_cells("A1:G1")
    ws["A1"] = "Laporan Kunjungan — Peken Banyumasan"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.merge_cells("A2:G2")
    ws["A2"] = f"{nama_event}  |  Tanggal: {tanggal}"
    ws["A2"].alignment = Alignment(horizontal="center")
    ws.append([])

    headers = ["No", "Tipe", "Nama / Pengunjung", "Waktu Masuk", "Waktu Keluar", "Durasi (mnt)", "Status"]
    header_fill = PatternFill("solid", fgColor="1E3A8A")
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col, value=h)
        cell.font      = Font(bold=True, color="FFFFFF")
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for i, row in enumerate(rows, start=1):
        even_fill = PatternFill("solid", fgColor="EFF6FF") if i % 2 == 0 else None
        values = [
            i,
            row.get("tipe_pengunjung", ""),
            row.get("nama_member") or "Pengunjung Biasa",
            _fmt_ts(row.get("waktu_masuk")),
            _fmt_ts(row.get("waktu_keluar")),
            row.get("durasi_menit") if row.get("durasi_menit") is not None else "-",
            row.get("status", ""),
        ]
        ws_row = ws.max_row + 1
        for col, val in enumerate(values, start=1):
            cell = ws.cell(row=ws_row, column=col, value=val)
            if even_fill:
                cell.fill = even_fill

    ws.append([])
    total_member = sum(1 for r in rows if r.get("tipe_pengunjung") == "member")
    total_biasa  = len(rows) - total_member
    ws.append([f"Total: {len(rows)}  |  Member: {total_member}  |  Pengunjung Biasa: {total_biasa}"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    for col, width in enumerate([5, 12, 28, 22, 22, 16, 12], start=1):
        ws.column_dimensions[get_column_letter(col)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), f"laporan_kunjungan_{tanggal}.xlsx"


def _generate_pdf(rows, tanggal, nama_event):
    from fpdf import FPDF

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_margins(12, 15, 12)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Laporan Kunjungan — Peken Banyumasan", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"{nama_event}  |  Tanggal: {tanggal}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    col_w   = [10, 20, 60, 48, 48, 30, 24]
    headers = ["No", "Tipe", "Nama / Pengunjung", "Waktu Masuk", "Waktu Keluar", "Durasi (mnt)", "Status"]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    for w, h in zip(col_w, headers):
        pdf.cell(w, 8, h, border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(0, 0, 0)
    for i, row in enumerate(rows, start=1):
        fill = True
        if i % 2 == 0:
            pdf.set_fill_color(239, 246, 255)
        else:
            pdf.set_fill_color(255, 255, 255)
        nama   = (row.get("nama_member") or "Pengunjung Biasa")[:32]
        durasi = str(row.get("durasi_menit")) if row.get("durasi_menit") is not None else "-"
        pdf.cell(col_w[0], 7, str(i),                           border=1, align="C", fill=fill)
        pdf.cell(col_w[1], 7, row.get("tipe_pengunjung", ""),   border=1, align="C", fill=fill)
        pdf.cell(col_w[2], 7, nama,                             border=1, fill=fill)
        pdf.cell(col_w[3], 7, _fmt_ts(row.get("waktu_masuk")),  border=1, fill=fill)
        pdf.cell(col_w[4], 7, _fmt_ts(row.get("waktu_keluar")), border=1, fill=fill)
        pdf.cell(col_w[5], 7, durasi,                           border=1, align="C", fill=fill)
        pdf.cell(col_w[6], 7, row.get("status", ""),            border=1, align="C", fill=fill)
        pdf.ln()

    pdf.ln(4)
    total_member = sum(1 for r in rows if r.get("tipe_pengunjung") == "member")
    total_biasa  = len(rows) - total_member
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 7, f"Total Kunjungan: {len(rows)}   |   Member: {total_member}   |   Pengunjung Biasa: {total_biasa}",
             new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output()), f"laporan_kunjungan_{tanggal}.pdf"