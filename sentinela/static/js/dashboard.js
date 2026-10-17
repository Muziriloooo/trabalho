'use strict';
try {
  if (!window.Chart) throw new Error('Chart.js indisponível');
  Chart.defaults.color = '#94a3b8';
  Chart.defaults.font.family = 'Segoe UI, system-ui, sans-serif';
  Chart.defaults.font.size = 11;
  const options = {
    responsive: true, maintainAspectRatio: false,
    animation: false,
    plugins: {legend: {display: false}},
    scales: {
      x: {grid: {display: false}, border: {display: false}, ticks: {padding: 12}},
      y: {beginAtZero: true, grid: {color: '#243146'}, border: {display: false}, ticks: {padding: 12, precision: 0}},
    },
  };
  new Chart(document.getElementById('activity-chart'), {
    type: 'line',
    data: {labels: ['00h', '03h', '06h', '09h', '12h', '15h', '18h', '21h'], datasets: [{
      label: 'Eventos de exemplo', data: [8, 5, 12, 28, 21, 34, 25, 15],
      borderColor: '#38bdf8', backgroundColor: '#38bdf81a', fill: true,
      borderWidth: 2.5, tension: 0.35, pointRadius: 3, pointBackgroundColor: '#38bdf8', pointHoverRadius: 5,
    }]}, options,
  });
  new Chart(document.getElementById('sites-chart'), {
    type: 'bar', data: {labels: ['Centro', 'Norte', 'Sul'], datasets: [{
      label: 'Câmeras de exemplo', data: [10, 8, 6], backgroundColor: ['#2563eb', '#38bdf8', '#6366f1'],
      borderRadius: 5, maxBarThickness: 42,
    }]}, options,
  });
} catch (error) {
  document.getElementById('chart-error').hidden = false;
  document.querySelectorAll('.chart-data').forEach((element) => { element.open = true; });
}
