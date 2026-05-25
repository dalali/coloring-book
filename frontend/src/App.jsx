import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  ACCEPTED_TYPES,
  MAX_SIZE_MB,
  fromInspire,
  fromText,
  getHealth,
  getLibrary,
  getLibraryCategories,
  getLibraryPage,
} from "./api.js";

const COMPLEXITIES = [
  { value: "simple", label: "Simple", hint: "~6" },
  { value: "medium", label: "Medium", hint: "~12" },
  { value: "detailed", label: "Detailed", hint: "~20" },
];

// ── state ─────────────────────────────────────────────────────────────────────

const initialState = {
  mode: "inspire",       // inspire | describe | browse
  textFlowEnabled: false,
  libraryEnabled: false,

  // inspire tab
  file: null,
  filePreview: null,

  // describe tab
  prompt: "",

  // shared create options
  complexity: "medium",
  status: "idle",        // idle | working | result | error
  result: null,
  error: null,
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_HEALTH":
      return {
        ...state,
        textFlowEnabled: action.textFlowEnabled,
        libraryEnabled: action.libraryEnabled,
      };
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
      return {
        ...initialState,
        textFlowEnabled: state.textFlowEnabled,
        libraryEnabled: state.libraryEnabled,
        // keep mode + input so user can edit and retry
        mode: state.mode,
        prompt: state.prompt,
        file: state.file,
        filePreview: state.filePreview,
        complexity: state.complexity,
      };
    default:
      return state;
  }
}

// ── small components ──────────────────────────────────────────────────────────

function AppHeader() {
  return (
    <header className="app-header">
      <h1 className="logo">🎨 Coloring Book</h1>
      <p className="tagline">Discover, create, and share color-by-number pages.</p>
    </header>
  );
}

function ModeTabs({ mode, textFlowEnabled, onChange }) {
  return (
    <div className="tabs" role="tablist">
      <button
        role="tab"
        aria-selected={mode === "inspire"}
        className={`tab ${mode === "inspire" ? "active" : ""}`}
        onClick={() => onChange("inspire")}
      >
        📷 Inspire
      </button>
      <button
        role="tab"
        aria-selected={mode === "describe"}
        className={`tab ${mode === "describe" ? "active" : ""}`}
        disabled={!textFlowEnabled}
        title={textFlowEnabled ? "" : "Add OPENAI_API_KEY to .env to unlock this tab"}
        onClick={() => textFlowEnabled && onChange("describe")}
      >
        {textFlowEnabled ? "✨ Describe" : "🔒 Describe"}
      </button>
      <button
        role="tab"
        aria-selected={mode === "browse"}
        className={`tab ${mode === "browse" ? "active" : ""}`}
        onClick={() => onChange("browse")}
      >
        🖼 Browse
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
            <span className="dz-icon">📷</span>
            <p>Upload a photo as inspiration</p>
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
      <p className="helper inspire-hint">
        💡 Your photo will be reimagined as clean coloring-book art by AI.
      </p>
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
      <div className="result-panel placeholder">
        <span className="placeholder-icon">⚠️</span>
        <p style={{ color: "var(--danger)", textAlign: "center", padding: "0 16px" }}>{error}</p>
        <button className="btn-secondary" onClick={onReset}>
          ↺ Try again
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
            ↺ Make another
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

// ── browse tab ────────────────────────────────────────────────────────────────

function PageModal({ page, onClose }) {
  useEffect(() => {
    const handler = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>
        {page.page_image ? (
          <img className="modal-image" src={page.page_image} alt="Coloring page" />
        ) : (
          <div className="modal-loading">
            <div className="spinner" />
          </div>
        )}
        <div className="modal-meta">
          {page.prompt && <p className="modal-prompt">"{page.prompt}"</p>}
          <div className="modal-actions">
            <span className="badge">{page.category}</span>
            {page.page_image && (
              <a className="btn-primary" href={page.page_image} download="coloring-page.png">
                ⬇ Download
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function BrowseTab({ libraryEnabled }) {
  const [categories, setCategories] = useState([]);
  const [activeCategory, setActiveCategory] = useState("All");
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedPage, setExpandedPage] = useState(null); // full page data
  const [loadingPage, setLoadingPage] = useState(false);

  const loadGallery = useCallback(async (cat) => {
    setLoading(true);
    try {
      const data = await getLibrary({ category: cat === "All" ? null : cat });
      setPages(data.pages);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!libraryEnabled) return;
    getLibraryCategories()
      .then((cats) => setCategories(cats))
      .catch(() => {});
    loadGallery("All");
  }, [libraryEnabled, loadGallery]);

  const selectCategory = (cat) => {
    setActiveCategory(cat);
    loadGallery(cat);
  };

  const openPage = async (id) => {
    setExpandedPage({ id }); // show modal immediately (loading state)
    setLoadingPage(true);
    try {
      const full = await getLibraryPage(id);
      setExpandedPage(full);
    } catch {
      setExpandedPage(null);
    } finally {
      setLoadingPage(false);
    }
  };

  if (!libraryEnabled) {
    return (
      <div className="browse-placeholder">
        <span className="placeholder-icon">📚</span>
        <p>The library needs a database. Start the full stack with <code>./run.sh start</code>.</p>
      </div>
    );
  }

  return (
    <div className="browse-tab">
      {/* Category pills */}
      <div className="category-pills">
        <button
          className={`pill ${activeCategory === "All" ? "active" : ""}`}
          onClick={() => selectCategory("All")}
        >
          All
        </button>
        {categories.map((c) => (
          <button
            key={c.category}
            className={`pill ${activeCategory === c.category ? "active" : ""}`}
            onClick={() => selectCategory(c.category)}
          >
            {c.category}
            <span className="pill-count">{c.count}</span>
          </button>
        ))}
      </div>

      {/* Gallery grid */}
      {loading ? (
        <div className="gallery-loading">
          <div className="spinner" />
        </div>
      ) : pages.length === 0 ? (
        <div className="gallery-empty">
          <span className="placeholder-icon">🎨</span>
          <p>No pages here yet — create one using Inspire or Describe!</p>
        </div>
      ) : (
        <div className="gallery-grid">
          {pages.map((p) => (
            <button key={p.id} className="gallery-card" onClick={() => openPage(p.id)}>
              {p.thumbnail ? (
                <img src={p.thumbnail} alt={p.prompt || "Coloring page"} className="gallery-thumb" />
              ) : (
                <div className="gallery-thumb gallery-thumb-placeholder">🖼️</div>
              )}
              <div className="gallery-card-meta">
                <span className="badge">{p.category}</span>
                {p.prompt && (
                  <p className="gallery-caption">{p.prompt.slice(0, 60)}{p.prompt.length > 60 ? "…" : ""}</p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Full-page modal */}
      {expandedPage && (
        <PageModal
          page={expandedPage}
          onClose={() => setExpandedPage(null)}
        />
      )}
    </div>
  );
}

// ── main app ──────────────────────────────────────────────────────────────────

function validateFile(file) {
  if (!ACCEPTED_TYPES.includes(file.type)) {
    return "Please choose a JPG, PNG, or WebP image.";
  }
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return `That file is too large — the max is ${MAX_SIZE_MB} MB.`;
  }
  return null;
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);

  useEffect(() => {
    getHealth()
      .then((h) =>
        dispatch({
          type: "SET_HEALTH",
          textFlowEnabled: !!h.text_flow_enabled,
          libraryEnabled: !!h.library_enabled,
        })
      )
      .catch(() => dispatch({ type: "SET_HEALTH", textFlowEnabled: false, libraryEnabled: false }));
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
    ((state.mode === "inspire" && state.file) ||
      (state.mode === "describe" && state.prompt.trim()));

  const submit = async () => {
    dispatch({ type: "WORKING" });
    try {
      const result =
        state.mode === "inspire"
          ? await fromInspire({ file: state.file, complexity: state.complexity })
          : await fromText({ prompt: state.prompt.trim(), complexity: state.complexity });
      dispatch({ type: "RESULT", result });
    } catch (e) {
      dispatch({ type: "ERROR", error: e.message });
    }
  };

  const isBrowse = state.mode === "browse";

  return (
    <div className="app">
      <AppHeader />

      <ModeTabs
        mode={state.mode}
        textFlowEnabled={state.textFlowEnabled}
        onChange={(m) => dispatch({ type: "SET_MODE", mode: m })}
      />

      {isBrowse ? (
        <div className="card browse-card">
          <BrowseTab libraryEnabled={state.libraryEnabled} />
        </div>
      ) : (
        <main className="layout">
          <section className="card input-card">
            {state.mode === "inspire" ? (
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

            {state.status === "error" && state.mode === "inspire" && (
              <div className="banner danger">{state.error}</div>
            )}

            <button className="btn-primary cta" disabled={!canSubmit} onClick={submit}>
              {state.status === "working"
                ? "Working…"
                : state.mode === "inspire"
                ? "Create coloring page"
                : "Generate & make page"}
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
      )}
    </div>
  );
}
