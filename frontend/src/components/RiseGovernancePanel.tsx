import React, { useState } from "react";
import {
  CheckCircle2,
  ClipboardCheck,
  Cpu,
  FileCheck2,
  Loader2,
  Scale,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { api } from "../api/client";
import type { AppState } from "../types";
import { useToast } from "./ToastProvider";

interface Props {
  state: AppState;
  onStateChange: (state: AppState) => void;
}

const DECISION_LABELS: Record<string, string> = {
  validado: "Tendencia validada",
  contexto_externo: "Explicado por contexto externo",
  seguimiento_sugerido: "Sugerir consulta geriátrica",
};

export const RiseGovernancePanel: React.FC<Props> = ({ state, onStateChange }) => {
  const { notify } = useToast();
  const [reviewerName, setReviewerName] = useState(state.account.caregiver_name || "Laura González");
  const [reviewerRole, setReviewerRole] = useState("Familiar Cuidador");
  const [decision, setDecision] = useState("contexto_externo");
  const [selectedFactors, setSelectedFactors] = useState<string[]>(["mal_sueno", "sundowning"]);
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const toggleFactor = (factorId: string) => {
    setSelectedFactors((prev) =>
      prev.includes(factorId) ? prev.filter((id) => id !== factorId) : [...prev, factorId]
    );
  };

  const handleSaveReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewerName.trim() || clinicalNotes.trim().length < 3) {
      notify("Escribe tu nombre y una observación clínica o contextual breve.", "error");
      return;
    }
    setSaving(true);
    try {
      const res = await api.createReview({
        reviewer_name: reviewerName.trim(),
        reviewer_role: reviewerRole,
        decision,
        confounding_factors: selectedFactors,
        clinical_notes: clinicalNotes.trim(),
      });
      onStateChange(res.state);
      setClinicalNotes("");
      notify(
        "Revisión Human-in-the-Loop guardada en SQLite y lista para incluirse en el Reporte PDF.",
        "success"
      );
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al guardar revisión.", "error");
    } finally {
      setSaving(false);
    }
  };

  const factorLabelMap = Object.fromEntries(
    state.confounding_factors_catalog.map((f) => [f.id, f.label])
  );

  return (
    <div className="space-y-6">
      {/* Non-Diagnostic Ethical Notice */}
      <div
        className="clinical-card p-4 flex items-start gap-3"
        style={{
          backgroundColor: "var(--amber-soft)",
          borderColor: "color-mix(in srgb, var(--amber) 35%, transparent)",
        }}
      >
        <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "var(--amber)" }} />
        <div className="text-xs sm:text-sm leading-relaxed">
          <strong className="block mb-0.5">
            Gobernanza RISE — Apoyo Clínico No Diagnóstico & Control Human-in-the-Loop
          </strong>
          Antes de exportar el Reporte Clínico PDF al geriatra, el familiar o médico puede documentar
          variables de confusión (insomnio, ajuste farmacológico, fatiga o <em>Sundowning</em> vespertino)
          para evitar falsos positivos y mantener responsabilidad humana auditable.
        </div>
      </div>

      {/* Main Grid: Human-in-the-Loop Form + Auditable History */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <form onSubmit={handleSaveReview} className="clinical-card p-5 lg:col-span-6 space-y-4">
          <div className="flex items-center gap-2">
            <UserCheck className="w-5 h-5" style={{ color: "var(--primary)" }} />
            <h3 className="text-base font-semibold">Registrar Revisión Human-in-the-Loop</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="space-y-1 text-xs">
              <span className="font-medium">Nombre del revisor</span>
              <input
                className="clinical-input"
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                placeholder="Ej. Laura González o Dra. Martínez"
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="font-medium">Rol clínico / familiar</span>
              <select
                className="clinical-input"
                value={reviewerRole}
                onChange={(e) => setReviewerRole(e.target.value)}
              >
                <option value="Familiar Cuidador">Familiar Cuidador</option>
                <option value="Médico Geriatra">Médico Geriatra</option>
                <option value="Neuropsicólogo">Neuropsicólogo</option>
              </select>
            </label>
          </div>

          <div className="space-y-2">
            <span className="text-xs font-medium block">
              Variables de confusión y factores circadianos (1 clic)
            </span>
            <div className="flex flex-wrap gap-2">
              {state.confounding_factors_catalog.map((f) => {
                const active = selectedFactors.includes(f.id);
                return (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => toggleFactor(f.id)}
                    title={f.description}
                    className="px-3 py-1.5 rounded-full text-xs font-medium border transition"
                    style={{
                      backgroundColor: active ? "var(--primary-soft)" : "var(--surface-subtle)",
                      borderColor: active ? "var(--primary)" : "var(--border)",
                      color: active ? "var(--primary)" : "var(--text-muted)",
                    }}
                  >
                    {f.label}
                  </button>
                );
              })}
            </div>
          </div>

          <label className="space-y-1 text-xs block">
            <span className="font-medium">Criterio de validación humana</span>
            <select
              className="clinical-input"
              value={decision}
              onChange={(e) => setDecision(e.target.value)}
            >
              <option value="contexto_externo">Explicado por contexto externo / fatiga</option>
              <option value="validado">Tendencia confirmada en casa</option>
              <option value="seguimiento_sugerido">Compartir PDF con geriatra para seguimiento</option>
            </select>
          </label>

          <label className="space-y-1 text-xs block">
            <span className="font-medium">Observación contextual (se imprime en el PDF clínico)</span>
            <textarea
              rows={3}
              className="clinical-input"
              placeholder="Ej. Anoche durmió poco por el calor y la plática fue a las 6:30 pm (Sundowning). Reevaluar mañana por la mañana."
              value={clinicalNotes}
              onChange={(e) => setClinicalNotes(e.target.value)}
            />
          </label>

          <button type="submit" disabled={saving} className="btn-primary w-full">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <ClipboardCheck className="w-4 h-4" />}
            Guardar validación en SQLite
          </button>
        </form>

        {/* Auditable History of Human Reviews */}
        <div className="clinical-card p-5 lg:col-span-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCheck2 className="w-5 h-5" style={{ color: "var(--emerald)" }} />
              <h3 className="text-base font-semibold">Bitácora Auditable (SQLite)</h3>
            </div>
            <span className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
              {state.clinical_reviews.length} registro(s)
            </span>
          </div>

          {state.clinical_reviews.length === 0 ? (
            <div
              className="p-5 rounded-xl border text-center text-xs"
              style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
            >
              Aún no se han guardado notas Human-in-the-Loop. Registra una observación a la izquierda y descarga el PDF para verla integrada en tiempo real.
            </div>
          ) : (
            <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
              {state.clinical_reviews.map((rev) => (
                <article
                  key={rev.id}
                  className="p-3.5 rounded-xl border space-y-2"
                  style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-subtle)" }}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="font-semibold">
                      {rev.reviewer_name} ·{" "}
                      <span style={{ color: "var(--text-muted)" }}>{rev.reviewer_role}</span>
                    </span>
                    <span
                      className="px-2 py-0.5 rounded-full font-medium"
                      style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
                    >
                      {DECISION_LABELS[rev.decision] || rev.decision}
                    </span>
                  </div>
                  <p className="text-sm leading-snug">{rev.clinical_notes}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {rev.confounding_factors.map((fid) => (
                      <span
                        key={fid}
                        className="px-2 py-0.5 rounded-md text-[11px] border"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                      >
                        {factorLabelMap[fid] || fid}
                      </span>
                    ))}
                  </div>
                  <div
                    className="text-[11px] tabular-nums flex justify-between"
                    style={{ color: "var(--text-muted)" }}
                  >
                    <span>
                      Instantánea: MATTR {rev.mattr_snapshot.toFixed(3)} · Pausas{" "}
                      {rev.pause_snapshot.toFixed(2)}s
                    </span>
                    <span>{rev.created_at.slice(0, 16).replace("T", " ")}</span>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Identify Your Tools (Notre Dame Use of AI Compliance) */}
      <section className="clinical-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5" style={{ color: "var(--primary)" }} />
          <div>
            <h3 className="text-base font-semibold">
              Declaración Transparente de Herramientas IA (Identify Your Tools)
            </h3>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Cumplimiento oficial de las reglas Use of AI del Notre Dame 2026 Global R.I.S.E. AI Hackathon.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {state.ai_tools_disclosure.map((item) => (
            <div
              key={item.tool}
              className="p-4 rounded-xl border space-y-1.5"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-subtle)" }}
            >
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-semibold">{item.tool}</h4>
                <span
                  className="text-[11px] px-2 py-0.5 rounded-full font-medium shrink-0"
                  style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
                >
                  {item.category}
                </span>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text)" }}>
                {item.role}
              </p>
              <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                <strong>Privacidad y límites:</strong> {item.privacy_and_limits}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* RISE Rights & Assisted Dual Consent Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="clinical-card p-4 space-y-1.5">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="w-4 h-4" style={{ color: "var(--emerald)" }} />
            Zero-Raw-Cloud Audio
          </div>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
            El audio del adulto mayor se normaliza en RAM con tuberías ffmpeg y se destruye de inmediato. Telegram aplica Abstract Summary Filter.
          </p>
        </div>

        <div className="clinical-card p-4 space-y-1.5">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Scale className="w-4 h-4" style={{ color: "var(--primary)" }} />
            Equidad sin Sesgo Educativo
          </div>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
            El Z-Score de 21 días compara al adulto mayor únicamente contra su propia línea base (D1–D14), eliminando discriminación socioeconómica o regional.
          </p>
        </div>

        <div className="clinical-card p-4 space-y-1.5">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <CheckCircle2 className="w-4 h-4" style={{ color: "var(--emerald)" }} />
            Consentimiento Dual ({state.consent_events.length})
          </div>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Aceptación del cuidador en onboarding más bienvenida hablada transparente disponible en cualquier momento dentro del Modo Kiosco.
          </p>
        </div>
      </div>
    </div>
  );
};
