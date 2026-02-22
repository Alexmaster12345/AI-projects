pub mod crypto;
mod fuse;

use clap::Parser;
use fuser::MountOption;
use std::path::PathBuf;

use crate::fuse::CipherFS;

/// CipherMount — encrypted FUSE filesystem (AES-256-GCM)
#[derive(Parser, Debug)]
#[command(author, version, about)]
struct Args {
    /// Physical backing directory (encrypted files stored here)
    #[arg(short, long)]
    source: PathBuf,

    /// Mount point (decrypted view exposed here)
    #[arg(short, long)]
    mountpoint: PathBuf,

    /// 32-byte key as 64-char hex string. Can also be set via CIPHER_KEY env var.
    #[arg(short, long, env = "CIPHER_KEY")]
    key: String,

    /// Allow other users to access the mount
    #[arg(long, default_value_t = false)]
    allow_other: bool,
}

fn main() -> anyhow::Result<()> {
    env_logger::init();

    let args = Args::parse();

    let key_bytes = hex::decode(&args.key)
        .map_err(|e| anyhow::anyhow!("Invalid key (must be 64-char hex): {}", e))?;
    anyhow::ensure!(key_bytes.len() == 32, "Key must be exactly 32 bytes (64 hex chars)");

    let key: [u8; 32] = key_bytes.try_into().unwrap();

    log::info!("CipherMount starting");
    log::info!("  Source:     {:?}", args.source);
    log::info!("  Mountpoint: {:?}", args.mountpoint);

    let mut options = vec![
        MountOption::FSName("ciphermount".to_string()),
        MountOption::AutoUnmount,
        MountOption::NoExec,
    ];
    if args.allow_other {
        options.push(MountOption::AllowOther);
    }

    let fs = CipherFS::new(args.source, key);
    fuser::mount2(fs, &args.mountpoint, &options)?;

    Ok(())
}
