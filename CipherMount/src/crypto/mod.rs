/// AES-GCM 256-bit encryption/decryption using the `ring` crate.
///
/// File layout on disk:
///   [ 12-byte nonce ][ ciphertext + 16-byte GCM tag ]
///
/// The nonce is randomly generated on every write so that encrypting the
/// same plaintext twice produces different ciphertext.

use anyhow::{anyhow, Result};
use ring::aead::{
    Aad, BoundKey, Nonce, NonceSequence, OpeningKey, SealingKey, UnboundKey, AES_256_GCM,
    NONCE_LEN,
};
use ring::error::Unspecified;
use ring::rand::{SecureRandom, SystemRandom};

/// Bytes prepended to every encrypted file on disk (the nonce).
pub const HEADER_LEN: usize = NONCE_LEN; // 12 bytes

struct SingleNonce([u8; NONCE_LEN]);

impl NonceSequence for SingleNonce {
    fn advance(&mut self) -> std::result::Result<Nonce, Unspecified> {
        Ok(Nonce::assume_unique_for_key(self.0))
    }
}

/// Encrypt `plaintext` with AES-256-GCM.
/// Returns `nonce || ciphertext || tag`.
pub fn encrypt(key: &[u8; 32], plaintext: &[u8]) -> Result<Vec<u8>> {
    let rng = SystemRandom::new();
    let mut nonce_bytes = [0u8; NONCE_LEN];
    rng.fill(&mut nonce_bytes).map_err(|_| anyhow!("RNG failure"))?;

    let unbound = UnboundKey::new(&AES_256_GCM, key).map_err(|_| anyhow!("Bad key"))?;
    let mut sealing = SealingKey::new(unbound, SingleNonce(nonce_bytes));

    let mut buf = plaintext.to_vec();
    sealing
        .seal_in_place_append_tag(Aad::empty(), &mut buf)
        .map_err(|_| anyhow!("Encryption failed"))?;

    let mut out = Vec::with_capacity(NONCE_LEN + buf.len());
    out.extend_from_slice(&nonce_bytes);
    out.extend_from_slice(&buf);
    Ok(out)
}

/// Decrypt a blob produced by `encrypt`.
/// Input must be at least `HEADER_LEN + 16` bytes (nonce + GCM tag).
pub fn decrypt(key: &[u8; 32], data: &[u8]) -> Result<Vec<u8>> {
    if data.len() < HEADER_LEN + 16 {
        return Err(anyhow!("Ciphertext too short"));
    }

    let (nonce_bytes, ciphertext) = data.split_at(HEADER_LEN);
    let nonce: [u8; NONCE_LEN] = nonce_bytes.try_into().unwrap();

    let unbound = UnboundKey::new(&AES_256_GCM, key).map_err(|_| anyhow!("Bad key"))?;
    let mut opening = OpeningKey::new(unbound, SingleNonce(nonce));

    let mut buf = ciphertext.to_vec();
    let plaintext = opening
        .open_in_place(Aad::empty(), &mut buf)
        .map_err(|_| anyhow!("Decryption failed (wrong key or corrupted data)"))?;

    Ok(plaintext.to_vec())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip() {
        let key = [0x42u8; 32];
        let plaintext = b"Hello, CipherMount!";
        let ciphertext = encrypt(&key, plaintext).unwrap();
        let decrypted = decrypt(&key, &ciphertext).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn wrong_key_fails() {
        let key1 = [0x01u8; 32];
        let key2 = [0x02u8; 32];
        let ciphertext = encrypt(&key1, b"secret").unwrap();
        assert!(decrypt(&key2, &ciphertext).is_err());
    }

    #[test]
    fn different_nonce_each_time() {
        let key = [0xAAu8; 32];
        let pt = b"same plaintext";
        let ct1 = encrypt(&key, pt).unwrap();
        let ct2 = encrypt(&key, pt).unwrap();
        assert_ne!(ct1, ct2); // different nonces → different ciphertext
    }
}
