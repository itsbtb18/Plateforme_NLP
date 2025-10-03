/**
 * notifications.js - Unified notification system for the Arabic NLP Platform
 */

// Store the notification WebSocket connection
let notificationSocket = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 3000;

// Initialize the notification system
document.addEventListener("DOMContentLoaded", function () {
  console.log("Initializing notification system...");

  // Check if user is authenticated (has notification elements on page)
  const hasNotificationElements =
    document.querySelector(".notification-dropdown") !== null ||
    document.getElementById("notificationList") !== null;

  if (hasNotificationElements) {
    console.log("Notification elements found, initializing...");

    // Connect to the WebSocket
    connectNotificationSocket();

    // Set up the notification badge and dropdown after a small delay
    setTimeout(() => {
      // Set up the notification badge
      updateNotificationBadge();

      // Set up the dropdown if it exists
      if (document.querySelector(".notification-dropdown")) {
        console.log("Setting up notification dropdown...");
        updateNotificationDropdown();
      }
    }, 100); // Délai de 100ms

    // Set up the full notification list if it exists
    if (document.getElementById("notificationList")) {
      console.log("Setting up notification list...");
      setupNotificationList();
    }
  } else {
    console.log("No notification elements found on page");
  }
});

// Connect to the WebSocket for real-time notifications
function connectNotificationSocket() {
  console.log("Attempting to connect to notification WebSocket...");

  // Close existing connection if any
  if (notificationSocket) {
    console.log("Closing existing WebSocket connection...");
    notificationSocket.close();
  }

  // Determine the WebSocket protocol
  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProtocol}//${window.location.host}/ws/notifications/`;
  console.log("WebSocket URL:", wsUrl);

  try {
    // Create the WebSocket connection
    notificationSocket = new WebSocket(wsUrl);

    // Handle the connection opening
    notificationSocket.onopen = function (e) {
      console.log("Notification WebSocket connected successfully");
      reconnectAttempts = 0; // Reset reconnect attempts on successful connection
    };

    // Handle messages from the server
    notificationSocket.onmessage = function (e) {
      try {
        const data = JSON.parse(e.data);
        console.log("WebSocket message received:", data);

        // Handle different message types
        if (data.type === "notification_list") {
          console.log("Received notification list:", data.notifications);
          if (document.getElementById("notificationList")) {
            displayNotifications(data.notifications);
          }
        } else if (data.type === "new_notification") {
          console.log("Received new notification:", data.notification);
          showNotificationToast(data.notification);
          loadNotifications();
        } else if (data.type === "notification_marked_read") {
          console.log("Notification marked as read:", data.notification_id);
          handleNotificationRead(data.notification_id);
        } else if (data.type === "all_notifications_marked_read") {
          console.log("All notifications marked as read");
          handleAllNotificationsRead();
        }
      } catch (error) {
        console.error("Error processing WebSocket message:", error);
        console.error("Raw message data:", e.data);
      }
    };

    // Handle connection closing
    notificationSocket.onclose = function (e) {
      console.log(
        "Notification WebSocket disconnected. Code:",
        e.code,
        "Reason:",
        e.reason
      );

      // Try to reconnect if we haven't exceeded max attempts
      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        console.log(
          `Attempting to reconnect (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`
        );
        setTimeout(connectNotificationSocket, RECONNECT_DELAY);
      } else {
        console.error(
          "Max reconnection attempts reached. Please refresh the page."
        );
        // Show user-friendly error message
        showErrorToast(
          "La connexion aux notifications a été perdue. Veuillez rafraîchir la page."
        );
      }
    };

    // Handle connection errors
    notificationSocket.onerror = function (e) {
      console.error("Notification WebSocket error:", e);
      // Show user-friendly error message
      showErrorToast(
        "Une erreur est survenue avec les notifications. Veuillez rafraîchir la page."
      );
    };
  } catch (error) {
    console.error("Error creating WebSocket connection:", error);
    showErrorToast(
      "Impossible de se connecter aux notifications. Veuillez rafraîchir la page."
    );
  }
}

// Show error toast notification
function showErrorToast(message) {
  const toastContainer =
    document.getElementById("toast-container") || createToastContainer();

  const toast = document.createElement("div");
  toast.className = "toast bg-danger text-white";
  toast.setAttribute("role", "alert");
  toast.setAttribute("aria-live", "assertive");
  toast.setAttribute("aria-atomic", "true");

  toast.innerHTML = `
        <div class="toast-header bg-danger text-white">
            <i class="fas fa-exclamation-circle me-2"></i>
            <strong class="me-auto">Erreur</strong>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;

  toastContainer.appendChild(toast);

  const bsToast = new bootstrap.Toast(toast, {
    delay: 5000,
  });
  bsToast.show();
}

// Create toast container if it doesn't exist
function createToastContainer() {
  const container = document.createElement("div");
  container.id = "toast-container";
  container.className = "toast-container position-fixed top-0 end-0 p-3";
  document.body.appendChild(container);
  return container;
}

// Update the notification badge count
function updateNotificationBadge() {
  fetch("/notifications/ajax/count/")
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((data) => {
      console.log("API /notifications/ajax/count/ response data:", data);
      const badge = document.querySelector(".notification-badge");
      if (badge) {
        console.log("Notification badge element found:", badge);
        if (data.count > 0) {
          badge.textContent = data.count;
          badge.style.display = "inline-block";
        } else {
          badge.style.display = "none";
        }
      } else {
        console.log("Notification badge element not found.");
      }
    })
    .catch((error) => {
      console.error("Error updating notification badge:", error);
    });
}

// Update the notification dropdown in the navbar
function updateNotificationDropdown() {
  const dropdown = document.querySelector(".notification-dropdown");
  if (!dropdown) return;

  fetch("/notifications/api/list/filtered/?read=false&limit=5")
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((data) => {
      const notificationBody = dropdown.querySelector(".notification-body");
      if (!notificationBody) return;

      // Handle empty notifications
      if (data.notifications.length === 0) {
        notificationBody.innerHTML = `
                    <div class="dropdown-item text-center py-3">
                        <p class="m-0 text-muted">No unread notifications</p>
                    </div>
                `;
        return;
      }

      // Generate HTML for notifications
      let html = "";
      data.notifications.forEach((notification) => {
        // Get appropriate icon for notification type
        let iconClass = getNotificationIcon(notification.type_code);

        // Format the timestamp
        const timeAgo = formatTimeAgo(notification.created_at);

        html += `
                    <div class="dropdown-item notification-item" data-id="${
                      notification.id
                    }">
                        <div class="d-flex align-items-start">
                            <div class="notification-icon me-2">
                                <i class="${iconClass}"></i>
                            </div>
                            <div class="notification-content flex-grow-1">
                                <h6 class="notification-title m-0">${
                                  notification.title
                                }</h6>
                                <p class="notification-text mb-1">${truncateText(
                                  notification.message,
                                  100
                                )}</p>
                                <small class="notification-time text-muted">
                                    ${timeAgo}
                                </small>
                            </div>
                        </div>
                    </div>
                `;
      });

      notificationBody.innerHTML = html;

      // Add click event listeners
      document
        .querySelectorAll(".notification-dropdown .notification-item")
        .forEach((item) => {
          item.addEventListener("click", function () {
            const notificationId = this.getAttribute("data-id");
            markNotificationAsRead(notificationId);
          });
        });
    })
    .catch((error) => {
      console.error("Error updating notification dropdown:", error);
    });
}

// Set up the full notification list page
function setupNotificationList() {
  // Load notifications
  loadNotifications("/notifications/api/list/");

  // Set up filter tabs
  const filterTabs = document.querySelectorAll(".tab-btn");
  if (filterTabs) {
    filterTabs.forEach((tab) => {
      tab.addEventListener("click", function () {
        // Remove active class from all tabs
        filterTabs.forEach((t) => t.classList.remove("active"));

        // Add active class to clicked tab
        this.classList.add("active");

        // Get the filter type
        const filter = this.getAttribute("data-filter");

        // Filter notifications
        if (filter === "all") {
          loadNotifications("/notifications/api/list/");
        } else if (filter === "read") {
          loadNotifications("/notifications/api/list/filtered/?read=true");
        } else if (filter === "unread") {
          loadNotifications("/notifications/api/list/filtered/?read=false");
        }
      });
    });
  }

  // Set up "Mark all as read" button
  const markAllReadBtn = document.getElementById("markAllAsReadBtn");
  if (markAllReadBtn) {
    markAllReadBtn.addEventListener("click", function () {
      markAllNotificationsAsRead();
    });
  }
}

// Load notifications into the notification list
function loadNotifications(url) {
  const notificationList = document.getElementById("notificationList");
  if (!notificationList) return;

  // Show loading spinner
  notificationList.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Chargement...</span>
            </div>
        </div>
    `;

  // Fetch notifications
  fetch(url)
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((data) => {
      displayNotifications(data.notifications);
    })
    .catch((error) => {
      console.error("Error loading notifications:", error);
      notificationList.innerHTML = `
                <div class="alert alert-danger">
                    Erreur lors du chargement des notifications. Veuillez réessayer.
                </div>
            `;
    });
}

// Display notifications in the notification list
function displayNotifications(notifications) {
  const notificationList = document.getElementById("notificationList");
  if (!notificationList) return;

  // Handle empty notifications
  if (notifications.length === 0) {
    notificationList.innerHTML = `
            <div class="text-center py-5">
                <p class="text-muted">No notifications.</p>
            </div>
        `;
    return;
  }

  // Generate HTML for notifications
  let html = "";
  notifications.forEach((notification) => {
    const readClass = notification.read ? "read" : "unread";
    const readIcon = notification.read
      ? '<i class="fas fa-check-circle text-success"></i>'
      : '<i class="fas fa-circle text-primary"></i>';

    // Format the date
    const formattedDate = formatDate(notification.created_at);

    html += `
            <div class="notification-item ${readClass}" data-id="${
      notification.id
    }">
                <div class="notification-status">${readIcon}</div>
                <div class="notification-content">
                    <div class="notification-header">
                        <h5 class="notification-title">${
                          notification.title
                        }</h5>
                        <div class="notification-type badge bg-secondary">${
                          notification.type
                        }</div>
                    </div>
                    <div class="notification-message">${
                      notification.message
                    }</div>
                    <div class="notification-footer">
                        <span class="notification-date">${formattedDate}</span>
                        <button class="btn btn-sm btn-link mark-read-btn" 
                                ${notification.read ? "disabled" : ""}
                                data-id="${notification.id}">
                            Marquer comme lu
                        </button>
                    </div>
                </div>
            </div>
        `;
  });

  notificationList.innerHTML = html;

  // Add click event listeners to "Mark as read" buttons
  document.querySelectorAll(".mark-read-btn").forEach((btn) => {
    if (!btn.hasAttribute("disabled")) {
      btn.addEventListener("click", function () {
        const notificationId = this.getAttribute("data-id");
        markNotificationAsRead(notificationId);
      });
    }
  });
}

// Handle a new notification
function handleNewNotification(notification) {
  // Play notification sound if available
  const notificationSound = document.getElementById("notification-sound");
  if (notificationSound) {
    notificationSound.play().catch((error) => {
      console.log(
        "Could not play notification sound due to browser restrictions"
      );
    });
  }

  // Show toast notification
  showNotificationToast(notification);

  // Update notification badge
  updateNotificationBadge();

  // Update notification dropdown if it exists
  if (document.querySelector(".notification-dropdown")) {
    updateNotificationDropdown();
  }

  // Update notification list if on notifications page
  if (document.getElementById("notificationList")) {
    // Get the active filter
    const activeTab = document.querySelector(".tab-btn.active");
    if (activeTab) {
      const filter = activeTab.getAttribute("data-filter");
      if (filter === "all" || filter === "unread") {
        // Add the new notification to the list
        prependNotificationToList(notification);
      }
    }
  }
}

// Handle a notification being marked as read
function handleNotificationRead(notificationId) {
  // Update the notification in the list
  const notificationItem = document.querySelector(
    `.notification-item[data-id="${notificationId}"]`
  );
  if (notificationItem) {
    notificationItem.classList.remove("unread");
    notificationItem.classList.add("read");

    const statusIcon = notificationItem.querySelector(".notification-status");
    if (statusIcon) {
      statusIcon.innerHTML = '<i class="fas fa-check-circle text-success"></i>';
    }

    const markReadBtn = notificationItem.querySelector(".mark-read-btn");
    if (markReadBtn) {
      markReadBtn.setAttribute("disabled", "disabled");
    }
  }

  // Update notification badge
  updateNotificationBadge();

  // Update notification dropdown if it exists
  if (document.querySelector(".notification-dropdown")) {
    updateNotificationDropdown();
  }
}

// Handle all notifications being marked as read
function handleAllNotificationsRead() {
  // Update all notifications in the list
  document.querySelectorAll(".notification-item.unread").forEach((item) => {
    item.classList.remove("unread");
    item.classList.add("read");

    const statusIcon = item.querySelector(".notification-status");
    if (statusIcon) {
      statusIcon.innerHTML = '<i class="fas fa-check-circle text-success"></i>';
    }

    const markReadBtn = item.querySelector(".mark-read-btn");
    if (markReadBtn) {
      markReadBtn.setAttribute("disabled", "disabled");
    }
  });

  // Update notification badge
  updateNotificationBadge();

  // Update notification dropdown if it exists
  if (document.querySelector(".notification-dropdown")) {
    updateNotificationDropdown();
  }
}

// Mark a notification as read
function markNotificationAsRead(notificationId) {
  if (notificationSocket && notificationSocket.readyState === WebSocket.OPEN) {
    // Send through WebSocket
    notificationSocket.send(
      JSON.stringify({
        action: "mark_as_read",
        notification_id: notificationId,
      })
    );
  } else {
    // Fallback to HTTP request
    fetch(`/notifications/api/mark-read/${notificationId}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "Content-Type": "application/json",
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        return response.json();
      })
      .then((data) => {
        if (data.success) {
          handleNotificationRead(notificationId);
        }
      })
      .catch((error) => {
        console.error("Error marking notification as read:", error);
      });
  }
}

// Mark all notifications as read
function markAllNotificationsAsRead() {
  if (notificationSocket && notificationSocket.readyState === WebSocket.OPEN) {
    // Send through WebSocket
    notificationSocket.send(
      JSON.stringify({
        action: "mark_all_as_read",
      })
    );
  } else {
    // Fallback to HTTP request
    fetch("/notifications/api/mark-all-read/", {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "Content-Type": "application/json",
      },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        return response.json();
      })
      .then((data) => {
        if (data.success) {
          handleAllNotificationsRead();
        }
      })
      .catch((error) => {
        console.error("Error marking all notifications as read:", error);
      });
  }
}

// Add a new notification to the top of the list
function prependNotificationToList(notification) {
  const notificationList = document.getElementById("notificationList");
  if (!notificationList) return;

  // Create new notification element
  const notificationElement = document.createElement("div");
  notificationElement.className = "notification-item unread";
  notificationElement.setAttribute("data-id", notification.id);

  // Format the date
  const formattedDate = formatDate(notification.created_at);

  notificationElement.innerHTML = `
        <div class="notification-status">
            <i class="fas fa-circle text-primary"></i>
        </div>
        <div class="notification-content">
            <div class="notification-header">
                <h5 class="notification-title">${notification.title}</h5>
                <div class="notification-type badge bg-secondary">${notification.type}</div>
            </div>
            <div class="notification-message">${notification.message}</div>
            <div class="notification-footer">
                <span class="notification-date">${formattedDate}</span>
                <button class="btn btn-sm btn-link mark-read-btn" data-id="${notification.id}">
                    Marquer comme lu
                </button>
            </div>
        </div>
    `;

  // Add to the top of the list
  const firstChild = notificationList.firstChild;
  if (firstChild) {
    notificationList.insertBefore(notificationElement, firstChild);
  } else {
    notificationList.appendChild(notificationElement);
  }

  // Add click event listener
  const markReadBtn = notificationElement.querySelector(".mark-read-btn");
  if (markReadBtn) {
    markReadBtn.addEventListener("click", function () {
      const notificationId = this.getAttribute("data-id");
      markNotificationAsRead(notificationId);
    });
  }
}

// Show a toast notification
function showNotificationToast(notification) {
  // Create toast container if it doesn't exist
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.className = "toast-container position-fixed top-0 end-0 p-3";
    document.body.appendChild(toastContainer);
  }

  // Create the toast
  const toastId = "toast-" + Date.now();
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.id = toastId;
  toast.setAttribute("role", "alert");
  toast.setAttribute("aria-live", "assertive");
  toast.setAttribute("aria-atomic", "true");

  // Get appropriate icon for notification type
  let iconClass = getNotificationIcon(notification.type_code);

  toast.innerHTML = `
        <div class="toast-header">
            <i class="${iconClass} me-2"></i>
            <strong class="me-auto">${notification.title}</strong>
            <small>${notification.type}</small>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
            ${notification.message}
        </div>
    `;

  toastContainer.appendChild(toast);

  // Show toast with Bootstrap
  const bsToast = new bootstrap.Toast(toast, {
    delay: 5000,
  });
  bsToast.show();

  // Add click event to mark as read and navigate to notifications page
  toast.addEventListener("click", function (e) {
    if (!e.target.classList.contains("btn-close")) {
      markNotificationAsRead(notification.id);
      window.location.href = "/notifications/";
    }
  });
}

// Helper function to get notification icon
function getNotificationIcon(typeCode) {
  switch (typeCode) {
    case "NC":
      return "fas fa-comment-alt text-primary";
    case "NFP":
      return "fas fa-comments text-info";
    case "NR":
      return "fas fa-book text-success";
    case "CU":
      return "fas fa-database text-warning";
    case "RU":
      return "fas fa-flask text-danger";
    case "ER":
      return "fas fa-calendar text-secondary";
    case "MR":
      return "fas fa-user-plus text-dark";
    case "AN":
      return "fas fa-bullhorn text-info";
    default:
      return "fas fa-bell text-muted";
  }
}

// Helper function to format date
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Helper function to format relative time
function formatTimeAgo(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.round(diffMs / 60000);
  const diffHours = Math.round(diffMs / 3600000);
  const diffDays = Math.round(diffMs / 86400000);

  if (diffMins < 60) {
    return `${diffMins} min`;
  } else if (diffHours < 24) {
    return `${diffHours} h`;
  } else {
    return `${diffDays} j`;
  }
}

// Helper function to truncate text
function truncateText(text, maxLength) {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength - 3) + "...";
}

// Helper function to get CSRF token
function getCsrfToken() {
  // Try to get from meta tag first
  const csrfToken = document
    .querySelector('meta[name="csrf-token"]')
    ?.getAttribute("content");
  if (csrfToken) {
    return csrfToken;
  }

  // Try to get from form input
  const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
  if (csrfInput) {
    return csrfInput.value;
  }

  // Try to get from cookie
  const cookies = document.cookie.split(";");
  for (let cookie of cookies) {
    cookie = cookie.trim();
    if (cookie.startsWith("csrftoken=")) {
      return cookie.substring("csrftoken=".length);
    }
  }

  return "";
}
