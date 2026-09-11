<template>
  <Teleport to="body">
    <div v-if="show" class="modal-backdrop" @click.self="close">
      <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="contact-modal-title">
        <div class="modal-header">
          <div>
            <div class="modal-eyebrow">Get in touch</div>
            <h2 id="contact-modal-title" class="modal-title">Contact us</h2>
          </div>
          <button class="modal-close" @click="close" aria-label="Close">✕</button>
        </div>

        <template v-if="sent">
          <div class="sent-icon">✉️</div>
          <p class="modal-sub success-sub">Thanks, {{ name }}!</p>
          <p style="font-size:.875rem;color:var(--text-muted);line-height:1.6">
            Your message has been sent. We'll get back to you at <strong>{{ email }}</strong> if a reply is needed.
          </p>
          <button class="btn btn-primary" style="width:100%;margin-top:1rem" @click="close">Close</button>
        </template>
        <template v-else>
          <p class="modal-sub">Questions, feedback, or feature requests — we'd love to hear from you.</p>

          <div class="form-field">
            <label class="label">Name</label>
            <input ref="nameInput" class="input" type="text" v-model="name" placeholder="Your name" />
          </div>
          <div class="form-field">
            <label class="label">Email</label>
            <input class="input" type="email" v-model="email" placeholder="you@example.com" />
          </div>
          <div class="form-field">
            <label class="label">Message</label>
            <textarea class="input" v-model="message" rows="4" placeholder="Tell us what's on your mind…" style="resize:vertical"></textarea>
          </div>

          <div v-if="errorMsg" class="error-box" style="margin-bottom:.75rem">{{ errorMsg }}</div>

          <button class="btn btn-primary" style="width:100%" :disabled="!canSubmit || loading" @click="submit">
            {{ loading ? 'Sending…' : 'Send Message' }}
          </button>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { authService } from '../services/api.js'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['close'])

const name = ref('')
const email = ref('')
const message = ref('')
const loading = ref(false)
const errorMsg = ref('')
const sent = ref(false)
const nameInput = ref(null)

const canSubmit = computed(() =>
  name.value.trim().length >= 2 && email.value.includes('@') && message.value.trim().length >= 10)

async function submit() {
  if (!canSubmit.value || loading.value) return
  loading.value = true; errorMsg.value = ''
  try {
    await authService.contact({ name: name.value.trim(), email: email.value.trim(), message: message.value.trim() })
    sent.value = true
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function close() {
  emit('close')
}

watch(() => props.show, async (visible) => {
  if (!visible) return
  sent.value = false; errorMsg.value = ''; name.value = ''; email.value = ''; message.value = ''
  await nextTick()
  nameInput.value?.focus()
})
</script>
