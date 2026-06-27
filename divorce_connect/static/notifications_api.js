// Retrieve stored token (e.g. from local storage)
const getAccessToken = () => localStorage.getItem('access_token');
const getRefreshToken = () => localStorage.getItem('refresh_token');

/**
 * Fetch active notifications and update Tailwind badge count
 */
async function updateNavbarNotifications() {
  let token = getAccessToken();
  if (!token) {
    console.warn("User is not authenticated. Skipping notifications fetch.");
    return;
  }

  try {
    let response = await fetch('/api/notifications/', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      }
    });

    if (response.status === 401) {
      // Access token expired, attempt to refresh
      console.log("Access token expired, attempting to refresh...");
      const refreshed = await refreshAccessToken();
      if (refreshed) {
        token = getAccessToken();
        response = await fetch('/api/notifications/', {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        });
      } else {
        console.error("Token expired or invalid.");
        return;
      }
    }

    if (!response.ok) throw new Error("Failed to fetch notifications");

    const notifications = await response.json();
    
    // Count unread items
    const unreadCount = notifications.filter(n => !n.is_read).length;
    
    // DOM update logic for Tailwind elements
    const badge = document.getElementById('notification-badge');
    if (badge) {
      if (unreadCount > 0) {
        badge.innerText = unreadCount;
        badge.classList.remove('hidden'); // Show badge
      } else {
        badge.classList.add('hidden'); // Hide badge
      }
    }
  } catch (error) {
    console.error("Error updating notifications badge:", error);
  }
}

/**
 * Request a new access token using the refresh token
 */
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
