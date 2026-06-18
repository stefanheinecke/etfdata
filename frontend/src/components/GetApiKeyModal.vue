<template>
  <Teleport to="body">
    <div v-if="show" class="modal-backdrop" @click.self="close">
      <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-title">

        <!-- Header -->
        <div class="modal-header">
          <div>
            <div class="modal-eyebrow">Free &amp; instant</div>
            <h2 id="modal-title" class="modal-title">API Key</h2>
          </div>
          <button class="modal-close" @click="close" aria-label="Close">✕</button>
        </div>

        <!-- Tabs -->
        <div class="modal-tabs">
          <button :class="['modal-tab', { active: activeTab === 'request' }]" @click="switchTab('request')">Request Key</button>
          <button :class="['modal-tab', { active: activeTab === 'enter' }]" @click="switchTab('enter')">Enter Key</button>
        </div>

        <!-- ── Tab: Request Key ── -->
        <template v-if="activeTab === 'request'">
          <!-- Success state -->
          <template v-if="sent">
            <div class="sent-icon">✉️</div>
            <p class="modal-sub success-sub">Check your inbox at <strong>{{ email }}</strong>.</p>
            <p style="font-size:.875rem;color:var(--text-muted);line-height:1.6">
              We sent a confirmation email. Click the button in the email to receive your API key.
              The link expires in <strong>30 minutes</strong>.
            </p>
            <p class="modal-note" style="margin-top:.75rem">Didn't receive it? Check your spam folder or try again.</p>
            <button class="btn btn-primary" style="width:100%;margin-top:1rem" @click="close">
              Close
            </button>
          </template>

          <!-- Form state -->
          <template v-else>
            <p class="modal-sub">Enter your email address to receive a free API key (60 req/min).</p>

            <div class="form-field">
              <label class="label">Email Address</label>
              <input
                ref="emailInput"
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
              :disabled="!email || loading"
              @click="submit"
            >
              {{ loading ? 'Sending…' : 'Get Free API Key' }}
            </button>

            <p class="modal-note">
              Your key will be emailed to you. We don't send marketing emails.
            </p>
          </template>
        </template>

        <!-- ── Tab: Enter Key ── -->
        <template v-else>
          <template v-if="keySaved">
            <div class="sent-icon">✅</div>
            <p class="modal-sub success-sub">API key saved successfully!</p>
            <p style="font-size:.875rem;color:var(--text-muted);line-height:1.6">
              Your key is stored locally in this browser. All API requests will now use it automatically.
            </p>
            <button class="btn btn-primary" style="width:100%;margin-top:1rem" @click="close">
              Done
            </button>
          </template>
          <template v-else>
            <p class="modal-sub">Already have a key? Paste it below to activate it in this browser.</p>

            <div class="form-field">
              <label class="label">Your API Key</label>
              <div class="key-input-wrap">
                <input
                  ref="keyInput"
                  class="input"
                  :type="showKey ? 'text' : 'password'"
                  v-model="apiKey"
                  placeholder="Paste your API key here…"
                  @keyup.enter="saveKey"
                />
                <button class="key-toggle" @click="showKey = !showKey" type="button" :aria-label="showKey ? 'Hide key' : 'Show key'">
                  {{ showKey ? '🙈' : '👁' }}
                </button>
              </div>
            </div>

            <div v-if="keyError" class="error-box" style="margin-bottom:.75rem">{{ keyError }}</div>

            <button
              class="btn btn-primary"
              style="width:100%"
              :disabled="!apiKey.trim()"
              @click="saveKey"
            >
              Save API Key
            </button>

            <p class="modal-note">
              Stored only in your browser's local storage. Never sent to our servers.
            </p>
          </template>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { authService } from '../services/api.js'

const props = defineProps({
  show: Boolean,
  initialTab: { type: String, default: 'request' }
})
const emit  = defineEmits(['close', 'key-saved'])

const activeTab  = ref(props.initialTab)
const email      = ref('')
const loading    = ref(false)
const errorMsg   = ref('')
const sent       = ref(false)
const emailInput = ref(null)

const apiKey   = ref('')
const showKey  = ref(false)
const keyError = ref('')
const keySaved = ref(false)
const keyInput = ref(null)

function switchTab(tab) {
  activeTab.value = tab
  errorMsg.value = ''
  keyError.value = ''
}

watch(() => props.show, async (val) => {
  if (val) {
    activeTab.value = props.initialTab
    email.value = ''; errorMsg.value = ''; sent.value = false
    apiKey.value = localStorage.getItem('api_key') || ''
    showKey.value = false; keyError.value = ''; keySaved.value = false
    await nextTick()
    if (activeTab.value === 'enter') keyInput.value?.focus()
    else emailInput.value?.focus()
  }
})

watch(() => props.initialTab, (val) => {
  if (props.show) activeTab.value = val
})

async function submit() {
  if (!email.value) return
  loading.value = true; errorMsg.value = ''
  try {
    await authService.requestKey(email.value.trim())
    sent.value = true
  } catch(e) {
    errorMsg.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function saveKey() {
  const trimmed = apiKey.value.trim()
  if (!trimmed) { keyError.value = 'Please enter a key.'; return }
  localStorage.setItem('api_key', trimmed)
  emit('key-saved')
  keySaved.value = true
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
.sent-icon { font-size: 2.5rem; text-align: center; margin-bottom: .5rem; }

.modal-tabs {
  display: flex;
  gap: .25rem;
  background: var(--bg-muted, #f4f5f7);
  border-radius: 10px;
  padding: .25rem;
  margin-bottom: 1.25rem;
}
.modal-tab {
  flex: 1;
  padding: .45rem 0;
  border: none;
  border-radius: 8px;
  font-size: .875rem;
  font-weight: 600;
  cursor: pointer;
  background: transparent;
  color: var(--text-muted, #888);
  transition: all .15s;
}
.modal-tab.active {
  background: var(--bg-card, #fff);
  color: var(--primary, #1585c8);
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}

.key-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.key-input-wrap .input {
  flex: 1;
  padding-right: 2.5rem;
}
.key-toggle {
  position: absolute;
  right: .5rem;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  padding: .2rem;
  line-height: 1;
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

.success-sub { color: #0b6aa5; font-weight: 500; }

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
