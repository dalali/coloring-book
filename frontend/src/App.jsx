import { useEffect, useReducer, useRef } from "react";
import {
  ACCEPTED_TYPES,
  MAX_SIZE_MB,
  fromImage,
  fromText,
  getHealth,
} from "./api.js";

const COMPLEXITIES = [
  { value: "simple", label: "Simple", hint: "~6" },
  { value: "medium", label: "Medium", hint: "~12" },
  { value: "detailed", label: "Detailed", hint: "~20" },
];

const initialState = {
  mode: "upload", // upload | describe
  textFlowEnabled: false,
  file: null,
  filePreview: null,
  prompt: "",
  complexity: "medium",
  status: "idle", // idle | working | result | error
  result: null,
  error: null,
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_HEALTH":
      return { ...state, textFlowEnabled: action.enabled };
    case "SET_MODE":
      return { ...state, mode: action.mode, error: null };
    case "SET_FILE":
      return { ...state, file: action.file, filePreview: action.preview, error: null };
    case "SET_PROMPT":
      return { ...state, prompt: action.prompt };
    case "SET_COMPLEXITY":
      return { ...state, complexity: action.complexity };
    case "WORKING":
      return { ...state, status: "working", error: null };
    case "RESULT":
      return { ...state, status: "result", result: action.result };
    case "ERROR":
      return { ...state, status: "error", error: action.error };
    case "RESET":
      return { ...initialState, textFlowEnabled: state.textFlowEnabled };
    default:
      return state;
  }
}

function validateFile(file) {
  if (!ACCEPTED_TYPES.includes(file.type)) {
    return "Please choose a JPG, PNG, or WebP image.";
  }
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return `That file is too large — the max is ${MAX_SIZE_MB} MB.`;
  }
  return null;
}

function AppHeader() {
  return (
    <header className="app-header">
      <h1 className="logo">🎨 Coloring Book</h1>
      <p className="tagline">Turn a photo or an idea into a color-by-number page.</p>
    </header>
  );
}

function ModeTabs({ mode, describeEnabled, onChange }) {
  return (
    <div className="tabs" role="tablist">
      <button
        role="tab"
        aria-selected={mode === "upload"}
        className={`tab ${mode === "upload" ? "active" : ""}`}
        onClick={() => onChange("upload")}
      >
        ⬆ Upload
      </button>
      <button
        role="tab"
        aria-selected={mode === "describe"}
        className={`tab ${mode === "describe" ? "active" : ""}`}
        disabled={!describeEnabled}
        title={describeEnabled ? "" : "Text-to-image is not configured on this server"}
        onClick={() => describeEnabled && onChange("describe")}
      >
        {describeEnabled ? "✨ Describe" : "🔒 Describe"}
      </button>
    </div>
  );
}

function Dropzone({ file, preview, error, onSelect }) {
  const inputRef = useRef(null);

  const handleFiles = (files) => {
    if (files && files[0]) onSelect(files[0]);
  };

  return (
    <div>
      <div
        className={`dropzone ${error ? "has-error" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleFiles(e.dataTransfer.files);
        }}
      >
        {preview ? (
          <img className="source-preview" src={preview} alt="Selected source" />
        ) : (
          <div className="dropzone-empty">
            <span className="dz-icon">⬆</span>
            <p>Click or drop an image here</p>
            <p className="helper">JPG, PNG or WebP · up to {MAX_SIZE_MB} MB</p>
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {file && <p className="helper">{file.name}</p>}
    </div>
  );
}

function PromptInput({ value, onChange }) {
  return (
    <div>
      <textarea
        className="prompt"
        rows={4}
        placeholder="e.g. a friendly dinosaur in a forest"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <p className="helper">{value.length}/1000 characters</p>
    </div>
  );
}

function ComplexityPicker({ value, onChange }) {
  return (
    <div className="field">
      <label className="field-label">Complexity</label>
      <div className="segmented">
        {COMPLEXITIES.map((c) => (
          <button
            key={c.value}
            className={`segment ${value === c.value ? "selected" : ""}`}
            onClick={() => onChange(c.value)}
          >
            <span>{c.label}</span>
            <span className="seg-hint">{c.hint}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Legend({ entries }) {
  return (
    <div className="legend">
      <h3 className="section-title">Legend</h3>
      <ul className="legend-list">
        {entries.map((e) => (
          <li key={e.n} className="legend-item">
            <span className="swatch" style={{ background: e.hex }} />
            <span>
              {e.n}. {e.name}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ResultPanel({ status, result, error, onReset }) {
  if (status === "working") {
    return (
      <div className="result-panel placeholder">
        <div className="spinner" />
        <p>Making your coloring page…</p>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="result-panel">
        <div className="banner danger">{error}</div>
        <button className="btn-secondary" onClick={onReset}>
          ↺ Start over
        </button>
      </div>
    );
  }
  if (status === "result" && result) {
    return (
      <div className="result-panel">
        <h3 className="section-title">Your coloring page</h3>
        <img className="coloring-page" src={result.page_image} alt="Coloring page" />
        <Legend entries={result.legend} />
        <div className="actions">
          <a
            className="btn-primary"
            href={result.page_image}
            download={`coloring-page.${result.format}`}
          >
            ⬇ Download
          </a>
          <button className="btn-secondary" onClick={onReset}>
            ↺ Start over
          </button>
        </div>
      </div>
    );
  }
  return (
    <div className="result-panel placeholder">
      <span className="placeholder-icon">🖼️</span>
      <p>Your color-by-number page will appear here.</p>
    </div>
  );
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);

  useEffect(() => {
    getHealth()
      .then((h) => dispatch({ type: "SET_HEALTH", enabled: !!h.text_flow_enabled }))
      .catch(() => dispatch({ type: "SET_HEALTH", enabled: false }));
  }, []);

  const onSelectFile = (file) => {
    const err = validateFile(file);
    if (err) {
      dispatch({ type: "ERROR", error: err });
      return;
    }
    const reader = new FileReader();
    reader.onload = () =>
      dispatch({ type: "SET_FILE", file, preview: reader.result });
    reader.readAsDataURL(file);
  };

  const canSubmit =
    state.status !== "working" &&
    ((state.mode === "upload" && state.file) ||
      (state.mode === "describe" && state.prompt.trim()));

  const submit = async () => {
    dispatch({ type: "WORKING" });
    try {
      const result =
        state.mode === "upload"
          ? await fromImage({ file: state.file, complexity: state.complexity })
          : await fromText({ prompt: state.prompt.trim(), complexity: state.complexity });
      dispatch({ type: "RESULT", result });
    } catch (e) {
      dispatch({ type: "ERROR", error: e.message });
    }
  };

  const ctaLabel =
    state.mode === "upload" ? "Make coloring page" : "Generate & make page";

  return (
    <div className="app">
      <AppHeader />
      <main className="layout">
        <section className="card input-card">
          <ModeTabs
            mode={state.mode}
            describeEnabled={state.textFlowEnabled}
            onChange={(m) => dispatch({ type: "SET_MODE", mode: m })}
          />
          {state.mode === "upload" ? (
            <Dropzone
              file={state.file}
              preview={state.filePreview}
              error={state.status === "error" ? state.error : null}
              onSelect={onSelectFile}
            />
          ) : (
            <PromptInput
              value={state.prompt}
              onChange={(p) => dispatch({ type: "SET_PROMPT", prompt: p })}
            />
          )}

          <ComplexityPicker
            value={state.complexity}
            onChange={(c) => dispatch({ type: "SET_COMPLEXITY", complexity: c })}
          />

          {state.status === "error" && state.mode === "upload" && (
            <div className="banner danger">{state.error}</div>
          )}

          <button className="btn-primary cta" disabled={!canSubmit} onClick={submit}>
            {state.status === "working" ? "Working…" : ctaLabel}
          </button>
        </section>

        <section className="card result-card">
          <ResultPanel
            status={state.status}
            result={state.result}
            error={state.error}
            onReset={() => dispatch({ type: "RESET" })}
          />
        </section>
      </main>
    </div>
  );
}
