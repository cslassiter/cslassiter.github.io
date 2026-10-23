#!/usr/bin/env python3
"""
encrypt_jester.py -- put a short video, a picture, or a text note behind the
password gate at https://cslassiter.github.io/rr/

How the gate works
------------------
The page ../rr/index.html decrypts in the browser with Web Crypto:
  * PBKDF2-HMAC-SHA256 (600,000 iterations, random 16-byte salt) turns the
    password into a 256-bit key;
  * AES-256-GCM (random 12-byte nonce) encrypts the content, so a wrong
    password simply fails to decrypt -- there is no stored password hash.
Content up to about 1 MB (encrypted) is embedded in index.html; anything
larger is written next to it as rr/payload-<hash>.bin, which the page
downloads and decrypts. The scripts never write the password anywhere: it
comes from the JESTER_PASSPHRASE environment variable if set, otherwise a
hidden prompt. The encrypted file is public, so a short password can be
guessed at offline; a longer passphrase is safer.

Usage (run from anywhere; the page path defaults to ../rr/index.html)
-------------------------------------------------------------------------
  python encrypt_jester.py C:\\path\\to\\clip.mp4
  python encrypt_jester.py C:\\path\\to\\clip.mp4 --caption "A line under it"
  python encrypt_jester.py C:\\path\\to\\picture.jpg
  python encrypt_jester.py --text "Nothing here yet."      # a text note instead
  python encrypt_jester.py --verify                         # decrypt what's in the page, report
  python encrypt_jester.py --verify --extract C:\\Users\\lassiter\\Videos\\check.mp4
      # ...and write the content to a file -- always somewhere OUTSIDE the site
      # folder; the script refuses a path inside the repo, where it could be committed.

Videos are embedded as they are (there is no ffmpeg here to re-encode). An
MP4 with H.264 video and AAC audio plays in every browser; the script reports
the codecs it finds and warns about HEVC, which Chrome, Firefox and Android
may refuse. Export a small, "most compatible" version from the phone or
Photos first. GitHub refuses files over 100 MB, so the limit here is 95 MB.

Pictures are re-encoded with Pillow when it is installed: EXIF metadata
(including any GPS location) is stripped, phone orientation is applied, and
the longest side is capped at --max-side (default 1600 px; 0 = keep size).
Use --keep-original to embed the file bytes untouched. Animated GIFs are
always kept as-is.

Afterwards, from the site repo:
  git add rr
  git commit -m "Update jester"
  git push
The page is live about a minute later. The R script encrypt_jester.R does the
same job (without the Pillow re-encoding step).
"""

import argparse
import base64
import getpass
import hashlib
import io
import json
import mimetypes
import os
import re
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover
    sys.exit("The 'cryptography' package is required:  python -m pip install cryptography")

ITERS = 600_000
INLINE_MAX = 1_000_000      # encrypted bytes; above this the content goes to a sidecar .bin
WARN_SIZE = 30_000_000      # bytes; warn that the page will be slow on phones
GITHUB_MAX = 95_000_000     # GitHub rejects files over 100 MB
HERE = Path(__file__).resolve().parent
DEFAULT_HTML = HERE.parent / "rr" / "index.html"
PAYLOAD_RE = re.compile(r'(<script id="payload" type="application/json">)(.*?)(</script>)', re.S)
SIDECAR_GLOB = "payload-*.bin"
VIDEO_MIME = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
BROWSER_SHY = {"image/heic", "image/heif", "image/tiff"}   # Safari-only image formats
NEXT_STEPS = 'Next, from the site repo:\n  git add rr\n  git commit -m "Update jester"\n  git push'


# ---------------------------------------------------------------- crypto ----

def _console_password(prompt: str) -> str:
    pw = getpass.getpass(prompt)
    if sys.platform == "win32":
        # The Windows console hands over UTF-16 units one at a time; rejoin emoji etc.
        try:
            pw = pw.encode("utf-16", "surrogatepass").decode("utf-16")
        except UnicodeDecodeError:
            sys.exit("The password contains a character the console could not pass through; "
                     "set JESTER_PASSPHRASE instead.")
    return pw


def get_passphrase(confirm: bool) -> str:
    pw = os.environ.get("JESTER_PASSPHRASE")
    if pw:
        return pw
    pw = _console_password("Password for the page (input hidden): ")
    if not pw:
        sys.exit("Empty password; nothing done.")
    if confirm and pw != _console_password("Confirm password: "):
        sys.exit("Passwords do not match; nothing done.")
    return pw


def derive_key(pw: str, salt: bytes, iters: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, iters, dklen=32)


def encrypt(plaintext: bytes, pw: str):
    """Return (meta dict without the ciphertext, ciphertext || 16-byte GCM tag)."""
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(derive_key(pw, salt, ITERS)).encrypt(iv, plaintext, None)
    b64 = lambda x: base64.b64encode(x).decode("ascii")
    meta = {"v": 2, "kdf": "PBKDF2-HMAC-SHA256", "iters": ITERS, "cipher": "AES-256-GCM",
            "salt": b64(salt), "iv": b64(iv)}
    return meta, ct


def decrypt(payload: dict, ct: bytes, pw: str) -> bytes:
    d = base64.b64decode
    key = derive_key(pw, d(payload["salt"]), int(payload["iters"]))
    return AESGCM(key).decrypt(d(payload["iv"]), ct, None)


# -------------------------------------------------------------- envelope ----
# Plaintext = one JSON header line + "\n" + content bytes. The browser reads
# header.type ("video", "image" or "text"), header.mime, header.caption.

def pack(header: dict, body: bytes) -> bytes:
    line = json.dumps(header, ensure_ascii=False, separators=(",", ":"))
    assert "\n" not in line
    return line.encode("utf-8") + b"\n" + body


def unpack(plain: bytes):
    i = plain.index(b"\n")
    return json.loads(plain[:i].decode("utf-8")), plain[i + 1:]


# -------------------------------------------------------------- content ----

def kind_of(path: Path):
    ext = path.suffix.lower()
    if ext in VIDEO_MIME:
        return "video", VIDEO_MIME[ext]
    mime = mimetypes.guess_type(path.name)[0] or ""
    if mime.startswith("video/"):
        return "video", mime
    if mime.startswith("image/"):
        return "image", mime
    sys.exit(f"Unrecognised file type: {path.name} (use mp4/mov/webm, or jpg/png/gif/webp)")


def sniff_video(data: bytes, mime: str) -> str:
    """Report the codecs in the file and warn about ones browsers dislike.

    MP4/MOV sample entries look like <fourcc> + six zero bytes + 00 01 (data
    reference index), which keeps chance matches in the compressed data out.
    """
    iso = ("avc1", "avc3", "hvc1", "hev1", "dvh1", "dvhe", "av01", "vp09", "mp4a")
    found = [t for t in iso if re.search(re.escape(t.encode()) + rb"\x00{6}\x00\x01", data)]
    found += [t for t in ("V_VP8", "V_VP9", "V_AV1", "A_OPUS", "A_VORBIS") if t.encode() in data]
    notes = []
    if {"hvc1", "hev1", "dvh1", "dvhe"} & set(found) and not {"avc1", "avc3"} & set(found):
        notes.append("HEVC video: Chrome/Firefox on Windows and many Android phones will not play it. "
                     "Export as H.264 (iPhone: Settings > Camera > Formats > Most Compatible, "
                     "or share with the 'compatible' option).")
    if not found:
        notes.append("could not identify the codec; test the page in Firefox and Chrome")
    return ("codecs: " + ", ".join(found) if found else "codecs: unknown") + ("; " + " ".join(notes) if notes else "")


def prepare_video(path: Path):
    data = path.read_bytes()
    mime = kind_of(path)[1]
    return data, mime, f"video {path.name} ({len(data)/1e6:.1f} MB; {sniff_video(data, mime)})"


def prepare_image(path: Path, max_side: int, keep_original: bool):
    """Return (bytes, mime, note). Re-encodes via Pillow unless told not to."""
    data = path.read_bytes()
    mime = kind_of(path)[1]
    if keep_original:
        if mime in BROWSER_SHY:
            sys.exit(f"{path.name}: browsers other than Safari cannot show {mime}; export it as JPEG first.")
        return data, mime, "embedded the original file bytes (no resize, metadata kept)"
    try:
        from PIL import Image, ImageOps
    except ImportError:
        if mime in BROWSER_SHY:
            sys.exit(f"{path.name}: browsers other than Safari cannot show {mime}; export it as JPEG first.")
        return data, mime, "Pillow not installed: embedded the original bytes (no resize, metadata kept)"
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:  # HEIC etc.
        sys.exit(f"Pillow cannot read {path.name} ({e}). Export it as JPEG or PNG first.")
    fmt = (im.format or "").upper()
    if fmt == "GIF":
        return data, "image/gif", "GIF kept as-is (animation preserved, no resize)"
    im = ImageOps.exif_transpose(im)
    w0, h0 = im.size
    if max_side and max(w0, h0) > max_side:
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    if fmt == "PNG" or has_alpha:
        im.save(out, "PNG", optimize=True)
        mime = "image/png"
    else:
        im.convert("RGB").save(out, "JPEG", quality=88, optimize=True, progressive=True, comment=b"")
        mime = "image/jpeg"
    note = f"{fmt or 'image'} {w0}x{h0} -> {mime.split('/')[1].upper()} {im.size[0]}x{im.size[1]}, metadata stripped"
    return out.getvalue(), mime, note


# ------------------------------------------------------------------ page ----

def read_payload(html_path: Path):
    """Return (payload dict, ciphertext bytes) from the page and its sidecar if any."""
    m = PAYLOAD_RE.search(html_path.read_text(encoding="utf-8"))
    if not m:
        sys.exit(f"No payload block found in {html_path}")
    raw = m.group(2).strip()
    if raw in ("", "{}"):
        sys.exit("The page has nothing behind the gate yet; run the script with a file or --text first.")
    try:
        payload = json.loads(raw)
    except ValueError:
        sys.exit(f"The payload block in {html_path} is not valid JSON.")
    if not (payload.get("salt") and payload.get("iv") and (payload.get("ct") or payload.get("src"))):
        sys.exit("The page has nothing behind the gate yet; run the script with a file or --text first.")
    if payload.get("src"):
        side = html_path.parent / payload["src"]
        if not side.is_file():
            sys.exit(f"The page refers to {side.name}, which is missing next to it.")
        ct = side.read_bytes()
    else:
        ct = base64.b64decode(payload["ct"])
    return payload, ct


def write_payload(html_path: Path, meta: dict, ct: bytes) -> str:
    """Write the ciphertext inline or as a sidecar, update the page, then remove stale sidecars."""
    text = html_path.read_text(encoding="utf-8")
    if len(PAYLOAD_RE.findall(text)) != 1:
        sys.exit(f"Expected exactly one payload block in {html_path}")
    folder = html_path.parent
    payload = dict(meta)
    new_name = None
    if len(ct) > INLINE_MAX:
        new_name = f"payload-{hashlib.sha256(ct).hexdigest()[:12]}.bin"
        (folder / new_name).write_bytes(ct)
        payload["src"] = new_name
        payload["bytes"] = len(ct)
        where = f"{html_path} + {new_name} ({len(ct):,} bytes)"
    else:
        payload["ct"] = base64.b64encode(ct).decode("ascii")
        where = f"{html_path} (inline)"
    blob = json.dumps(payload, separators=(",", ":"))
    assert "</script" not in blob  # base64 + fixed keys cannot contain '<'
    new = PAYLOAD_RE.sub(lambda m: m.group(1) + blob + m.group(3), text, count=1)
    html_path.write_text(new, encoding="utf-8", newline="\n")
    for old in folder.glob(SIDECAR_GLOB):      # only after the page points at the new one
        if old.name != new_name:
            old.unlink()
    return where


def repo_root(path: Path):
    """The git working tree containing path, or None."""
    for p in [path.resolve()] + list(path.resolve().parents):
        if (p / ".git").exists():
            return p
    return None


def check_extract_target(extract: str, html_path: Path) -> Path:
    out = Path(extract).resolve()
    if out.is_dir():
        sys.exit(f"--extract needs a file name, not a folder: {out}")
    if not out.parent.is_dir():
        sys.exit(f"Folder does not exist: {out.parent}")
    repo = repo_root(html_path)
    if repo and (out == repo or repo in out.parents):
        sys.exit(f"Refusing to write decrypted content inside the site repo ({repo}); "
                 f"it could be committed and published. Choose a path outside it.")
    return out


# ------------------------------------------------------------------ main ----

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="video (mp4/mov/webm) or picture (jpg/png/gif/webp) to encrypt")
    ap.add_argument("--text", help="encrypt this text note instead of a file")
    ap.add_argument("--caption", help="caption shown under the video or picture")
    ap.add_argument("--max-side", type=int, default=1600, help="pictures: cap the longest side in px (0 = keep)")
    ap.add_argument("--keep-original", action="store_true", help="pictures: embed file bytes untouched")
    ap.add_argument("--verify", action="store_true", help="decrypt the current payload and report")
    ap.add_argument("--extract", help="with --verify: write the decrypted content to this file (outside the repo)")
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML, help=f"page to update (default {DEFAULT_HTML})")
    a = ap.parse_args(argv)

    modes = sum(bool(x) for x in (a.file, a.text, a.verify))
    if modes != 1:
        ap.error("give exactly one of: a file, --text, or --verify")
    if not a.html.is_file():
        sys.exit(f"Page not found: {a.html}")

    if a.verify:
        out = check_extract_target(a.extract, a.html) if a.extract else None
        payload, ct = read_payload(a.html)
        pw = get_passphrase(confirm=False)
        try:
            header, body = unpack(decrypt(payload, ct, pw))
        except Exception:
            sys.exit("Decryption failed: wrong password, or the payload is damaged.")
        print(f"OK: {header.get('type')} {header.get('mime')} ({len(body):,} bytes; "
              f"{'sidecar ' + payload['src'] if payload.get('src') else 'inline'})"
              + (f"  caption: {header['caption']!r}" if header.get("caption") else ""))
        if out:
            out.write_bytes(body)
            print(f"wrote {out}")
        return

    if a.text:
        header = {"type": "text", "mime": "text/plain"}
        body = a.text.encode("utf-8")
        note = f"text note ({len(body)} bytes)"
    else:
        path = Path(a.file)
        if not path.is_file():
            sys.exit(f"Not a file: {path}")
        kind = kind_of(path)[0]
        if kind == "video":
            body, mime, note = prepare_video(path)
        else:
            body, mime, note = prepare_image(path, a.max_side, a.keep_original)
        header = {"type": kind, "mime": mime, "name": path.name}
        if a.caption:
            header["caption"] = a.caption
    if len(body) > GITHUB_MAX:
        sys.exit(f"The content is {len(body)/1e6:.0f} MB; GitHub Pages cannot host files over 100 MB. "
                 f"Trim it or export a smaller version.")

    pw = get_passphrase(confirm=True)
    meta, ct = encrypt(pack(header, body), pw)
    # Round-trip check before touching the page.
    h2, b2 = unpack(decrypt(meta, ct, pw))
    assert h2 == header and b2 == body, "internal round-trip check failed"
    where = write_payload(a.html, meta, ct)
    print(f"Encrypted {note}\n  -> {where}")
    if len(ct) > WARN_SIZE:
        print(f"Warning: {len(ct)/1e6:.0f} MB is a lot to download and decrypt on a phone; "
              f"a shorter or smaller export would be kinder.")
    print(NEXT_STEPS)


if __name__ == "__main__":
    main()
