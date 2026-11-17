/** Helpers for the few places that build HTML as strings (Leaflet divIcons,
 *  which set it with innerHTML): names and other user text go in escaped, and
 *  a plan image only as an image the browser made itself. */

const ENTITIES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** Any value as text that is safe in HTML content and in quoted attributes. */
export function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ENTITIES[c]);
}

// What fileToPlanImage makes (a base64 data URL) or an object URL. Nothing
// else: a project file, a CSV or an AI command could hold any text, and a
// plan ends up in a CSS url() and an <img>.
const DATA_IMAGE = /^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$/;
const BLOB_URL = /^blob:[A-Za-z0-9.:/_-]+$/;

export function isSafeImageUrl(url: unknown): url is string {
  return typeof url === 'string' && (DATA_IMAGE.test(url) || BLOB_URL.test(url));
}

/** The plan image URL, or undefined if it is not one we accept. */
export const safeImageUrl = (url: unknown): string | undefined =>
  isSafeImageUrl(url) ? url : undefined;
