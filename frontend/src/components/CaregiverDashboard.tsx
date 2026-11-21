import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BellRing,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  HeartHandshake,
  Image as ImageIcon,
  ImagePlus,
  Loader2,
  Lock,
  Moon,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Trash2,
  Volume2,
} from "lucide-react";
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, apiUrl } from "../api/client";
import type { AppState, ThemeMode, TurnResponse } from "../types";
import { RiseGovernancePanel } from "./RiseGovernancePanel";
import { useToast } from "./ToastProvider";

interface Props {
  state: AppState;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onStateChange: (state: AppState) => void;
  onLockKiosk: () => void;
}

type DashboardTab = "resumen" | "album" | "gobernanza" | "configuracion" | "simulador";
type ChartMode = "combinada" | "mattr" | "pausas";

const THEME_BADGE_LABELS: Record<string, string> = {
  ferrocarril: "Ferrocarril",
  musica_boleros: "Boleros",
  playa_manzanillo: "Playa Manzanillo",
  familia_hogar: "Familia y Hogar",
  mascotas: "Mascotas",
};

function formatSigned(value: number, decimals = 1): string {
  const num = Number.isFinite(value) ? value : 0;
  if (Math.abs(num) < 0.5 * Math.pow(10, -decimals)) {
    return (0).toFixed(decimals);
  }
  return `${num > 0 ? "+" : ""}${num.toFixed(decimals)}`;
}

function formatLocalTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(11, 16);
  return d.toLocaleTimeString("es-MX", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export const CaregiverDashboard: React.FC<Props> = ({
  state,
  theme,
  onToggleTheme,
  onStateChange,
  onLockKiosk,
}) => {
  const { notify } = useToast();
  const [activeTab, setActiveTab] = useState<DashboardTab>("resumen");
  const [chartMode, setChartMode] = useState<ChartMode>("combinada");
  const [busy, setBusy] = useState(false);

  // Album tab state
  const [photoTitle, setPhotoTitle] = useState("");
  const [photoCaption, setPhotoCaption] = useState("");
  const [photoTheme, setPhotoTheme] = useState("familia_hogar");
  const [rotationSec, setRotationSec] = useState(state.account.rotation_interval_sec || 8);

  // Settings tab state
  const [editName, setEditName] = useState(state.profile.paciente.nombre_completo);
  const [editPreferred, setEditPreferred] = useState(state.profile.paciente.nombre_preferido);
  const [editCity, setEditCity] = useState(state.profile.paciente.ciudad_residencia);
  const [editCaregiver, setEditCaregiver] = useState(state.account.caregiver_name);
  const [editVoice, setEditVoice] = useState<"male" | "female">(state.account.voice_gender);
  const [showAdminCreds, setShowAdminCreds] = useState(false);
  const [adminGeminiKey, setAdminGeminiKey] = useState("");
  const [adminTgToken, setAdminTgToken] = useState("");
  const [adminTgUser, setAdminTgUser] = useState(state.telegram_status.bot_username || "");
  const [adminChatId, setAdminChatId] = useState(state.account.telegram_chat_id || "");

  // Keep controlled Settings & Album inputs synchronized when server state updates (e.g., demo reset / Telegram bind)
  useEffect(() => {
    setEditName(state.profile.paciente.nombre_completo);
    setEditPreferred(state.profile.paciente.nombre_preferido);
    setEditCity(state.profile.paciente.ciudad_residencia);
  }, [
    state.profile.paciente.nombre_completo,
    state.profile.paciente.nombre_preferido,
    state.profile.paciente.ciudad_residencia,
  ]);

  useEffect(() => {
    setEditCaregiver(state.account.caregiver_name);
    setEditVoice(state.account.voice_gender);
    setRotationSec(state.account.rotation_interval_sec || 8);
    setAdminChatId(state.account.telegram_chat_id || "");
  }, [
    state.account.caregiver_name,
    state.account.voice_gender,
    state.account.rotation_interval_sec,
    state.account.telegram_chat_id,
  ]);

  useEffect(() => {
    setAdminTgUser(state.telegram_status.bot_username || "");
  }, [state.telegram_status.bot_username]);

  // Simulator tab state
  const [customText, setCustomText] = useState("");
  const [lastTurnResult, setLastTurnResult] = useState<TurnResponse | null>(null);

  const ev = state.evaluation;
  const paciente = state.profile.paciente;

  const playAudio = (uri?: string | null) => {
    if (!uri) return;
    const a = new Audio(uri);
    a.play().catch(() => {});
  };

  const handleSendLevel2 = async () => {
    setBusy(true);
    try {
      const res = await api.sendLevel2Warning();
      onStateChange(res.state);
      notify("Aviso Preventivo Nivel 2 enviado y registrado en el Puente Familiar.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al enviar aviso Nivel 2.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadPdf = async () => {
    setBusy(true);
    const url = api.reportPdfUrl();
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `Reporte_MemoriaViva_${paciente.id || "paciente"}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 4000);
      notify("Reporte Clínico PDF descargado con las notas Human-in-the-Loop actuales.", "success");
    } catch {
      window.open(url, "_blank", "noopener,noreferrer");
      notify("Abriendo Reporte Clínico PDF en una nueva pestaña.", "info");
    } finally {
      setBusy(false);
    }
  };

  const handleDiscoverTelegram = async () => {
    setBusy(true);
    try {
      const res = await api.discoverTelegramChat();
      onStateChange(res.state);
      notify(res.result.detail, res.result.found ? "success" : "info");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al detectar vinculación.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleUploadPhoto = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    try {
      for (const f of Array.from(files)) {
        await api.uploadPhoto(f, photoTitle || f.name.replace(/\.[^.]+$/, ""), photoCaption, photoTheme);
      }
      const fresh = await api.getState();
      onStateChange(fresh);
      setPhotoTitle("");
      setPhotoCaption("");
      notify("Fotografía(s) guardadas en el Álbum Familiar.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al subir fotografía.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleDeletePhoto = async (filename: string) => {
    setBusy(true);
    try {
      await api.deletePhoto(filename);
      const fresh = await api.getState();
      onStateChange(fresh);
      notify("Fotografía eliminada del álbum.", "info");
    } catch (err) {
      notify(err instanceof Error ? err.message : "No se pudo eliminar la fotografía.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleRestoreSamples = async () => {
    setBusy(true);
    try {
      await api.generateSamplePhotos();
      const fresh = await api.getState();
      onStateChange(fresh);
      notify("10 postales nostálgicas restauradas con sus etiquetas temáticas.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al restaurar postales.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveRotation = async (nextSec: number) => {
    setRotationSec(nextSec);
    try {
      const res = await api.updateSettings({ rotation_interval_sec: nextSec });
      onStateChange(res.state);
      notify(`Intervalo de rotación guardado: ${nextSec}s por foto.`, "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al guardar intervalo.", "error");
    }
  };

  const handleSavePatientSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.updateProfile({
        nombre_completo: editName,
        nombre_preferido: editPreferred,
        ciudad_residencia: editCity,
      });
      const res = await api.updateSettings({
        caregiver_name: editCaregiver,
        voice_gender: editVoice,
      });
      onStateChange(res.state);
      notify("Datos del paciente y preferencias guardados.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al guardar perfil.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleSaveAdminCreds = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload: Record<string, string> = {};
      if (adminGeminiKey.trim()) payload.gemini_api_key = adminGeminiKey.trim();
      if (adminTgToken.trim()) payload.telegram_bot_token = adminTgToken.trim();
      if (adminTgUser.trim()) payload.telegram_bot_username = adminTgUser.trim();
      if (adminChatId.trim()) payload.telegram_chat_id = adminChatId.trim();
      const res = await api.updateSettings(payload);
      onStateChange(res.state);
      setAdminGeminiKey("");
      setAdminTgToken("");
      notify("Credenciales de servidor actualizadas en .env y memoria activa.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al actualizar credenciales.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleRunScenario = async (scenarioId: string) => {
    setBusy(true);
    try {
      const res = await api.submitTurn({ demo_scenario_id: scenarioId });
      setLastTurnResult(res);
      if (res.state) onStateChange(res.state);
      playAudio(res.audio_data_uri);
      notify(
        res.emergency_triggered
          ? "Acto 3 ejecutado: Validación de Naomi Feil + Alerta Roja S.O.S. registrada."
          : "Escenario ejecutado y persistido en SQLite. Gráfica de 21 días actualizada.",
        res.emergency_triggered ? "error" : "success"
      );
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al ejecutar escenario.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleRunCustomText = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customText.trim()) return;
    setBusy(true);
    try {
      const res = await api.submitTurn({ custom_text: customText.trim() });
      setLastTurnResult(res);
      if (res.state) onStateChange(res.state);
      setCustomText("");
      playAudio(res.audio_data_uri);
      notify("Turno de texto libre analizado y guardado en SQLite.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al procesar texto libre.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleResetDemo = async () => {
    setBusy(true);
    try {
      const res = await api.resetDemo();
      onStateChange(res.state);
      setLastTurnResult(null);
      notify("Estado Demo de Don Manuel restablecido limpiamente para ensayos.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al reiniciar demo.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleResetSystem = async () => {
    if (!window.confirm("¿Restablecer la configuración y volver al asistente de Onboarding?")) return;
    setBusy(true);
    try {
      const res = await api.resetSystem();
      onStateChange(res.state);
      notify("Sistema restablecido al asistente de bienvenida.", "info");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al restablecer sistema.", "error");
    } finally {
      setBusy(false);
    }
  };

  const navItems: Array<{ id: DashboardTab; label: string; icon: React.ReactNode }> = [
    { id: "resumen", label: "Resumen Clínico", icon: <Activity className="w-4 h-4" /> },
    { id: "album", label: "Álbum Familiar", icon: <ImageIcon className="w-4 h-4" /> },
    { id: "gobernanza", label: "Gobernanza RISE & IA", icon: <ShieldCheck className="w-4 h-4" /> },
    { id: "configuracion", label: "Configuración", icon: <Settings className="w-4 h-4" /> },
    { id: "simulador", label: "Simulador Demo", icon: <Play className="w-4 h-4" /> },
  ];

  const isDark = theme === "dark";
  const gridStroke = isDark ? "#26313E" : "#E2E8F0";
  const axisTickColor = isDark ? "#94A3B8" : "#475569";

  return (
    <div className="min-h-screen flex flex-col">
      {/* Unified Header */}
      <header
        className="sticky top-0 z-30 border-b backdrop-blur-md"
        style={{
          backgroundColor: "color-mix(in srgb, var(--surface) 92%, transparent)",
          borderColor: "var(--border)",
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
            >
              <HeartHandshake className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight">MemoriaViva RISE</h1>
                <span
                  className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                  style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
                >
                  {paciente.nombre_preferido} ({paciente.edad} años)
                </span>
              </div>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Panel Familiar y Clínico · Cuidador: {state.account.caregiver_name}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button type="button" onClick={onToggleTheme} className="btn-secondary !px-3">
              {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
              <span className="hidden sm:inline">{theme === "light" ? "Modo Noche" : "Modo Día"}</span>
            </button>
            <button type="button" onClick={onLockKiosk} className="btn-primary">
              <Lock className="w-4 h-4" />
              Activar Modo Kiosco
            </button>
          </div>
        </div>

        {/* 5 Clean Navigation Tabs */}
        <nav className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center gap-1 overflow-x-auto">
          {navItems.map((tab) => {
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className="flex items-center gap-2 px-3.5 py-2.5 text-xs sm:text-sm font-medium border-b-2 whitespace-nowrap transition"
                style={{
                  borderBottomColor: active ? "var(--primary)" : "transparent",
                  color: active ? "var(--primary)" : "var(--text-muted)",
                }}
              >
                {tab.icon}
                {tab.label}
              </button>
            );
          })}
        </nav>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* ================= TAB 1: RESUMEN CLÍNICO ================= */}
        {activeTab === "resumen" && (
          <div className="space-y-6">
            {/* 3 Clinical KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="clinical-card p-5 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                  <span>Vitalidad Conversacional</span>
                  <span
                    className="px-2 py-0.5 rounded-full font-semibold"
                    style={{
                      backgroundColor: ev.level2_alert_triggered ? "var(--amber-soft)" : "var(--emerald-soft)",
                      color: ev.level2_alert_triggered ? "var(--amber)" : "var(--emerald)",
                    }}
                  >
                    {ev.level2_alert_triggered ? "Revisión sugerida" : "Estable"}
                  </span>
                </div>
                <div className="text-3xl font-bold tabular-nums">
                  {ev.vitality_score}
                  <span className="text-base font-medium" style={{ color: "var(--text-muted)" }}>
                    {" "}
                    / 100
                  </span>
                </div>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Auto-referenciado vs Días 1–14 · {state.recent_turns.length} turno(s) nuevo(s) en SQLite
                </p>
              </div>

              <div className="clinical-card p-5 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                  <span>Riqueza Léxica (MATTR W=20)</span>
                  <span className="tabular-nums font-semibold" style={{ color: "var(--primary)" }}>
                    {formatSigned(ev.delta_mattr_pct_display, 1)}% vs base
                  </span>
                </div>
                <div className="text-3xl font-bold tabular-nums" style={{ color: "var(--primary)" }}>
                  {ev.recent_mattr_mean.toFixed(3)}
                </div>
                <p className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
                  Línea base: {ev.baseline_mattr_mean.toFixed(3)} · Z-Score personal: {formatSigned(ev.z_mattr, 2)}
                </p>
              </div>

              <div className="clinical-card p-5 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                  <span>Ritmo del Habla (Pausas)</span>
                  <span className="tabular-nums font-semibold" style={{ color: "var(--amber)" }}>
                    {formatSigned(ev.delta_pause_pct_display, 1)}% vs base
                  </span>
                </div>
                <div className="text-3xl font-bold tabular-nums" style={{ color: "var(--amber)" }}>
                  {ev.recent_pause_mean.toFixed(2)} s
                </div>
                <p className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
                  Línea base: {ev.baseline_pause_mean.toFixed(2)} s · Z-Score personal: {formatSigned(ev.z_pause, 2)}
                </p>
              </div>
            </div>

            {/* Chart + Telegram Bridge Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left 8 cols: 21-Day Longitudinal Chart */}
              <div className="clinical-card p-5 lg:col-span-8 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold">
                      Serie Longitudinal Auto-Referenciada (21 Días)
                    </h2>
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                      Banda sombreada: Línea Base Personal (D1–D14) · Ventana reciente (D17–D21)
                    </p>
                  </div>

                  {/* Segmented Chart Mode Control */}
                  <div
                    className="inline-flex rounded-xl p-1 text-xs"
                    style={{ backgroundColor: "var(--surface-subtle)" }}
                  >
                    {(["combinada", "mattr", "pausas"] as ChartMode[]).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => setChartMode(mode)}
                        className="px-3 py-1.5 rounded-lg font-medium capitalize transition"
                        style={{
                          backgroundColor: chartMode === mode ? "var(--surface)" : "transparent",
                          color: chartMode === mode ? "var(--text)" : "var(--text-muted)",
                          boxShadow: chartMode === mode ? "var(--shadow-card)" : "none",
                        }}
                      >
                        {mode === "mattr" ? "MATTR" : mode}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={state.history_21_days}
                      margin={{ top: 12, right: 20, left: 6, bottom: 4 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
                      <XAxis
                        dataKey="date_label"
                        tick={{ fontSize: 11, fill: axisTickColor }}
                        interval={2}
                      />
                      {(chartMode === "combinada" || chartMode === "mattr") && (
                        <YAxis
                          yAxisId="left"
                          domain={[0.35, 1.0]}
                          tick={{ fontSize: 11, fill: axisTickColor }}
                          label={{
                            value: "MATTR",
                            angle: -90,
                            position: "insideLeft",
                            style: { fontSize: 11, fill: axisTickColor },
                          }}
                        />
                      )}
                      {(chartMode === "combinada" || chartMode === "pausas") && (
                        <YAxis
                          yAxisId="right"
                          orientation={chartMode === "pausas" ? "left" : "right"}
                          domain={[0, "auto"]}
                          tick={{ fontSize: 11, fill: axisTickColor }}
                          label={{
                            value: "Pausa (s)",
                            angle: chartMode === "pausas" ? -90 : 90,
                            position: chartMode === "pausas" ? "insideLeft" : "insideRight",
                            style: { fontSize: 11, fill: axisTickColor },
                          }}
                        />
                      )}
                      <Tooltip
                        contentStyle={{
                          backgroundColor: isDark ? "#171E26" : "#FFFFFF",
                          borderColor: gridStroke,
                          borderRadius: "10px",
                          fontSize: "12px",
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "6px" }} />
                      <ReferenceArea
                        yAxisId={chartMode === "pausas" ? "right" : "left"}
                        x1="Día 1"
                        x2="Día 14"
                        fill={isDark ? "#22B8CF" : "#0E7490"}
                        fillOpacity={0.09}
                        label={{
                          value: "Base D1–D14",
                          position: "insideTopLeft",
                          fill: axisTickColor,
                          fontSize: 11,
                        }}
                      />
                      {(chartMode === "combinada" || chartMode === "mattr") && (
                        <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="mattr"
                          name="Riqueza Léxica (MATTR)"
                          stroke={isDark ? "#22B8CF" : "#0E7490"}
                          strokeWidth={2.5}
                          dot={{ r: 3 }}
                          activeDot={{ r: 5 }}
                        />
                      )}
                      {(chartMode === "combinada" || chartMode === "pausas") && (
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="mean_pause"
                          name="Pausa Media (s)"
                          stroke={isDark ? "#F59E0B" : "#D97706"}
                          strokeWidth={2.5}
                          dot={{ r: 3 }}
                          activeDot={{ r: 5 }}
                        />
                      )}
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>

                {/* Action Bar: PDF Report + Level 2 Warning */}
                <div className="pt-3 border-t flex flex-wrap items-center justify-between gap-3" style={{ borderColor: "var(--border)" }}>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Distribución circadiana: Matutino {ev.circadian_summary.matutino} · Vespertino (Sundowning){" "}
                    {ev.circadian_summary.vespertino_sundowning} · Nocturno {ev.circadian_summary.nocturno}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={handleSendLevel2}
                      className="btn-secondary text-xs"
                    >
                      <BellRing className="w-4 h-4" style={{ color: "var(--amber)" }} />
                      Enviar Aviso Preventivo Nivel 2
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={handleDownloadPdf}
                      className="btn-primary text-xs"
                    >
                      <Download className="w-4 h-4" />
                      Descargar Reporte Clínico (PDF)
                    </button>
                  </div>
                </div>
              </div>

              {/* Right 4 cols: Telegram Family Bridge Feed */}
              <div className="clinical-card p-5 lg:col-span-4 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Send className="w-4 h-4" style={{ color: "var(--primary)" }} />
                    <h2 className="text-base font-semibold">Puente Familiar (Telegram)</h2>
                  </div>
                  <span
                    className="text-[11px] font-semibold px-2 py-0.5 rounded-full"
                    style={{
                      backgroundColor: state.telegram_status.linked
                        ? "var(--emerald-soft)"
                        : "var(--surface-subtle)",
                      color: state.telegram_status.linked ? "var(--emerald)" : "var(--text-muted)",
                    }}
                  >
                    {state.telegram_status.linked ? "Vinculado" : "Vista previa"}
                  </span>
                </div>

                {!state.telegram_status.linked && (
                  <div
                    className="p-3 rounded-xl border flex items-center gap-3"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-subtle)" }}
                  >
                    <img
                      src={state.telegram_status.qr_base64}
                      alt="QR Telegram"
                      className="w-16 h-16 rounded bg-white p-1 shrink-0"
                    />
                    <div className="space-y-1 text-xs">
                      <p className="font-medium">Vincula en 5s ({state.telegram_status.link_code})</p>
                      <div className="flex flex-wrap gap-1.5">
                        <a
                          href={state.telegram_status.deep_link}
                          target="_blank"
                          rel="noreferrer"
                          className="underline font-medium"
                          style={{ color: "var(--primary)" }}
                        >
                          Abrir Bot
                        </a>
                        <span>·</span>
                        <button
                          type="button"
                          onClick={handleDiscoverTelegram}
                          className="underline font-medium"
                          style={{ color: "var(--primary)" }}
                        >
                          Detectar
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex-1 space-y-2.5 max-h-[340px] overflow-y-auto pr-1">
                  {state.telegram_logs.length === 0 ? (
                    <p className="text-xs py-6 text-center" style={{ color: "var(--text-muted)" }}>
                      Ejecuta un turno en el Kiosco o Simulador Demo para ver las notificaciones Nivel 1, 2 y 3 en tiempo real.
                    </p>
                  ) : (
                    state.telegram_logs.map((log) => (
                      <article
                        key={log.id}
                        className="p-3 rounded-xl border text-xs space-y-1"
                        style={{
                          borderColor: "var(--border)",
                          borderLeftWidth: "4px",
                          borderLeftColor:
                            log.level === 3
                              ? "var(--danger)"
                              : log.level === 2
                                ? "var(--amber)"
                                : "var(--emerald)",
                          backgroundColor: "var(--surface-subtle)",
                        }}
                      >
                        <div className="flex items-center justify-between gap-2 font-semibold">
                          <span>{log.title}</span>
                          <span className="text-[10px] tabular-nums" style={{ color: "var(--text-muted)" }}>
                            {formatLocalTime(log.created_at)}
                          </span>
                        </div>
                        <p className="whitespace-pre-line leading-relaxed" style={{ color: "var(--text-muted)" }}>
                          {log.message}
                        </p>
                        <div className="pt-1 flex justify-end">
                          <span
                            className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                            style={{
                              backgroundColor: log.delivered
                                ? "var(--emerald-soft)"
                                : log.channel_status === "queued_async"
                                  ? "var(--amber-soft)"
                                  : "var(--surface)",
                              color: log.delivered
                                ? "var(--emerald)"
                                : log.channel_status === "queued_async"
                                  ? "var(--amber)"
                                  : "var(--text-muted)",
                            }}
                          >
                            {log.delivered
                              ? "Entregado en Telegram"
                              : log.channel_status === "queued_async"
                                ? "Enviando a Telegram"
                                : "Vista previa local"}
                          </span>
                        </div>
                      </article>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Learned Biographical Memory Card */}
            <section className="clinical-card p-5 space-y-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4" style={{ color: "var(--emerald)" }} />
                <h3 className="text-sm font-semibold">
                  Memoria Biográfica Viva (RAG-Lite · {state.profile.recuerdos_aprendidos.length} nuevos)
                </h3>
              </div>
              {state.profile.recuerdos_aprendidos.length === 0 ? (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Cuando {paciente.nombre_preferido} comparta un recuerdo nuevo (ej. su perro Sultán en el Acto 1), se guardará automáticamente aquí y en su perfil JSON.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {state.profile.recuerdos_aprendidos.map((fact, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1.5 rounded-full text-xs font-medium inline-flex items-center gap-1.5"
                      style={{ backgroundColor: "var(--emerald-soft)", color: "var(--emerald)" }}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {fact}
                    </span>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* ================= TAB 2: ÁLBUM FAMILIAR ================= */}
        {activeTab === "album" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              <div className="clinical-card p-5 lg:col-span-7 space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <ImagePlus className="w-5 h-5" style={{ color: "var(--primary)" }} />
                    <h2 className="text-base font-semibold">Agregar Fotografía al Anclaje Visual</h2>
                  </div>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={handleRestoreSamples}
                    className="btn-secondary text-xs"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Restaurar 10 postales
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label className="space-y-1 text-xs">
                    <span className="font-medium">Título del recuerdo</span>
                    <input
                      className="clinical-input"
                      placeholder="Ej. Vacaciones en Manzanillo"
                      value={photoTitle}
                      onChange={(e) => setPhotoTitle(e.target.value)}
                    />
                  </label>
                  <label className="space-y-1 text-xs">
                    <span className="font-medium">Tema para Anclaje Voz ↔ Foto</span>
                    <select
                      className="clinical-input"
                      value={photoTheme}
                      onChange={(e) => setPhotoTheme(e.target.value)}
                    >
                      {Object.entries(THEME_BADGE_LABELS).map(([k, lbl]) => (
                        <option key={k} value={k}>
                          {lbl}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-xs sm:col-span-2">
                    <span className="font-medium">Pie de foto (usado en "Platicar sobre esta foto")</span>
                    <input
                      className="clinical-input"
                      placeholder="Describe brevemente quién aparece o qué lugar es..."
                      value={photoCaption}
                      onChange={(e) => setPhotoCaption(e.target.value)}
                    />
                  </label>
                </div>

                <label
                  className="flex items-center justify-center gap-2 p-4 rounded-xl border border-dashed cursor-pointer text-xs font-medium hover:opacity-85 transition"
                  style={{ borderColor: "var(--primary)", backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
                >
                  <ImagePlus className="w-4 h-4" />
                  <span>Seleccionar imagen(es) JPG, PNG o WebP</span>
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={(e) => handleUploadPhoto(e.target.files)}
                  />
                </label>
              </div>

              <div className="clinical-card p-5 lg:col-span-5 flex flex-col justify-between gap-4">
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <SlidersHorizontal className="w-5 h-5" style={{ color: "var(--primary)" }} />
                    <h2 className="text-base font-semibold">Velocidad del Marco Digital</h2>
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Controla cada cuántos segundos rota suavemente la fotografía en el Modo Kiosco cuando no está conversando.
                  </p>
                  <div className="space-y-2 pt-2">
                    <div className="flex justify-between text-sm font-semibold tabular-nums">
                      <span>Intervalo</span>
                      <span style={{ color: "var(--primary)" }}>{rotationSec} segundos</span>
                    </div>
                    <input
                      type="range"
                      min={4}
                      max={15}
                      value={rotationSec}
                      onChange={(e) => handleSaveRotation(Number(e.target.value))}
                      className="w-full accent-cyan-700"
                    />
                    <div className="flex justify-between text-[11px]" style={{ color: "var(--text-muted)" }}>
                      <span>4s (dinámico)</span>
                      <span>15s (pausado)</span>
                    </div>
                  </div>
                </div>
                <div
                  className="text-xs p-3 rounded-xl"
                  style={{ backgroundColor: "var(--surface-subtle)", color: "var(--text-muted)" }}
                >
                  Total en álbum: <strong className="tabular-nums">{state.photos.length}</strong> fotografías (mínimo requerido: {state.min_screensaver_photos}).
                </div>
              </div>
            </div>

            {/* 4-Column Responsive Gallery */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {state.photos.map((photo) => (
                <article key={photo.filename} className="clinical-card overflow-hidden flex flex-col">
                  <div className="relative aspect-[16/10] bg-slate-900">
                    <img
                      src={apiUrl(photo.url)}
                      alt={photo.title}
                      className="w-full h-full object-cover"
                    />
                    <span className="absolute top-2 left-2 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-950/70 text-white backdrop-blur-sm">
                      {THEME_BADGE_LABELS[photo.theme] || photo.theme}
                    </span>
                  </div>
                  <div className="p-3.5 flex-1 flex flex-col justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-semibold leading-snug">{photo.title}</h3>
                      <p className="text-xs mt-1 line-clamp-2" style={{ color: "var(--text-muted)" }}>
                        {photo.caption}
                      </p>
                    </div>
                    {state.photos.length > state.min_screensaver_photos && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => handleDeletePhoto(photo.filename)}
                        className="btn-danger !py-1.5 !text-xs w-full mt-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Eliminar
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </div>
        )}

        {/* ================= TAB 3: GOBERNANZA RISE & IA ================= */}
        {activeTab === "gobernanza" && (
          <RiseGovernancePanel state={state} onStateChange={onStateChange} />
        )}

        {/* ================= TAB 4: CONFIGURACIÓN ================= */}
        {activeTab === "configuracion" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Card 1: Patient & System */}
            <form onSubmit={handleSavePatientSettings} className="clinical-card p-5 space-y-4">
              <h2 className="text-base font-semibold">Paciente y Sistema</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="space-y-1 text-xs">
                  <span className="font-medium">Nombre completo</span>
                  <input
                    className="clinical-input"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs">
                  <span className="font-medium">Nombre preferido</span>
                  <input
                    className="clinical-input"
                    value={editPreferred}
                    onChange={(e) => setEditPreferred(e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs sm:col-span-2">
                  <span className="font-medium">Ciudad de residencia</span>
                  <input
                    className="clinical-input"
                    value={editCity}
                    onChange={(e) => setEditCity(e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs">
                  <span className="font-medium">Familiar responsable</span>
                  <input
                    className="clinical-input"
                    value={editCaregiver}
                    onChange={(e) => setEditCaregiver(e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs">
                  <span className="font-medium">Voz geriátrica (Edge-TTS)</span>
                  <select
                    className="clinical-input"
                    value={editVoice}
                    onChange={(e) => setEditVoice(e.target.value as "male" | "female")}
                  >
                    <option value="male">Jorge (es-MX · -15%, -5Hz)</option>
                    <option value="female">Dalia (es-MX · -15%, -5Hz)</option>
                  </select>
                </label>
              </div>
              <button type="submit" disabled={busy} className="btn-primary">
                {busy && <Loader2 className="w-4 h-4 animate-spin" />}
                Guardar cambios del paciente
              </button>

              {/* Danger Zone */}
              <div className="pt-4 mt-4 border-t space-y-2" style={{ borderColor: "var(--border)" }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--danger)" }}>
                  Zona de Restablecimiento
                </h3>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Vuelve al asistente inicial de Onboarding o reinicia el estado de pruebas de Don Manuel.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={handleResetDemo} className="btn-secondary text-xs">
                    <RotateCcw className="w-3.5 h-3.5" />
                    Reiniciar datos Demo
                  </button>
                  <button type="button" onClick={handleResetSystem} className="btn-danger text-xs">
                    Restablecer Onboarding
                  </button>
                </div>
              </div>
            </form>

            {/* Card 2: Integrations + Collapsed Admin Advanced Accordion */}
            <div className="clinical-card p-5 space-y-4">
              <h2 className="text-base font-semibold">Integraciones (Zero-API-Key UX)</h2>

              <div className="flex items-center gap-4 p-4 rounded-xl border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-subtle)" }}>
                <img
                  src={state.telegram_status.qr_base64}
                  alt="QR Telegram"
                  className="w-24 h-24 rounded-lg bg-white p-1.5 shrink-0"
                />
                <div className="space-y-2 text-xs">
                  <p className="font-semibold text-sm">
                    Telegram Deep-Link: {state.telegram_status.link_code}
                  </p>
                  <p style={{ color: "var(--text-muted)" }}>
                    Estado: {state.telegram_status.linked ? `Conectado (Chat ${state.telegram_status.chat_id})` : "Pendiente de vincular"}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <a
                      href={state.telegram_status.deep_link}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-secondary !py-1.5 !text-xs"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      Abrir Bot
                    </a>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={handleDiscoverTelegram}
                      className="btn-primary !py-1.5 !text-xs"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      Detectar vinculación
                    </button>
                  </div>
                </div>
              </div>

              {/* Collapsed Admin Advanced Credentials Accordion */}
              <div className="rounded-xl border" style={{ borderColor: "var(--border)" }}>
                <button
                  type="button"
                  onClick={() => setShowAdminCreds((v) => !v)}
                  className="w-full px-4 py-3 flex items-center justify-between text-xs font-semibold"
                >
                  <span>Configuración Avanzada (Admin / Credenciales de Servidor)</span>
                  {showAdminCreds ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {showAdminCreds && (
                  <form
                    onSubmit={handleSaveAdminCreds}
                    className="px-4 pb-4 pt-2 space-y-3 border-t text-xs"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <p style={{ color: "var(--text-muted)" }}>
                      Solo para administradores del hackathon: inyecta o reemplaza llaves en tiempo de ejecución (.env).
                    </p>
                    <label className="space-y-1 block">
                      <span>GEMINI_API_KEY ({state.runtime_status.gemini_configured ? "Configurada" : "Respaldo local"})</span>
                      <input
                        type="password"
                        className="clinical-input"
                        placeholder="AIzaSy... (dejar vacío para no cambiar)"
                        value={adminGeminiKey}
                        onChange={(e) => setAdminGeminiKey(e.target.value)}
                      />
                    </label>
                    <label className="space-y-1 block">
                      <span>TELEGRAM_BOT_TOKEN ({state.runtime_status.telegram_bot_configured ? "Configurado" : "Vista previa"})</span>
                      <input
                        type="password"
                        className="clinical-input"
                        placeholder="123456:ABC... (dejar vacío para no cambiar)"
                        value={adminTgToken}
                        onChange={(e) => setAdminTgToken(e.target.value)}
                      />
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <label className="space-y-1 block">
                        <span>Bot Username</span>
                        <input
                          className="clinical-input"
                          value={adminTgUser}
                          onChange={(e) => setAdminTgUser(e.target.value)}
                        />
                      </label>
                      <label className="space-y-1 block">
                        <span>Chat ID manual</span>
                        <input
                          className="clinical-input tabular-nums"
                          value={adminChatId}
                          onChange={(e) => setAdminChatId(e.target.value)}
                        />
                      </label>
                    </div>
                    <button type="submit" disabled={busy} className="btn-secondary w-full">
                      Guardar credenciales Admin
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ================= TAB 5: SIMULADOR DEMO (PITCH FAIL-SAFE) ================= */}
        {activeTab === "simulador" && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Simulador Demo Fail-Safe (3 Actos del Pitch)</h2>
                <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                  Ejecuta el pipeline real completo (Biomarcadores + LLM + SQLite + Edge-TTS + Telegram) incluso si falla el micrófono en Zoom.
                </p>
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={handleResetDemo}
                className="btn-secondary text-xs"
              >
                <RotateCcw className="w-4 h-4" />
                Reiniciar Demo (Estado Limpio)
              </button>
            </div>

            {/* 3 Theatrical Scenario Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {state.demo_scenarios.map((sc, idx) => (
                <article
                  key={sc.id}
                  className="clinical-card p-5 flex flex-col justify-between gap-4"
                  style={{
                    borderTopWidth: "4px",
                    borderTopColor:
                      idx === 2 ? "var(--danger)" : idx === 1 ? "var(--amber)" : "var(--emerald)",
                  }}
                >
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold">{sc.title}</h3>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                      {sc.subtitle}
                    </p>
                    <p
                      className="text-xs italic p-2.5 rounded-lg"
                      style={{ backgroundColor: "var(--surface-subtle)" }}
                    >
                      “{sc.transcript}”
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleRunScenario(sc.id)}
                    className={idx === 2 ? "btn-danger w-full" : "btn-primary w-full"}
                  >
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    Ejecutar {idx === 0 ? "Acto 1" : idx === 1 ? "Acto 2" : "Acto 3 S.O.S."}
                  </button>
                </article>
              ))}
            </div>

            {/* Custom Free-Text Test Box */}
            <form onSubmit={handleRunCustomText} className="clinical-card p-4 flex flex-col sm:flex-row gap-3">
              <input
                className="clinical-input flex-1"
                placeholder="Prueba texto libre personalizado como Don Manuel (ej. 'Me encanta escuchar boleros de Los Panchos...')"
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
              />
              <button type="submit" disabled={busy || !customText.trim()} className="btn-primary shrink-0">
                <Send className="w-4 h-4" />
                Probar turno libre
              </button>
            </form>

            {/* Last Executed Turn Inspector */}
            {lastTurnResult && (
              <section className="clinical-card p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold">Inspector del Último Turno Ejecutado</h3>
                  <div className="flex flex-wrap items-center gap-2">
                    {lastTurnResult.audio_data_uri && (
                      <button
                        type="button"
                        onClick={() => playAudio(lastTurnResult.audio_data_uri)}
                        className="btn-secondary !py-1.5 !text-xs"
                      >
                        <Volume2 className="w-3.5 h-3.5" />
                        Escuchar voz Edge-TTS
                      </button>
                    )}
                    {lastTurnResult.engine_used && (
                      <span
                        className="text-xs px-2.5 py-1 rounded-full font-medium"
                        style={{ backgroundColor: "var(--emerald-soft)", color: "var(--emerald)" }}
                      >
                        Motor: {lastTurnResult.engine_used}
                      </span>
                    )}
                    <span
                      className="text-xs px-2.5 py-1 rounded-full font-medium"
                      style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
                    >
                      Tema visual: {THEME_BADGE_LABELS[lastTurnResult.memory_album_theme] || lastTurnResult.memory_album_theme}
                    </span>
                  </div>
                </div>

                {lastTurnResult.emergency_triggered && (
                  <div
                    className="p-3 rounded-xl text-xs font-semibold flex items-center gap-2"
                    style={{ backgroundColor: "var(--danger-soft)", color: "var(--danger)" }}
                  >
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    Alerta Roja S.O.S. Nivel 3 activada · Validación de Naomi Feil (0 preguntas cognitivas).
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="p-3.5 rounded-xl space-y-1.5" style={{ backgroundColor: "var(--surface-subtle)" }}>
                    <span className="font-semibold block">Respuesta de MemoriaViva</span>
                    <p className="text-sm leading-relaxed">{lastTurnResult.assistant_reply}</p>
                    {lastTurnResult.dinner_conversation_tip && (
                      <p className="pt-1" style={{ color: "var(--text-muted)" }}>
                        <strong>Sugerencia cena:</strong> {lastTurnResult.dinner_conversation_tip}
                      </p>
                    )}
                  </div>
                  <div className="p-3.5 rounded-xl grid grid-cols-2 gap-2 tabular-nums" style={{ backgroundColor: "var(--surface-subtle)" }}>
                    <div>
                      <span style={{ color: "var(--text-muted)" }}>MATTR:</span>
                      <div className="text-base font-bold">{lastTurnResult.biomarkers?.mattr.mattr.toFixed(3)}</div>
                    </div>
                    <div>
                      <span style={{ color: "var(--text-muted)" }}>Pausa Máx:</span>
                      <div className="text-base font-bold">{lastTurnResult.biomarkers?.pauses.max_pause_sec.toFixed(2)}s</div>
                    </div>
                    <div>
                      <span style={{ color: "var(--text-muted)" }}>Anómicas (&gt;=2s):</span>
                      <div className="text-base font-bold">{lastTurnResult.biomarkers?.pauses.anomic_count}</div>
                    </div>
                    <div>
                      <span style={{ color: "var(--text-muted)" }}>Periodo Circadiano:</span>
                      <div className="text-xs font-semibold mt-1">{lastTurnResult.biomarkers?.circadian_period}</div>
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* SQLite Turn History Table */}
            <section className="clinical-card p-5 space-y-3">
              <h3 className="text-sm font-semibold">
                Historial de Turnos Persistidos en SQLite ({state.recent_turns.length})
              </h3>
              {state.recent_turns.length === 0 ? (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Ejecuta alguno de los 3 actos o conversa en el Modo Kiosco para ver los registros en vivo.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead>
                      <tr className="border-b" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
                        <th className="py-2 pr-3">Hora</th>
                        <th className="py-2 pr-3">MATTR</th>
                        <th className="py-2 pr-3">Pausa Máx</th>
                        <th className="py-2 pr-3">Anómicas</th>
                        <th className="py-2 pr-3">Emoción</th>
                        <th className="py-2 pr-3">Tema Visual</th>
                        <th className="py-2">Nivel</th>
                      </tr>
                    </thead>
                    <tbody className="tabular-nums">
                      {state.recent_turns.map((t) => (
                        <tr key={t.id} className="border-b" style={{ borderColor: "var(--border)" }}>
                          <td className="py-2 pr-3">{formatLocalTime(t.created_at)}</td>
                          <td className="py-2 pr-3 font-medium">{t.mattr.toFixed(3)}</td>
                          <td className="py-2 pr-3">{t.max_pause_sec.toFixed(2)}s</td>
                          <td className="py-2 pr-3">{t.anomic_count}</td>
                          <td className="py-2 pr-3 capitalize">{t.emotional_state.replace("_", " ")}</td>
                          <td className="py-2 pr-3">{THEME_BADGE_LABELS[t.memory_album_theme] || t.memory_album_theme}</td>
                          <td className="py-2 font-semibold">
                            <span
                              style={{
                                color:
                                  t.alert_level === 3
                                    ? "var(--danger)"
                                    : t.alert_level === 2
                                      ? "var(--amber)"
                                      : "var(--emerald)",
                              }}
                            >
                              N{t.alert_level}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
};
