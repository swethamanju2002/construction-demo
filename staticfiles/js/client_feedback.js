document.addEventListener('DOMContentLoaded', () => {
  const modal = document.querySelector('[data-feedback-modal]');
  const form = modal?.querySelector('[data-feedback-form]');
  if (!modal || !form) return;

  const title = modal.querySelector('[data-feedback-title]');
  const context = modal.querySelector('[data-feedback-context]');
  const errorMessage = modal.querySelector('[data-feedback-error]');
  const messageField = form.elements.message;
  const notificationField = form.elements.notification_id;
  const submitButton = form.querySelector('[type="submit"]');
  let loading = false;
  let activeNotificationId = null;

  const hideModal = () => {
    modal.hidden = true;
    activeNotificationId = null;
  };

  const showError = (message) => {
    errorMessage.textContent = message;
    errorMessage.hidden = false;
  };

  const post = async (url, body) => {
    const response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
    return data;
  };

  const poll = async () => {
    if (loading || !modal.hidden) return;
    loading = true;
    try {
      const response = await fetch(form.dataset.pendingUrl, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`Feedback request failed (${response.status})`);
      const data = await response.json();
      if (!data.request) return;

      activeNotificationId = data.request.notification_id;
      notificationField.value = String(activeNotificationId);
      title.textContent = `How does ${data.request.site_name} look?`;
      context.textContent = `${data.request.title}: ${data.request.message}`;
      messageField.value = '';
      errorMessage.hidden = true;
      modal.hidden = false;
      messageField.focus();
    } catch (error) {
      console.error('Unable to check for feedback requests.', error);
    } finally {
      loading = false;
    }
  };

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!activeNotificationId) return;
    errorMessage.hidden = true;
    submitButton.disabled = true;
    try {
      await post(
        form.dataset.submitUrl,
        new URLSearchParams(new FormData(form))
      );
      hideModal();
      await poll();
    } catch (error) {
      showError(error.message);
    } finally {
      submitButton.disabled = false;
    }
  });

  modal.querySelectorAll('[data-feedback-dismiss]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (!activeNotificationId) return;
      errorMessage.hidden = true;
      button.disabled = true;
      try {
        await post(
          form.dataset.dismissUrl,
          new URLSearchParams({ notification_id: activeNotificationId })
        );
        hideModal();
        await poll();
      } catch (error) {
        showError(error.message);
      } finally {
        button.disabled = false;
      }
    });
  });

  poll();
  window.setInterval(poll, 20000);
});
