from __future__ import annotations

import base64
import binascii
import hashlib
import importlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class DigestResult:
    ok: bool
    hex: Optional[str] = None
    error: Optional[str] = None
    note: Optional[str] = None


def _crc16_ibm(data: bytes) -> int:
    # CRC-16/IBM (aka CRC-16/ARC): poly=0xA001, init=0x0000, xorout=0x0000, refin/refout=true
    crc = 0x0000
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def decode_input(raw: str, *, input_format: str) -> Tuple[Optional[bytes], Optional[str]]:
    fmt = (input_format or "text").strip().lower()
    if fmt == "text":
        return raw.encode("utf-8", errors="replace"), None

    if fmt == "hex":
        try:
            cleaned = "".join(str(raw).split())
            if cleaned.startswith("0x"):
                cleaned = cleaned[2:]
            return bytes.fromhex(cleaned), None
        except Exception:
            return None, "invalid hex"

    if fmt == "base64":
        try:
            cleaned = "".join(str(raw).split())
            return base64.b64decode(cleaned, validate=True), None
        except Exception:
            return None, "invalid base64"

    return None, "input_format must be one of: text, hex, base64"


def _hashlib_hex(name: str, data: bytes) -> str:
    h = hashlib.new(name)
    h.update(data)
    return h.hexdigest()


def _try_crypto_hash(algo: str, data: bytes) -> Tuple[Optional[str], Optional[str]]:
    # Optional dependency: pycryptodome
    try:
        if algo == "MD2":
            from Crypto.Hash import MD2

            return MD2.new(data=data).hexdigest(), None
        if algo == "MD4":
            from Crypto.Hash import MD4

            return MD4.new(data=data).hexdigest(), None
        if algo == "WHIRLPOOL":
            # Some builds don't ship Whirlpool; attempt dynamic import.
            # Common names seen in the wild: Crypto.Hash.WHIRLPOOL or Crypto.Hash.Whirlpool
            for mod_name in ("Crypto.Hash.WHIRLPOOL", "Crypto.Hash.Whirlpool"):
                try:
                    mod = importlib.import_module(mod_name)
                    new = getattr(mod, "new", None)
                    if callable(new):
                        return new(data=data).hexdigest(), None
                except Exception:
                    continue

            return None, "whirlpool hash not available in pycryptodome"
        if algo == "RIPEMD160":
            from Crypto.Hash import RIPEMD

            return RIPEMD.new(data=data).hexdigest(), None
    except Exception as e:
        return None, str(e)

    return None, None


def compute_digests(
    *,
    raw_input: str,
    input_format: str,
    algorithms: Iterable[str],
) -> Dict[str, DigestResult]:
    algs = [str(a).strip() for a in algorithms if str(a).strip()]
    if not algs:
        return {"error": DigestResult(ok=False, error="no algorithms selected")}

    data, err = decode_input(raw_input, input_format=input_format)
    if err or data is None:
        return {"error": DigestResult(ok=False, error=err or "invalid input")}

    out: Dict[str, DigestResult] = {}

    for label in algs:
        key = label
        norm = label.strip().upper().replace("_", "-")

        # NTLM is MD4(UTF-16LE(password))
        if norm == "NTLM":
            if (input_format or "text").strip().lower() != "text":
                out[key] = DigestResult(ok=False, error="NTLM expects input_format=text (password string)")
                continue
            try:
                from Crypto.Hash import MD4

                pw = raw_input.encode("utf-16le", errors="replace")
                out[key] = DigestResult(ok=True, hex=MD4.new(data=pw).hexdigest(), note="NTLM = MD4(UTF-16LE(password))")
            except Exception as e:
                out[key] = DigestResult(ok=False, error=f"NTLM failed: {e}")
            continue

        # Checksums
        if norm == "CRC32":
            v = binascii.crc32(data) & 0xFFFFFFFF
            out[key] = DigestResult(ok=True, hex=f"{v:08x}")
            continue

        if norm == "ADLER32":
            import zlib

            v = zlib.adler32(data) & 0xFFFFFFFF
            out[key] = DigestResult(ok=True, hex=f"{v:08x}")
            continue

        if norm == "CRC16":
            v = _crc16_ibm(data)
            out[key] = DigestResult(ok=True, hex=f"{v:04x}", note="CRC16-IBM/ARC")
            continue

        # Unsupported (not readily available in stdlib/pycryptodome)
        if norm in {"MD6-128", "MD6-256", "MD6-512", "RIPEMD-128", "RIPEMD-256", "RIPEMD-320"}:
            out[key] = DigestResult(ok=False, error="unsupported in this build")
            continue

        # RIPEMD naming normalization
        if norm in {"RIPEMD-160", "RIPEMD160"}:
            hx, e = _try_crypto_hash("RIPEMD160", data)
            if hx:
                out[key] = DigestResult(ok=True, hex=hx)
            else:
                out[key] = DigestResult(ok=False, error=("pycryptodome required" if e is None else e))
            continue

        if norm == "WHIRLPOOL":
            # Prefer OpenSSL-backed hashlib if present.
            try:
                out[key] = DigestResult(ok=True, hex=_hashlib_hex("whirlpool", data))
                continue
            except Exception:
                pass

            hx, e = _try_crypto_hash("WHIRLPOOL", data)
            if hx:
                out[key] = DigestResult(ok=True, hex=hx)
            else:
                out[key] = DigestResult(
                    ok=False,
                    error=(
                        "unsupported in this environment (no hashlib whirlpool; pycryptodome lacks it). "
                        "Install build tools (gcc) and a Whirlpool implementation, or use a Python/OpenSSL build that exposes 'whirlpool' in hashlib."
                    ),
                    note=e,
                )
            continue

        # MD family
        if norm == "MD2":
            hx, e = _try_crypto_hash("MD2", data)
            if hx:
                out[key] = DigestResult(ok=True, hex=hx)
            else:
                out[key] = DigestResult(ok=False, error=("pycryptodome required" if e is None else e))
            continue

        if norm == "MD4":
            hx, e = _try_crypto_hash("MD4", data)
            if hx:
                out[key] = DigestResult(ok=True, hex=hx)
            else:
                out[key] = DigestResult(ok=False, error=("pycryptodome required" if e is None else e))
            continue

        if norm == "MD5":
            out[key] = DigestResult(ok=True, hex=hashlib.md5(data).hexdigest())
            continue

        # SHA family
        if norm in {"SHA1", "SHA-1"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha1(data).hexdigest())
            continue

        if norm in {"SHA-224", "SHA224"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha224(data).hexdigest())
            continue

        if norm in {"SHA-256", "SHA256"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha256(data).hexdigest())
            continue

        if norm in {"SHA-384", "SHA384"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha384(data).hexdigest())
            continue

        if norm in {"SHA-512", "SHA512"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha512(data).hexdigest())
            continue

        if norm in {"SHA3-224", "SHA3_224"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha3_224(data).hexdigest())
            continue

        if norm in {"SHA3-256", "SHA3_256"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha3_256(data).hexdigest())
            continue

        if norm in {"SHA3-384", "SHA3_384"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha3_384(data).hexdigest())
            continue

        if norm in {"SHA3-512", "SHA3_512"}:
            out[key] = DigestResult(ok=True, hex=hashlib.sha3_512(data).hexdigest())
            continue

        out[key] = DigestResult(ok=False, error="unknown algorithm")

    return out
