import DefaultTheme from 'vitepress/theme'
import './custom.css'
import Redoc from './components/Redoc.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Redoc', Redoc)
  },
}
