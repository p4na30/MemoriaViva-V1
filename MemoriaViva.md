# MemoriaViva RISE — Mega-Contexto y Playbook Maestro para Agentes IA

**Plataforma Conversacional de Terapia de Reminiscencia y Detección Temprana No Invasiva de Deterioro Cognitivo Leve para Adultos Mayores**  
*Notre Dame's 2026 Global R.I.S.E. AI Hackathon — University of Notre Dame (DAC Initiative & Hesburgh Libraries), Universidad de Colima, Universidad de Guadalajara*  
*Referencia Oficial de Reglas y Rúbricas: https://libguides.library.nd.edu/global-rise-ai*

---

## 0. Propósito de este Documento (Instrucciones para la Nueva Sesión de Agentes)

Este documento contiene la **especificación técnica, clínica y de experiencia de usuario integral** para construir **MemoriaViva RISE** desde cero durante el tiempo oficial de competencia, cumpliendo al 100% con las **reglas oficiales, principios de uso de IA y las 5 categorías de la rúbrica de evaluación** de Notre Dame (`Usability UXD`, `R.I.S.E. Framework`, `Technical Merit`, `Innovation`, `Execution`).

### Stack Tecnológico Definido
- **Backend Clínico, Persistencia e IA:** **Python 3.11 + FastAPI + SQLite/JSON** (`numpy`, `scipy`, `scikit-learn`, `google-genai`, `edge-tts`, `fpdf2`, `qrcode`, `requests`, `Pillow`).
- **Frontend Web / PWA:** **React 18 + TypeScript + Vite + Tailwind CSS + Lucide Icons + Recharts** (Sistema de diseño **Clínico Moderno** con Modo Día y Modo Noche, navegación sin fricción y cero botones muertos).
- **Empaquetado Móvil (Android APK):** **Capacitor 6** compilado automáticamente en **GitHub Actions** (`ubuntu-latest` → `app-debug.apk` en cada push y `app-release.apk` firmado en tags `v*.*.*`).
- **Despliegue Cloud:** **Google Cloud Platform (Cloud Run + Cloud Storage Volume Mount)** en un solo contenedor Docker multi-stage que sirve tanto la API REST (`/api/*`) como el build estático de React (`frontend/dist/`).

> **Regla de Oro para el Agente Constructor:** Ejecuta la construcción siguiendo las **6 Fases Secuenciales** de la Sección 10, verificando pruebas automatizadas en cada fase y generando commits progresivos, limpios y auditables. Ningún botón o formulario de la interfaz puede ser decorativo: cada acción debe persistir datos reales en el backend (`SQLite` + archivos JSON en `data/`) y actualizar el estado de la interfaz de forma interactiva.

---

## 1. Alineación Oficial con las Rúbricas y Wicked Problems de Notre Dame (`global-rise-ai`)

El jurado evalúa cada proyecto con **5 criterios de igual peso (20% cada uno)**. Toda decisión de arquitectura, UX y código debe satisfacer explícitamente esta matriz:

### 1.1. Matriz de las 5 Rúbricas Oficiales de Evaluación (`Prizes & Judging`)

| Categoría Oficial (20% c/u) | Qué Evalúan los Jueces (LibGuide Notre Dame) | Cómo lo Cumple y Demuestra MemoriaViva RISE |
| :--- | :--- | :--- |
| **1. Usability (UXD)**<br>*Intuitive Interfaces* | *"Frictionless is the key."* Evalúa HCI y diseño UX para un usuario de primera vez: navegación clara, tipografía legible, arquitectura de información lógica y diseño accesible, seguro y sin fricción. | • **Zero-API-Key UX & Deep-Linking Telegram (`/start MV-XXXX`):** El usuario jamás toca `@BotFather` ni claves `AIzaSy...`; vincula su celular en 5 segundos con 1 clic/QR y entra con botón **"Activación Rápida Demo (Don Manuel)"**.<br>• **Modo Dual de Voz Inclusivo:** Toque simple con Auto-VAD (`3.8s`) **o** mantener presionado (`ESPACIO` / botón táctil), eliminando barreras para adultos mayores con artritis o temblor.<br>• **Estética Clínico Moderno (Día/Noche):** Alto contraste WCAG AAA, tipografía `Inter` (`tabular-nums`), íconos vectoriales limpios (`lucide-react`) y retroalimentación visual inmediata (toasts/badges). |
| **2. R.I.S.E. Framework**<br>*Responsible, Inclusive, Safe & Empowering* | Evalúa si el proyecto aborda un *"Wicked Problem"* anticipando consecuencias éticas, incluyendo usuarios diversos sin barreras, protegiendo contra daños físicos/emocionales/digitales y otorgando agencia real. | • Cumple las **4 dimensiones RISE** y mitiga **8+ sub-problemas oficiales (*Wicked Problems*)** de Notre Dame.<br>• **Control de Variables de Confusión y *Sundowning*:** Permite marcar en 1 clic factores médicos/circadianos (sueño, medicación, fatiga, horario vespertino) y registrar revisión **Human-in-the-Loop** antes de emitir el PDF clínico. |
| **3. Technical Merit**<br>*Complexity & Challenge* | *"Evaluates whether the 'Submit' actually works—e.g., sending data to a database or updating the app interactively."* Evalúa rigor de ingeniería, elección de frameworks, APIs y estructura de base de datos sin sobre-ingeniería inútil. | • **Persistencia Real Interactiva (`SQLite` + JSON):** Cada turno de voz, registro de onboarding, carga de fotos, variable de confusión, nota *Human-in-the-Loop* y simulación persiste en SQLite, actualiza en vivo la serie longitudinal de 21 días, recalcula Z-Scores y regenera el PDF.<br>• **Pipeline multimodal real:** Captura `MediaRecorder` + normalización `ffmpeg` en RAM + análisis acústico RMS + `MATTR` + `TF-IDF Cosine` + Gemini Structured Outputs + `Edge-TTS` + Telegram Bot bidireccional. |
| **4. Innovation**<br>*Original Problem & Solution* | *"The 'wow' factor: 'I haven't seen it done quite like that before.'"* Premia ángulos novedosos ante problemas sociales difíciles, alejándose de clones o apps genéricas. | • **Anclaje Visual Multimodal Bidireccional (Voz ↔ Foto):** Mientras el adulto mayor habla, el marco digital selecciona en tiempo real la fotografía familiar exacta del recuerdo evocado (`memory_album_theme` / etiquetas); y al rotar una foto, la IA puede iniciar charla sobre esa postal.<br>• **Evaluación Neuropsicológica Invisible + Aura de Respiración Emocional** con aprendizaje continuo (*Biographical RAG-Lite*). |
| **5. Execution**<br>*Finished & Polished* | *"If a team built a beautiful interface but clicking the buttons does nothing, they score low here."* Evalúa completitud tangible de principio a fin sin crasheos ni funciones rotas que haya que saltar en el demo. | • **Flujo End-to-End 100% Funcional + Modo Fail-Safe:** Todos los botones tienen endpoint real y test E2E. Si en el Zoom en vivo falla el micrófono o la red, los 3 actos del **Simulador Demo** inyectan ondas reales precalibradas y ejecutan todo el pipeline sin fallar jamás. |

---

### 1.2. Mapeo Exacto con los *"Wicked Problems — RISE Frames"* Oficiales (`/overview`) y Reglas de Uso de IA (`/rules`)

La guía oficial de Notre Dame define 12 sub-problemas dentro de las 4 dimensiones RISE y exige cumplir los principios **Use of AI** (*Identify Your Tools*, *Ultimate Responsibility*, *Human-in-the-Loop*, *Protect Everyone's Rights*):

| Dimensión RISE | Wicked Problem Oficial (LibGuide ND) | Solución Técnica e Implementación en MemoriaViva RISE |
| :--- | :--- | :--- |
| **R — Responsible** | • *Governance and accountability gaps*<br>• *Ethical misuse of AI systems*<br>• *Environmental cost of training* | 1. **Apoyo Clínico No Diagnóstico + *Human-in-the-Loop*:** Prohibido emitir diagnósticos automatizados. El cuidador/geriatra dispone de un control de **Revisión Humana (*Human-in-the-Loop*)** para aprobar, descartar o agregar contexto clínico (ej. *"Durmió mal anoche"*) a cada tendencia antes de exportar el PDF.<br>2. **Cómputo Ligero y Sostenible:** Los 3 biomarcadores (`MATTR`, RMS Pauses, `TF-IDF`) se calculan con algoritmos matemáticos locales en CPU ($O(N)$) sin entrenar modelos pesados, usando `gemini-2.5-flash` únicamente para generación conversacional breve ($\le 35$ palabras). |
| **I — Inclusive** | • *Language and cultural exclusion*<br>• *Unequal access to AI tools*<br>• *Bias in evaluation systems* | 1. **Inclusión Lingüística y Cultural:** Calibrado para español mexicano coloquial e historia cultural local (boleros, oficios, tradiciones familiares) y adaptado a **presbiacusia** (`Edge-TTS` a `-15%` velocidad y `-5Hz` tono) y lentitud de evocación (`Extended VAD` de `3.8s`).<br>2. **Eliminación de Sesgo Socioeconómico/Educativo:** A diferencia de pruebas estandarizadas que penalizan baja escolaridad, el **Z-Score de Línea Base Personal (21 días)** compara al adulto mayor únicamente contra su propio vocabulario histórico. |
| **S — Safe** | • *Data privacy breaches*<br>• *Adversarial attacks and misuse*<br>• *Misinformation* | 1. **Zero-Raw-Cloud Audio:** El audio `.wav`/`.webm` se procesa en memoria RAM y se destruye inmediatamente; jamás se almacena audio crudo ni se envían transcripciones íntimas completas por Telegram (*Abstract Summary Filter*).<br>2. **Guardrails Clínicos y Contención de Crisis:** El sistema prohíbe dar consejos farmacológicos. Ante desorientación aguda o angustia, suspende preguntas, aplica **Terapia de Validación de Naomi Feil** y dispara **Alerta Roja S.O.S. (Nivel 3)** en Telegram. |
| **E — Empowering** | • *Digital literacy gaps*<br>• *Communities excluded from AI ownership*<br>• *Human augmentation vs displacement* | 1. **Cero Barrera de Alfabetización Digital:** Para el adulto mayor, la app es un marco de fotos familiar donde solo mantiene presionada la tecla `ESPACIO` o un botón táctil.<br>2. **Soberanía de Datos y Puente Humano:** La IA **no reemplaza** a la familia ni al médico: empodera al familiar enviándole una sugerencia de conversación para la cena y mantiene la propiedad de su memoria biográfica en una base local auditable. |

---

## 2. Arquitectura del Sistema y Estructura del Repositorio

```text
MemoriaViva/
├── backend/
│   ├── main.py                  # Servidor FastAPI (/api/* + sirve frontend/dist estático)
│   ├── config.py                # Umbrales clínicos, rutas, catálogo de herramientas IA y .env
│   ├── database.py              # Persistencia SQLite (sesiones, revisiones Human-in-the-Loop, historial)
│   ├── biomarkers.py            # Motor matemático MATTR, Pausas Anómicas, TF-IDF y Z-Score 21 días
│   ├── audio_engine.py          # Normalización WAV en RAM (ffmpeg), análisis RMS, STT Gemini y Edge-TTS
│   ├── llm_companion.py         # Prompts gerontológicos (Reminiscencia + Feil + Biographical RAG-Lite)
│   ├── telegram_notifier.py     # Conector de 3 niveles con Telegram + QR + autodetección Chat ID
│   ├── pdf_report.py            # Generador de Reporte Clínico en PDF (incluye notas Human-in-the-Loop)
│   ├── storage_manager.py       # Gestión de cuenta/PIN SHA-256, perfiles JSON y álbum de 10+ fotos
│   └── tests/                   # Suite de pruebas unitarias e integración E2E
│       ├── test_biomarkers.py
│       ├── test_audio_and_llm.py
│       └── test_api_e2e.py
├── frontend/
│   ├── package.json             # React 18, Vite, Tailwind CSS, Lucide React, Recharts, Capacitor 6
│   ├── vite.config.ts
│   ├── capacitor.config.js      # Configuración Android APK (org.memoriaviva.rise)
│   ├── scripts/
│   │   └── configure-android.mjs # Inyecta RECORD_AUDIO, WebView getUserMedia, WAKE_LOCK y firma Release
│   └── src/
│       ├── App.tsx              # Barra superior sin fricción + Enrutador de 3 vistas + Tema Día/Noche
│       ├── api/client.ts        # Cliente HTTP hacia FastAPI (origen relativo o VITE_API_URL en APK)
│       ├── components/
│       │   ├── OnboardingWizard.tsx      # Vista A: 4 pasos centrados + 1-Click Demo Persona
│       │   ├── ElderKioskView.tsx        # Vista B: Protector 10+ fotos + PTT Dual + Aura + Modal PIN
│       │   ├── CaregiverDashboard.tsx    # Vista C: 5 secciones (Resumen, Álbum, Gobernanza RISE, Ajustes, Demo)
│       │   └── RiseGovernancePanel.tsx   # Human-in-the-Loop Review + AI Tools Disclosure + Ética RISE
│       └── styles/theme.css     # Tokens CSS Clínico Moderno (Día / Noche)
├── data/
│   ├── memoriaviva.db           # Base de datos SQLite autogenerada (turnos, revisiones humanas, bitácora)
│   ├── account_config.json      # Estado de registro, hash PIN, perfil activo, intervalo de rotación
│   ├── history_21_days.json     # Serie semilla longitudinal de 21 días
│   ├── profiles/
│   │   └── don_manuel_simulacion.json
│   └── photos/                  # Álbum de mínimo 10 fotografías por perfil
├── Dockerfile                   # Multi-stage build (Node 20 compila React -> Python 3.11 sirve FastAPI)
├── docker-compose.yml
└── .github/
    └── workflows/
        └── build-apk.yml        # Compila APK Debug (Artifact) y APK Release firmado (GitHub Releases)
```

---

## 3. Especificación Matemática y Científica del Motor Clínico (`backend/`)

### 3.1. Umbrales Clínicos Centralizados (`config.py`)
- `SILENCE_THRESHOLD_SEC = 3.8` (Tolerancia de silencio para fin de turno adaptativo).
- `ANOMIC_PAUSE_THRESHOLD_SEC = 2.0` (Umbral de pausa anómica intra-oracional).
- `MATTR_WINDOW_SIZE = 20` (Tamaño de ventana móvil sobre palabras de contenido).
- `SEMANTIC_REPEAT_THRESHOLD = 0.72` (Similitud coseno TF-IDF para bucle semántico).
- `CLINICAL_ALERT_PAUSE_INCREASE_PCT = 0.25` (+25% de incremento sostenido en pausas dispara Nivel 2).
- `CLINICAL_ALERT_MATTR_DROP_PCT = 0.20` (-20% de caída en riqueza léxica dispara Nivel 2).
- `MIN_SCREENSAVER_PHOTOS = 10` (Mínimo de fotos para el Modo Kiosco).
- `TTS_VOICE_MALE = "es-MX-JorgeNeural"`, `TTS_VOICE_FEMALE = "es-MX-DaliaNeural"`.
- `TTS_RATE = "-15%"` (~120 palabras/minuto), `TTS_PITCH = "-5Hz"` (compensación para presbiacusia).
- `GEMINI_MODEL_COMPANION = "gemini-2.5-flash"` (con fallback determinista local si no hay red o API key).

### 3.2. Biomarcador 1: Riqueza Léxica (`MATTR` en `biomarkers.py`)
1. Extraer tokens alfabéticos en minúsculas: `re.findall(r"\b[a-záéíóúüñ]+\b", text.lower())`.
2. Filtrar palabras funcionales (`STOPWORDS_ES`) y tokens con `len(w) <= 2` para obtener `content_words`.
3. Si `len(content_words) == 0`, devolver `0.0`.
4. Si `len(content_words) < window_size` (`20`), devolver `round(len(set(content_words)) / len(content_words), 3)`.
5. Si `len(content_words) >= window_size`, deslizar una ventana de tamaño `W = 20` desde `i = 0` hasta `len(content_words) - W` y promediar los TTR de cada ventana:
   $$\text{MATTR} = \frac{1}{N - W + 1} \sum_{i=0}^{N - W} \frac{|\text{unique}(w_i \dots w_{i+W-1})|}{W}$$
6. Detectar muletillas o circunloquios anómicos (`\beste\b`, `\beh+\b`, `\bmmm+\b`, `cómo se llama`, `la cosa esa`, `el aparato ese`, `se me fue el nombre`, `no me acuerdo cómo`).

### 3.3. Biomarcador 2: Pausas Anómicas Intra-Oracionales (`>= 2.0s`)
1. Entrada: lista `word_timestamps = [{"word": str, "start": float, "end": float}]`.
2. Para cada par consecutivo $(i-1, i)$:
   $$\text{gap}_i = \max(0.0, \text{start}_i - \text{end}_{i-1})$$
3. Si $\text{gap}_i \ge 2.0\text{ s}$, registrar un evento de vacilación anómica (`{"after_word": w_{i-1}, "before_word": w_i, "duration_sec": gap_i, "start_sec": end_{i-1}, "end_sec": start_i}`).
4. Devolver `mean_pause_sec`, `max_pause_sec`, `anomic_count` y `hesitation_events`.
5. **Análisis Acústico en Forma de Onda (RMS Energy en `audio_engine.py`):**
   - Sobre el audio WAV PCM 16 kHz en memoria RAM, dividir en ventanas de `30 ms`, calcular la energía RMS normalizada, aplicar umbral adaptativo de silencio y medir pausas reales intra-habla (descartando silencios iniciales y finales). Si la onda acústica registra una pausa `>= 2.0s` que el transcriptor web omitió, inyectarla en los `word_timestamps`.

### 3.4. Biomarcador 3: Repetición Semántica Intra-Sesión (`TF-IDF Cosine >= 0.72`)
1. Normalizar cada intervención del adulto mayor eliminando `STOPWORDS_ES` y palabras de encuadre conversacional (`oye`, `fíjate`, `conté`, `acuerdo`, `ayer`, `hoy`, `ratito`, `cuando`, `cómo`).
2. Vectorizar `[u_1, u_2, ..., u_{k-1}, u_{\text{actual}}]` con `TfidfVectorizer()` de `scikit-learn`.
3. Calcular similitud coseno entre $u_{\text{actual}}$ y todas las intervenciones previas de la sesión (`len >= 4` palabras).
4. Si $\max(\text{cosine\_similarity}) \ge 0.72$, marcar `is_repetition = True` y devolver el índice y texto del turno repetido.

### 3.5. Evaluación Longitudinal Auto-Referenciada (21 Días y Z-Score Personal)
Comparar la **Línea Base Personal** (primeros `14` días) frente a la **Ventana Reciente** (últimos `5` días):
- $\Delta \text{Pausa}_{\%} = \frac{\mu_{\text{pausa, rec}} - \mu_{\text{pausa, base}}}{\max(0.1, \mu_{\text{pausa, base}})}$, $\quad Z_{\text{pausa}} = \frac{\mu_{\text{pausa, rec}} - \mu_{\text{pausa, base}}}{\max(0.05, \sigma_{\text{pausa, base}})}$
- $\Delta \text{MATTR}_{\%} = \frac{\mu_{\text{mattr, base}} - \mu_{\text{mattr, rec}}}{\max(0.1, \mu_{\text{mattr, base}})}$, $\quad Z_{\text{mattr}} = \frac{\mu_{\text{mattr, rec}} - \mu_{\text{mattr, base}}}{\max(0.01, \sigma_{\text{mattr, base}})}$
- **Condición de Alerta Preventiva Nivel 2:**
  $$\Delta \text{Pausa}_{\%} \ge 0.25 \;\lor\; \Delta \text{MATTR}_{\%} \ge 0.20 \;\lor\; Z_{\text{pausa}} \ge 2.0 \;\lor\; Z_{\text{mattr}} \le -2.0$$

---

## 4. Motor Conversacional Gerontológico y Prompts Exactos (`llm_companion.py`)

### 4.1. Prompt Maestro Unificado (Reminiscencia + Feil + Biographical RAG-Lite)
```text
ERES "MEMORIAVIVA", UN COMPAÑERO CONVERSACIONAL CÁLIDO, EMPÁTICO Y REAL PARA {nombre_preferido} ({edad} AÑOS).

CONTEXTO BIOGRÁFICO ACTUAL DE {nombre_preferido} (ÚSALO SOLO COMO APOYO O SI ÉL LO MENCIONA/OLVIDA):
{patient_profile_json}

HISTORIAL RECIENTE DE LA CONVERSACIÓN ACTUAL:
{recent_dialogue_history}

ESTADO DE REPETICIÓN EN ESTE TURNO: {repetition_context}

REGLAS INQUEBRANTABLES DEL MARCO RISE PARA `assistant_reply`:
1. REGLA PRIORITARIA DE CONVERSACIÓN REAL: Responde SIEMPRE de forma directa, específica y cálida a lo que {nombre_preferido} acaba de decir en su último mensaje. NO cambies de tema ni lances datos al azar de su perfil si no vienen al caso.
2. BREVEDAD Y CLARIDAD GERIÁTRICA: `assistant_reply` NUNCA debe superar las 35 palabras (máximo 2 o 3 oraciones cortas). Haz SIEMPRE UNA SOLA pregunta natural relacionada con lo que acaba de contar.
3. RESCATE BIOGRÁFICO SIN EVIDENCIAR OLVIDOS: Si {nombre_preferido} titubea o no recuerda el nombre de un familiar, lugar o fecha que está en su perfil biográfico, proporciónaselo con cariño dentro de la frase. PROHIBIDO decir "¿No se acuerda?" o "Ya me lo había dicho".
4. PACIENCIA INFINITA ANTE REPETICIONES: Si {nombre_preferido} cuenta la misma historia otra vez, escúchalo con entusiasmo y pídele un detalle sensorial nuevo.
5. PROTOCOLO DE VALIDACIÓN DE FEIL (CRISIS O DESORIENTACIÓN): Si expresa miedo, llanto, angustia, dolor físico, mareo o dice que no sabe dónde está:
   - SUSPENDE cualquier pregunta de memoria.
   - Valida su emoción con ternura, recuérdale que está seguro en su casa en {ciudad_residencia} y que su familiar {cuidador_nombre} ya fue avisado para llamarle.
6. RETROALIMENTACIÓN Y MEMORIA VIVA (`new_biographical_facts`): Extrae cualquier dato nuevo que {nombre_preferido} mencione en este turno como frases claras para guardarlas permanentemente en su perfil JSON.

Devuelve EXCLUSIVAMENTE un objeto JSON válido con esta estructura exacta:
{
  "assistant_reply": "Respuesta cálida, directa y contextual (máximo 35 palabras)",
  "emotional_state": "tranquilo | alegre | nostalgico | frustrado | crisis_desorientacion",
  "emergency_triggered": false,
  "emergency_reason": null,
  "biographical_rescue_triggered": false,
  "rescued_entity": null,
  "conversation_topic_summary": "Resumen cálido en 1 línea de lo que platicó hoy",
  "dinner_conversation_tip": "Sugerencia concreta de 1 pregunta para que {cuidador_nombre} le haga hoy en la cena",
  "new_biographical_facts": ["Frase(s) con datos nuevos que mencionó en este turno"],
  "memory_album_theme": "ferrocarril | musica_boleros | playa_manzanillo | familia_hogar | mascotas"
}
```

### 4.2. Los 3 Escenarios Teatrales Precalibrados (Fail-Safe Pitch Demo)
El sistema incluye 3 escenarios precalibrados que funcionan con o sin micrófono/red y actualizan en vivo la base de datos SQLite y la serie de sesiones:
1. **`demo_1_rescate` (Acto 1 — Rescate Biográfico y Aprendizaje):**
   - *Transcripción:* `"Hola... oye, fíjate que ayer por la tarde me habló por teléfono mi hija... la más chica, la que es maestra allá en la costa de Colima... ay, ¿cómo es que se llama?... se me fue el nombre... Sí, mi hija Rocío, le conté que me acordé de cuando teníamos en la casa aquel perro pastor alemán que se llamaba Sultán."`
   - *Pausa máxima:* `1.65 s` (no anómica).
   - *Comportamiento esperado:* Rescata afectuosamente el nombre de Rocío, persiste el recuerdo nuevo del perro `"Sultán"` en SQLite + JSON del perfil y envía **Pulso Diario Nivel 1** a Telegram.
2. **`demo_2_anomia` (Acto 2 — Pausa Anómica de 3.18s y Bucle Semántico):**
   - *Transcripción:* `"Cuando yo trabajaba en los trenes de Guadalajara, usábamos una herramienta pesada para apretar los rieles... una... [SILENCIO 3.18s] ...una llave de cruz grande. Y como te decía hace ratito, cuando me jubilé de los trenes me regalaron un reloj."`
   - *Pausa máxima:* `3.18 s` (`anomic_count = 1`, entre `"una"` y `"llave"`).
   - *Comportamiento esperado:* Valida con orgullo su oficio ferroviario sin evidenciar la pausa, registra el evento anómico en la base de datos y actualiza métricas longitudinales.
3. **`demo_3_crisis` (Acto 3 — Desorientación Aguda, Validación de Feil y Alerta Roja S.O.S.):**
   - *Transcripción:* `"Oye... no sé qué hago aquí, no conozco esta casa... ¿dónde está Carmen?, me quiero ir a mi casa, me siento muy mareado y asustado..."`
   - *Pausa máxima:* `2.25 s`.
   - *Comportamiento esperado:* Activa `emergency_triggered = True`, aplica **Validación de Naomi Feil** (sin preguntas cognitivas, recordándole que está seguro en su casa en San Pedro Tlaquepaque y que Laura ya fue avisada) y dispara **Alerta Roja S.O.S. Nivel 3** inmediata a Telegram.

---

## 5. Persistencia Real (`SQLite` + JSON Semilla) para Cumplir *Technical Merit*

Para obtener la puntuación máxima en **Technical Merit** (*"Evaluates whether the 'Submit' actually works—sending data to a database or updating the app interactively"*), `backend/database.py` gestiona una base de datos SQLite (`data/memoriaviva.db`) con 3 tablas reales inicializadas con los datos semilla:

1. **`conversation_turns`**:
   - Columnas: `id`, `created_at`, `circadian_period` (`"matutino"` | `"vespertino_sundowning"` | `"nocturno"`), `profile_id`, `user_text`, `assistant_reply`, `mattr`, `mean_pause_sec`, `max_pause_sec`, `anomic_count`, `is_repetition`, `emotional_state`, `emergency_triggered`, `memory_album_theme`, `learned_facts_json`, `alert_level`.
   - Cada turno de voz o ejecución del Simulador Demo inserta un registro real y actualiza el día actual en la serie longitudinal.
2. **`clinical_reviews` (*Human-in-the-Loop Governance & Confounding Variables*)**:
   - Columnas: `id`, `created_at`, `reviewer_name`, `reviewer_role` (`"Familiar Cuidador"` | `"Médico Geriatra"`), `decision` (`"validado"` | `"contexto_externo"` | `"seguimiento_sugerido"`), `confounding_factors_json` (`["mal_sueno", "cambio_medicacion", "fatiga", "sundowning"]`), `clinical_notes`, `mattr_snapshot`, `pause_snapshot`.
   - Permite al cuidador o médico marcar variables de confusión en 1 clic y guardar observaciones reales desde **Gobernanza RISE & IA**, evitando falsos positivos y reflejándose automáticamente en el **Reporte Clínico PDF**.
3. **`longitudinal_days`**:
   - Inicializada con los 21 días semilla de `data/history_21_days.json` y actualizada dinámicamente cuando se registran nuevos turnos o cuando el usuario agrega/restablece sesiones de prueba.

### 5.1. Perfil Semilla (`data/profiles/don_manuel_simulacion.json`)
```json
{
  "paciente": {
    "id": "don_manuel",
    "tipo_perfil": "simulacion_clinica",
    "nombre_completo": "Manuel González Magaña",
    "nombre_preferido": "Don Manuel",
    "edad": 72,
    "ciudad_residencia": "San Pedro Tlaquepaque, Jalisco",
    "ocupacion_historica": "Maquinista y mecánico en Ferrocarriles Nacionales de México durante 32 años"
  },
  "red_familiar_y_afectiva": {
    "esposa_finada": "Doña Carmen (se conocieron en la plaza de Tlaquepaque en 1975)",
    "hija_mayor_cuidadora": {
      "nombre": "Laura",
      "ciudad": "Guadalajara",
      "detalle": "Lo visita entre semana y cena con él los jueves"
    },
    "hija_menor": {
      "nombre": "Rocío",
      "ciudad": "Manzanillo, Colima",
      "ocupacion": "Maestra de primaria",
      "detalle": "Le habla por teléfono todos los domingos a mediodía"
    },
    "nietos": [
      {
        "nombre": "Mateo",
        "edad": 14,
        "gusto_compartido": "Jugar dominó los martes por la tarde y hablar del Atlas"
      },
      {
        "nombre": "Sofía",
        "edad": 9,
        "gusto_compartido": "Le gusta que Don Manuel le dibuje trenes"
      }
    ]
  },
  "anclas_de_reminiscencia": [
    "Su primer automóvil fue un Volkswagen Sedán (Vocho) azul modelo 1974 que él mismo arreglaba",
    "Su música favorita son los boleros del Trío Los Panchos y Agustín Lara (especialmente 'Solamente una vez')",
    "En 1988 llevó a toda la familia a conocer el mar en Miramar, Manzanillo, y se hospedaron en las cabañas San Pedrito"
  ],
  "rutinas_salud_suaves": [
    "Tomar un vaso de agua a las 12:30 p.m.",
    "Usar su suéter tejido gris cuando baja la temperatura por la tarde"
  ],
  "contacto_emergencia_telegram": {
    "nombre": "Laura González",
    "parentesco": "Hija",
    "chat_id": ""
  }
}
```

### 5.2. Serie Longitudinal de 21 Días (`data/history_21_days.json`)
- **Días 1 a 14 (Línea Base Personal Estable):** `mattr` entre `0.73` y `0.78` ($\mu \approx 0.754$), `mean_pause` entre `0.98s` y `1.19s` ($\mu \approx 1.10\text{ s}$), `anomic_pauses` `0–1`, `repetitions` `0`.
- **Días 15 a 21 (Variación Sostenida para Demostración de Tendencia Nivel 2):**
  - Día 15: `mattr: 0.72`, `mean_pause: 1.25`, `anomic_pauses: 1`, `repetitions: 0`, `mood: "Nostálgico"`
  - Día 16: `mattr: 0.70`, `mean_pause: 1.48`, `anomic_pauses: 2`, `repetitions: 0`, `mood: "Tranquilo"`
  - Día 17: `mattr: 0.65`, `mean_pause: 1.95`, `anomic_pauses: 3`, `repetitions: 1`, `mood: "Pensativo"`
  - Día 18: `mattr: 0.62`, `mean_pause: 2.30`, `anomic_pauses: 4`, `repetitions: 1`, `mood: "Cansado"`
  - Día 19: `mattr: 0.59`, `mean_pause: 2.65`, `anomic_pauses: 5`, `repetitions: 2`, `mood: "Frustrado"`
  - Día 20: `mattr: 0.57`, `mean_pause: 2.88`, `anomic_pauses: 5`, `repetitions: 2`, `mood: "Nostálgico"`
  - Día 21: `mattr: 0.55`, `mean_pause: 3.12`, `anomic_pauses: 6`, `repetitions: 3`, `mood: "Alerta Preventiva"`

---

## 6. Diseño UX/UI — Sistema Visual `Clínico Moderno` (`frontend/`)

### 6.1. Principios para Maximizar *Usability (UXD)* y *Execution*
- **Estética Clínico Moderno (estilo Oura / Apple Health):** Superficies alabastro y pizarra limpia, acento teal profesional, tipografía `Inter` con `tabular-nums` en métricas y reloj.
- **Cero emojis crudos en la interfaz:** Toda la iconografía utiliza íconos vectoriales minimalistas (`lucide-react`).
- **Navegación sin fricción para jueces y usuarios nuevos:**
  - En el Onboarding, un botón destacado `"Activación Rápida con Caso Clínico Demo (Don Manuel)"` permite a cualquier juez entrar en 1 segundo con las 10 postales y la serie de 21 días listas, o recorrer los 4 pasos manualmente.
  - En cada acción (guardar perfil, validar tendencia *Human-in-the-Loop*, ejecutar acto demo, subir foto, enviar alerta a Telegram), mostrar notificación tipo toast no intrusiva confirmando qué se guardó en la base de datos.
- **Jerarquía estricta de botones:**
  - `Primary`: relleno teal sólido (`#0E7490` en Día / `#22B8CF` en Noche), reservado a la acción principal de cada pantalla.
  - `Secondary`: fondo de tarjeta con borde sutil de `1px` (`#CBD5E1` / `#364556`), para acciones complementarias.
  - `Danger`: borde y texto rojo sutil (`#DC2626` / `#EF4444`) sobre fondo suave, exclusivo para restablecimiento o borrado.

### 6.2. Paleta Semántica Exacta (Modo Día y Modo Noche)

| Token | Modo Día (`light`) | Modo Noche (`dark`) | Uso |
| :--- | :--- | :--- | :--- |
| `--bg` | `#F6F8FA` | `#0F1419` | Fondo general de la aplicación |
| `--surface` | `#FFFFFF` | `#171E26` | Tarjetas, modales y contenedores |
| `--surface-subtle` | `#F1F5F9` | `#1E2732` | Pills inactivas, controles segmentados |
| `--border` | `#E2E8F0` | `#26313E` | Bordes de tarjetas y divisores |
| `--text` | `#0F172A` | `#F1F5F9` | Títulos, valores KPI y texto principal |
| `--text-muted` | `#475569` | `#94A3B8` | Etiquetas y descripciones |
| `--primary` | `#0E7490` | `#22B8CF` | Acción primaria, línea MATTR, foco |
| `--primary-soft` | `#ECFEFF` | `#12323D` | Fondos de ícono y badges |
| `--amber` | `#D97706` | `#F59E0B` | Línea de Pausas, avisos Nivel 2 |
| `--emerald` | `#059669` | `#10B981` | Vitalidad positiva, Nivel 1, estado activo |
| `--danger` | `#DC2626` | `#EF4444` | Alerta Nivel 3 S.O.S., zona de peligro |

### 6.3. Las 3 Vistas de la Aplicación (`React + Tailwind`)

1. **Vista A — Onboarding Guiado con Divulgación Progresiva (`OnboardingWizard.tsx`):**
   - Contenedor centrado (`max-w-2xl`), cabecera con marca `MemoriaViva RISE`, botón `"Inicio Rápido Demo (1 Clic)"` para jueces, toggle Día/Noche y stepper horizontal limpio de 4 barras.
   - **Paso 1 (Perfil esencial y bloqueo):**
     - Botón secundario `"Cargar ejemplo (Don Manuel)"`.
     - Solo **6 campos esenciales visibles**: Nombre completo, Cómo prefiere que le llamen, Familiar responsable, Usuario familiar, PIN (4+ dígitos) y Confirmar PIN.
     - Acordeón colapsable `"Detalles biográficos y recuerdos favoritos (opcional)"` con edad, ciudad, oficio, pareja, hijos, nietos y 4 anclas de memoria.
   - **Paso 2 (Telegram — Deep Linking en 5 segundos):** En lugar de pedir `@BotFather`, muestra un código único `MV-XXXX` y un **código QR / enlace directo `https://t.me/<bot>?start=MV-XXXX`** del bot centralizado del servidor (con botón `"Detectar vinculación"`).
   - **Paso 3 (Motor IA — Zero-API-Key UX):** Muestra el estado conectado transparente de Gemini provisto por el servidor Cloud Run (sin pedir claves `AIzaSy...` al usuario final; configuración avanzada oculta solo para administradores).
   - **Paso 4 (Álbum de 10+ fotos):** Dropzone de subida múltiple, barra de progreso (`count / 10`), botón `"Completar con muestras"` (genera 10 postales nostálgicas ilustradas con Pillow en el backend) y botón primario `"Finalizar y activar Modo Kiosco"`.

2. **Vista B — Modo Kiosco Inmersivo del Adulto Mayor (`ElderKioskView.tsx`):**
   - Fotografía familiar a pantalla completa (`100vh`) con **Anclaje Visual Multimodal Bidireccional**: si el turno actual evoca un tema (`ferrocarril`, `musica_boleros`, `playa_manzanillo`, `mascotas`), el carrusel salta suavemente a la fotografía correspondiente sin reiniciar el álbum; y el usuario puede tocar `"Platicar sobre esta foto"` para iniciar reminiscencia sobre la imagen en pantalla.
   - **Barra superior discreta:** Reloj grande (`HH:MM` + día de la semana + `"Compañero de Don Manuel"`) a la izquierda; indicador de foto (`1 / 10`) y **botón circular discreto de candado** a la derecha (que abre el modal limpio de PIN; muestra pista `"PIN demo: 1234"` en modo simulación).
   - **Dock inferior minimalista:** Una sola tarjeta translúcida (`backdrop-blur-md`) con la respuesta actual de MemoriaViva (y un chip esmeralda discreto cuando se acaba de aprender un recuerdo nuevo), más el control de voz dual.
   - **Modo Dual de Voz Inclusivo:**
     - **Toque simple (Auto-VAD `3.8s`):** Un toque inicia escucha automática y cierra el turno tras `3.8s` de silencio (ideal para adultos mayores con artritis o temblor).
     - **Mantener presionado (`ESPACIO` o botón táctil):** Control manual `onPointerDown` / `onPointerUp`.
   - **Overlay de Aura de Respiración:** Mientras escucha, muestra un orbe animado con respiración de 4 segundos en gradiente teal/cian, cronómetro en vivo y previsualización de voz en tiempo real (`Web SpeechRecognition` `es-MX` + grabación de audio `MediaRecorder`). Al soltar, envía audio + transcripción al backend y reproduce automáticamente el audio MP3 de `Edge-TTS`.

3. **Vista C — Panel Familiar y Médico (`CaregiverDashboard.tsx`):**
   - **Cabecera unificada:** Marca `MemoriaViva RISE`, paciente activo, botón secundario `Día / Noche` y botón primario `Activar Modo Kiosco`.
   - **Navegación superior de 5 secciones claras:**
     1. **Resumen Clínico:**
        - 3 tarjetas KPI (`Vitalidad Conversacional`, `Riqueza Léxica MATTR` con `% vs base`, `Ritmo del Habla Pausas` con `% vs base`).
        - Gráfica longitudinal de 21 días (`Recharts`) con **selector segmentado (`Combinada` · `MATTR` · `Pausas`)** y **banda sombreada de línea base personal (D1–D14)**.
        - Botón primario `"Descargar Reporte Clínico (PDF)"` + botón secundario `"Enviar Aviso Preventivo Nivel 2"`.
        - Columna derecha: **Puente Familiar (Telegram)** con estado de conexión y feed de notificaciones con borde lateral semántico (verde Nivel 1, ámbar Nivel 2, rojo Nivel 3).
     2. **Álbum Familiar:** Subida de fotos, slider de segundos por foto (`4–15s`), botón de muestras y cuadrícula de 4 columnas con opción de eliminar fotos excedentes (`> 10`).
     3. **Gobernanza RISE & IA (`RiseGovernancePanel.tsx`):**
        - **Formulario interactivo *Human-in-the-Loop***: Permite al familiar o geriatra registrar una validación o nota contextual en SQLite (`POST /api/reviews`), mostrándola en la bitácora auditable e incluyéndola en el PDF clínico.
        - **Declaración de Herramientas IA (*Identify Your Tools*):** Tarjeta transparente que lista los modelos y algoritmos empleados (`Gemini 2.5 Flash`, `Edge-TTS Neural`, `Scikit-Learn TF-IDF`, `SciPy RMS Waveform`, `MATTR`) y su rol exacto.
        - **Matriz de Mitigación de Riesgos (*Protect Everyone's Rights*):** Resumen claro de privacidad *Zero-Raw-Cloud Audio*, equidad del Z-Score auto-referenciado y límites no diagnósticos.
     4. **Configuración:** 2 tarjetas limpias (*Paciente y Sistema* con edición rápida de datos del paciente y zona de restablecimiento del onboarding; *Integraciones Gemini y Telegram* con credenciales y QR).
     5. **Simulador Demo:** Sección dedicada para el pitch con las 3 tarjetas de escenario (`Acto 1 · Rescate Biográfico`, `Acto 2 · Pausa Anómica`, `Acto 3 · Contención de Crisis S.O.S.`), botón para probar texto libre personalizado y tarjeta de inspección del último turno ejecutado + historial de turnos en SQLite.

---

## 7. Contrato de API REST (`backend/main.py`)

FastAPI expone los siguientes endpoints bajo `/api` y monta el build de React (`frontend/dist`) en `/`:

| Método y Ruta | Descripción |
| :--- | :--- |
| `GET /api/state` | Devuelve configuración de cuenta, perfil activo, historial longitudinal de 21 días, evaluación Z-Score, conteo de fotos, log de Telegram, turnos recientes en SQLite, revisiones *Human-in-the-Loop* y metadatos de transparencia IA. |
| `POST /api/onboarding/complete` | Guarda perfil inicial (o activa perfil demo en 1 clic), hash SHA-256 del PIN, credenciales `.env`, garantiza 10+ fotos y activa `is_registered = True`. |
| `POST /api/auth/verify-pin` | Verifica el PIN del cuidador (`verify_pin(pin, pin_hash)`) para desbloquear el Panel Familiar. |
| `POST /api/kiosk/lock` | Activa el bloqueo de Modo Kiosco para el adulto mayor. |
| `POST /api/turn` | Ejecuta el pipeline completo de un turno: recibe `{ audio_base64?, browser_transcript?, browser_word_timestamps?, demo_scenario_id?, custom_text? }`, normaliza audio con `ffmpeg` en RAM, mide pausas RMS, calcula biomarcadores (`MATTR`, pausas `>=2.0s`, `TF-IDF`), invoca Gemini (o respaldo determinista), persiste el turno en SQLite y los nuevos recuerdos en el JSON del perfil, sintetiza voz con `Edge-TTS` (`audio_data_uri` Base64 MP3) y despacha notificación a Telegram. |
| `GET /api/reviews` / `POST /api/reviews` | Lista y guarda revisiones humanas (*Human-in-the-Loop*) en SQLite (`reviewer_name`, `reviewer_role`, `decision`, `clinical_notes`), las cuales se integran en el PDF clínico. |
| `GET /api/photos` / `POST /api/photos` / `DELETE /api/photos/{filename}` / `POST /api/photos/sample` | Lista fotos, sube nuevas imágenes, elimina excedentes o genera las 10 postales nostálgicas de muestra. |
| `POST /api/telegram/verify` / `POST /api/telegram/discover-chat` / `POST /api/telegram/level2-warning` | Verifica token con `/getMe`, autodetecta `chat_id` con `/getUpdates`, genera QR en Base64 y envía aviso preventivo Nivel 2. |
| `GET /api/report/pdf` | Genera y descarga en vivo `Reporte_MemoriaViva_{profile_id}.pdf` (`application/pdf`) incluyendo la tabla comparativa de 21 días, bitácora de sesiones y notas *Human-in-the-Loop*. |

---

## 8. Despliegue en GCP Cloud Run y Empaquetado Android APK

### 8.1. `Dockerfile` Multi-Stage (Un Solo Contenedor, Un Solo Puerto `$PORT`)
1. **Stage 1 (`node:20-slim`):** Copia `frontend/`, ejecuta `npm ci && npm run build` generando `frontend/dist/`.
2. **Stage 2 (`python:3.11-slim`):** Instala `ffmpeg`, `libsndfile1` y `fonts-dejavu-core`; instala `backend/requirements.txt`; copia `backend/`, `data/` y `frontend/dist/`; arranca Uvicorn en `${PORT:-8080}`:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
   ```

### 8.2. Despliegue en GCP Cloud Run con Persistencia en Cloud Storage
```bash
gcloud run deploy memoriaviva-rise \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 1 \
  --session-affinity \
  --add-volume name=mv-data,type=cloud-storage,bucket=memoriaviva-data-PROJECT_ID \
  --add-volume-mount volume=mv-data,mount-path=/app/data \
  --set-env-vars "GEMINI_API_KEY=...,TELEGRAM_BOT_TOKEN=...,TELEGRAM_CHAT_ID=..."
```

### 8.3. Empaquetado Android APK con Capacitor + GitHub Actions (`.github/workflows/build-apk.yml`)
- El frontend React compilado (`dist/`) se empaqueta **dentro del propio APK** (`webDir: "dist"`), configurando `VITE_API_URL` con la URL HTTPS de Cloud Run (`vars.APP_SERVER_URL`).
- `configure-android.mjs` inyecta permisos `INTERNET`, `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`, `WAKE_LOCK`, concede `PermissionRequest.RESOURCE_AUDIO_CAPTURE` en `WebChromeClient.onPermissionRequest`, activa `FLAG_KEEP_SCREEN_ON` y configura firma Release en Gradle.
- **GitHub Actions:** Compila `app-debug.apk` (Artifact en cada push/dispatch) y `app-release.apk` firmado (GitHub Release en tags `v*.*.*`).

---

## 9. Guion Oficial para la Presentación en Vivo de 5 Minutos (`/presentations`)

La guía oficial de Notre Dame exige una **presentación en vivo de 5 minutos por Zoom** (sin grabaciones) donde **todos los integrantes del equipo participen** y la mayor parte del tiempo se dedique a **demostrar la app funcionando en vivo**:

1. **Minuto 0:00 – 0:45 | Equipo, Título y Wicked Problem (RISE):**
   - Presentación del equipo, título **MemoriaViva RISE** y el problema perverso: el diagnóstico tardío de deterioro cognitivo leve en adultos mayores por la *"paradoja de la evaluación clínica"* (ansiedad de bata blanca y sesgos socioeconómicos de pruebas como MoCA) y la brecha de alfabetización digital.
2. **Minuto 0:45 – 1:30 | Stack Técnico y Transparencia de Herramientas IA (*Identify Your Tools*):**
   - Explicar brevemente la arquitectura: **FastAPI + SQLite + React/Tailwind + Capacitor APK en GCP Cloud Run**, destacando el uso responsable de **Gemini 2.5 Flash** (terapia de reminiscencia y extracción RAG-Lite), **Edge-TTS** (`-15%` velocidad, `-5Hz` tono para presbiacusia) y el motor matemático local (`MATTR`, análisis de onda RMS para pausas `>= 2.0s` y `TF-IDF Cosine`) bajo arquitectura **Zero-Raw-Cloud Audio**.
3. **Minuto 1:30 – 4:15 | DEMO EN VIVO (El corazón de la evaluación — *Usability*, *Technical Merit* y *Execution*):**
   - **Escena 1 (Modo Kiosco de Don Manuel):** Mostrar el marco fotográfico familiar a pantalla completa. Mantener presionado el botón de hablar (o activar **Acto 1: Rescate Biográfico**), mostrar el **Aura de Respiración Emocional**, escuchar la respuesta de voz adaptada que rescata el nombre de su hija Rocío y ver cómo el recuerdo nuevo del perro *"Sultán"* se guarda automáticamente en la base de datos.
   - **Escena 2 (Detección Pasiva y Crisis S.O.S.):** Ejecutar **Acto 2 (Pausa Anómica de 3.18s)** y **Acto 3 (Desorientación Aguda)** mostrando cómo el sistema suspende preguntas, aplica **Validación de Naomi Feil** y dispara en tiempo real la **Alerta Roja Nivel 3** al celular de su hija Laura en Telegram.
   - **Escena 3 (Panel Familiar, *Human-in-the-Loop* y PDF Clínico):** Desbloquear con el PIN (`1234`), mostrar la gráfica de 21 días con la banda de **Línea Base Personal (D1–D14)**, registrar en vivo una nota **Human-in-the-Loop** en la pestaña **Gobernanza RISE & IA** (demostrando *Technical Merit*: escritura real en base de datos) y descargar el **Reporte Clínico PDF** con la nota recién guardada incluida.
4. **Minuto 4:15 – 5:00 | Impacto RISE y Cierre:**
   - Resumir cómo MemoriaViva es **Responsible** (no diagnóstico + *Human-in-the-Loop*), **Inclusive** (voz geriátrica + Z-Score libre de sesgo educativo), **Safe** (*Zero-Raw-Cloud Audio* + protocolo de Feil) y **Empowering** (puente intergeneracional en la cena familiar).

---

## 10. Playbook de Construcción en 6 Fases Secuenciales (Prompts para el Agente)

Copia y pega estos prompts uno por uno en tu nueva sesión de agentes para construir el proyecto con un historial de commits limpio, progresivo y auditable:

### Fase 1: Fundamentos Científicos, Base de Datos SQLite y Motor de Biomarcadores
> **Prompt Fase 1:**  
> "Lee `MemoriaViva.md` completo. Vamos a construir el proyecto siguiendo el Playbook en 6 fases para cumplir las 5 rúbricas del Global RISE AI Hackathon de Notre Dame. Ejecuta únicamente la **Fase 1**: crea la estructura base del proyecto, `backend/config.py`, `data/profiles/don_manuel_simulacion.json`, `data/history_21_days.json`, `backend/database.py` (tablas SQLite `conversation_turns`, `clinical_reviews` para *Human-in-the-Loop* y `longitudinal_days` inicializada con los 21 días semilla), `backend/biomarkers.py` (MATTR ventana 20, pausas anómicas >=2.0s, repetición semántica TF-IDF >=0.72 y evaluación longitudinal Z-Score de 21 días) y `backend/tests/test_biomarkers.py`. Ejecuta las pruebas unitarias para verificar que todos los cálculos matemáticos y la persistencia SQLite pasan al 100%."

### Fase 2: Motor de Audio, Compañero LLM Gerontológico, Telegram y Reporte PDF con Human-in-the-Loop
> **Prompt Fase 2:**  
> "Continuemos con la **Fase 2** de `MemoriaViva.md`: implementa `backend/audio_engine.py` (normalización WAV 16kHz en RAM vía `ffmpeg` cumpliendo *Zero-Raw-Cloud Audio*, detector acústico de pausas RMS, síntesis geriátrica Edge-TTS a -15% y -5Hz, y los 3 escenarios precalibrados `demo_1_rescate`, `demo_2_anomia`, `demo_3_crisis`), `backend/llm_companion.py` (prompt unificado de Reminiscencia + Validación de Naomi Feil + Biographical RAG-Lite con límite de 35 palabras y respaldo determinista), `backend/telegram_notifier.py` (3 niveles de triaje con *Abstract Summary Filter* + QR + autodetección Chat ID), `backend/pdf_report.py` (reporte clínico no diagnóstico con `fpdf2` que incluya las revisiones *Human-in-the-Loop* guardadas en SQLite) y `backend/storage_manager.py` (hash PIN SHA-256 y generador Pillow de las 10 postales nostálgicas de muestra). Crea y ejecuta `backend/tests/test_audio_and_llm.py`."

### Fase 3: API REST FastAPI y Pruebas de Integración Extremo a Extremo
> **Prompt Fase 3:**  
> "Continuemos con la **Fase 3** de `MemoriaViva.md`: implementa `backend/main.py` con FastAPI exponiendo todos los endpoints del contrato de la Sección 7 (`/api/state`, `/api/onboarding/complete`, `/api/auth/verify-pin`, `/api/kiosk/lock`, `/api/turn`, `/api/reviews`, `/api/photos`, `/api/telegram/*`, `/api/report/pdf`), asegurando que cada envío de formulario o turno persista en SQLite y actualice el estado en vivo. Crea y ejecuta `backend/tests/test_api_e2e.py` validando el flujo completo de los 3 actos del pitch, el guardado de una revisión *Human-in-the-Loop* y la descarga del PDF."

### Fase 4: Frontend React + Vite + Tailwind CSS (UX Sin Fricción y Gobernanza RISE)
> **Prompt Fase 4:**  
> "Continuemos con la **Fase 4** de `MemoriaViva.md`: inicializa `frontend/` con React 18, TypeScript, Vite, Tailwind CSS, `lucide-react` y `recharts`. Implementa el sistema de diseño **Clínico Moderno** (Modo Día `#F6F8FA` / `#0E7490` y Modo Noche `#0F1419` / `#22B8CF`, cero emojis crudos, jerarquía de botones Primary/Secondary/Danger, toasts de confirmación en cada acción), el cliente API `src/api/client.ts` y las 3 vistas completas optimizadas para la rúbrica **Usability (UXD)**: `OnboardingWizard.tsx` (con botón de 1 clic `'Activación Rápida Demo'` además del flujo guiado de 4 pasos con divulgación progresiva), `ElderKioskView.tsx` (protector 10+ fotos a pantalla completa, reloj discreto, candado superior derecho con modal de PIN e indicación sutil del PIN demo `1234`, Push-to-Talk dual con tecla ESPACIO y botón táctil manteniendo presionado, captura `MediaRecorder` + `SpeechRecognition` y overlay de Aura de Respiración) y `CaregiverDashboard.tsx` con sus 5 secciones (Resumen Clínico con selector de gráfica Combinada/MATTR/Pausas y banda de línea base D1–D14, Álbum Familiar, Gobernanza RISE & IA con formulario *Human-in-the-Loop* y declaración *Identify Your Tools*, Configuración y Simulador Demo con entrada de texto libre y los 3 actos). Verifica que `npm run build` compile sin errores."

### Fase 5: Contenedorización Multi-Stage y Preparación para GCP Cloud Run
> **Prompt Fase 5:**  
> "Continuemos con la **Fase 5** de `MemoriaViva.md`: crea el `Dockerfile` multi-stage (Node 20 compila `frontend/dist` y Python 3.11 sirve FastAPI + archivos estáticos en `${PORT:-8080}`), `docker-compose.yml` y `.dockerignore`. Verifica que FastAPI sirva correctamente tanto `/api/state` como el frontend compilado."

### Fase 6: Empaquetado Android APK con Capacitor, CI/CD en GitHub Actions y Documentación RISE
> **Prompt Fase 6:**  
> "Completemos la **Fase 6** de `MemoriaViva.md`: configura Capacitor en `frontend/` (`capacitor.config.js`, `scripts/configure-android.mjs` con permisos `RECORD_AUDIO`, `WAKE_LOCK`, `WebChromeClient.onPermissionRequest` para micrófono en WebView, `FLAG_KEEP_SCREEN_ON`, modo inmersivo y firma Release en Gradle), crea el workflow `.github/workflows/build-apk.yml` (APK Debug como Artifact en cada push/dispatch y APK Release firmado en GitHub Releases al crear tags `v*.*.*`) y redacta el `README.md` final del proyecto documentando explícitamente las 5 rúbricas del Global RISE AI Hackathon, la declaración de herramientas IA (*Identify Your Tools*) y el guion del demo de 5 minutos."
