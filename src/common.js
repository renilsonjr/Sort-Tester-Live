// The few things every screen needs in exactly the same form, the sign-in
// screen included. This file imports nothing and holds no state, so the
// page where the Quiz Code is typed can load it without loading the app.
// Keep it that way: a helper that needs another module belongs elsewhere.

// Text placed into markup goes through here. Nothing becomes an empty
// string rather than the word "undefined".
export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// The public result of an outside security test of this site, shown as
// ImmuniWeb's own badge at the foot of the sign-in screen and in Settings.
// A link and a local image: nothing from another site runs or loads here.
export const SECURITY_REPORT_URL = 'https://www.immuniweb.com/websec/sortquiz.app/Df6GfdiI/';
