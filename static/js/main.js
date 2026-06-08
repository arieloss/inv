// Auto-dismiss alerts after 5s
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert-custom').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });
});
