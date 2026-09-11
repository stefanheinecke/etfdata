<template>
  <section class="concept-shell">
    <iframe
      class="concept-frame"
      :srcdoc="brandedHtml"
      :title="`${BRAND.name} Frontpage`"
    ></iframe>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import conceptHtml from '../../goetf_concept.html?raw'
import { BRAND, BRAND_PREFIX } from '../brand.js'

// The marketing page is static HTML/JS rendered in an iframe. Branding is
// injected here at runtime, rather than duplicated inside that file, so
// brand.js stays the single source of truth for the app's name.
const brandedHtml = computed(() => conceptHtml
  .replaceAll('<a href="/" class="logo">Go<span>ETF</span></a>', `<a href="/" class="logo">${BRAND_PREFIX}<span>ETF</span></a>`)
  .replaceAll('<div class="footer-logo">Go<span>ETF</span></div>', `<div class="footer-logo">${BRAND_PREFIX}<span>ETF</span></div>`)
  .replace('<title>GoETF —', `<title>${BRAND.name} —`)
  .replace('© 2026 GoETF.ch', `© 2026 ${BRAND.domain}`)
  .replace('<a href="mailto:info@goetf.ch">info@goetf.ch</a>', '<a href="#contactForm" class="footer-contact-link">Contact us</a>')
  .replaceAll('https://api.goetf.ch', `https://api.${BRAND.domain}`)
  .replace(/\bGoETF\b/g, BRAND.name))
</script>

<style scoped>
.concept-shell {
  width: 100%;
  min-height: 100vh;
  background: #f8f9fb;
}

.concept-frame {
  width: 100%;
  height: 100vh;
  border: 0;
  display: block;
  background: #f8f9fb;
}
</style>
