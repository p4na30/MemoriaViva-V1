"""Clinical PDF Report Generator (fpdf2) with Non-Diagnostic Clause,
21-Day Self-Referenced Biomarker Table, Circadian Summary, and Human-in-the-Loop Reviews.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Sequence

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from backend.config import AI_TOOLS_DISCLOSURE, CONFOUNDING_FACTORS, get_local_now, get_local_timezone

FACTOR_LABELS = {f["id"]: f["label"] for f in CONFOUNDING_FACTORS}


def _fmt_local_iso(iso_str: Any) -> str:
    """Convert UTC ISO timestamp to configured clinical local timezone (YYYY-MM-DD HH:MM)."""
    raw = str(iso_str or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(get_local_timezone())
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw[:16]


def _fmt_signed(value: Any, decimals: int = 1) -> str:
    """Format signed deltas/Z-scores cleanly without '+-' artifacts."""
    num = float(value or 0.0)
    if abs(num) < (0.5 * (10 ** (-decimals))):
        return f"{0.0:.{decimals}f}"
    return f"{num:+.{decimals}f}"


def _find_unicode_fonts() -> tuple[str | None, str | None]:
    regular_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ]
    reg = next((p for p in regular_candidates if Path(p).exists()), None)
    bold = next((p for p in bold_candidates if Path(p).exists()), None)
    return reg, bold


class ClinicalReportPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(14, 26, 14)
        self.set_auto_page_break(auto=True, margin=16)
        reg, bold = _find_unicode_fonts()
        self.unicode_enabled = bool(reg)
        if reg:
            self.add_font("BodyFont", "", reg)
            self.add_font("BodyFont", "B", bold or reg)
            self.base_font = "BodyFont"
        else:
            self.base_font = "Helvetica"

    def safe(self, text: str) -> str:
        if self.unicode_enabled:
            return str(text)
        normalized = (
            str(text)
            .replace("→", "->")
            .replace("≤", "<=")
            .replace("≥", ">=")
            .replace("–", "-")
            .replace("—", "-")
        )
        return normalized.encode("latin-1", "replace").decode("latin-1")

    def full_w(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def section_heading(self, title: str) -> None:
        self.set_x(self.l_margin)
        self.set_text_color(15, 23, 42)
        self.set_font(self.base_font, "B", 11)
        self.cell(
            self.full_w(),
            7,
            self.safe(title),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    def body_paragraph(self, text: str, line_h: float = 4.6, border: Any = 0, fill: bool = False) -> None:
        self.set_x(self.l_margin)
        self.multi_cell(
            self.full_w(),
            line_h,
            self.safe(text),
            border=border,
            fill=fill,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    def header(self) -> None:
        self.set_fill_color(14, 116, 144)  # Clinical Teal #0E7490
        self.rect(0, 0, 210, 22, style="F")
        self.set_xy(14, 5.5)
        self.set_text_color(255, 255, 255)
        self.set_font(self.base_font, "B", 13)
        self.cell(180, 6, self.safe("MemoriaViva RISE - Reporte Clínico Longitudinal"))
        self.set_font(self.base_font, "", 8.5)
        self.set_xy(14, 12.5)
        self.cell(
            180,
            5,
            self.safe(
                "Plataforma de Terapia de Reminiscencia y Biomarcadores Pasivos del Habla (Apoyo No Diagnóstico)"
            ),
        )
        self.set_xy(self.l_margin, 26)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(self.base_font, "", 7.5)
        self.set_text_color(100, 116, 139)
        self.cell(
            0,
            6,
            self.safe(
                f"MemoriaViva RISE v3.0 · Privacidad Zero-Raw-Cloud Audio · Página {self.page_no()}"
            ),
            align="C",
        )


def generate_clinical_pdf_bytes(
    profile: Dict[str, Any],
    history_days: Sequence[Dict[str, Any]],
    evaluation: Dict[str, Any],
    clinical_reviews: Sequence[Dict[str, Any]],
    recent_turns: Sequence[Dict[str, Any]],
    consent_events: Sequence[Dict[str, Any]] = (),
) -> bytes:
    """Build complete auditable PDF clinical report in memory."""
    pdf = ClinicalReportPDF()
    pdf.add_page()

    paciente = profile.get("paciente", {})
    red = profile.get("red_familiar_y_afectiva", {})
    cuidador = red.get("hija_mayor_cuidadora", {}).get("nombre") or profile.get(
        "contacto_emergencia_telegram", {}
    ).get("nombre", "Familiar")

    # 1. Non-Diagnostic Governance Banner
    pdf.set_fill_color(254, 243, 199)
    pdf.set_draw_color(217, 119, 6)
    pdf.set_text_color(120, 53, 15)
    pdf.set_font(pdf.base_font, "B", 8.5)
    pdf.body_paragraph(
        "CLÁUSULA ÉTICA RISE (APOYO CLÍNICO NO DIAGNÓSTICO): Este reporte sintetiza tendencias "
        "longitudinales auto-referenciadas del habla espontánea para apoyar la entrevista geriátrica. "
        "No constituye un diagnóstico médico ni sustituye una valoración neuropsicológica formal.",
        line_h=4.8,
        border=1,
        fill=True,
    )
    pdf.ln(3)

    # 2. Patient Summary Header
    pdf.section_heading("1. Perfil del Adulto Mayor y Resumen Ejecutivo")
    pdf.set_font(pdf.base_font, "", 9)
    pdf.set_text_color(51, 65, 85)
    generated_at = get_local_now().strftime("%Y-%m-%d %H:%M %Z")
    pdf.body_paragraph(
        f"Paciente: {paciente.get('nombre_completo', 'N/D')} ({paciente.get('nombre_preferido', '')})  |  "
        f"Edad: {paciente.get('edad', 'N/D')} años  |  Residencia: {paciente.get('ciudad_residencia', 'N/D')}\n"
        f"Familiar responsable: {cuidador}  |  Fecha de emisión: {generated_at}",
        line_h=4.8,
    )
    pdf.ln(2)

    # KPI Summary Boxes
    mattr_delta_str = _fmt_signed(evaluation.get("delta_mattr_pct_display", 0), 1)
    z_mattr_str = _fmt_signed(evaluation.get("z_mattr", 0), 2)
    pause_delta_str = _fmt_signed(evaluation.get("delta_pause_pct_display", 0), 1)
    z_pause_str = _fmt_signed(evaluation.get("z_pause", 0), 2)
    kpis = [
        ("Vitalidad", f"{evaluation.get('vitality_score', 0)}/100", "Índice compuesto"),
        (
            "MATTR Reciente",
            f"{evaluation.get('recent_mattr_mean', 0):.3f}",
            f"Base: {evaluation.get('baseline_mattr_mean', 0):.3f} ({mattr_delta_str}%, Z={z_mattr_str})",
        ),
        (
            "Pausas Recientes",
            f"{evaluation.get('recent_pause_mean', 0):.2f} s",
            f"Base: {evaluation.get('baseline_pause_mean', 0):.2f} s ({pause_delta_str}%, Z={z_pause_str})",
        ),
    ]
    start_y = pdf.get_y()
    col_w = (pdf.full_w() - 6) / 3.0
    for idx, (label, val, sub) in enumerate(kpis):
        x = pdf.l_margin + idx * (col_w + 3)
        pdf.set_fill_color(241, 245, 249)
        pdf.set_draw_color(203, 213, 225)
        pdf.rect(x, start_y, col_w, 20, style="DF")
        pdf.set_xy(x + 3, start_y + 2)
        pdf.set_font(pdf.base_font, "B", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(col_w - 6, 4, pdf.safe(label))
        pdf.set_xy(x + 3, start_y + 7)
        pdf.set_font(pdf.base_font, "B", 12)
        pdf.set_text_color(14, 116, 144)
        pdf.cell(col_w - 6, 6, pdf.safe(val))
        pdf.set_xy(x + 3, start_y + 14)
        pdf.set_font(pdf.base_font, "", 7)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(col_w - 6, 4, pdf.safe(sub[:42]))
    pdf.set_xy(pdf.l_margin, start_y + 23)

    circ = evaluation.get("circadian_summary", {})
    pdf.set_font(pdf.base_font, "", 8.5)
    pdf.set_text_color(51, 65, 85)
    pdf.body_paragraph(
        f"Distribución circadiana (21 días): Matutino={circ.get('matutino', 0)} | "
        f"Vespertino/Sundowning={circ.get('vespertino_sundowning', 0)} | Nocturno={circ.get('nocturno', 0)}",
        line_h=4.6,
    )
    pdf.ln(2)

    # 3. Human-in-the-Loop Override Log & Confounding Variables (Notre Dame RISE Alignment)
    pdf.section_heading("2. Bitácora de Auditoría y Anulación Humana (Human-in-the-Loop Override Log)")
    if clinical_reviews:
        for rev in list(clinical_reviews)[:8]:
            factors = [FACTOR_LABELS.get(f, f) for f in (rev.get("confounding_factors") or [])]
            factors_str = ", ".join(factors) if factors else "Sin variables de confusión marcadas"
            pdf.set_fill_color(236, 254, 255)
            pdf.set_draw_color(14, 116, 144)
            pdf.set_font(pdf.base_font, "B", 8.4)
            pdf.set_text_color(15, 23, 42)
            header_line = (
                f"[{_fmt_local_iso(rev.get('created_at'))}] {rev.get('reviewer_name', 'Revisor')} "
                f"({rev.get('reviewer_role', '')}) - Decisión: {str(rev.get('decision', '')).upper()}"
            )
            pdf.body_paragraph(header_line, line_h=4.8, border="LTR", fill=True)
            pdf.set_font(pdf.base_font, "", 8.2)
            pdf.set_text_color(51, 65, 85)
            body_line = (
                f"Variables de confusión: {factors_str}\n"
                f"Notas clínicas: {rev.get('clinical_notes', '')}\n"
                f"Instantánea: MATTR={float(rev.get('mattr_snapshot', 0)):.3f}, "
                f"Pausas={float(rev.get('pause_snapshot', 0)):.2f} s"
            )
            pdf.body_paragraph(body_line, line_h=4.5, border="LBR", fill=False)
            pdf.ln(1.8)
    else:
        pdf.set_font(pdf.base_font, "", 8.5)
        pdf.set_text_color(100, 116, 139)
        pdf.body_paragraph(
            "Aún no se registran notas Human-in-the-Loop. Registre contexto en Gobernanza RISE & IA."
        )
    pdf.ln(2)

    # 4. Longitudinal 21-Day Table
    pdf.section_heading("3. Serie Longitudinal Auto-Referenciada (21 Días)")
    headers = ["Día", "Ventana", "MATTR", "Pausa (s)", "Anómicas", "Rep.", "Estado", "Circadiano"]
    widths = [14, 24, 18, 20, 18, 12, 38, 38]

    pdf.set_x(pdf.l_margin)
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(pdf.base_font, "B", 7.8)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, pdf.safe(h), border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font(pdf.base_font, "", 7.5)
    for idx, d in enumerate(history_days):
        day_num = int(d.get("day_number", idx + 1))
        window_lbl = "Base (D1-14)" if day_num <= 14 else "Reciente"
        if day_num > 14:
            pdf.set_fill_color(255, 251, 235)
        else:
            pdf.set_fill_color(248, 250, 252) if idx % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        pdf.set_x(pdf.l_margin)
        pdf.set_text_color(30, 41, 59)
        circ_raw = str(d.get("circadian_period", "matutino"))
        circ_map = {
            "matutino": "Matutino",
            "vespertino_sundowning": "Vesp. (Sundowning)",
            "nocturno": "Nocturno",
        }
        circ_lbl = circ_map.get(circ_raw, circ_raw.replace("_", " ").capitalize()[:18])
        row_vals = [
            f"D{day_num}",
            window_lbl,
            f"{float(d.get('mattr', 0)):.3f}",
            f"{float(d.get('mean_pause', 0)):.2f}",
            str(d.get("anomic_pauses", 0)),
            str(d.get("repetitions", 0)),
            str(d.get("mood", ""))[:20],
            circ_lbl,
        ]
        for val, w in zip(row_vals, widths):
            pdf.cell(w, 5.2, pdf.safe(val), border=1, fill=True, align="C")
        pdf.ln()
    pdf.ln(4)

    # 5. Recent Sessions Log
    pdf.section_heading("4. Bitácora Resumida de Sesiones Recientes (SQLite)")
    pdf.set_font(pdf.base_font, "", 8.2)
    pdf.set_text_color(51, 65, 85)
    circ_pdf_map = {
        "matutino": "Matutino",
        "vespertino_sundowning": "Vesp. (Sundowning)",
        "nocturno": "Nocturno",
    }
    emo_pdf_map = {
        "tranquilo": "Tranquilo",
        "alegre": "Alegre",
        "nostalgico": "Nostálgico",
        "frustrado": "Frustrado",
        "crisis_desorientacion": "Crisis · desorientación",
    }
    theme_pdf_map = {
        "ferrocarril": "Ferrocarril",
        "musica_boleros": "Boleros",
        "playa_manzanillo": "Playa Manzanillo",
        "familia_hogar": "Familia y Hogar",
        "mascotas": "Mascotas",
    }
    if recent_turns:
        for t in list(recent_turns)[:8]:
            c_raw = str(t.get("circadian_period") or "matutino")
            e_raw = str(t.get("emotional_state") or "tranquilo").lower()
            th_raw = str(t.get("memory_album_theme") or "familia_hogar")
            line = (
                f"- [{_fmt_local_iso(t.get('created_at'))} | {circ_pdf_map.get(c_raw, c_raw)}] "
                f"MATTR={float(t.get('mattr', 0)):.3f} | Pausa Máx={float(t.get('max_pause_sec', 0)):.2f} s | "
                f"Anómicas={t.get('anomic_count', 0)} | Emoción={emo_pdf_map.get(e_raw, e_raw.capitalize())} | "
                f"Tema={theme_pdf_map.get(th_raw, th_raw)} | Nivel={t.get('alert_level', 1)}"
            )
            pdf.body_paragraph(line, line_h=4.5)
    else:
        pdf.body_paragraph("Sin turnos nuevos registrados en esta sesión.")
    pdf.ln(2)

    # 6. Model Card, Clinical Boundaries, Dual Consent & Identify Your Tools
    pdf.section_heading("5. Model Card, Consentimiento Dual y Transparencia IA (Identify Your Tools)")
    pdf.set_font(pdf.base_font, "", 7.8)
    pdf.set_text_color(71, 85, 105)
    pdf.body_paragraph(
        "Model Card & Límites Clínicos: Sistema de apoyo a la Terapia de Reminiscencia (Butler, 1963; Woods et al., 2018) "
        "y Validación no confrontativa (Feil, 1993) con biomarcadores locales auto-referenciados (MATTR: Covington & McFall, 2010; "
        "Habla espontánea MCI: Fraser et al., 2016; Pausas anómicas: Pistono et al., 2016; Repetición semántica: Guinn & Habash, 2012). "
        "Mecanismo de corrección (Redress): toda alerta puede ser anulada o contextualizada por el cuidador/geriatra en el Override Log.",
        line_h=4.2,
    )
    if consent_events:
        for ev in list(consent_events)[:4]:
            pdf.body_paragraph(
                f"- [{_fmt_local_iso(ev.get('created_at'))}] {ev.get('consent_type', '')} "
                f"({ev.get('acknowledged_by', '')}): {ev.get('summary_text', '')}",
                line_h=4.2,
            )
    else:
        pdf.body_paragraph(
            "- Privacidad Zero-Raw-Cloud Audio activa: 0 bytes de audio crudo almacenados.",
            line_h=4.2,
        )

    for tool in AI_TOOLS_DISCLOSURE:
        pdf.body_paragraph(f"- {tool['tool']}: {tool['role']}", line_h=4.2)

    return bytes(pdf.output())
