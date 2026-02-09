import { watch, onUnmounted, type Ref } from 'vue'
import { createFocusTrap, type FocusTrap } from 'focus-trap'

export function useFocusTrap(
  containerRef: Ref<HTMLElement | null | undefined>,
  isActive: Ref<boolean>,
) {
  let trap: FocusTrap | null = null

  function activate() {
    const el = containerRef.value
    if (!el || trap) return
    trap = createFocusTrap(el, {
      escapeDeactivates: false,
      allowOutsideClick: true,
      fallbackFocus: el,
    })
    trap.activate()
  }

  function deactivate() {
    if (!trap) return
    trap.deactivate()
    trap = null
  }

  watch(
    [isActive, containerRef],
    ([active]) => {
      if (active && containerRef.value) {
        activate()
      } else {
        deactivate()
      }
    },
    { flush: 'post' },
  )

  onUnmounted(deactivate)

  return { activate, deactivate }
}
