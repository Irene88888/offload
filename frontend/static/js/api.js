const API = {
  async listRecords(params = {}) {
    const qs = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v)));
    return API._json(`/api/records?${qs}`);
  },
  async createRecord(data) {
    return API._json("/api/records", { method: "POST", body: JSON.stringify(data) });
  },
  async patchRecord(id, data) {
    return API._json(`/api/records/${id}`, { method: "PATCH", body: JSON.stringify(data) });
  },
  async deleteRecord(id) {
    return API._json(`/api/records/${id}`, { method: "DELETE" });
  },
  async getOptions() {
    return API._json("/api/options");
  },
  async addOption(category, value) {
    return API._json("/api/options", { method: "POST", body: JSON.stringify({ category, value }) });
  },
  async getStats() {
    return API._json("/api/stats");
  },
  async ocrImage(file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/ocr", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "OCR 失敗");
    return res.json();
  },
  async importXlsx(file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/import-xlsx", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "匯入失敗");
    return res.json();
  },
  async _json(url, opts = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch {}
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  },
};

function toast(message, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

function fmtNumber(n) {
  if (n === null || n === undefined || n === "") return "";
  return Number(n).toLocaleString("zh-TW");
}

function statusBadge(text, kind) {
  if (!text) return "";
  const cls = kind === "yes" ? "yes" : kind === "no" ? "no" : "pending";
  return `<span class="badge ${cls}">${text}</span>`;
}
