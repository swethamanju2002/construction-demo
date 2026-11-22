// Client Dashboard Visual Progress Analytics Engine
document.addEventListener('DOMContentLoaded', () => {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const animationDuration = prefersReducedMotion ? 0 : 800;

  // 1. Overall Progress Donut Chart
  const donutCanvas = document.getElementById('overallProgressDonut');
  if (donutCanvas && window.Chart) {
    const completedPct = parseFloat(donutCanvas.getAttribute('data-completed') || '0');
    const remainingPct = parseFloat(donutCanvas.getAttribute('data-remaining') || '100');

    // Custom plugin to draw percentage in center of donut
    const centerTextPlugin = {
      id: 'centerText',
      afterDraw(chart) {
        const { ctx, chartArea: { top, bottom, left, right, width, height } } = chart;
        ctx.save();
        const centerX = left + width / 2;
        const centerY = top + height / 2;

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Value text
        ctx.font = 'bold 2rem Inter, sans-serif';
        ctx.fillStyle = '#10213F';
        ctx.fillText(`${completedPct}%`, centerX, centerY - 6);

        // Subtitle text
        ctx.font = '600 0.8rem Inter, sans-serif';
        ctx.fillStyle = '#687B98';
        ctx.fillText('COMPLETED', centerX, centerY + 22);

        ctx.restore();
      }
    };

    new Chart(donutCanvas, {
      type: 'doughnut',
      data: {
        labels: ['Completed', 'Remaining'],
        datasets: [{
          data: [completedPct, remainingPct],
          backgroundColor: ['#1976ED', '#E8EEF7'],
          hoverBackgroundColor: ['#1266D6', '#D6E0EE'],
          borderWidth: 0,
          cutout: '76%',
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: animationDuration,
        },
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label: (context) => ` ${context.label}: ${context.raw}%`
            }
          }
        }
      },
      plugins: [centerTextPlugin]
    });
  }

  // 2. Category Breakdown Horizontal Bar Chart
  const barCanvas = document.getElementById('categoryBarChart');
  if (barCanvas && window.Chart) {
    const rawLabels = barCanvas.getAttribute('data-labels');
    const rawData = barCanvas.getAttribute('data-values');

    let labels = [];
    let values = [];

    try {
      labels = JSON.parse(rawLabels || '[]');
      values = JSON.parse(rawData || '[]');
    } catch (err) {
      console.error('Error parsing category chart data:', err);
    }

    // Palette mapping by category
    const categoryColors = [
      '#1976ED', // Building Work
      '#F5B323', // Electrical Work
      '#19B66A', // Plumbing Work
      '#657EEA', // Showcase Work
      '#48A8B5', // Wall Ceiling Work
    ];

    new Chart(barCanvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Completion %',
          data: values,
          backgroundColor: categoryColors.slice(0, labels.length),
          borderRadius: 6,
          barThickness: 24,
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: animationDuration,
        },
        scales: {
          x: {
            min: 0,
            max: 100,
            ticks: {
              callback: (val) => `${val}%`,
              stepSize: 25,
            },
            grid: {
              color: '#F1F5F9',
            }
          },
          y: {
            grid: {
              display: false,
            },
            ticks: {
              font: {
                family: 'Inter, sans-serif',
                weight: '600',
              },
              color: '#10213F',
            }
          }
        },
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label: (context) => ` ${context.raw}% Completed`
            }
          }
        }
      }
    });
  }
});
