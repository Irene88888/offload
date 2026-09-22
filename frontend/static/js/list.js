const EDIT_FIELDS = [
  { key: "location", label: "卸魚地點", type: "select", cat: "location", required: true },
  { key: "unload_date", label: "卸魚日期", type: "date" },
  { key: "slip_no", label: "傳票編號/序號", type: "text" },
  { key: "vehicle_no", label: "車號", type: "text" },
  { key: "owner_boat", label: "魚貨主/船名", type: "text" },
  { key: "gross_weight", label: "總重(KG)", type: "number" },
  { key: "tare_weight", label: "空重(KG)", type: "number" },
  { key: "net_weight", label: "淨重(KG)", type: "number" },
  { key: "notes", label: "備註(魚種/數量)", type: "textarea" },
  { key: "pricing_slip_received", label: "是否收到計價單", type: "select", cat: "pricing_slip_received" },
  { key: "pricing_slip_date", label: "計價單收到日期", type: "date" },
  { key: "payment_schedule", label: "付款排程(卸魚+14天)", type: "date" },
  { key: "price_amount", label: "計價金額(未稅,元)", type: "number" },
  { key: "net_transfer_amount", label: "切結轉帳淨額(元)", type: "number" },
  { key: "payment_status", label: "付款狀態", type: "select", cat: "payment_status" },
  { key: "actual_payment_date", label: "實際付款日", type: "date" },
  { key: "included_in_stats", label: "計入統計加總（金額未併入其他列）", type: "checkbox" },
];

let OPTIONS = {};
let CURRENT_EDIT_ID = null;

function fieldInputHtml(f, value) {
  const v = value === null || value === undefined ? "" : value;
  if (f.type === "select") {
    const opts = (OPTIONS[f.cat] || [])
      .map((o) => `<option value="${o}" ${o === v ? "selected" : ""}>${o}</option>`)
      .join("");
    return `<select name="${f.key}"><option value="">（未填）</option>${opts}</select>`;
  }
  if (f.type === "textarea") {
    return `<textarea name="${f.key}" rows="2">${v}</textarea>`;
  }
  if (f.type === "checkbox") {
    return `<input type="checkbox" name="${f.key}" ${v ? "checked" : ""} style="width:auto;">`;
  }
  return `<input type="${f.type}" name="${f.key}" value="${v}">`;
}

async function loadOptionsIntoFilters() {
  OPTIONS = await API.getOptions();
  const fill = (id, cat) => {
    const sel = document.getElementById(id);
    (OPTIONS[cat] || []).forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v; opt.textContent = v;
      sel.appendChild(opt);
    });
  };
  fill("f-location", "location");
  fill("f-pricing", "pricing_slip_received");
  fill("f-payment", "payment_status");
}

function currentFilters() {
  return {
    location: document.getElementById("f-location").value,
    pricing_slip_received: document.getElementById("f-pricing").value,
    payment_status: document.getElementById("f-payment").value,
    date_from: document.getElementById("f-date-from").value,
    date_to: document.getElementById("f-date-to").value,
    q: document.getElementById("f-q").value,
  };
}

function pricingKind(v) {
  if (v === "是") return "yes";
  if (v === "否") return "no";
  return "pending";
}
function paymentKind(v) {
  if (v === "已付款") return "yes";
  if (v === "未付款") return "no";
  return "pending";
}

function rowHtml(r) {
  const photo = r.image_path
    ? `<a href="/uploads/${r.image_path}" target="_blank">照片</a>`
    : "";
  return `<tr data-id="${r.id}">
    <td>${r.location || ""}</td>
    <td>${r.unload_date || ""}</td>
    <td>${r.owner_boat || ""}</td>
    <td>${r.slip_no || ""}</td>
    <td>${r.vehicle_no || ""}</td>
    <td>${fmtNumber(r.net_weight)}</td>
    <td class="notes-cell">${r.notes || ""}</td>
    <td>${statusBadge(r.pricing_slip_received, pricingKind(r.pricing_slip_received))}</td>
    <td>${statusBadge(r.payment_status, paymentKind(r.payment_status))}</td>
    <td>${fmtNumber(r.price_amount)}</td>
    <td>${fmtNumber(r.net_transfer_amount)}</td>
    <td>${r.payment_schedule || ""}</td>
    <td>${r.actual_payment_date || ""}</td>
    <td>${photo}</td>
    <td class="actions-cell">
      <button data-action="edit">編輯</button>
      <button data-action="delete" class="danger">刪除</button>
    </td>
  </tr>`;
}

async function refreshList() {
  const tbody = document.getElementById("records-body");
  tbody.innerHTML = `<tr><td colspan="15">載入中…</td></tr>`;
  const records = await API.listRecords(currentFilters());
  document.getElementById("count-hint").textContent = `共 ${records.length} 筆`;
  tbody.innerHTML = records.length
    ? records.map(rowHtml).join("")
    : `<tr><td colspan="15">沒有符合條件的紀錄</td></tr>`;
}

function openEditDialog(record) {
  CURRENT_EDIT_ID = record.id;
  const wrap = document.getElementById("edit-fields");
  wrap.innerHTML = EDIT_FIELDS.map(
    (f) => `<div class="field"><label>${f.label}</label>${fieldInputHtml(f, record[f.key])}</div>`
  ).join("");
  document.getElementById("edit-dialog").showModal();
}

async function handleTableClick(ev) {
  const btn = ev.target.closest("button[data-action]");
  if (!btn) return;
  const tr = ev.target.closest("tr[data-id]");
  const id = Number(tr.dataset.id);

  if (btn.dataset.action === "delete") {
    if (!confirm("確定要刪除這筆紀錄嗎？此動作無法復原。")) return;
    try {
      await API.deleteRecord(id);
      toast("已刪除");
      refreshList();
    } catch (e) {
      toast(e.message, true);
    }
  } else if (btn.dataset.action === "edit") {
    try {
      const records = await API.listRecords(currentFilters());
      const record = records.find((r) => r.id === id);
      if (record) openEditDialog(record);
    } catch (e) {
      toast(e.message, true);
    }
  }
}

async function handleEditSubmit(ev) {
  ev.preventDefault();
  const form = document.getElementById("edit-form");
  const data = {};
  EDIT_FIELDS.forEach((f) => {
    const el = form.elements[f.key];
    if (!el) return;
    if (f.type === "checkbox") {
      data[f.key] = el.checked;
    } else if (f.type === "number") {
      data[f.key] = el.value === "" ? null : Number(el.value);
    } else {
      data[f.key] = el.value || null;
    }
  });
  try {
    await API.patchRecord(CURRENT_EDIT_ID, data);
    document.getElementById("edit-dialog").close();
    toast("已儲存");
    refreshList();
  } catch (e) {
    toast(e.message, true);
  }
}

async function handleImport(ev) {
  const file = ev.target.files[0];
  if (!file) return;
  try {
    const res = await API.importXlsx(file);
    toast(`已匯入 ${res.imported} 筆紀錄`);
    await loadOptionsIntoFilters();
    refreshList();
  } catch (e) {
    toast(e.message, true);
  } finally {
    ev.target.value = "";
  }
}

document.getElementById("btn-filter").addEventListener("click", refreshList);
document.getElementById("btn-clear").addEventListener("click", () => {
  ["f-location", "f-pricing", "f-payment", "f-date-from", "f-date-to", "f-q"].forEach((id) => {
    document.getElementById(id).value = "";
  });
  refreshList();
});
document.getElementById("records-body").addEventListener("click", handleTableClick);
document.getElementById("edit-form").addEventListener("submit", handleEditSubmit);
document.getElementById("edit-cancel").addEventListener("click", () => document.getElementById("edit-dialog").close());
document.getElementById("import-file").addEventListener("change", handleImport);

(async function init() {
  await loadOptionsIntoFilters();
  await refreshList();
})();
