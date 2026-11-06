// Private Set Intersection in the browser. Same maths as app/psi_reference.py.
// Secret keys are created here and never leave this page.

const P = BigInt("0x" +
  "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74" +
  "020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F1437" +
  "4FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED" +
  "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF05" +
  "98DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB" +
  "9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B" +
  "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF695581718" +
  "3995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF");
const Q = (P - 1n) / 2n;
const DOMAIN = "biosentinel-family/psi/v1|";

// (base ^ exp) mod m, by square-and-multiply
function modPow(base, exp, m) {
  let result = 1n;
  base %= m;
  while (exp > 0n) {
    if (exp & 1n) result = (result * base) % m;
    base = (base * base) % m;
    exp >>= 1n;
  }
  return result;
}

const toHex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

async function hashToGroup(item) {
  let hex = "";
  for (let i = 0; i < 9; i++) {
    const bytes = new TextEncoder().encode(`${DOMAIN}${i}|${item}`);
    hex += toHex(await crypto.subtle.digest("SHA-256", bytes));
  }
  const x = BigInt("0x" + hex) % P;
  return modPow(x, 2n, P);
}

function newKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(256));
  return (BigInt("0x" + toHex(bytes)) % (Q - 2n)) + 2n;
}

export const PSI = {
  newKey,
  // Lock my own items: H(x)^k
  async lockItems(items, key) {
    const out = [];
    for (const it of items) out.push(modPow(await hashToGroup(it), key, P).toString(16));
    return out;
  },
  // Lock values received from the other side: v^k (keeps the order)
  lockValues(hexValues, key) {
    return hexValues.map((h) => modPow(BigInt("0x" + h), key, P).toString(16));
  },
  shared(myItems, myDouble, theirDouble) {
    const theirs = new Set(theirDouble);
    return myItems.filter((_, i) => theirs.has(myDouble[i]));
  },
  // Fisher-Yates shuffle, so the order of my list reveals nothing
  shuffle(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = crypto.getRandomValues(new Uint32Array(1))[0] % (i + 1);
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  },
};
