// End-to-end encryption of what a person sends to a genetic counsellor (WebCrypto, no library).
//
// Each counsellor DEVICE has an ECDH P-256 key pair; the private key never leaves that browser.
// The person's phone:
//   1. encrypts the case with a fresh random AES-256-GCM key (the "content key"),
//   2. for each registered counsellor device, derives a wrapping key with ECDH (a fresh ephemeral
//      key pair) + HKDF-SHA-256, and encrypts the content key with it.
// The server only ever stores ciphertext. Only a registered counsellor device can open a case.
// Works in browsers and in Node 20+ (globalThis.crypto), so the tests can run it.

const subtle = globalThis.crypto.subtle;
const enc = new TextEncoder(), dec = new TextDecoder();
const ALG = "ECDH-P256+HKDF-SHA256+A256GCM";
const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
const ECDH = { name: "ECDH", namedCurve: "P-256" };

async function wrappingKey(privateKey, publicKey, kid, iv) {
  const bits = await subtle.deriveBits({ name: "ECDH", public: publicKey }, privateKey, 256);
  const hk = await subtle.importKey("raw", bits, "HKDF", false, ["deriveKey"]);
  return subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: iv, info: enc.encode(`bsf-case-v1:${kid}`) },
                          hk, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}

/** A short public id for a device key: first 16 hex chars of SHA-256(x || y). */
export async function keyId(publicJwk) {
  const h = await subtle.digest("SHA-256", enc.encode(publicJwk.x + publicJwk.y));
  return [...new Uint8Array(h)].slice(0, 8).map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** New counsellor device: {kid, publicJwk, privateJwk}. Keep privateJwk on the device only. */
export async function newDevice() {
  const kp = await subtle.generateKey(ECDH, true, ["deriveBits"]);
  const publicJwk = await subtle.exportKey("jwk", kp.publicKey);
  const privateJwk = await subtle.exportKey("jwk", kp.privateKey);
  const pub = { kty: publicJwk.kty, crv: publicJwk.crv, x: publicJwk.x, y: publicJwk.y };
  return { kid: await keyId(pub), publicJwk: pub, privateJwk };
}

/** Encrypt `obj` for every device in `devices` ([{kid, jwk}]). Returns a JSON-safe envelope. */
export async function seal(obj, devices) {
  if (!devices?.length) throw new Error("no counsellor device registered");
  const contentKey = await subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
  const iv = globalThis.crypto.getRandomValues(new Uint8Array(12));
  const ct = await subtle.encrypt({ name: "AES-GCM", iv }, contentKey, enc.encode(JSON.stringify(obj)));
  const raw = await subtle.exportKey("raw", contentKey);
  const eph = await subtle.generateKey(ECDH, true, ["deriveBits"]);
  const epk = await subtle.exportKey("jwk", eph.publicKey);
  const keys = [];
  for (const d of devices) {
    const pub = await subtle.importKey("jwk", d.jwk, ECDH, false, []);
    const kiv = globalThis.crypto.getRandomValues(new Uint8Array(12));
    const wk = await wrappingKey(eph.privateKey, pub, d.kid, kiv);
    keys.push({ kid: d.kid, iv: b64(kiv), wk: b64(await subtle.encrypt({ name: "AES-GCM", iv: kiv }, wk, raw)) });
  }
  return { v: 1, alg: ALG, epk: { kty: epk.kty, crv: epk.crv, x: epk.x, y: epk.y }, iv: b64(iv), ct: b64(ct), keys };
}

/** Decrypt an envelope with this device ({kid, privateJwk}). Throws if it was not sealed for it. */
export async function open(envelope, device) {
  const k = envelope.keys.find((x) => x.kid === device.kid);
  if (!k) throw new Error("not sealed for this device");
  const priv = await subtle.importKey("jwk", device.privateJwk, ECDH, false, ["deriveBits"]);
  const epk = await subtle.importKey("jwk", envelope.epk, ECDH, false, []);
  const kiv = unb64(k.iv);
  const wk = await wrappingKey(priv, epk, device.kid, kiv);
  const raw = await subtle.decrypt({ name: "AES-GCM", iv: kiv }, wk, unb64(k.wk));
  const contentKey = await subtle.importKey("raw", raw, "AES-GCM", false, ["decrypt"]);
  const pt = await subtle.decrypt({ name: "AES-GCM", iv: unb64(envelope.iv) }, contentKey, unb64(envelope.ct));
  return JSON.parse(dec.decode(pt));
}
