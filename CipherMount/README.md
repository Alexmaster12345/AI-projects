# CipherMount

An encrypted FUSE filesystem written in Rust. Files are stored AES-256-GCM encrypted on disk and exposed as plaintext through a mount point.

## How It Works

```
/mnt/secure/          ← Mount point (plaintext view)
    secret.txt        ← You read/write normal text here

/home/data/           ← Backing store (encrypted on disk)
    secret.txt        ← Stored as: [12-byte nonce][ciphertext][16-byte GCM tag]
```

Every `read()` decrypts on the fly. Every `write()` encrypts before hitting disk.

## Tech Stack

- **Language:** Rust
- **FUSE interface:** [`fuser`](https://crates.io/crates/fuser)
- **Encryption:** [`ring`](https://crates.io/crates/ring) — AES-256-GCM
- **Kernel interface:** `/dev/fuse`

## Project Structure

```
CipherMount/
├── bin/                  # Compiled binaries (after cargo build)
├── docs/                 # Architecture diagrams and notes
├── src/
│   ├── crypto/mod.rs     # AES-256-GCM encrypt/decrypt
│   ├── fuse/mod.rs       # FUSE callbacks (getattr, readdir, read, write, ...)
│   └── main.rs           # CLI entry point + mount
├── tests/
│   └── integration_test.rs
├── Cargo.toml
└── README.md
```

## Build

```bash
# Install system dependency
sudo apt install fuse libfuse-dev   # Debian/Ubuntu
sudo dnf install fuse fuse-devel    # RHEL/Rocky/CentOS

# Build
cargo build --release
cp target/release/ciphermount bin/
```

## Usage

```bash
# Generate a random 32-byte key (64 hex chars)
KEY=$(openssl rand -hex 32)
echo "Key: $KEY"

# Create directories
mkdir -p /tmp/cipher_store /tmp/cipher_mount

# Mount
export CIPHER_KEY=$KEY
./bin/ciphermount --source /tmp/cipher_store --mountpoint /tmp/cipher_mount

# In another terminal — use it like a normal filesystem
echo "top secret" > /tmp/cipher_mount/secret.txt
cat /tmp/cipher_mount/secret.txt   # → top secret

# On disk it's encrypted
xxd /tmp/cipher_store/secret.txt   # → binary garbage

# Unmount
fusermount -u /tmp/cipher_mount
```

## Roadmap

### Week 1 — Mirror Filesystem ✅
- [x] `getattr`, `lookup`, `readdir`, `open`
- [x] `read`, `write`, `create`, `unlink`, `mkdir`, `rmdir`

### Week 2 — Cryptography Layer ✅
- [x] AES-256-GCM encrypt on write
- [x] AES-256-GCM decrypt on read
- [x] Random nonce per write (stored as 12-byte file header)
- [x] Partial write support (read-modify-encrypt-write)

### Week 3 — Hardening (TODO)
- [ ] Filename encryption (encrypt filenames on disk)
- [ ] `mlock` key in memory (prevent swap to disk)
- [ ] Thread-safety audit
- [ ] Key derivation from passphrase (Argon2)

## Run Tests

```bash
cargo test
```
