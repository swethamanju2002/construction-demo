document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-notification-center]').forEach((center) => {
    const toggle = center.querySelector('[data-notification-toggle]');
    const menu = center.querySelector('[data-notification-menu]');
    const count = center.querySelector('[data-notification-count]');
    const summary = center.querySelector('[data-notification-summary]');
    const items = center.querySelector('[data-notification-items]');
    const readAll = center.querySelector('[data-notification-read-all]');
    let loading = false;

    const post = async (url, body = '') => {
      const response = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCookie('csrftoken'),
        },
        body,
      });
      if (!response.ok) throw new Error(`Notification request failed (${response.status})`);
      return response.json();
    };

    const markRead = async (id) => {
      await post(center.dataset.readUrl, new URLSearchParams({ notification_id: id }));
    };

    const render = (data) => {
      const unreadCount = Number(data.unread_count) || 0;
      count.textContent = unreadCount > 99 ? '99+' : String(unreadCount);
      count.hidden = unreadCount === 0;
      toggle.setAttribute(
        'aria-label',
        unreadCount ? `Notifications, ${unreadCount} unread` : 'Notifications'
      );
      summary.textContent = unreadCount
        ? `${unreadCount} unread update${unreadCount === 1 ? '' : 's'}`
        : 'You’re all caught up';
      readAll.disabled = unreadCount === 0;
      items.replaceChildren();

      if (!data.notifications.length) {
        const empty = document.createElement('p');
        empty.className = 'notification-empty';
        empty.textContent = 'No notifications yet.';
        items.append(empty);
        return;
      }

      data.notifications.forEach((notification) => {
        const link = document.createElement('a');
        let targetUrl = '#';
        try {
          const parsed = new URL(notification.url, window.location.origin);
          if (parsed.origin === window.location.origin) {
            targetUrl = `${parsed.pathname}${parsed.search}${parsed.hash}`;
          }
        } catch (error) {
          console.error('Unable to render a notification link.', error);
        }
        link.href = targetUrl;
        link.className = `notification-item${notification.is_read ? '' : ' unread'}`;

        const heading = document.createElement('strong');
        heading.textContent = notification.title;
        const message = document.createElement('span');
        message.textContent = notification.message;
        const time = document.createElement('time');
        time.dateTime = notification.created_at;
        const createdAt = new Date(notification.created_at);
        time.textContent = Number.isNaN(createdAt.getTime())
          ? ''
          : createdAt.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

        link.append(heading, message, time);
        if (!notification.is_read) {
          const unreadDot = document.createElement('span');
          unreadDot.className = 'notification-unread-dot';
          unreadDot.setAttribute('aria-hidden', 'true');
          link.append(unreadDot);
        }
        link.addEventListener('click', async (event) => {
          if (targetUrl === '#') {
            event.preventDefault();
            return;
          }
          if (!notification.is_read) {
            event.preventDefault();
            try {
              await markRead(notification.id);
            } catch (error) {
              console.error('Unable to mark the notification as read.', error);
            }
            window.location.assign(targetUrl);
          }
        });
        items.append(link);
      });
    };

    const refresh = async () => {
      if (loading) return;
      loading = true;
      try {
        const response = await fetch(center.dataset.apiUrl, {
          credentials: 'same-origin',
          headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error(`Notification feed failed (${response.status})`);
        render(await response.json());
      } catch (error) {
        console.error('Unable to load notifications.', error);
      } finally {
        loading = false;
      }
    };

    toggle.addEventListener('click', () => {
      const isOpen = !menu.hidden;
      menu.hidden = isOpen;
      toggle.setAttribute('aria-expanded', String(!isOpen));
      if (!isOpen) refresh();
    });

    readAll.addEventListener('click', async () => {
      try {
        await post(center.dataset.readAllUrl);
        await refresh();
      } catch (error) {
        console.error('Unable to mark notifications as read.', error);
      }
    });

    document.addEventListener('click', (event) => {
      if (!center.contains(event.target)) {
        menu.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
      }
    });

    refresh();
    window.setInterval(refresh, 60000);
  });
});
