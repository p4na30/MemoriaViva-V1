import React, { createContext, useCallback, useContext, useState } from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";

type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastContextValue {
  notify: (message: string, kind?: ToastKind) => void;
}

const ToastContext = createContext<ToastContextValue>({ notify: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const notify = useCallback((message: string, kind: ToastKind = "success") => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((prev) => [...prev.slice(-3), { id, kind, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  const dismiss = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-[calc(100vw-2rem)] pointer-events-none"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto clinical-card px-4 py-3 flex items-start gap-3 text-sm"
            style={{
              borderLeftWidth: "4px",
              borderLeftColor:
                t.kind === "success"
                  ? "var(--emerald)"
                  : t.kind === "error"
                    ? "var(--danger)"
                    : "var(--primary)",
            }}
          >
            {t.kind === "success" && (
              <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "var(--emerald)" }} />
            )}
            {t.kind === "error" && (
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "var(--danger)" }} />
            )}
            {t.kind === "info" && (
              <Info className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "var(--primary)" }} />
            )}
            <span className="flex-1 leading-snug">{t.message}</span>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="opacity-60 hover:opacity-100 p-0.5"
              aria-label="Cerrar notificación"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};
