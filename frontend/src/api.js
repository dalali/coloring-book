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

export async function fromImage({ file, complexity }) {
  const form = new FormData();
  form.append("file", file);
  form.append("complexity", complexity);
  const resp = await fetch(`${API_URL}/api/coloring/from-image`, {
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
