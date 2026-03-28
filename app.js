const COORDS = { latitude: 45.16, longitude: 18.01 }; // Slavonski Brod
const DAILY_FIELDS = ["temperature_2m_mean", "temperature_2m_min", "temperature_2m_max"];

const form = document.querySelector("#weather-form");
const fromDateInput = document.querySelector("#from-date");
const toDateInput = document.querySelector("#to-date");
const yearsInput = document.querySelector("#years");
const loadBtn = document.querySelector("#load-btn");
const statusEl = document.querySelector("#status");
const tableBody = document.querySelector("#summary-table tbody");

const chartCtx = document.querySelector("#temp-chart");
let chart;

const todayIso = new Date().toISOString().slice(0, 10);
fromDateInput.value = `${new Date().getUTCFullYear()}-01-01`;
toDateInput.value = todayIso;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearOutput();

  const fromDate = new Date(`${fromDateInput.value}T00:00:00Z`);
  const toDate = new Date(`${toDateInput.value}T00:00:00Z`);
  const years = Number(yearsInput.value);

  if (Number.isNaN(fromDate.getTime()) || Number.isNaN(toDate.getTime())) {
    setStatus("Please provide valid start and end dates.");
    return;
  }

  if (fromDate > toDate) {
    setStatus("From date must be before or equal to To date.");
    return;
  }

  if (!Number.isInteger(years) || years < 1 || years > 30) {
    setStatus("Last N years must be between 1 and 30.");
    return;
  }

  const durationDays = Math.floor((toDate - fromDate) / 86400000) + 1;
  const endYear = toDate.getUTCFullYear();
  const requests = [];

  for (let i = 0; i < years; i += 1) {
    const year = endYear - i;
    const periodStart = makeDateInYear(fromDate, year);
    const periodEnd = addDays(periodStart, durationDays - 1);

    if (periodStart > new Date()) {
      continue;
    }

    requests.push(fetchYearData(year, periodStart, periodEnd));
  }

  if (!requests.length) {
    setStatus("No valid historical years available for selected range.");
    return;
  }

  try {
    loadBtn.disabled = true;
    setStatus("Loading data from Open-Meteo archive API...");

    const allData = await Promise.all(requests);
    const valid = allData.filter((entry) => entry.daily.time.length > 0);

    if (!valid.length) {
      setStatus("No data returned for the selected settings.");
      return;
    }

    renderTable(valid);
    renderChart(valid);
    setStatus(`Loaded ${valid.length} year(s) of data for Slavonski Brod.`);
  } catch (error) {
    console.error(error);
    setStatus("Failed to load weather data. Try again in a moment.");
  } finally {
    loadBtn.disabled = false;
  }
});

async function fetchYearData(year, startDate, endDate) {
  const params = new URLSearchParams({
    latitude: COORDS.latitude,
    longitude: COORDS.longitude,
    start_date: toIsoDate(startDate),
    end_date: toIsoDate(endDate),
    daily: DAILY_FIELDS.join(","),
    timezone: "UTC",
  });

  const response = await fetch(`https://archive-api.open-meteo.com/v1/archive?${params}`);
  if (!response.ok) {
    throw new Error(`API failed for ${year}: ${response.status}`);
  }

  const payload = await response.json();
  return { year, daily: payload.daily };
}

function makeDateInYear(sourceDate, targetYear) {
  const month = sourceDate.getUTCMonth();
  const day = sourceDate.getUTCDate();
  const candidate = new Date(Date.UTC(targetYear, month, day));

  if (candidate.getUTCMonth() !== month) {
    return new Date(Date.UTC(targetYear, month + 1, 0));
  }
  return candidate;
}

function addDays(date, days) {
  return new Date(date.getTime() + days * 86400000);
}

function toIsoDate(date) {
  return date.toISOString().slice(0, 10);
}

function setStatus(text) {
  statusEl.textContent = text;
}

function clearOutput() {
  tableBody.innerHTML = "";
  if (chart) {
    chart.destroy();
    chart = null;
  }
}

function renderTable(yearData) {
  const sorted = [...yearData].sort((a, b) => a.year - b.year);
  for (const item of sorted) {
    const meanTemps = item.daily.temperature_2m_mean;
    const minTemps = item.daily.temperature_2m_min;
    const maxTemps = item.daily.temperature_2m_max;

    const avgMean = average(meanTemps);
    const minValue = Math.min(...minTemps);
    const maxValue = Math.max(...maxTemps);

    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.year}</td>
      <td>${avgMean.toFixed(2)}</td>
      <td>${minValue.toFixed(2)}</td>
      <td>${maxValue.toFixed(2)}</td>
    `;
    tableBody.appendChild(row);
  }
}

function renderChart(yearData) {
  const sorted = [...yearData].sort((a, b) => a.year - b.year);
  const dayCount = Math.max(...sorted.map((item) => item.daily.time.length));
  const labels = Array.from({ length: dayCount }, (_, i) => `Day ${i + 1}`);

  const datasets = sorted.map((item, index) => ({
    label: String(item.year),
    data: item.daily.temperature_2m_mean,
    borderWidth: 2,
    tension: 0.2,
    pointRadius: 0,
    borderColor: colorFor(index, sorted.length),
    spanGaps: true,
  }));

  chart = new Chart(chartCtx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: "nearest", intersect: false },
      plugins: {
        legend: { position: "bottom" },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} °C` } },
      },
      scales: {
        y: {
          title: { display: true, text: "Mean temperature (°C)" },
        },
        x: {
          title: { display: true, text: "Day in selected period" },
        },
      },
    },
  });
}

function average(values) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function colorFor(index, total) {
  const hue = Math.round((index / Math.max(total, 1)) * 320);
  return `hsl(${hue}, 70%, 45%)`;
}
