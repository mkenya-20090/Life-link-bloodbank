// Auto-dismiss flash alerts
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity .5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  }, 4000);
});

// Modal functions
function openModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.add('show'); m.style.display = 'flex'; }
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) { m.classList.remove('show'); m.style.display = 'none'; }
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal')) closeModal(e.target.id);
});

// Highlight active nav link
const path = window.location.pathname;
document.querySelectorAll('.nav-link').forEach(a => {
  if (a.getAttribute('href') && a.getAttribute('href') !== '#' && path.startsWith(a.getAttribute('href'))) {
    a.classList.add('active');
  }
});
