'use strict';
const dashboardData = document.getElementById('dashboard-data');
if (dashboardData) {
  try {
    if (!window.Chart) throw new Error('Chart.js indisponível');
    const charts = JSON.parse(dashboardData.dataset.charts);
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = 'Segoe UI, system-ui, sans-serif';
    Chart.defaults.font.size = 11;
    const palette = ['#38bdf8','#a78bfa','#22c55e','#f59e0b'];
    for (const [key, values] of Object.entries(charts)) {
      new Chart(document.getElementById(`${key}-chart`), {
        type: key === 'activity' ? 'line' : 'bar',
        data: {labels: values.labels, datasets: values.datasets.map((series,index) => ({
          ...series, borderColor: palette[index % palette.length],
          backgroundColor: palette[index % palette.length], borderWidth: 2,
          pointRadius: 2, tension: .15, maxBarThickness: 42,
        }))},
        options: {responsive:true, maintainAspectRatio:false, animation:false,
          plugins:{legend:{display:values.datasets.length > 1}},
          scales:{x:{grid:{display:false},ticks:{maxTicksLimit:8}},
            y:{beginAtZero:true, max:key === 'availability' ? 100 : undefined,
              ticks:{precision:0},grid:{color:'#243146'}}}},
      });
    }
  } catch (_) {
    document.getElementById('chart-error').hidden = false;
    document.querySelectorAll('.chart-data').forEach(element => { element.open = true; });
  }
}
