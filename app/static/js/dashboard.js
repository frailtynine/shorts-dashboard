const data = window.DASHBOARD_DATA;
const selectedChannel = window.SELECTED_CHANNEL;
const defaultWeekKey = window.DEFAULT_WEEK_KEY;
const isMobile = window.matchMedia("(max-width: 680px)").matches;

function compactWeekLabel(label) {
  const parts = String(label).split(" - ");
  if (!parts.length) {
    return label;
  }
  const first = parts[0].trim();
  const firstBits = first.split(" ");
  if (firstBits.length < 2) {
    return first;
  }
  const day = firstBits[0];
  const monthWord = firstBits[1];
  return `${day} ${monthWord.slice(0, 3)}.`;
}

const weekLabels = isMobile
  ? data.labels.map(compactWeekLabel)
  : data.labels;
const chartAnimation = isMobile ? false : { duration: 220 };

function pieTopThemes(input, limit = 6) {
  const labels = [];
  const values = [];
  let otherSum = 0;

  input.theme_labels.forEach((label, idx) => {
    const value = Number(input.theme_values[idx] || 0);
    if (idx < limit) {
      labels.push(label);
      values.push(value);
      return;
    }
    otherSum += value;
  });

  if (otherSum > 0) {
    labels.push("Прочие");
    values.push(otherSum);
  }

  return { labels, values };
}

const pieData = pieTopThemes(data, isMobile ? 5 : 8);

const ruNumber = (value) => new Intl.NumberFormat("ru-RU").format(value);

new Chart(document.getElementById("viewsChart"), {
  type: "bar",
  data: {
    labels: weekLabels,
    datasets: [{
      label: "Просмотры",
      data: data.weekly_views,
      backgroundColor: "rgba(14, 116, 144, 0.75)",
      borderColor: "rgba(14, 116, 144, 1)",
      borderWidth: 1,
    }],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: chartAnimation,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        ticks: {
          maxRotation: isMobile ? 0 : 40,
          minRotation: isMobile ? 0 : 0,
          autoSkip: true,
          maxTicksLimit: isMobile ? 5 : 9,
        },
      },
      y: {
        ticks: {
          callback: (value) => ruNumber(value),
        },
      },
    },
  },
});

new Chart(document.getElementById("durationChart"), {
  type: "line",
  data: {
    labels: weekLabels,
    datasets: [{
      label: "Средняя длительность",
      data: data.weekly_avg_duration,
      borderColor: "rgba(2, 132, 199, 1)",
      backgroundColor: "rgba(2, 132, 199, 0.2)",
      tension: 0.25,
      fill: true,
    }],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: chartAnimation,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        ticks: {
          maxRotation: isMobile ? 0 : 40,
          minRotation: isMobile ? 0 : 0,
          autoSkip: true,
          maxTicksLimit: isMobile ? 5 : 9,
        },
      },
    },
  },
});

new Chart(document.getElementById("themesChart"), {
  type: "pie",
  data: {
    labels: pieData.labels,
    datasets: [{
      data: pieData.values,
      backgroundColor: [
        "#0284c7", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed",
        "#0ea5e9", "#f97316", "#84cc16", "#14b8a6", "#8b5cf6",
      ],
    }],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: chartAnimation,
    elements: {
      arc: { borderWidth: 1 },
    },
    plugins: {
      legend: {
        display: !isMobile,
        position: "bottom",
        labels: { boxWidth: 12 },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const value = ctx.raw || 0;
            return `${ctx.label}: ${ruNumber(value)} ср. просмотров`;
          },
        },
      },
    },
  },
});

function applyWeekFilter() {
  const selected = document.getElementById("weekFilter").value;
  const weeklyGrid = document.getElementById("weeklyGrid");
  const showAll = selected === "all";

  weeklyGrid.classList.toggle("is-hidden", showAll);

  document.querySelectorAll(".week-card").forEach((card) => {
    const weekKey = card.dataset.weekKey;
    const visible = !showAll && weekKey === selected;
    card.classList.toggle("is-hidden", !visible);
  });

  document.querySelectorAll("#shortsTable tbody tr").forEach((row) => {
    const weekKey = row.dataset.weekKey;
    const visible = showAll || weekKey === selected;
    row.classList.toggle("is-hidden", !visible);
  });
}

window.applyWeekFilter = applyWeekFilter;

function onChannelChange() {
  const selected = document.getElementById("channelSelect").value;
  if (!selected) {
    return;
  }
  const url = new URL(window.location.href);
  url.searchParams.set("channel", selected);
  window.location.href = url.toString();
}

window.onChannelChange = onChannelChange;

const sortState = {
  published: true,
  title: true,
  theme: true,
  duration: true,
  views: true,
  likes: true,
  comments: true,
};

function sortTable(column, type) {
  const table = document.getElementById("shortsTable");
  const tbody = table.querySelector("tbody");
  const rows = Array.from(tbody.querySelectorAll("tr"));

  const indexMap = {
    published: 0,
    title: 1,
    theme: 2,
    duration: 3,
    views: 4,
    likes: 5,
    comments: 6,
  };
  const colIndex = indexMap[column];
  const asc = sortState[column];

  rows.sort((a, b) => {
    const aCell = a.children[colIndex];
    const bCell = b.children[colIndex];
    const aVal = aCell.dataset.sort || aCell.textContent.trim();
    const bVal = bCell.dataset.sort || bCell.textContent.trim();

    if (type === "number") {
      return asc
        ? Number(aVal) - Number(bVal)
        : Number(bVal) - Number(aVal);
    }
    if (type === "date") {
      return asc
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal));
    }
    return asc
      ? String(aVal).localeCompare(String(bVal), "ru")
      : String(bVal).localeCompare(String(aVal), "ru");
  });

  rows.forEach((row) => tbody.appendChild(row));
  sortState[column] = !asc;
}

window.sortTable = sortTable;

if (defaultWeekKey && defaultWeekKey !== "all") {
  const weekFilter = document.getElementById("weekFilter");
  weekFilter.value = defaultWeekKey;
}
applyWeekFilter();
