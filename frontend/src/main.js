import { createApp } from 'vue'
import App from './App.vue'
import { BRAND } from './brand.js'

document.title = BRAND.name

const app = createApp(App)
app.mount('#app')
