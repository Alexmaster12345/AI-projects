/// Week 1: Pass-through filesystem (mirrors a physical directory).
/// Week 2: Intercepts read/write to encrypt/decrypt with AES-256-GCM.

use crate::crypto;
use fuser::{
    FileAttr, FileType, Filesystem, ReplyAttr, ReplyData, ReplyDirectory, ReplyEmpty,
    ReplyEntry, ReplyOpen, ReplyWrite, Request,
};
use libc::{ENOENT, ENOTDIR, EIO};
use std::collections::HashMap;
use std::ffi::OsStr;
use std::fs;
use std::os::unix::fs::MetadataExt;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Duration, UNIX_EPOCH};

const TTL: Duration = Duration::from_secs(1);
const ROOT_INO: u64 = 1;

pub struct CipherFS {
    source: PathBuf,
    key: [u8; 32],
    /// inode → path mapping (in-memory, rebuilt on each lookup)
    inodes: Arc<Mutex<HashMap<u64, PathBuf>>>,
    next_ino: Arc<Mutex<u64>>,
}

impl CipherFS {
    pub fn new(source: PathBuf, key: [u8; 32]) -> Self {
        let mut inodes = HashMap::new();
        inodes.insert(ROOT_INO, source.clone());
        Self {
            source,
            key,
            inodes: Arc::new(Mutex::new(inodes)),
            next_ino: Arc::new(Mutex::new(2)),
        }
    }

    fn alloc_ino(&self) -> u64 {
        let mut n = self.next_ino.lock().unwrap();
        let ino = *n;
        *n += 1;
        ino
    }

    fn path_for(&self, ino: u64) -> Option<PathBuf> {
        self.inodes.lock().unwrap().get(&ino).cloned()
    }

    fn register(&self, path: PathBuf) -> u64 {
        let mut map = self.inodes.lock().unwrap();
        // Return existing ino if already registered
        for (ino, p) in map.iter() {
            if p == &path {
                return *ino;
            }
        }
        let ino = {
            let mut n = self.next_ino.lock().unwrap();
            let i = *n;
            *n += 1;
            i
        };
        map.insert(ino, path);
        ino
    }

    fn meta_to_attr(ino: u64, meta: &fs::Metadata) -> FileAttr {
        let kind = if meta.is_dir() {
            FileType::Directory
        } else {
            FileType::RegularFile
        };
        let mtime = meta
            .modified()
            .unwrap_or(UNIX_EPOCH)
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default();
        let atime = meta
            .accessed()
            .unwrap_or(UNIX_EPOCH)
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default();
        FileAttr {
            ino,
            size: meta.len(),
            blocks: meta.blocks(),
            atime: UNIX_EPOCH + atime,
            mtime: UNIX_EPOCH + mtime,
            ctime: UNIX_EPOCH + mtime,
            crtime: UNIX_EPOCH,
            kind,
            perm: meta.mode() as u16,
            nlink: meta.nlink() as u32,
            uid: meta.uid(),
            gid: meta.gid(),
            rdev: meta.rdev() as u32,
            blksize: 512,
            flags: 0,
        }
    }
}

impl Filesystem for CipherFS {
    fn getattr(&mut self, _req: &Request, ino: u64, reply: ReplyAttr) {
        if let Some(path) = self.path_for(ino) {
            match fs::metadata(&path) {
                Ok(meta) => reply.attr(&TTL, &Self::meta_to_attr(ino, &meta)),
                Err(_) => reply.error(ENOENT),
            }
        } else {
            reply.error(ENOENT);
        }
    }

    fn lookup(&mut self, _req: &Request, parent: u64, name: &OsStr, reply: ReplyEntry) {
        if let Some(parent_path) = self.path_for(parent) {
            let child_path = parent_path.join(name);
            match fs::metadata(&child_path) {
                Ok(meta) => {
                    let ino = self.register(child_path);
                    reply.entry(&TTL, &Self::meta_to_attr(ino, &meta), 0);
                }
                Err(_) => reply.error(ENOENT),
            }
        } else {
            reply.error(ENOENT);
        }
    }

    fn readdir(
        &mut self,
        _req: &Request,
        ino: u64,
        _fh: u64,
        offset: i64,
        mut reply: ReplyDirectory,
    ) {
        let path = match self.path_for(ino) {
            Some(p) => p,
            None => {
                reply.error(ENOENT);
                return;
            }
        };

        if !path.is_dir() {
            reply.error(ENOTDIR);
            return;
        }

        let entries = match fs::read_dir(&path) {
            Ok(e) => e,
            Err(_) => {
                reply.error(EIO);
                return;
            }
        };

        let mut all: Vec<(u64, FileType, String)> = vec![
            (ino, FileType::Directory, ".".to_string()),
            (ino, FileType::Directory, "..".to_string()),
        ];

        for entry in entries.flatten() {
            let child_path = entry.path();
            let child_ino = self.register(child_path.clone());
            let kind = if child_path.is_dir() {
                FileType::Directory
            } else {
                FileType::RegularFile
            };
            let name = entry.file_name().to_string_lossy().to_string();
            all.push((child_ino, kind, name));
        }

        for (i, (child_ino, kind, name)) in all.iter().enumerate().skip(offset as usize) {
            if reply.add(*child_ino, (i + 1) as i64, *kind, name) {
                break;
            }
        }
        reply.ok();
    }

    fn open(&mut self, _req: &Request, ino: u64, _flags: i32, reply: ReplyOpen) {
        if self.path_for(ino).is_some() {
            reply.opened(0, 0);
        } else {
            reply.error(ENOENT);
        }
    }

    /// Read: load file from disk → decrypt → return plaintext to caller.
    fn read(
        &mut self,
        _req: &Request,
        ino: u64,
        _fh: u64,
        offset: i64,
        size: u32,
        _flags: i32,
        _lock_owner: Option<u64>,
        reply: ReplyData,
    ) {
        let path = match self.path_for(ino) {
            Some(p) => p,
            None => {
                reply.error(ENOENT);
                return;
            }
        };

        let raw = match fs::read(&path) {
            Ok(b) => b,
            Err(_) => {
                reply.error(EIO);
                return;
            }
        };

        // If file is empty or too short to be encrypted, return empty
        if raw.len() < crypto::HEADER_LEN + 16 {
            reply.data(&[]);
            return;
        }

        match crypto::decrypt(&self.key, &raw) {
            Ok(plaintext) => {
                let start = offset as usize;
                let end = (start + size as usize).min(plaintext.len());
                if start >= plaintext.len() {
                    reply.data(&[]);
                } else {
                    reply.data(&plaintext[start..end]);
                }
            }
            Err(e) => {
                log::error!("Decrypt error on {:?}: {}", path, e);
                reply.error(EIO);
            }
        }
    }

    /// Write: encrypt buffer → write to disk.
    fn write(
        &mut self,
        _req: &Request,
        ino: u64,
        _fh: u64,
        offset: i64,
        data: &[u8],
        _write_flags: u32,
        _flags: i32,
        _lock_owner: Option<u64>,
        reply: ReplyWrite,
    ) {
        let path = match self.path_for(ino) {
            Some(p) => p,
            None => {
                reply.error(ENOENT);
                return;
            }
        };

        // Read existing plaintext (if any) so we can handle partial writes
        let mut plaintext = if path.exists() {
            let raw = fs::read(&path).unwrap_or_default();
            if raw.len() >= crypto::HEADER_LEN + 16 {
                crypto::decrypt(&self.key, &raw).unwrap_or_default()
            } else {
                vec![]
            }
        } else {
            vec![]
        };

        // Extend buffer if needed and write at offset
        let end = offset as usize + data.len();
        if plaintext.len() < end {
            plaintext.resize(end, 0);
        }
        plaintext[offset as usize..end].copy_from_slice(data);

        match crypto::encrypt(&self.key, &plaintext) {
            Ok(ciphertext) => match fs::write(&path, &ciphertext) {
                Ok(_) => reply.written(data.len() as u32),
                Err(_) => reply.error(EIO),
            },
            Err(e) => {
                log::error!("Encrypt error on {:?}: {}", path, e);
                reply.error(EIO);
            }
        }
    }

    fn create(
        &mut self,
        _req: &Request,
        parent: u64,
        name: &OsStr,
        _mode: u32,
        _umask: u32,
        _flags: i32,
        reply: fuser::ReplyCreate,
    ) {
        let parent_path = match self.path_for(parent) {
            Some(p) => p,
            None => {
                reply.error(ENOENT);
                return;
            }
        };
        let child_path = parent_path.join(name);
        match fs::File::create(&child_path) {
            Ok(_) => {
                let ino = self.register(child_path.clone());
                let meta = fs::metadata(&child_path).unwrap();
                reply.created(&TTL, &Self::meta_to_attr(ino, &meta), 0, 0, 0);
            }
            Err(_) => reply.error(EIO),
        }
    }

    fn unlink(&mut self, _req: &Request, parent: u64, name: &OsStr, reply: ReplyEmpty) {
        let parent_path = match self.path_for(parent) {
            Some(p) => p,
            None => {
                reply.error(ENOENT);
                return;
            }
        };
        let child_path = parent_path.join(name);
        match fs::remove_file(&child_path) {
            Ok(_) => reply.ok(),
            Err(_) => reply.error(EIO),
        }
    }

    fn mkdir(
        &mut self,
        _req: &Request,
        parent: u64,
        name: &OsStr,
        _mode: u32,
        _umask: u32,
        reply: ReplyEntry,
    ) {
        let parent_path = match self.path_for(parent) {
            Some(p) => p,
            None => {
                reply.error(ENOENT);
                return;
            }
        };
        let child_path = parent_path.join(name);
        match fs::create_dir(&child_path) {
            Ok(_) => {
                let ino = self.register(child_path.clone());
                let meta = fs::metadata(&child_path).unwrap();
                reply.entry(&TTL, &Self::meta_to_attr(ino, &meta), 0);
            }
            Err(_) => reply.error(EIO),
        }
    }

    fn rmdir(&mut self, _req: &Request, parent: u64, name: &OsStr, reply: ReplyEmpty) {
        let parent_path = match self.path_for(parent) {
            Some(p) => p,
            None => {
                reply.error(ENOENT);
                return;
            }
        };
        let child_path = parent_path.join(name);
        match fs::remove_dir(&child_path) {
            Ok(_) => reply.ok(),
            Err(_) => reply.error(EIO),
        }
    }
}
