"""Private Set Intersection (PSI), reference implementation in Python.

The real protocol runs in the two browsers (web/psi.js). This file is the
same maths in Python, used by the tests to prove it works and as a readable
version for learning.

Idea (Diffie-Hellman PSI, semi-honest model)
--------------------------------------------
Each partner has a secret random number: a (Amina), b (Khalid).
H(gene) turns a gene name into a number in a large prime group.
Exponentiation "locks" a value; locks commute:  (H^a)^b == (H^b)^a.

  1. Amina sends  H(x)^a  for each of her genes x        (looks random)
  2. Khalid sends back (H(x)^a)^b, in the same order, and his own H(y)^b
  3. Amina computes (H(y)^b)^a
  4. A value appears in both double-locked lists exactly when x == y.

Amina learns which of HER genes are shared (she knows the order), and
nothing about Khalid's other genes: they stay locked under b, which only
Khalid knows. Step 5 sends Amina's double-locked copy of Khalid's list back
so he learns the same intersection. The relay server only ever sees locked
values.

Known limits (documented in docs/HOW_IT_WORKS.md):
  - both sides learn how many genes the other has on the list
  - a dishonest partner could put ALL 570 panel genes in their list to learn
    the other's full result; production needs lab-signed inputs
"""
import hashlib
import secrets

# RFC 3526, group 14: a 2048-bit "safe prime" P, with Q = (P-1)/2 also prime.
P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74"
    "020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F1437"
    "4FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF05"
    "98DA48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB"
    "9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF695581718"
    "3995497CEA956AE515D2261898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF", 16)
Q = (P - 1) // 2
DOMAIN = "biosentinel-family/psi/v1|"


def hash_to_group(item: str) -> int:
    """Map a gene name to an element of the order-Q subgroup.

    SHA-256 gives 256 bits; we chain 9 blocks to cover 2048+ bits, reduce
    mod P, then square: squares mod a safe prime form the subgroup of
    prime order Q, where the "locks commute" maths is sound.
    """
    blocks = b"".join(hashlib.sha256(f"{DOMAIN}{i}|{item}".encode()).digest() for i in range(9))
    x = int.from_bytes(blocks, "big") % P
    return pow(x, 2, P)


def new_key() -> int:
    return secrets.randbelow(Q - 2) + 2


def lock(values: list[int], key: int) -> list[int]:
    return [pow(v, key, P) for v in values]


def shared_items(my_items: list[str], my_double: list[int], their_double: list[int]) -> list[str]:
    """my_double[i] is my item i locked by both keys; compare with their list."""
    theirs = set(their_double)
    return [item for item, d in zip(my_items, my_double) if d in theirs]
