# Jester page tools

`https://cslassiter.github.io/jester/` is a password-gated page. Everything
behind the gate is encrypted; the visitor's browser decrypts it after the
password is typed (Web Crypto: PBKDF2-HMAC-SHA256 with 600,000 rounds, then
AES-256-GCM). There is no server and no stored password; a wrong password
simply fails to decrypt, and there is nothing readable at a direct URL or in
this repo. The scripts never write the password anywhere.

Two honest limits. The encrypted file is public, so anyone who downloads it
can guess passwords at it offline for as long as they like; a long passphrase
(several words) is much safer than a short word. And this repo is public:
the site never serves this folder, but it is browsable on github.com, so
never put the password or anything private in here.

Small content (a text note, a picture) is embedded in `jester/index.html`.
Anything larger, such as a video, is stored next to it as
`jester/payload-<hash>.bin`, which the page downloads and decrypts.

## Put the video up

1. Export a small, compatible version from the phone or Photos: MP4 with
   H.264 video (iPhone: Settings > Camera > Formats > Most Compatible, or
   share with the "compatible" option). A minute of 1080p is roughly 60 MB;
   720p or a shorter clip is much kinder to phones. GitHub refuses files over
   100 MB. Save it somewhere outside the site folder, e.g.
   `C:\Users\lassiter\Videos\bird.mp4`.
2. In a terminal:

   ```
   cd C:\Users\lassiter\vscode101\cslassiter.github.io
   python _jester_tools\encrypt_jester.py C:\Users\lassiter\Videos\bird.mp4
   ```

   It asks for the password twice (typing is hidden), reports the codecs it
   found, and warns if the clip is HEVC, which some browsers refuse. Add
   `--caption "..."` for a line under the video. Nothing is re-encoded;
   the file goes in as it is.
3. Test locally. A page with a separate payload file must be served, not opened
   as a file:

   ```
   python -m http.server 8000 --bind 127.0.0.1
   ```

   then open http://localhost:8000/jester/ in Firefox and enter the password.
   (A page with only a note or a picture inside can be opened directly as a
   file. A phone on the same Wi-Fi cannot test it this way: browsers only
   allow the decryption code over https or localhost.)
4. Publish:

   ```
   git add jester
   git commit -m "Update jester"
   git push
   ```

   Live about a minute later at https://cslassiter.github.io/jester/. A
   browser that visited before may keep the old page for up to ten minutes;
   if it says it couldn't load the content right after an update, reload.
   A push warning about a file over 50 MB is expected and harmless below 100 MB.

## Other things

- A picture instead: `python _jester_tools\encrypt_jester.py C:\path\to\bird.jpg`.
  Pictures are rotated the way the phone meant, resized to at most 1600 px,
  and stripped of metadata (including GPS) before encryption.
- A text note instead: `python _jester_tools\encrypt_jester.py --text "Back soon."`
- Change the password: run the script again with the same file and type the
  new password. Old versions stay in the repo's git history (still encrypted
  under the password they were made with), so a new password only protects
  the newly published content.
- See what is currently in the page:
  `python _jester_tools\encrypt_jester.py --verify`
  To get the content back out, add `--extract` with a path OUTSIDE the site
  folder, e.g. `--extract C:\Users\lassiter\Videos\check.mp4`; anything left
  inside the repo can be committed and published, and the script refuses
  such a path.
- Skip the prompt by putting the password in the environment first. In
  PowerShell type `$env:JESTER_PASSPHRASE = Read-Host "Password"` (the typed
  value is not recorded in the command history, unlike a literal on the
  command line) and `Remove-Item Env:JESTER_PASSPHRASE` when done.
- Repo size: every swap adds the full encrypted file to the public repo's
  history for good, so keep swaps few and clips small. If it ever matters,
  `git filter-repo --path-glob 'jester/payload-*.bin' --invert-paths` and a
  force-push remove them.
- `encrypt_jester.R` is the R twin, same commands via `Rscript`. It embeds
  files as they are (no picture resizing) and takes a minute or more per run
  because the key derivation and the authentication tag are computed in R.
  Under `Rscript` its password prompt may echo what you type; prefer the
  environment variable there, and use plain ASCII characters in the password
  if you type it at an R prompt on Windows.

## Format notes

- `<script id="payload" type="application/json">` in `jester/index.html` holds
  `{v, kdf, iters, cipher, salt, iv}` plus either `ct` (base64 ciphertext,
  inline) or `src` + `bytes` (the sidecar file's name and size). The
  ciphertext ends with the 16-byte GCM tag, as Web Crypto expects. The scripts
  delete any older `payload-*.bin` in the folder once the page points at the
  new one.
- The plaintext is one JSON header line (`type` = video, image or text;
  `mime`; `name`; optional `caption`), a newline, then the content bytes.
- Same construction as the `formal-logic/` gate (built by
  `jeffrey_logic/site_build/build_site.py`), with 600,000 rounds instead of
  200,000. The R script computes the GCM tag itself (GHASH per NIST SP
  800-38D) because the R `openssl` package's `aes_gcm_encrypt()` drops it;
  the tags were checked byte-for-byte against Python's `cryptography`.
