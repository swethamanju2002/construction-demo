// Main UI Utilities & Lightbox
document.addEventListener('DOMContentLoaded', () => {
  // Mobile Navigation Drawer Toggle
  const mobileToggle = document.getElementById('mobileNavToggle');
  const navMenu = document.getElementById('navMenu');
  if (mobileToggle && navMenu) {
    mobileToggle.addEventListener('click', () => {
      navMenu.classList.toggle('mobile-open');
    });
  }

  // Global Lightbox for Image Previews
  const lightboxOverlay = document.getElementById('lightboxOverlay');
  const lightboxImg = document.getElementById('lightboxImg');
  const lightboxCaption = document.getElementById('lightboxCaption');
  const lightboxClose = document.getElementById('lightboxClose');

  if (lightboxOverlay && lightboxImg) {
    document.querySelectorAll('.open-lightbox').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        const src = el.getAttribute('data-img-src') || el.getAttribute('href');
        const caption = el.getAttribute('data-caption') || '';
        lightboxImg.src = src;
        if (lightboxCaption) lightboxCaption.textContent = caption;
        lightboxOverlay.classList.add('active');
      });
    });

    if (lightboxClose) {
      lightboxClose.addEventListener('click', () => {
        lightboxOverlay.classList.remove('active');
      });
    }

    lightboxOverlay.addEventListener('click', (e) => {
      if (e.target === lightboxOverlay) {
        lightboxOverlay.classList.remove('active');
      }
    });
  }
});

// Helper: Get Django CSRF Token from cookie
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
