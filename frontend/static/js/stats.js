function tile(value, label) {
  return `<div class="stat-tile"><div class="value">${value}</div><div class="label">${label}</div></div>`;
}

async function load() {
  const { summary, by_date } = await API.getStats();

  document.getElementById("summary-tiles").innerHTML = [
    tile(summary.total_count, "總筆數"),
    tile(summary.pricing_slip_not_received_count, "尚未收到計價單"),
    tile(summary.pricing_slip_received_count, "已收到計價單"),
    tile(summary.unpaid_count, "未付款筆數"),
    tile(summary.scheduled_count, "已排款筆數"),
    tile(summary.paid_count, "已付款筆數"),
  ].join("");

  const locBody = document.querySelector("#location-table tbody");
  locBody.innerHTML = summary.by_location.length
    ? summary.by_location.map((l) => `<tr><td>${l.location}</td><td>${l.count}</td><td>${fmtNumber(l.net_weight_kg)}</td></tr>`).join("")
    : `<tr><td colspan="3">尚無資料</td></tr>`;

  const dateBody = document.querySelector("#date-table tbody");
  dateBody.innerHTML = by_date.length
    ? by_date.map((d) => `<tr><td>${d.date}</td><td>${fmtNumber(d.amount)}</td><td>${d.detail}</td></tr>`).join("")
    : `<tr><td colspan="3">尚無資料</td></tr>`;
}

load();
