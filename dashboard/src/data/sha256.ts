/**
 * SHA-256 through the Web Crypto API. `crypto.subtle` exists only in a secure context (https or
 * localhost); elsewhere verification is reported as unavailable, never as passed (§9.2).
 */

export function getSubtle(): SubtleCrypto | null {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  return c !== undefined && c.subtle !== undefined && globalThis.isSecureContext !== false ? c.subtle : null;
}

export async function sha256Hex(bytes: Uint8Array, subtle: SubtleCrypto): Promise<string> {
  const digest = await subtle.digest("SHA-256", bytes as Uint8Array<ArrayBuffer>);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}
