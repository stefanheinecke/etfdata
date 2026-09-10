<template>
  <Combobox :model-value="modelValue" nullable @update:model-value="selectETF">
    <div class="etf-selector">
      <ComboboxLabel class="selector-label">{{ label }}</ComboboxLabel>
      <div class="selector-input-wrap">
        <ComboboxInput
          class="input selector-input"
          :aria-label="label"
          :display-value="displayETF"
          placeholder="Search by name or ISIN…"
          autocomplete="off"
          @change="query = $event.target.value"
        />
        <ComboboxButton class="selector-toggle" :aria-label="'Show options for ' + label">▾</ComboboxButton>
      </div>
      <TransitionRoot as="template" @after-leave="query = ''">
        <ComboboxOptions class="selector-options">
          <li v-if="!matches.length" class="selector-message" role="presentation">
            {{ etfs.length ? 'No ETFs match your search.' : 'No ETFs available.' }}
          </li>
          <ComboboxOption v-for="etf in visibleMatches" :key="etf.id" v-slot="{ active, selected }" :value="etf.id" as="template">
            <li class="selector-option" :class="{ active, selected }">
              <span class="selector-isin">{{ etf.isin }}<span v-if="selected" aria-hidden="true"> ✓</span></span>
              <span class="selector-name">{{ etf.name }}</span>
            </li>
          </ComboboxOption>
          <li v-if="matches.length > visibleMatches.length" class="selector-message" role="presentation">
            Showing {{ visibleMatches.length }} of {{ matches.length }} ETFs. Type to narrow your search.
          </li>
        </ComboboxOptions>
      </TransitionRoot>
    </div>
  </Combobox>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Combobox, ComboboxLabel, ComboboxInput, ComboboxButton, ComboboxOptions, ComboboxOption, TransitionRoot } from '@headlessui/vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  etfs: { type: Array, default: () => [] },
  label: { type: String, default: 'ETF' },
})
const emit = defineEmits(['update:modelValue'])
const query = ref('')
const matches = computed(() => {
  const terms = query.value.trim().toLowerCase().split(/\s+/).filter(Boolean)
  return props.etfs.filter(etf => {
    const text = `${etf.isin ?? ''} ${etf.name ?? ''}`.toLowerCase()
    return terms.every(term => text.includes(term))
  })
})
// Search the entire catalog, but avoid rendering thousands of options at once.
const visibleMatches = computed(() => matches.value.slice(0, 100))

function displayETF(id) {
  const etf = props.etfs.find(etf => etf.id === id)
  return etf ? `${etf.isin} — ${etf.name}` : ''
}

function selectETF(id) {
  emit('update:modelValue', id ?? '')
  query.value = ''
}
</script>

<style scoped>
.etf-selector{position:relative;min-width:0}
.selector-label{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.selector-input-wrap{position:relative}
.selector-input{width:100%;padding-right:2.25rem;text-overflow:ellipsis}
.selector-toggle{position:absolute;right:1px;top:1px;bottom:1px;width:2rem;border:0;background:transparent;color:var(--text-muted);cursor:pointer;border-radius:var(--radius)}
.selector-toggle:focus-visible{outline:2px solid #1a6ab8}
.selector-options{position:absolute;z-index:50;top:100%;left:0;right:0;margin:.25rem 0 0;padding:.25rem;list-style:none;max-height:300px;overflow-y:auto;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-md)}
.selector-option{display:flex;flex-direction:column;gap:.2rem;padding:.6rem .75rem;border-radius:4px;cursor:pointer;overflow-wrap:anywhere}
.selector-option.active{background:rgba(26,106,184,.12)}
.selector-option.selected .selector-isin{color:#0f4c81}
.selector-isin{font-size:.85rem;font-weight:700;color:var(--text)}
.selector-name{font-size:.8rem;color:var(--text-muted)}
.selector-message{padding:.75rem;font-size:.8rem;color:var(--text-muted)}
</style>