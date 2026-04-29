/**
 * dashboard.js — Carga datos de /api/dashboard y renderiza gráficas Chart.js
 * Paleta: borgoña + dorado institucional
 */

const COLORS = {
  bordo:  '#6B2737',
  dorado: '#C4973A',
  verde:  '#2D6A4F',
  azul:   '#1A4D6B',
  gris:   '#9A9088',
  bordoAlpha: 'rgba(107,39,55,.15)',
  doradoAlpha:'rgba(196,151,58,.15)',
};

const PALETTE_DONA = [
  '#6B2737','#C4973A','#2D6A4F','#1A4D6B',
  '#8B5A2B','#4A5568','#9B2335','#2C5F2E',
];

Chart.defaults.font.family = "'Source Sans 3', system-ui, sans-serif";
Chart.defaults.font.size   = 12;
Chart.defaults.color       = '#5A5448';

async function cargarDashboard() {
  try {
    const res  = await fetch('/api/dashboard');
    const data = await res.json();

    renderMovimientos(data.entradas_salidas);
    renderDeptos(data.top_departamentos);
    renderMateriales(data.top_materiales);
  } catch (e) {
    console.error('Error cargando dashboard:', e);
  }
}

function renderMovimientos(d) {
  const ctx = document.getElementById('chartMovimientos');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: d.labels,
      datasets: [
        {
          label: 'Entradas',
          data: d.entradas,
          backgroundColor: COLORS.doradoAlpha,
          borderColor: COLORS.dorado,
          borderWidth: 2,
          borderRadius: 4,
        },
        {
          label: 'Salidas',
          data: d.salidas,
          backgroundColor: COLORS.bordoAlpha,
          borderColor: COLORS.bordo,
          borderWidth: 2,
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: 'index' },
      plugins: {
        legend: { position: 'top', align: 'end' },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0,0,0,.06)' },
          ticks: { stepSize: 1 },
        },
      },
    },
  });
}

function renderDeptos(d) {
  const ctx = document.getElementById('chartDeptos');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: d.labels,
      datasets: [{
        data: d.data,
        backgroundColor: PALETTE_DONA,
        borderWidth: 2,
        borderColor: '#fff',
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      cutout: '60%',
      plugins: {
        legend: {
          position: 'right',
          labels: { boxWidth: 12, padding: 14, font: { size: 11 } },
        },
      },
    },
  });
}

function renderMateriales(d) {
  const ctx = document.getElementById('chartMateriales');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: d.labels,
      datasets: [{
        label: 'Unidades solicitadas',
        data: d.data,
        backgroundColor: d.data.map((_, i) =>
          i === 0 ? COLORS.bordo : i < 3 ? COLORS.dorado : '#D6CBBC'
        ),
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: 'rgba(0,0,0,.06)' } },
        y: { grid: { display: false } },
      },
    },
  });
}

document.addEventListener('DOMContentLoaded', cargarDashboard);
