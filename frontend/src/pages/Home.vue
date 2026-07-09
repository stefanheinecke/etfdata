<template>
  <section class="concept-shell">
    <iframe
      class="concept-frame"
      :srcdoc="conceptHtml"
      title="GoETF Frontpage"
    ></iframe>
  </section>
</template>

<script setup>
import conceptHtml from '../../goetf_concept.html?raw'
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
