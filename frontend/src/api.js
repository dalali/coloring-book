// Thin API client using native fetch (architecture §1.2, §7).
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const MAX_SIZE_MB = 10;
export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

async function parseError(resp) {
  try {
    const body = await resp.json();
    if (body && body.error && body.error.message) return body.error.message;
  } catch {
    /* fall through */
  }
  return `Request failed (${resp.status}).`;
}

export async function getHealth() {
  const resp = await fetch(`${API_URL}/api/health`);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

// ── creation ─────────────────────────────────────────────────────────────────

export async function fromInspire({ file, complexity }) {
  const form = new FormData();
  form.append("file", file);
  form.append("complexity", complexity);
  const resp = await fetch(`${API_URL}/api/coloring/from-inspire`, {
    method: "POST",
    body: form,
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

export async function fromText({ prompt, complexity }) {
  const resp = await fetch(`${API_URL}/api/coloring/from-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, complexity }),
  });
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}

// ── library ───────────────────────────────────────────────────────────────────

export async function getLibrary({ category = null, limit = 24, offset = 0 } = {}) {
  const params = new URLSearchParams({ limit, offset });
  if (category && category !== "All") params.set("category", category);
  const resp = await fetch(`${API_URL}/api/library?${params}`);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json(); // { pages: [...], total_shown: N }
}

export async function getLibraryCategories() {
  const resp = await fetch(`${API_URL}/api/library/categories`);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json(); // [{ category, count }, ...]
}

export async function getLibraryPage(id) {
  const resp = await fetch(`${API_URL}/api/library/${id}`);
  if (!resp.ok) throw new Error(await parseError(resp));
  return resp.json();
}
