/// Integration tests for the crypto layer.
/// FUSE mount tests require root/fuse permissions and are run manually.

use ciphermount::crypto;

#[test]
fn encrypt_decrypt_round_trip() {
    let key = [0x42u8; 32];
    let plaintext = b"The quick brown fox jumps over the lazy dog";
    let ciphertext = crypto::encrypt(&key, plaintext).unwrap();
    let decrypted = crypto::decrypt(&key, &ciphertext).unwrap();
    assert_eq!(decrypted.as_slice(), plaintext);
}

#[test]
fn wrong_key_returns_error() {
    let key1 = [0x01u8; 32];
    let key2 = [0x02u8; 32];
    let ciphertext = crypto::encrypt(&key1, b"secret data").unwrap();
    assert!(crypto::decrypt(&key2, &ciphertext).is_err());
}

#[test]
fn empty_plaintext_round_trip() {
    let key = [0xFFu8; 32];
    let ciphertext = crypto::encrypt(&key, b"").unwrap();
    let decrypted = crypto::decrypt(&key, &ciphertext).unwrap();
    assert_eq!(decrypted, b"");
}

#[test]
fn ciphertext_is_nondeterministic() {
    let key = [0xABu8; 32];
    let pt = b"same input";
    let ct1 = crypto::encrypt(&key, pt).unwrap();
    let ct2 = crypto::encrypt(&key, pt).unwrap();
    assert_ne!(ct1, ct2, "Each encryption must use a unique nonce");
}

#[test]
fn truncated_ciphertext_fails() {
    let key = [0x10u8; 32];
    let bad = vec![0u8; 10]; // too short: needs at least HEADER_LEN(12) + TAG(16)
    assert!(crypto::decrypt(&key, &bad).is_err());
}
