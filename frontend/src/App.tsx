import React, { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { api } from "./api/client";
import type { AppState, ThemeMode } from "./types";
import { OnboardingWizard } from "./components/OnboardingWizard";
import { ElderKioskView } from "./components/ElderKioskView";
import { CaregiverDashboard } from "./components/CaregiverDashboard";
import { useToast } from "./components/ToastProvider";

export default function App() {
  const [state, setState] = useState<AppState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = window.localStorage.getItem("mv_theme");
    return saved === "dark" ? "dark" : "light";
  });
  const { notify } = useToast();

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("mv_theme", theme);
  }, [theme]);

  const loadState = useCallback(async () => {
    try {
      setError(null);
      const data = await api.getState();
      setState(data);
      if (data.account.theme_mode === "dark" || data.account.theme_mode === "light") {
        const localSaved = window.localStorage.getItem("mv_theme");
        if (!localSaved) setTheme(data.account.theme_mode);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo conectar con el backend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadState();
  }, [loadState]);

  const handleToggleTheme = async () => {
    const next: ThemeMode = theme === "light" ? "dark" : "light";
    setTheme(next);
    try {
      const res = await api.updateSettings({ theme_mode: next });
      setState(res.state);
    } catch {
      // keep local preference even if offline
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 p-6">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: "var(--primary)" }} />
        <p className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>
          Iniciando MemoriaViva RISE...
        </p>
      </div>
    );
  }

  if (error || !state) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="clinical-card max-w-md w-full p-6 text-center space-y-4">
          <h1 className="text-lg font-semibold">Error de conexión con el servidor</h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {error || "Verifica que FastAPI esté activo en el puerto configurado."}
          </p>
          <button
            type="button"
            className="btn-primary mx-auto"
            onClick={() => {
              setLoading(true);
              loadState();
            }}
          >
            <RefreshCw className="w-4 h-4" />
            Reintentar conexión
          </button>
        </div>
      </div>
    );
  }

  // Vista A: Guided 4-step Onboarding + 1-Click Demo
  if (!state.account.is_registered) {
    return (
      <OnboardingWizard
        state={state}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        onStateChange={setState}
      />
    );
  }

  // Vista B: Immersive Elder Kiosk Mode (Photo Frame + Dual Voice + Visual Anchor)
  if (state.account.kiosk_locked) {
    return (
      <ElderKioskView
        state={state}
        onStateChange={setState}
        onUnlocked={(nextState) => {
          setState(nextState);
          notify("Panel Familiar desbloqueado.", "info");
        }}
      />
    );
  }

  // Vista C: Caregiver & Clinician Dashboard (5 sections + RISE Governance)
  return (
    <CaregiverDashboard
      state={state}
      theme={theme}
      onToggleTheme={handleToggleTheme}
      onStateChange={setState}
      onLockKiosk={async () => {
        try {
          await api.lockKiosk();
          const fresh = await api.getState();
          setState(fresh);
          notify("Modo Kiosco activado para el adulto mayor.", "success");
        } catch (err) {
          notify(err instanceof Error ? err.message : "Error al activar Modo Kiosco", "error");
        }
      }}
    />
  );
}
