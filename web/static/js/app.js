// Global app utilities
document.querySelectorAll(".nav-link").forEach(link => {
  if (link.pathname === window.location.pathname) {
    link.style.color = "var(--text)";
    link.style.background = "var(--border)";
  }
});