const form = document.getElementById("record-form");
let currentImageId = null;
let currentOcrText = "";
let OPTIONS = {};

function populateSelect(name, values, selected) {
  const sel = form.elements[name];
  sel.innerHTML = `<option value="">（未填）</option>` +
    values.map((v) => `<option value="${v}" ${v === selected ? "selected" : ""}>${v}</option>`).join("") +
    `<option value="__new__">+ 新增選項…</option>`;
}

async function loadOptions() {
  OPTIONS = await API.getOptions();
  populateSelect("location", OPTIONS.location || []);
  populateSelect("pricing_slip_received", OPTIONS.pricing_slip_received || []);
  populateSelect("payment_status", OPTIONS.payment_status || []);
}

async function handleNewOption(selectEl, category) {
  const value = prompt("請輸入新的選項內容：");
  if (!value) {
    selectEl.value = "";
    return;
  }
  await API.addOption(category, value);
  await loadOptions();
  selectEl.value = value;
}

["location", "pricing_slip_received", "payment_status"].forEach((name) => {
  form.elements[name].addEventListener("change", (ev) => {
    if (ev.target.value === "__new__") handleNewOption(ev.target, name);
  });
});

function markGuessed(name) {
  const el = form.elements[name];
  if (el) el.classList.add("guessed");
}
function clearGuessMarks() {
  Array.from(form.elements).forEach((el) => el.classList && el.classList.remove("guessed"));
}

async function handleFile(file) {
  if (!file) return;
  const previewImg = document.getElementById("preview-img");
  previewImg.src = URL.createObjectURL(file);
  previewImg.style.display = "block";

  const statusEl = document.getElementById("ocr-status");
  statusEl.textContent = "OCR 辨識中…";

  try {
    const result = await API.ocrImage(file);
    currentImageId = result.image_id;
    currentOcrText = result.raw_text || "";

    if (!result.ocr_available) {
      statusEl.textContent = result.ocr_message || "OCR 無法使用，請手動填寫。";
    } else if (!result.raw_text.trim()) {
      statusEl.textContent = "OCR 沒有辨識到文字，請手動填寫下方欄位。";
    } else {
      statusEl.textContent = "OCR 已辨識，已為找到的欄位填入建議值（黃底），請核對後修改。";
    }

    if (result.raw_text) {
      document.getElementById("ocr-details").style.display = "block";
      document.getElementById("ocr-raw").textContent = result.raw_text;
    }

    clearGuessMarks();
    const g = result.guesses || {};
    Object.entries(g).forEach(([key, value]) => {
      const el = form.elements[key];
      if (!el || value === null || value === undefined) return;
      el.value = value;
      markGuessed(key);
    });
  } catch (e) {
    statusEl.textContent = "OCR 呼叫失敗：" + e.message + "（可直接手動填寫）";
  }
}

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (ev) => handleFile(ev.target.files[0]));
["dragover", "dragenter"].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add("dragover"); })
);
["dragleave", "drop"].forEach((evt) =>
  dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.remove("dragover"); })
);
dropZone.addEventListener("drop", (e) => handleFile(e.dataTransfer.files[0]));

function resetForm() {
  form.reset();
  clearGuessMarks();
  currentImageId = null;
  currentOcrText = "";
  document.getElementById("preview-img").style.display = "none";
  document.getElementById("ocr-status").textContent = "";
  document.getElementById("ocr-details").style.display = "none";
}
document.getElementById("btn-reset").addEventListener("click", resetForm);

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const fd = new FormData(form);
  const data = {
    location: fd.get("location") || "",
    unload_date: fd.get("unload_date") || null,
    slip_no: fd.get("slip_no") || null,
    vehicle_no: fd.get("vehicle_no") || null,
    owner_boat: fd.get("owner_boat") || null,
    gross_weight: fd.get("gross_weight") ? Number(fd.get("gross_weight")) : null,
    tare_weight: fd.get("tare_weight") ? Number(fd.get("tare_weight")) : null,
    net_weight: fd.get("net_weight") ? Number(fd.get("net_weight")) : null,
    notes: fd.get("notes") || null,
    pricing_slip_received: fd.get("pricing_slip_received") || null,
    pricing_slip_date: fd.get("pricing_slip_date") || null,
    payment_schedule: fd.get("payment_schedule") || null,
    price_amount: fd.get("price_amount") ? Number(fd.get("price_amount")) : null,
    net_transfer_amount: fd.get("net_transfer_amount") ? Number(fd.get("net_transfer_amount")) : null,
    payment_status: fd.get("payment_status") || null,
    actual_payment_date: fd.get("actual_payment_date") || null,
    included_in_stats: form.elements["included_in_stats"].checked,
    image_id: currentImageId,
    ocr_raw_text: currentOcrText || null,
  };
  if (!data.location) {
    toast("請選擇卸魚地點", true);
    return;
  }
  try {
    await API.createRecord(data);
    toast("已儲存，可繼續新增下一筆");
    resetForm();
  } catch (e) {
    toast(e.message, true);
  }
});

loadOptions();
