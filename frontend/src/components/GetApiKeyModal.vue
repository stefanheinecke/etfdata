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

        <template v-if="googleSignedIn">
          <div class="sent-icon">✅</div>
          <p class="modal-sub success-sub">Signed in with Google as <strong>{{ googleEmail }}</strong>.</p>
          <p v-if="googleKeyEmailed" class="modal-note">
            We emailed your API key to this address. Keep that email safe; the key is not shown in the browser.
          </p>
          <template v-else-if="googleHasApiKey">
            <p class="modal-note">
              An active API key already exists for this address. It was kept unchanged.
              If you saved the original key email, the key is available there.
            </p>
          </template>
          <template v-else>
            <p class="error-box" style="margin-bottom:.75rem">{{ googleKeyEmailError }}</p>
            <button class="btn btn-outline" style="width:100%;margin-top:.75rem" @click="requestEmailKey">
              Request API key by email instead
            </button>
          </template>
          <button class="btn btn-primary" style="width:100%;margin-top:1rem" @click="close">
            Done
          </button>
        </template>

        <template v-else-if="sent">
          <div class="sent-icon">✉️</div>
          <p class="modal-sub success-sub">Check your inbox at <strong>{{ email }}</strong>.</p>
          <p v-if="emailHasActiveKey" style="font-size:.875rem;color:var(--text-muted);line-height:1.6">
            Click the confirmation button in the email to sign in. Your existing API key will remain unchanged.
          </p>
          <p v-else style="font-size:.875rem;color:var(--text-muted);line-height:1.6">
            Your new API key is included in the email but stays inactive until you click the confirmation button.
            After confirmation, this browser will be signed in.
          </p>
          <p class="modal-note" style="margin-top:.75rem">
            The confirmation link expires in 30 minutes. Check your spam folder if needed.
          </p>
          <button class="btn btn-primary" style="width:100%;margin-top:1rem" @click="close">
            Close
          </button>
        </template>

        <template v-else>
          <p class="modal-sub">
            We’ll email you a confirmation button. New API keys are activated only after you confirm your email.
            Existing active keys are never changed by this request.
          </p>

          <div v-if="googleClientId" class="google-signin">
            <div ref="googleButton"></div>
            <div class="auth-divider"><span>or</span></div>
          </div>

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
            You can also sign in with Google for immediate access to the website.
          </p>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { authService } from '../services/api.js'

const googleClientId = window.__ETF_RUNTIME_CONFIG__?.googleClientId
  || import.meta.env.VITE_GOOGLE_CLIENT_ID
  || ''
let googleScriptPromise

const props = defineProps({
  show: Boolean
})
const emit  = defineEmits(['close', 'google-authenticated', 'email-confirmation-pending'])

const email      = ref('')
const loading    = ref(false)
const errorMsg   = ref('')
const sent       = ref(false)
const emailHasActiveKey = ref(false)
const emailInput = ref(null)
const googleButton = ref(null)
const googleSignedIn = ref(false)
const googleEmail = ref('')
const googleHasApiKey = ref(false)
const googleKeyEmailed = ref(false)
const googleKeyEmailError = ref('')

function loadGoogleIdentityServices() {
  if (window.google?.accounts?.id) return Promise.resolve()
  if (googleScriptPromise) return googleScriptPromise

  googleScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = resolve
    script.onerror = () => {
      googleScriptPromise = null
      reject(new Error('Google sign-in could not be loaded.'))
    }
    document.head.appendChild(script)
  })
  return googleScriptPromise
}

async function handleGoogleCredential(response) {
  loading.value = true
  errorMsg.value = ''
  try {
    const result = await authService.googleSignIn(response.credential)
    googleEmail.value = result.data.email || ''
    googleHasApiKey.value = !!result.data.has_api_key
    googleKeyEmailed.value = !!result.data.api_key_emailed
    googleKeyEmailError.value = result.data.api_key_email_error || ''
    googleSignedIn.value = true
    emit('google-authenticated', result.data)
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
}

function requestEmailKey() {
  googleSignedIn.value = false
  email.value = googleEmail.value
  sent.value = false
  emailHasActiveKey.value = false
  errorMsg.value = ''
  nextTick(() => emailInput.value?.focus())
}

async function initializeGoogleButton() {
  if (!googleClientId || !googleButton.value) return
  try {
    await loadGoogleIdentityServices()
    if (!props.show || !googleButton.value) return
    googleButton.value.replaceChildren()
    window.google.accounts.id.initialize({
      client_id: googleClientId,
      callback: handleGoogleCredential,
      auto_select: false,
    })
    window.google.accounts.id.renderButton(googleButton.value, {
      theme: 'outline',
      size: 'large',
      shape: 'rect',
      text: 'continue_with',
      width: 360,
    })
  } catch (e) {
    errorMsg.value = e.message
  }
}

watch(() => props.show, async (val) => {
  if (val) {
    email.value = ''; errorMsg.value = ''; sent.value = false
    emailHasActiveKey.value = false
    googleSignedIn.value = false
    googleEmail.value = ''
    googleHasApiKey.value = false
    googleKeyEmailed.value = false
    googleKeyEmailError.value = ''
    await nextTick()
    emailInput.value?.focus()
    initializeGoogleButton()
  }
})

async function submit() {
  if (!email.value) return
  loading.value = true; errorMsg.value = ''
  try {
    const result = await authService.requestKey(email.value.trim())
    sent.value = true
    emailHasActiveKey.value = !!result.data.has_active_key
    emit('email-confirmation-pending')
  } catch(e) {
    errorMsg.value = e.response?.data?.detail || e.message
  } finally {
    loading.value = false
  }
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
.google-signin {
  margin: 0 0 1rem;
}
.google-signin > div:first-child {
  display: flex;
  justify-content: center;
  min-height: 40px;
}
.auth-divider {
  display: flex;
  align-items: center;
  gap: .75rem;
  margin-top: .9rem;
  color: var(--text-muted, #888);
  font-size: .8rem;
}
.auth-divider::before,
.auth-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border, #e5e7eb);
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
