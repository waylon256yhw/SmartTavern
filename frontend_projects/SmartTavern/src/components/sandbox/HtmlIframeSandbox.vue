<template>
  <iframe
    ref="frame"
    class="st-iframe"
    :sandbox="effectiveSandbox"
    :allow="effectiveAllow"
    allowfullscreen
    :srcdoc="computedSrcdoc"
    :style="autoHeight && heightPx > 0 ? { height: heightPx + 'px' } : null"
  >
  </iframe>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch, onBeforeUnmount, nextTick } from 'vue';
import { generateSandboxBridgeScript, generateGuardedBridgeScript } from '@/utils/sandboxBridge';
import { SANDBOX_ATTRS, ALLOW_ATTRS } from '@/features/themes/sandbox/types';
import type { TrustLevel } from '@/features/themes/sandbox/types';
import { createSandboxHost } from '@/features/themes/sandbox/host';
import type { SandboxHost } from '@/features/themes/sandbox/host';
// Raw import of client.js source for guarded mode injection
import clientJsSrc from '@/features/themes/sandbox/client.js?raw';

const props = defineProps({
  html: { type: String, default: '' },
  baseUrl: { type: String, default: '' },
  trustLevel: {
    type: String as () => TrustLevel,
    default: 'trusted' as TrustLevel,
  },
  sandbox: { type: String, default: '' },
  allow: { type: String, default: '' },
  injectCss: { type: String, default: '' },
  csp: { type: String, default: '' },
  autoHeight: { type: Boolean, default: true },
});

const emit = defineEmits(['iframe-loaded']);

const frame = ref<HTMLIFrameElement | null>(null);
const heightPx = ref<number>(0);

let __ro: ResizeObserver | null = null;
let __onLoad: ((this: HTMLIFrameElement, ev: Event) => any) | null = null;
let __sandboxHost: SandboxHost | null = null;
let __guardedNonce: string | null = null;

const effectiveSandbox = computed(() => {
  if (props.sandbox) return props.sandbox;
  return SANDBOX_ATTRS[props.trustLevel] ?? SANDBOX_ATTRS.trusted;
});

const effectiveAllow = computed(() => {
  if (props.allow) return props.allow;
  return ALLOW_ATTRS[props.trustLevel] ?? ALLOW_ATTRS.trusted;
});

function buildBridgeScripts(): string {
  const scriptOpen = '<' + 'script>';
  const scriptClose = '<' + '/script>';

  if (props.trustLevel === 'strict') {
    __guardedNonce = null;
    return '';
  }
  if (props.trustLevel === 'guarded') {
    __guardedNonce = crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2) + Date.now().toString(36);
    const nonceScript =
      scriptOpen + `window.__stSandboxNonce=${JSON.stringify(__guardedNonce)};` + scriptClose;
    const clientScript = scriptOpen + clientJsSrc + scriptClose;
    const guardedBridge = scriptOpen + generateGuardedBridgeScript() + scriptClose;
    return nonceScript + clientScript + guardedBridge;
  }
  __guardedNonce = null;
  // trusted: full bridge via window.parent
  return scriptOpen + generateSandboxBridgeScript() + scriptClose;
}

const computedSrcdoc = computed(() => {
  const base = props.baseUrl ? `<base href="${props.baseUrl}">` : '';
  let csp = '';
  if (props.csp) {
    csp = `<meta http-equiv="Content-Security-Policy" content="${props.csp}">`;
  } else if (props.trustLevel === 'guarded') {
    csp = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline' data:; img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; form-action 'none'; prefetch-src 'none';">`;
  }
  const injected = props.injectCss ? `<style>${props.injectCss}</style>` : '';
  const normalize = props.autoHeight
    ? `<style>html,body{min-height:100%;margin:0;padding:0;background:transparent}</style>`
    : `<style>html,body{height:100%;margin:0;padding:0;background:transparent}</style>`;
  const bridgeScripts = buildBridgeScripts();
  return `<!doctype html><html><head><meta charset="utf-8">${csp}${base}${normalize}${injected}${bridgeScripts}</head><body>${props.html}</body></html>`;
});

function setupSandboxHost() {
  disposeSandboxHost();
  if (props.trustLevel !== 'guarded') return;
  const f = frame.value;
  if (!f) return;
  __sandboxHost = createSandboxHost(f, {
    trustLevel: 'guarded',
    nonce: __guardedNonce ?? undefined,
  });
  registerReadOnlyHandlers(__sandboxHost);
}

function registerReadOnlyHandlers(host: SandboxHost) {
  const readFunctions = [
    'getCharAvatarPath',
    'getPersonaAvatarPath',
    'getChar',
    'getPersona',
    'getVariable',
    'getVariables',
    'getVariableJSON',
    'getChatSettings',
    'getChatSettingsField',
    'getLlmConfig',
    'getLlmConfigField',
    'getPreset',
    'getWorldBooks',
    'getRegexRules',
    'showToast',
  ];
  for (const name of readFunctions) {
    const fn = (window as any)[name];
    if (typeof fn === 'function') {
      host.registerHandler(name, (...args: any[]) => fn(...args));
    }
  }
}

function disposeSandboxHost() {
  if (__sandboxHost) {
    __sandboxHost.dispose();
    __sandboxHost = null;
  }
}

function __measure() {
  if (!props.autoHeight) return;
  const f = frame.value;
  const doc = f?.contentDocument;
  const de = doc?.documentElement;
  const body = doc?.body;
  if (!doc || !de || !body) return;
  const h = Math.max(
    body.scrollHeight,
    de.scrollHeight,
    body.offsetHeight,
    de.offsetHeight,
    body.getBoundingClientRect().height,
  );
  heightPx.value = Math.max(1, Math.round(h));
}

function __disposeObservers() {
  if (__ro) {
    try {
      __ro.disconnect();
    } catch (_) {}
    __ro = null;
  }
}

function __setupObservers() {
  __disposeObservers();
  if (!props.autoHeight) return;
  // In guarded mode (no allow-same-origin), contentDocument is not accessible
  if (props.trustLevel === 'guarded' || props.trustLevel === 'strict') return;
  const f = frame.value;
  const doc = f?.contentDocument;
  const de = doc?.documentElement;
  const body = doc?.body;
  if (!doc || !de || !body) return;
  const RO = (f!.contentWindow as any)?.ResizeObserver || ResizeObserver;
  __ro = new RO(() => __measure());
  if (__ro) {
    try {
      __ro.observe(body);
      __ro.observe(de);
    } catch (_) {}
  }
  __measure();
}

onMounted(() => {
  const f = frame.value;
  if (!f) return;
  __onLoad = () => {
    __setupObservers();
    setupSandboxHost();
    nextTick(() => {
      __measure();
      emit('iframe-loaded');
    });
  };
  f.addEventListener('load', __onLoad);
  nextTick(() => __setupObservers());
});

onBeforeUnmount(() => {
  const f = frame.value;
  if (f && __onLoad) {
    try {
      f.removeEventListener('load', __onLoad);
    } catch (_) {}
  }
  __onLoad = null;
  __disposeObservers();
  disposeSandboxHost();
});

watch(
  () => props.html,
  () => {
    if (props.autoHeight) heightPx.value = 0;
  },
);

watch(
  () => props.trustLevel,
  () => {
    setupSandboxHost();
  },
);
</script>

<style scoped>
.st-iframe {
  width: 100%;
  height: 100%;
  border: 0;
  border-radius: inherit;
  background: transparent;
  display: block;
}
</style>
