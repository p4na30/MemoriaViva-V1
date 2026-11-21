import React, { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  ExternalLink,
  HeartHandshake,
  ImagePlus,
  Loader2,
  Moon,
  QrCode,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Sun,
  Zap,
} from "lucide-react";
import { api, apiUrl } from "../api/client";
import type { AppState, ThemeMode } from "../types";
import { useToast } from "./ToastProvider";

interface Props {
  state: AppState;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onStateChange: (state: AppState) => void;
}

const STEP_LABELS = [
  "Perfil y PIN",
  "Puente Telegram",
  "Motor IA RISE",
  "Álbum Familiar",
];

export const OnboardingWizard: React.FC<Props> = ({
  state,
  theme,
  onToggleTheme,
  onStateChange,
}) => {
  const { notify } = useToast();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [showBioAccordion, setShowBioAccordion] = useState(false);

  // Step 1 — 6 essential fields + optional collapsible details
  const [nombreCompleto, setNombreCompleto] = useState("");
  const [nombrePreferido, setNombrePreferido] = useState("");
  const [caregiverName, setCaregiverName] = useState("");
  const [caregiverUsername, setCaregiverUsername] = useState("");
  const [pin, setPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [consentAccepted, setConsentAccepted] = useState(true);
  const [voiceGender, setVoiceGender] = useState<"male" | "female">("male");

  // Optional biographical details
  const [edad, setEdad] = useState("72");
  const [ciudad, setCiudad] = useState("San Pedro Tlaquepaque, Jalisco");
  const [ocupacion, setOcupacion] = useState("");
  const [pareja, setPareja] = useState("");
  const [hijosDetalle, setHijosDetalle] = useState("");
  const [anclasText, setAnclasText] = useState("");

  // Step 4 — Album upload state
  const [uploadTheme, setUploadTheme] = useState("familia_hogar");
  const [photos, setPhotos] = useState(state.photos);

  const loadDonManuelExample = () => {
    setNombreCompleto("Manuel González Magaña");
    setNombrePreferido("Don Manuel");
    setCaregiverName("Laura González");
    setCaregiverUsername("laura.gonzalez");
    setPin("1234");
    setConfirmPin("1234");
    setEdad("72");
    setCiudad("San Pedro Tlaquepaque, Jalisco");
    setOcupacion("Maquinista y mecánico en Ferrocarriles Nacionales durante 32 años");
    setPareja("Doña Carmen (se conocieron en la plaza de Tlaquepaque en 1975)");
    setHijosDetalle("Rocío vive en Manzanillo, Colima y es maestra de primaria");
    setAnclasText(
      "Su primer automóvil fue un Vocho azul 1974\nBoleros del Trío Los Panchos y Agustín Lara\nViaje familiar a Playa Miramar, Manzanillo en 1988"
    );
    setConsentAccepted(true);
    notify("Datos de ejemplo de Don Manuel precargados.", "info");
  };

  const handleQuickDemoActivate = async () => {
    setBusy(true);
    try {
      const res = await api.completeOnboarding({
        use_demo_persona: true,
        consent_accepted: true,
        launch_kiosk: true,
      });
      onStateChange(res.state);
      notify(
        "Caso clínico Don Manuel activado con 10 postales y serie de 21 días (PIN: 1234).",
        "success"
      );
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al activar demo.", "error");
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
      notify(err instanceof Error ? err.message : "No se pudo consultar Telegram.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleGenerateSamples = async () => {
    setBusy(true);
    try {
      const res = await api.generateSamplePhotos();
      setPhotos(res.photos);
      const fresh = await api.getState();
      onStateChange(fresh);
      notify(`Se cargaron ${res.count} postales nostálgicas etiquetadas en el álbum.`, "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al generar muestras.", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleUploadFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    setBusy(true);
    try {
      let latestPhotos = photos;
      for (const file of Array.from(fileList)) {
        const res = await api.uploadPhoto(file, file.name.replace(/\.[^.]+$/, ""), "", uploadTheme);
        latestPhotos = res.photos;
      }
      setPhotos(latestPhotos);
      notify(`${fileList.length} fotografía(s) guardadas en el álbum familiar.`, "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al subir fotografías.", "error");
    } finally {
      setBusy(false);
    }
  };

  const validateStep1 = (): boolean => {
    if (!nombreCompleto.trim() || !nombrePreferido.trim() || !caregiverName.trim()) {
      notify("Completa los campos esenciales del adulto mayor y familiar responsable.", "error");
      return false;
    }
    if (pin.trim().length < 4) {
      notify("El PIN de bloqueo debe tener al menos 4 dígitos.", "error");
      return false;
    }
    if (pin.trim() !== confirmPin.trim()) {
      notify("Los campos de PIN y Confirmar PIN no coinciden.", "error");
      return false;
    }
    if (!consentAccepted) {
      notify("Acepta el Consentimiento Dual RISE para continuar.", "error");
      return false;
    }
    return true;
  };

  const handleFinishManual = async () => {
    if (!validateStep1()) {
      setStep(1);
      return;
    }
    setBusy(true);
    try {
      const anchors = anclasText
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);
      const res = await api.completeOnboarding({
        use_demo_persona: false,
        nombre_completo: nombreCompleto,
        nombre_preferido: nombrePreferido,
        caregiver_name: caregiverName,
        caregiver_username: caregiverUsername || "familiar",
        pin,
        edad: Number(edad) || 72,
        ciudad_residencia: ciudad,
        ocupacion_historica: ocupacion,
        esposa_o_pareja: pareja,
        hijos_detalle: hijosDetalle,
        anclas_de_reminiscencia: anchors,
        consent_accepted: consentAccepted,
        voice_gender: voiceGender,
        launch_kiosk: true,
      });
      onStateChange(res.state);
      notify("Configuración guardada en SQLite. Activando Modo Kiosco.", "success");
    } catch (err) {
      notify(err instanceof Error ? err.message : "Error al finalizar onboarding.", "error");
    } finally {
      setBusy(false);
    }
  };

  const photoCount = photos.length;
  const minPhotos = state.min_screensaver_photos || 10;
  const progressPct = Math.min(100, Math.round((photoCount / minPhotos) * 100));

  return (
    <div className="min-h-screen py-8 px-4 flex flex-col items-center">
      <div className="w-full max-w-2xl space-y-6">
        {/* Top Bar */}
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: "var(--primary-soft)", color: "var(--primary)" }}
            >
              <HeartHandshake className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">MemoriaViva RISE</h1>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Terapia de Reminiscencia y Biomarcadores Pasivos
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onToggleTheme}
              className="btn-secondary !px-3"
              aria-label="Alternar tema Día/Noche"
            >
              {theme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
              <span className="hidden sm:inline">{theme === "light" ? "Noche" : "Día"}</span>
            </button>
          </div>
        </header>

        {/* 1-Click Judge / Demo Persona Hero Banner */}
        <section
          className="clinical-card p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
          style={{
            backgroundColor: "var(--primary-soft)",
            borderColor: "color-mix(in srgb, var(--primary) 30%, var(--border))",
          }}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--primary)" }}>
              <Sparkles className="w-3.5 h-3.5" />
              Inicio Rápido para Jurado y Demo en Vivo
            </div>
            <p className="text-sm font-medium">
              Activa al instante el caso clínico de <strong>Don Manuel (72 años)</strong> con 10 postales familiares y serie longitudinal de 21 días.
            </p>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={handleQuickDemoActivate}
            className="btn-primary shrink-0 w-full sm:w-auto"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            Activación Rápida Demo (1 Clic)
          </button>
        </section>

        {/* 4-Bar Horizontal Stepper */}
        <nav aria-label="Pasos de configuración" className="grid grid-cols-4 gap-2">
          {STEP_LABELS.map((label, index) => {
            const idx = index + 1;
            const active = step === idx;
            const done = step > idx;
            return (
              <button
                key={label}
                type="button"
                onClick={() => setStep(idx)}
                className="text-left group focus:outline-none"
              >
                <div
                  className="h-1.5 rounded-full transition-all mb-1.5"
                  style={{
                    backgroundColor:
                      active || done ? "var(--primary)" : "var(--border)",
                    opacity: done ? 0.65 : 1,
                  }}
                />
                <span
                  className="text-xs font-medium block truncate"
                  style={{ color: active ? "var(--text)" : "var(--text-muted)" }}
                >
                  {idx}. {label}
                </span>
              </button>
            );
          })}
        </nav>

        {/* Main Card */}
        <main className="clinical-card p-6 space-y-5">
          {step === 1 && (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold">1. Perfil esencial y bloqueo seguro</h2>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    Solo 6 campos esenciales. El PIN protege el Panel Clínico del cuidador.
                  </p>
                </div>
                <button type="button" onClick={loadDonManuelExample} className="btn-secondary text-xs">
                  Cargar ejemplo (Don Manuel)
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <label className="space-y-1.5 text-sm">
                  <span className="font-medium">Nombre completo del adulto mayor</span>
                  <input
                    className="clinical-input"
                    placeholder="Ej. Manuel González Magaña"
                    value={nombreCompleto}
                    onChange={(e) => setNombreCompleto(e.target.value)}
                  />
                </label>
                <label className="space-y-1.5 text-sm">
                  <span className="font-medium">Cómo prefiere que le llamen</span>
                  <input
                    className="clinical-input"
                    placeholder="Ej. Don Manuel"
                    value={nombrePreferido}
                    onChange={(e) => setNombrePreferido(e.target.value)}
                  />
                </label>
                <label className="space-y-1.5 text-sm">
                  <span className="font-medium">Familiar responsable</span>
                  <input
                    className="clinical-input"
                    placeholder="Ej. Laura González"
                    value={caregiverName}
                    onChange={(e) => setCaregiverName(e.target.value)}
                  />
                </label>
                <label className="space-y-1.5 text-sm">
                  <span className="font-medium">Usuario familiar</span>
                  <input
                    className="clinical-input"
                    placeholder="Ej. laura.gonzalez"
                    value={caregiverUsername}
                    onChange={(e) => setCaregiverUsername(e.target.value)}
                  />
                </label>
                <label className="space-y-1.5 text-sm">
                  <span className="font-medium">PIN de bloqueo (4+ dígitos)</span>
                  <input
                    type="password"
                    inputMode="numeric"
                    className="clinical-input tabular-nums"
                    placeholder="1234"
                    value={pin}
                    onChange={(e) => setPin(e.target.value)}
                  />
                </label>
                <label className="space-y-1.5 text-sm">
                  <span className="font-medium">Confirmar PIN</span>
                  <input
                    type="password"
                    inputMode="numeric"
                    className="clinical-input tabular-nums"
                    placeholder="1234"
                    value={confirmPin}
                    onChange={(e) => setConfirmPin(e.target.value)}
                  />
                </label>
              </div>

              {/* Progressive Disclosure Accordion */}
              <div className="rounded-xl border" style={{ borderColor: "var(--border)" }}>
                <button
                  type="button"
                  onClick={() => setShowBioAccordion((v) => !v)}
                  className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium"
                >
                  <span>Detalles biográficos y recuerdos favoritos (opcional)</span>
                  {showBioAccordion ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                {showBioAccordion && (
                  <div className="px-4 pb-4 pt-1 grid grid-cols-1 sm:grid-cols-2 gap-3 border-t" style={{ borderColor: "var(--border)" }}>
                    <label className="space-y-1 text-xs">
                      <span style={{ color: "var(--text-muted)" }}>Edad</span>
                      <input className="clinical-input" value={edad} onChange={(e) => setEdad(e.target.value)} />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span style={{ color: "var(--text-muted)" }}>Ciudad de residencia</span>
                      <input className="clinical-input" value={ciudad} onChange={(e) => setCiudad(e.target.value)} />
                    </label>
                    <label className="space-y-1 text-xs sm:col-span-2">
                      <span style={{ color: "var(--text-muted)" }}>Oficio o profesión histórica</span>
                      <input className="clinical-input" value={ocupacion} onChange={(e) => setOcupacion(e.target.value)} />
                    </label>
                    <label className="space-y-1 text-xs sm:col-span-2">
                      <span style={{ color: "var(--text-muted)" }}>Pareja / familiares clave</span>
                      <input className="clinical-input" value={pareja} onChange={(e) => setPareja(e.target.value)} />
                    </label>
                    <label className="space-y-1 text-xs sm:col-span-2">
                      <span style={{ color: "var(--text-muted)" }}>Hijos / nietos</span>
                      <input className="clinical-input" value={hijosDetalle} onChange={(e) => setHijosDetalle(e.target.value)} />
                    </label>
                    <label className="space-y-1 text-xs sm:col-span-2">
                      <span style={{ color: "var(--text-muted)" }}>Anclas de memoria (una por línea)</span>
                      <textarea
                        rows={3}
                        className="clinical-input"
                        value={anclasText}
                        onChange={(e) => setAnclasText(e.target.value)}
                      />
                    </label>
                    <label className="space-y-1 text-xs">
                      <span style={{ color: "var(--text-muted)" }}>Voz de Edge-TTS (-15%, -5Hz)</span>
                      <select
                        className="clinical-input"
                        value={voiceGender}
                        onChange={(e) => setVoiceGender(e.target.value as "male" | "female")}
                      >
                        <option value="male">Voz cálida masculina (Jorge es-MX)</option>
                        <option value="female">Voz cálida femenina (Dalia es-MX)</option>
                      </select>
                    </label>
                  </div>
                )}
              </div>

              {/* Assisted Dual Consent Card */}
              <label
                className="flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer text-xs leading-relaxed"
                style={{ backgroundColor: "var(--surface-subtle)", borderColor: "var(--border)" }}
              >
                <input
                  type="checkbox"
                  checked={consentAccepted}
                  onChange={(e) => setConsentAccepted(e.target.checked)}
                  className="mt-0.5 accent-cyan-700"
                />
                <span>
                  <strong>Consentimiento Dual Asistido (Marco RISE):</strong> Confirmo que MemoriaViva es una herramienta de apoyo conversacional y seguimiento <em>no diagnóstico</em>. El audio se procesa en RAM (<strong>Zero-Raw-Cloud Audio</strong>) y el adulto mayor podrá escuchar la bienvenida de transparencia en cualquier momento desde el Kiosco.
                </span>
              </label>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-base font-semibold">2. Puente Familiar Telegram (Deep-Linking en 5s)</h2>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                  Cero fricción: no necesitas crear bots en @BotFather. Escanea el QR desde el celular del cuidador y pulsa <strong>Iniciar</strong> en Telegram.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 items-center">
                <div className="flex flex-col items-center p-4 rounded-xl border bg-white text-slate-900" style={{ borderColor: "var(--border)" }}>
                  <img
                    src={state.telegram_status.qr_base64}
                    alt="Código QR Telegram Deep-Link"
                    className="w-44 h-44 object-contain"
                  />
                  <span className="mt-2 text-xs font-mono font-semibold px-2.5 py-1 rounded-md bg-slate-100">
                    /start {state.telegram_status.link_code}
                  </span>
                </div>

                <div className="space-y-3 text-sm">
                  <div className="flex items-center gap-2">
                    <QrCode className="w-4 h-4" style={{ color: "var(--primary)" }} />
                    <span className="font-medium">Bot: @{state.telegram_status.bot_username}</span>
                  </div>
                  <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
                    Al vincularse, recibirás <strong>Nivel 1</strong> (Pulso diario con sugerencia para la cena), <strong>Nivel 2</strong> (Aviso preventivo de tendencia) y <strong>Nivel 3</strong> (Alerta Roja S.O.S.) sin exponer grabaciones ni transcripciones íntimas.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <a
                      href={state.telegram_status.deep_link}
                      target="_blank"
                      rel="noreferrer"
                      className="btn-secondary text-xs"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      Abrir en Telegram
                    </a>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={handleDiscoverTelegram}
                      className="btn-primary text-xs"
                    >
                      {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                      Detectar vinculación
                    </button>
                  </div>
                  {state.telegram_status.linked ? (
                    <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "var(--emerald)" }}>
                      <CheckCircle2 className="w-4 h-4" />
                      Vinculado correctamente (Chat ID {state.telegram_status.chat_id})
                    </div>
                  ) : (
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                      Puedes continuar ahora y vincular tu celular más tarde desde el Panel Familiar.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div>
                <h2 className="text-base font-semibold">3. Motor IA Listo (Zero-API-Key UX)</h2>
                <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
                  La arquitectura gestiona el motor conversacional de forma segura en el servidor sin pedir claves técnicas a la familia.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-4 rounded-xl border space-y-1.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-subtle)" }}>
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Cpu className="w-4 h-4" style={{ color: "var(--primary)" }} />
                    Gemini 2.5 Flash + Respaldo Local
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {state.runtime_status.gemini_configured
                      ? "Conectado vía variables seguras del servidor (Cloud Run / .env)."
                      : "Operando con respaldo gerontológico determinista local 100% funcional (puedes activar Gemini en .env o Configuración Avanzada)."}
                  </p>
                </div>

                <div className="p-4 rounded-xl border space-y-1.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-subtle)" }}>
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <ShieldCheck className="w-4 h-4" style={{ color: "var(--emerald)" }} />
                    Zero-Raw-Cloud Audio
                  </div>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    El audio se normaliza en RAM con ffmpeg y se descarta al instante. Los biomarcadores MATTR, pausas RMS (&gt;= 2.0s) y TF-IDF corren localmente.
                  </p>
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold">4. Álbum Familiar (Mínimo {minPhotos} fotos)</h2>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    El Modo Kiosco rota estas postales y sincroniza la imagen con lo que el adulto mayor conversa.
                  </p>
                </div>
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleGenerateSamples}
                  className="btn-secondary text-xs"
                >
                  {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  Completar con 10 postales de muestra
                </button>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-medium tabular-nums">
                  <span>Progreso del álbum</span>
                  <span>
                    {photoCount} / {minPhotos} fotos
                  </span>
                </div>
                <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "var(--surface-subtle)" }}>
                  <div
                    className="h-full transition-all"
                    style={{
                      width: `${progressPct}%`,
                      backgroundColor: photoCount >= minPhotos ? "var(--emerald)" : "var(--primary)",
                    }}
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 p-4 rounded-xl border border-dashed" style={{ borderColor: "var(--border)" }}>
                <ImagePlus className="w-5 h-5" style={{ color: "var(--primary)" }} />
                <div className="flex-1 min-w-[180px]">
                  <label className="text-xs font-medium block mb-1">Subir fotografías familiares</label>
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(e) => handleUploadFiles(e.target.files)}
                    className="text-xs w-full"
                  />
                </div>
                <select
                  className="clinical-input !w-auto text-xs"
                  value={uploadTheme}
                  onChange={(e) => setUploadTheme(e.target.value)}
                >
                  <option value="familia_hogar">Tema: Familia y Hogar</option>
                  <option value="ferrocarril">Tema: Ferrocarril / Oficio</option>
                  <option value="musica_boleros">Tema: Música y Boleros</option>
                  <option value="playa_manzanillo">Tema: Playa / Viajes</option>
                  <option value="mascotas">Tema: Mascotas</option>
                </select>
              </div>

              {photos.length > 0 && (
                <div className="grid grid-cols-5 gap-2">
                  {photos.slice(0, 10).map((p) => (
                    <div key={p.filename} className="relative aspect-[4/3] rounded-lg overflow-hidden border" style={{ borderColor: "var(--border)" }}>
                      <img src={apiUrl(p.url)} alt={p.title} className="w-full h-full object-cover" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Footer Navigation */}
          <div className="pt-4 border-t flex items-center justify-between gap-3" style={{ borderColor: "var(--border)" }}>
            <button
              type="button"
              disabled={step === 1 || busy}
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              className="btn-secondary"
            >
              <ArrowLeft className="w-4 h-4" />
              Anterior
            </button>

            {step < 4 ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  if (step === 1 && !validateStep1()) return;
                  setStep((s) => Math.min(4, s + 1));
                }}
                className="btn-primary"
              >
                Siguiente
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                disabled={busy}
                onClick={handleFinishManual}
                className="btn-primary"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                Finalizar y activar Modo Kiosco
              </button>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};
