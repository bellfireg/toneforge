// Mandarin Tutor — runtime config.
// API base is empty => same-origin (PWA served by the FastAPI backend on :8900).
// If you serve the app from a different host, set API_BASE to the Tailscale URL,
// e.g. "http://100.125.94.107:8900".
window.MT_CONFIG = {
  API_BASE: "",
  DEFAULT_VOICE: "zh-CN-XiaoxiaoNeural",
};
