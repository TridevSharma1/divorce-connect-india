// Retrieve stored token (e.g. from local storage)
const getAccessToken = () => localStorage.getItem('access_token');
const getRefreshToken = () => localStorage.getItem('refresh_token');

/**
 * Fetch active notifications and populate navbar list and badge
 */
async function updateNavbarNotifications() {
  const token = getAccessToken();
  if (!token) {
    console.warn("User is not authenticated. Skipping notifications fetch.");
    return;
  }

  // Find DOM elements dynamically across client, lawyer, and admin navbars
  const badge = document.getElementById('notification-badge') || 
                document.getElementById('admin-notification-badge') || 
                document.getElementById('notificationDot');
                
  const listContainer = document.querySelector('.notifications-list') || 
                        document.querySelector('.admin-notifications-list') || 
                        document.getElementById('notificationsList');
                        
  const markAllReadBtn = document.getElementById('mark-all-read') || 
                        document.getElementById('admin-mark-all-read') || 
                        document.getElementById('markAllRead');

  if (!listContainer) return; // No notifications layout on this page

  try {
    let response = await fetch('/api/notifications/', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });

    if (response.status === 401) {
      console.log("Access token expired, attempting to refresh...");
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        return updateNavbarNotifications();
      } else {
        console.error("Token expired or invalid.");
        return;
      }
    }

    if (!response.ok) throw new Error("Failed to fetch notifications");

    const notifications = await response.json();
    
    // Render list
    listContainer.innerHTML = '';
    
    if (notifications.length === 0) {
      listContainer.innerHTML = '<div class="p-4 text-center text-xs text-gray-400">No notifications yet.</div>';
    } else {
      notifications.forEach(n => {
        const itemHTML = createNotificationItemHTML(n);
        listContainer.insertAdjacentHTML('beforeend', itemHTML);
      });
    }

    // Attach click handlers to dynamic items
    listContainer.querySelectorAll('.notification-item').forEach(item => {
      item.addEventListener('click', async function(e) {
        const id = this.getAttribute('data-id');
        const isRead = !this.classList.contains('bg-gray-50');
        if (!isRead) {
          e.preventDefault();
          const targetUrl = this.getAttribute('href');
          await markAsRead(id, this);
          if (targetUrl && targetUrl !== '#') {
            window.location.href = targetUrl;
          }
        }
      });
    });

    // Update UI badge
    const unreadCount = notifications.filter(n => !n.is_read).length;
    updateBadgeUI(unreadCount, badge);

    // Hook mark all read button
    if (markAllReadBtn) {
      markAllReadBtn.onclick = async function(e) {
        e.preventDefault();
        try {
          const res = await fetch('/api/notifications/mark-all-read/', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          });
          if (res.ok) {
            listContainer.querySelectorAll('.notification-item').forEach(item => {
              item.classList.remove('bg-gray-50');
              item.classList.add('bg-white');
              const indicator = item.querySelector('.unread-indicator');
              if (indicator) indicator.remove();
            });
            updateBadgeUI(0, badge);
          }
        } catch (err) {
          console.error("Error marking all read:", err);
        }
      };
    }

  } catch (error) {
    console.error("Error updating notifications list:", error);
  }
}

function updateBadgeUI(count, badge) {
  if (!badge) return;
  if (count > 0) {
    badge.innerText = count;
    badge.classList.remove('hidden');
    // For lawyer dot badge which uses simple opacity/visibility classes
    badge.classList.remove('opacity-0');
  } else {
    badge.innerText = '';
    badge.classList.add('hidden');
  }
}

async function markAsRead(id, element) {
  const token = getAccessToken();
  if (!token) return;
  try {
    const response = await fetch(`/api/notifications/${id}/`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ is_read: true })
    });
    if (response.ok) {
      element.classList.remove('bg-gray-50');
      element.classList.add('bg-white');
      const indicator = element.querySelector('.unread-indicator');
      if (indicator) indicator.remove();
      
      // Decrement badge count
      const badge = document.getElementById('notification-badge') || 
                    document.getElementById('admin-notification-badge') || 
                    document.getElementById('notificationDot');
      if (badge && badge.innerText.trim()) {
        let currentCount = parseInt(badge.innerText.trim());
        if (!isNaN(currentCount) && currentCount > 0) {
          updateBadgeUI(currentCount - 1, badge);
        }
      }
    }
  } catch (err) {
    console.error("Failed to mark notification as read:", err);
  }
}

function createNotificationItemHTML(notification) {
  const isUnread = !notification.is_read;
  const bgClass = isUnread ? 'bg-gray-50' : 'bg-white';
  const unreadIndicator = isUnread ? '<span class="unread-indicator w-2 h-2 bg-yellow-500 rounded-full flex-shrink-0"></span>' : '';
  const dateStr = new Date(notification.created_at).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
  const itemUrl = notification.url || '#';

  return `
    <a href="${itemUrl}" class="notification-item flex items-start gap-4 p-4 border-b border-gray-50 hover:bg-gray-50 transition-colors duration-150 ${bgClass}" data-id="${notification.id}">
      <div class="flex-1 min-w-0 text-left">
        <p class="text-sm font-semibold text-gray-900 truncate">${notification.title}</p>
        <p class="text-xs text-gray-500 mt-1 break-words">${notification.message}</p>
        <p class="text-[10px] text-gray-400 mt-2">${dateStr}</p>
      </div>
      <div class="flex items-center gap-2 mt-1">
        ${unreadIndicator}
      </div>
    </a>
  `;
}

// WebSocket setup for real-time notifications
let notificationWS = null;
function connectNotificationWS() {
  const token = getAccessToken();
  if (!token) return;

  if (notificationWS && (notificationWS.readyState === WebSocket.OPEN || notificationWS.readyState === WebSocket.CONNECTING)) {
    return;
  }

  let wsUrl;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const userId = payload.user_id || payload.sub;
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    wsUrl = `${protocol}${window.location.host}/ws/notifications/${userId}?token=${encodeURIComponent(token)}`;
  } catch (err) {
    console.error("Failed to parse token for WebSocket connection:", err);
    return;
  }
  
  console.log("Connecting notification WebSocket to:", wsUrl);
  notificationWS = new WebSocket(wsUrl);

  notificationWS.onmessage = function(event) {
    console.log("Notification WS Message received:", event.data);
    
    // Parse message
    const data = event.data;
    let title = "Notification";
    let message = data;
    const colonIndex = data.indexOf(":");
    if (colonIndex !== -1) {
      title = data.substring(0, colonIndex).trim();
      message = data.substring(colonIndex + 1).trim();
    }

    // Refresh navbar to render the new notification from DB
    updateNavbarNotifications();

    // Show premium Toast alert
    showToastNotification(title, message);
  };

  notificationWS.onclose = function(e) {
    console.warn("Notification WS closed. Reconnecting in 5 seconds...", e.reason);
    setTimeout(connectNotificationWS, 5000);
  };

  notificationWS.onerror = function(err) {
    console.error("Notification WS encountered error: ", err);
    notificationWS.close();
  };
}

// Premium Toast Alert
function showToastNotification(title, message) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed top-24 right-6 z-[9999] flex flex-col gap-3 max-w-sm w-full pointer-events-none';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'toast-message pointer-events-auto flex gap-3 w-full bg-slate-900/95 backdrop-blur text-white p-4 rounded-2xl shadow-2xl border border-white/10 transform translate-x-[120%] opacity-0 transition-all duration-500 ease-out';
  
  toast.innerHTML = `
    <div class="flex-shrink-0 w-8 h-8 rounded-xl bg-yellow-500/10 flex items-center justify-center">
      <svg class="w-4 h-4 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
      </svg>
    </div>
    <div class="flex-1 min-w-0">
      <h4 class="text-xs font-black tracking-widest uppercase text-yellow-500">${title}</h4>
      <p class="text-sm font-semibold text-white mt-1 break-words">${message}</p>
    </div>
    <button class="flex-shrink-0 self-start text-slate-400 hover:text-white transition-colors duration-150" onclick="this.parentElement.remove()">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  `;

  container.appendChild(toast);
  
  // Slide in
  setTimeout(() => {
    toast.classList.remove('translate-x-[120%]', 'opacity-0');
    toast.classList.add('translate-x-0', 'opacity-100');
  }, 100);

  // Auto dismiss after 6 seconds
  setTimeout(() => {
    if (document.body.contains(toast)) {
      toast.classList.remove('translate-x-0', 'opacity-100');
      toast.classList.add('translate-x-[120%]', 'opacity-0');
      setTimeout(() => toast.remove(), 500);
    }
  }, 6000);
}

// Request new access token using refresh token
async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch('/api/token/refresh/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ refresh: refreshToken })
    });

    if (response.ok) {
      const data = await response.json();
      localStorage.setItem('access_token', data.access);
      if (data.refresh) {
        localStorage.setItem('refresh_token', data.refresh);
      }
      return true;
    }
  } catch (err) {
    console.error("Failed to refresh token:", err);
  }
  return false;
}

// Auto-run on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  updateNavbarNotifications();
  connectNotificationWS();
});
