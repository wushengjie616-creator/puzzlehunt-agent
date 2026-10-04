async function responseErrorMessage(response) {
  const body = await response.text();
  if (!body.trim()) return `HTTP ${response.status}`;
  try {
    const parsed = JSON.parse(body);
    if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail;
  } catch (_error) {
    // Proxies and uncaught server errors may return plain text instead of JSON.
  }
  return body.slice(0, 1000);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { responseErrorMessage };
} else {
  globalThis.responseErrorMessage = responseErrorMessage;
}
