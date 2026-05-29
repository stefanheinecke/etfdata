<template>
  <Teleport to="body">
    <div v-if="show" class="modal-backdrop" @click.self="close">
      <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-title">

        <!-- Header -->
        <div class="modal-header">
          <div>
            <div class="modal-eyebrow">Free &amp; instant</div>
            <h2 id="modal-title" class="modal-title">Get Your API Key</h2>
          </div>
          <button class="modal-close" @click="close" aria-label="Close">✕</button>
        </div>

        <!-- Success state -->
        <template v-if="apiKey">
          <p class="modal-sub success-sub">✓ Your key has been created. Copy it now — it won't be shown again.</p>
          <div class="key-display">
            <code class="key-code">{{ apiKey }}</code>
            <button class="btn btn-outline btn-sm" @click="copyKey">{{ copied ? '✓ Copied' : 'Copy' }}</button>
          </div>
          <button class="btn btn-primary" style="width:100%;margin-top:1rem" @click="useKey">
            Use this key &amp; close
          </button>
        </template>

        <!-- Form state -->
        <template v-else>
          <p class="modal-sub">Enter your name and email to get a free API key with 60 req/min.</p>

          <div class="form-field">
            <label class="label">Your Name</label>
            <input
              ref="nameInput"
              class="input"
              v-model="name"
              placeholder="e.g. Jane Smith"
              @keyup.enter="submit"
            />
          </div>
          <div class="form-field">
            <label class="label">Email Address</label>
            <input
              class="input"
              type="email"
              v-model="email"
              placeholder="jane@example.com"
              @keyup.enter="submit"
            />
          </div>

          <div v-if="errorMsg" class="error-box" style="margin-bottom:.75rem">{{ errorMsg }}</div>

          <button
            class="btn btn-primary"
            style="width:100%"
            :disabled="!name || !email || loading"
            @click="submit"
          >
            {{ loading ? 'Creating…' : 'Create API Key' }}
          </button>

          <p class="modal-note">
            Your email is only used to identify your key. We don't send marketing emails.
          </p>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { authService } from '../services/api.js'

const props = defineProps({ show: Boolean })
const emit  = defineEmits(['close'])

const name     = ref('')
const email    = ref('')
const loading  = ref(false)
const errorMsg = ref('')
const apiKey   = ref('')
const copied   = ref(false)
const nameInput = ref(null)

watch(() => props.show, async (val) => {
  if (val) {
    name.value = ''; email.value = ''; errorMsg.value = ''; apiKey.value = ''; copied.value = false
    await nextTick()
    nameInput.value?.focus()
  }
})

async function submit() {
  if (!name.value || !email.value) return
  loading.value = true; errorMsg.value = ''
  try {
    const r = await authService.requestKey(name.value.trim(), email.value.trim())
    apiKey.value = r.data.api_key
  } catch(e) {
    errorMsg.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function copyKey() {
  navigator.clipboard.writeText(apiKey.value).then(() => {
    copied.value = true
    setTimeout(() => copied.value = false, 2000)
  })
}

function useKey() {
  localStorage.setItem('api_key', apiKey.value)
  // Trigger storage event for other components listening
  window.dispatchEvent(new StorageEvent('storage', { key: 'api_key', newValue: apiKey.value }))
  close()
}

function close() {
  emit('close')
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-box {
  background: var(--bg-card, #fff);
  border-radius: 16px;
  padding: 2rem;
  width: 100%;
  max-width: 440px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.25);
  animation: modal-in 0.18s ease;
}

@keyframes modal-in {
  from { opacity: 0; transform: translateY(-16px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.modal-eyebrow {
  font-size: .75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--primary, #667eea);
  margin-bottom: .2rem;
}

.modal-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  color: var(--text-muted, #999);
  padding: .25rem .5rem;
  border-radius: 4px;
  line-height: 1;
}
.modal-close:hover { background: var(--bg-hover, #f0f0f0); }

.modal-sub {
  font-size: .9rem;
  color: var(--text-muted, #666);
  margin: 0 0 1.25rem;
}

.success-sub { color: #15803d; font-weight: 500; }

.form-field { margin-bottom: 1rem; }

.key-display {
  display: flex;
  align-items: center;
  gap: .5rem;
  background: var(--bg-muted, #f4f5f7);
  border-radius: 8px;
  padding: .75rem 1rem;
}

.key-code {
  flex: 1;
  font-size: .8rem;
  word-break: break-all;
  color: var(--text, #222);
}

.btn-sm { padding: .4rem .8rem; font-size: .8rem; }

.modal-note {
  font-size: .78rem;
  color: var(--text-muted, #aaa);
  text-align: center;
  margin-top: .75rem;
}

/* Reuse global button / input / label styles */
.btn { padding: .75rem 1.5rem; border: none; border-radius: 8px; cursor: pointer; font-size: .95rem; font-weight: 600; transition: opacity .15s; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn-primary { background: var(--primary, #667eea); color: #fff; }
.btn-primary:hover:not(:disabled) { opacity: .9; }
.btn-outline { background: transparent; border: 1.5px solid var(--border, #ddd); color: var(--text, #333); }
.btn-outline:hover { background: var(--bg-hover, #f5f5f5); }
.input { width: 100%; padding: .7rem .9rem; border: 1.5px solid var(--border, #ddd); border-radius: 8px; font-size: .95rem; box-sizing: border-box; background: var(--bg-input, #fff); color: var(--text, #333); }
.input:focus { outline: none; border-color: var(--primary, #667eea); }
.label { display: block; font-weight: 600; font-size: .85rem; margin-bottom: .4rem; color: var(--text, #333); }
.error-box { background: #fef2f2; border: 1px solid #fca5a5; color: #dc2626; padding: .6rem .9rem; border-radius: 6px; font-size: .875rem; }
</style>
