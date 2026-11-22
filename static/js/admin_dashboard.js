// Admin Dashboard Dynamic Interactions & Task Checklist Engine
document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('adminSidebar');
  const menuToggle = document.getElementById('adminMenuToggle');
  const sidebarBackdrop = document.getElementById('adminSidebarBackdrop');

  const closeSidebar = () => {
    if (sidebar) sidebar.classList.remove('open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
    if (menuToggle) menuToggle.setAttribute('aria-expanded', 'false');
  };

  if (menuToggle && sidebar) {
    menuToggle.addEventListener('click', () => {
      const isOpen = sidebar.classList.toggle('open');
      if (sidebarBackdrop) sidebarBackdrop.classList.toggle('active', isOpen);
      menuToggle.setAttribute('aria-expanded', String(isOpen));
    });
  }
  if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', closeSidebar);

  const dateTarget = document.getElementById('adminCurrentDate');
  if (dateTarget) {
    dateTarget.textContent = new Intl.DateTimeFormat('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    }).format(new Date());
  }

  document.querySelectorAll('.reveal').forEach((element, index) => {
    element.style.animationDelay = `${Math.min(index * 70, 350)}ms`;
  });

  if (window.Chart) {
    document.querySelectorAll('.siteProgressChart').forEach((canvas) => {
      const completed = Number(canvas.dataset.completed || 0);
      const remaining = Math.max(0, 100 - completed);
      new Chart(canvas, {
        type: 'doughnut',
        data: {
          datasets: [{
            data: [completed, remaining],
            backgroundColor: ['#1976ED', '#E8EEF7'],
            borderWidth: 0,
            borderRadius: 3
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '72%',
          rotation: -90,
          circumference: 360,
          plugins: {
            legend: { display: false },
            tooltip: { enabled: false }
          },
          animation: { animateRotate: true, duration: 800 }
        }
      });
    });
  }

  const csrftoken = getCookie('csrftoken');

  // Subtask Checklist Toggle
  document.querySelectorAll('.task-toggle-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', async (e) => {
      const taskId = e.target.getAttribute('data-task-id');
      const itemContainer = document.getElementById(`task-item-${taskId}`);
      
      try {
        const response = await fetch('/admin-portal/api/toggle-task/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
          },
          body: JSON.stringify({ task_id: taskId })
        });

        const data = await response.json();
        if (data.success) {
          // Update item state
          if (data.is_completed) {
            itemContainer.classList.add('completed');
          } else {
            itemContainer.classList.remove('completed');
          }

          // Update Category Progress Bar & Count
          const categoryId = data.category_id;
          const catProgressBar = document.getElementById(`cat-progress-bar-${categoryId}`);
          const catProgressText = document.getElementById(`cat-progress-text-${categoryId}`);
          const catTaskCount = document.getElementById(`cat-task-count-${categoryId}`);

          if (catProgressBar) {
            catProgressBar.style.width = `${data.category_progress}%`;
          }
          if (catProgressText) {
            catProgressText.textContent = `${data.category_progress}%`;
          }
          if (catTaskCount) {
            catTaskCount.textContent = `${data.completed_tasks} of ${data.total_tasks} completed`;
          }

          // Update Site Overall Progress Header & Progress Bar
          const overallProgressVal = document.getElementById('overall-progress-val');
          const overallProgressBar = document.getElementById('overall-progress-bar');
          if (overallProgressVal) {
            overallProgressVal.textContent = `${data.overall_progress}%`;
          }
          if (overallProgressBar) {
            overallProgressBar.style.width = `${data.overall_progress}%`;
          }
        } else {
          alert(`Error updating task: ${data.error || 'Server error'}`);
          e.target.checked = !e.target.checked;
        }
      } catch (err) {
        console.error('Fetch error toggling task:', err);
        alert('Communication error. Reverting change.');
        e.target.checked = !e.target.checked;
      }
    });
  });

  // Optional Category Enable/Disable Switch
  document.querySelectorAll('.category-toggle-checkbox').forEach(toggle => {
    toggle.addEventListener('change', async (e) => {
      const categoryProgressId = e.target.getAttribute('data-category-progress-id');
      const isEnabled = e.target.checked;
      const categoryCard = document.getElementById(`category-card-${categoryProgressId}`);
      
      try {
        const response = await fetch('/admin-portal/api/toggle-category/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken,
          },
          body: JSON.stringify({
            category_progress_id: categoryProgressId,
            is_enabled: isEnabled
          })
        });

        const data = await response.json();
        if (data.success) {
          // Toggle card opacity / enabled visual styling
          if (categoryCard) {
            if (data.is_enabled) {
              categoryCard.classList.remove('category-disabled');
              const badge = document.getElementById(`cat-status-badge-${categoryProgressId}`);
              if (badge) {
                badge.className = 'badge badge-ongoing';
                badge.textContent = 'Active / Enabled';
              }
            } else {
              categoryCard.classList.add('category-disabled');
              const badge = document.getElementById(`cat-status-badge-${categoryProgressId}`);
              if (badge) {
                badge.className = 'badge badge-optional';
                badge.textContent = 'Disabled (Excluded from Calc)';
              }
            }
          }

          // Update Site Overall Progress Indicator
          const overallProgressVal = document.getElementById('overall-progress-val');
          const overallProgressBar = document.getElementById('overall-progress-bar');
          if (overallProgressVal) {
            overallProgressVal.textContent = `${data.overall_progress}%`;
          }
          if (overallProgressBar) {
            overallProgressBar.style.width = `${data.overall_progress}%`;
          }
        } else {
          alert(`Error: ${data.error}`);
          e.target.checked = !isEnabled;
        }
      } catch (err) {
        console.error('Fetch error toggling category:', err);
        alert('Network error updating category toggle.');
        e.target.checked = !isEnabled;
      }
    });
  });
});
