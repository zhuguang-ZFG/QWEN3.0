<template>
  <div ref="container" class="redoc-container"></div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface Props {
  specUrl: string
}

const props = defineProps<Props>()
const container = ref<HTMLDivElement | null>(null)

declare global {
  interface Window {
    Redoc?: {
      init: (specUrlOrObject: string | object, options: object, container: HTMLElement) => void
    }
  }
}

onMounted(() => {
  if (!container.value) return

  const init = () => {
    if (window.Redoc) {
      window.Redoc.init(props.specUrl, {}, container.value as HTMLDivElement)
    }
  }

  if (window.Redoc) {
    init()
  } else {
    const script = document.createElement('script')
    script.src = 'https://cdn.redocly.com/redoc/latest/bundles/redoc.standalone.js'
    script.async = true
    script.onload = init
    document.head.appendChild(script)
  }
})
</script>

<style scoped>
.redoc-container {
  min-height: 70vh;
}
</style>
