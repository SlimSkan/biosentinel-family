# Threat model

What could go wrong with genetic data in BioSentinel Family, what the prototype already does
about it, and what is planned before any clinical pilot. "Prototype" means it is built and tested
(see `tests/test_core.py`); "Planned" means it is not built yet.

Context: genetic data is among the most sensitive personal data. In the UAE, Federal Decree-Law
No. 49 of 2023 regulates the use of the human genome and requires genetic data to be kept
confidential, and Federal Law No. 2 of 2019 governs health data in ICT. A pilot needs a legal
review against both, a data-protection impact assessment and an independent security audit.

## What each party sees

| Party | Sees | Never sees |
|---|---|---|
| Server (Render demo) | Locked PSI numbers, invite ids and counters, encrypted cases (ciphertext), routing fields (service, priority, status, timestamps), counsellor devices' public keys | Names, full results, which genes a person carries, the content of any case |
| Partner | The genes both carry, and whether it is the identical variant | Any other result of the partner, or the partner's variant when it differs |
| Relative (family invite) | One gene and its meaning, their own chance | Who sent the invite, the sender's other results |
| AI provider (Google, for Gemma 4 on the Gemini API) | De-identified prompts: gene, condition, risk numbers, quiz answers, the reader's own question | Names, contact details, lab, the encrypted case, the questions the person chose to send to the counsellor |
| Counsellor device | The brief the person approved, decrypted locally | Anything the person did not include |

## Threats and protections

| Threat | Protection now (prototype) | Planned |
|---|---|---|
| Network interception | HTTPS (TLS) on the demo; cases end-to-end encrypted (ECDH P-256 + HKDF-SHA-256 + AES-256-GCM) before leaving the phone | Certificate pinning in a native app |
| Server breach | The server stores ciphertext only for cases; no names or full results; in-memory storage, nothing on disk | UAE-hosted database with encryption at rest, Key Vault, audit logging (Azure Monitor) |
| Stolen phone | Results live in page memory only and disappear when the page closes | Encrypted on-device storage behind device authentication |
| Unauthorised counsellor access | Counsellor key required to register devices and read routing data; optional key expiry (`BSF_COUNSELLOR_KEY_EXPIRES`); cases can only be opened by a registered device's private key | Individual sign-in (Microsoft Entra ID), administrator approval of devices, keys in a hardware or OS keystore |
| Compromised counsellor device | Revocation: a device can be removed, and new cases are no longer encrypted for it; audit trail records which device changed a status | Re-encryption of open cases for remaining devices; mandatory device attestation |
| Partner learns too much | PSI reveals only shared genes and identical variants; consent ticked by each partner; a link alone can never join a match | Lab-signed results to prevent "set inflation" (adding genes one does not carry to probe the partner) |
| Probing the PSI | Match sessions expire after 30 minutes; at most 64 items per list | Rate limiting per device; protocol review by a cryptographer |
| Correlating family invites | Invite ids are random; the relative's relation is chosen on their phone and never stored; the sender sees only counts | Counsellor-sent invites for very small families, where the sender could be guessed |
| AI error or invented risk | The AI never computes a number; six guardrails; answers must cite numbered facts, checked; fallback to reviewed text | Counsellor review of a sample of real outputs; an entailment check per sentence |
| Misuse: pressure about marriage | Options are never ranked; directive language is blocked; decisions stay with the couple | Native-speaker and counsellor review of every Arabic text |
| Consent withdrawal | The person can withdraw a referral, which deletes it from the server; nothing is kept after a restart | Withdrawal of family invites and data export on request |

## Known limits (stated openly)

- The demo counsellor key is shared and printed on the access slide because the organisers ask for
  guest credentials; it is temporary and will be rotated after the evaluation.
- Counsellor device keys live in the browser's storage, which is weaker than a hardware keystore.
- The PSI code is our own implementation of a standard Diffie-Hellman PSI; it has tests but has
  not been independently audited.
