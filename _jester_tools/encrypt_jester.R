#!/usr/bin/env Rscript
# encrypt_jester.R -- R twin of encrypt_jester.py: put a short video, a picture,
# or a text note behind the password gate at https://cslassiter.github.io/rr/
#
# Same payload format and the same command line as the Python script:
#   Rscript encrypt_jester.R C:\path\to\clip.mp4
#   Rscript encrypt_jester.R C:\path\to\clip.mp4 --caption "A line under it"
#   Rscript encrypt_jester.R C:\path\to\picture.jpg
#   Rscript encrypt_jester.R --text "Nothing here yet."
#   Rscript encrypt_jester.R --verify
#   Rscript encrypt_jester.R --verify --extract C:\Users\lassiter\Videos\check.mp4
#       (always a path OUTSIDE the site folder; a path inside the repo is refused)
#   (optional: --html path\to\index.html)
#
# The password comes from the JESTER_PASSPHRASE environment variable if set,
# otherwise a prompt: on Windows a small dialog (hidden typing); if that is not
# available the script falls back to a plain console prompt and SAYS SO, since
# typing is then visible. Use plain ASCII characters if you type it at that
# console prompt: Windows consoles hand non-ASCII characters to R in a code
# page the browser would not reproduce. The script never writes the password.
#
# Content up to about 1 MB (encrypted) is embedded in index.html; anything
# larger is written next to it as rr/payload-<hash>.bin for the page to fetch.
#
# Differences from the Python script:
#   * No image re-encoding: file bytes are embedded as they are (no resize,
#     EXIF/GPS metadata kept). Resize and strip beforehand, or use the Python script.
#   * The key derivation (600,000 PBKDF2 rounds) runs in an R loop and takes
#     about a minute; the authentication tag over a video adds a minute or two
#     more. The Python/browser versions take well under a second.
#   * The AES-GCM authentication tag is computed here in R (GHASH over GF(2^128)),
#     because the openssl package's aes_gcm_encrypt() does not return it. The
#     construction is NIST SP 800-38D; it is verified against Python and Web Crypto.

suppressPackageStartupMessages({
  library(openssl)
  library(jsonlite)
})

ITERS <- 600000L
INLINE_MAX <- 1e6        # encrypted bytes; above this the content goes to a sidecar .bin
WARN_SIZE <- 30e6
GITHUB_MAX <- 95e6
NEXT_STEPS <- 'Next, from the site repo:\n  git add rr\n  git commit -m "Update jester"\n  git push\n'

script_dir <- function() {
  f <- sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE))
  if (length(f)) dirname(normalizePath(f[1], winslash = "/")) else getwd()
}
DEFAULT_HTML <- file.path(dirname(script_dir()), "rr", "index.html")

## ---- password ---------------------------------------------------------------

get_passphrase <- function(confirm) {
  pw <- Sys.getenv("JESTER_PASSPHRASE", unset = "")
  if (nzchar(pw)) return(pw)
  con <- NULL
  on.exit(if (!is.null(con)) close(con))
  ask <- function(prompt) {
    if (requireNamespace("askpass", quietly = TRUE)) {
      # Rscript is not "interactive", which makes askpass give up; its Windows dialog works anyway.
      old <- options(rlib_interactive = (.Platform$OS.type == "windows"))
      on.exit(options(old), add = TRUE)
      r <- tryCatch(askpass::askpass(prompt), error = function(e) NULL)
      if (!is.null(r) && nzchar(r)) return(r)
    }
    if (is.null(con)) con <<- file("stdin", "r")
    cat(prompt, "(typing is visible here)\n")
    r <- readLines(con, n = 1, warn = FALSE)
    if (length(r)) r else ""
  }
  pw <- ask("Password for the page:")
  if (!nzchar(pw)) stop("Empty password; nothing done.", call. = FALSE)
  if (confirm && !identical(pw, ask("Confirm password:")))
    stop("Passwords do not match; nothing done.", call. = FALSE)
  pw
}

## ---- PBKDF2-HMAC-SHA256 (one 32-byte block) ---------------------------------

pbkdf2_sha256 <- function(pw_raw, salt, iters, dklen = 32L) {
  stopifnot(dklen <= 32L, length(pw_raw) > 0L)
  u <- sha256(c(salt, as.raw(c(0L, 0L, 0L, 1L))), key = pw_raw)
  t <- as.raw(u)
  for (i in seq_len(iters - 1L)) {
    u <- sha256(u, key = pw_raw)
    t <- xor(t, u)
  }
  as.raw(t)[seq_len(dklen)]
}

## ---- AES-256-GCM with the tag computed here (NIST SP 800-38D) ---------------

# E_K(block): AES-CTR of sixteen zero bytes with the block as the counter.
aes_block <- function(key, block16) as.raw(aes_ctr_encrypt(raw(16L), key, iv = block16))

# 128-bit field elements are integer vectors of 16 bytes (0..255), byte 1 leftmost.
# Multiply by x: shift right one bit; if the bit shifted out was 1, xor R = 0xE1 || 0^120.
gf_mul_x <- function(v) {
  carry <- bitwShiftL(bitwAnd(c(0L, v[-16L]), 1L), 7L)
  out <- bitwOr(bitwShiftR(v, 1L), carry)
  if (bitwAnd(v[16L], 1L) == 1L) out[1L] <- bitwXor(out[1L], 0xE1L)
  out
}

# Byte-wise multiplication tables: tbl[[i]][b + 1, ] = (b placed in byte i) * H.
ghash_tables <- function(H) {
  pow <- vector("list", 128L)            # pow[[k + 1]] = H * x^k
  pow[[1L]] <- H
  for (k in 2:128) pow[[k]] <- gf_mul_x(pow[[k - 1L]])
  tbl <- vector("list", 16L)
  for (i in 1:16) {
    m <- matrix(0L, 256L, 16L)
    for (b in 1:255) {
      hb <- as.integer(floor(log2(b)))   # highest set bit of b has value 2^hb
      j <- 7L - hb                       # ... which is bit position j from the byte's MSB
      m[b + 1L, ] <- bitwXor(m[b - 2L^hb + 1L, ], pow[[8L * (i - 1L) + j + 1L]])
    }
    tbl[[i]] <- m
  }
  tbl
}

# GHASH_H over data (raw, a multiple of 16 bytes): Y_i = (Y_{i-1} xor X_i) * H.
ghash <- function(tbl, data) {
  M <- matrix(as.integer(data), nrow = 16L)
  Y <- integer(16L)
  for (jj in seq_len(ncol(M))) {
    Y <- bitwXor(Y, M[, jj])
    Z <- tbl[[1L]][Y[1L] + 1L, ]
    for (i in 2:16) Z <- bitwXor(Z, tbl[[i]][Y[i] + 1L, ])
    Y <- Z
  }
  Y
}

int64_be <- function(n) {
  out <- raw(8L)
  for (i in 8:1) { out[i] <- as.raw(n %% 256); n <- n %/% 256 }
  out
}

# Tag = E_K(J0) xor GHASH_H(C || pad || [len(A) = 0]_64 || [len(C) in bits]_64), J0 = IV || 0^31 || 1.
gcm_tag <- function(key, iv, ct) {
  tbl <- ghash_tables(as.integer(aes_block(key, raw(16L))))
  ej0 <- as.integer(aes_block(key, c(iv, as.raw(c(0L, 0L, 0L, 1L)))))
  pad <- (16L - length(ct) %% 16L) %% 16L
  s <- ghash(tbl, c(ct, raw(pad), raw(8L), int64_be(length(ct) * 8)))
  as.raw(bitwXor(ej0, s))
}

gcm_encrypt <- function(key, iv, plaintext) {
  ct <- as.raw(aes_gcm_encrypt(plaintext, key, iv))
  c(ct, gcm_tag(key, iv, ct))
}

gcm_decrypt <- function(key, iv, ct_tag) {
  n <- length(ct_tag)
  if (n < 16L) stop("ciphertext too short")
  ct <- ct_tag[seq_len(n - 16L)]
  tag <- ct_tag[(n - 15L):n]
  if (!identical(gcm_tag(key, iv, ct), tag)) stop("authentication failed")
  as.raw(aes_gcm_decrypt(ct, key, iv))
}

## ---- payload ---------------------------------------------------------------------

# Returns list(meta = fields without the ciphertext, ct = ciphertext || tag).
encrypt_payload <- function(plaintext, pw) {
  salt <- rand_bytes(16L); iv <- rand_bytes(12L)
  key <- pbkdf2_sha256(charToRaw(enc2utf8(pw)), salt, ITERS)
  ct_tag <- gcm_encrypt(key, iv, plaintext)
  if (!identical(as.raw(aes_gcm_decrypt(ct_tag[seq_len(length(ct_tag) - 16L)], key, iv)), plaintext))
    stop("internal round-trip check failed")
  list(meta = list(v = 2L, kdf = "PBKDF2-HMAC-SHA256", iters = ITERS, cipher = "AES-256-GCM",
                   salt = base64_encode(salt), iv = base64_encode(iv)),
       ct = ct_tag)
}

decrypt_payload <- function(payload, ct, pw) {
  key <- pbkdf2_sha256(charToRaw(enc2utf8(pw)), base64_decode(payload$salt), as.integer(payload$iters))
  gcm_decrypt(key, base64_decode(payload$iv), ct)
}

## ---- envelope: one JSON header line, "\n", content bytes ---------------------

pack <- function(header, body) {
  line <- as.character(toJSON(header, auto_unbox = TRUE))
  stopifnot(!grepl("\n", line, fixed = TRUE))
  c(charToRaw(enc2utf8(line)), as.raw(0x0a), body)
}

unpack <- function(plain) {
  nl <- which(plain == as.raw(0x0a))[1]
  if (is.na(nl)) stop("bad envelope")
  line <- rawToChar(plain[seq_len(nl - 1L)]); Encoding(line) <- "UTF-8"
  list(header = fromJSON(line), body = plain[-seq_len(nl)])
}

## ---- content ---------------------------------------------------------------------

VIDEO_MIME <- c(mp4 = "video/mp4", m4v = "video/mp4", mov = "video/quicktime", webm = "video/webm")
IMAGE_MIME <- c(jpg = "image/jpeg", jpeg = "image/jpeg", png = "image/png", gif = "image/gif",
                webp = "image/webp", avif = "image/avif", svg = "image/svg+xml", bmp = "image/bmp")

kind_of <- function(path) {
  ext <- tolower(tools::file_ext(path))
  if (ext %in% names(VIDEO_MIME)) return(list(kind = "video", mime = VIDEO_MIME[[ext]]))
  if (ext %in% names(IMAGE_MIME)) return(list(kind = "image", mime = IMAGE_MIME[[ext]]))
  stop("Unrecognised file type: ", basename(path), " (use mp4/mov/webm, or jpg/png/gif/webp)", call. = FALSE)
}

# MP4/MOV sample entries look like <fourcc> + six zero bytes + 00 01, which keeps
# chance matches in the compressed data out.
sniff_video <- function(data, mime) {
  iso <- c("avc1", "avc3", "hvc1", "hev1", "dvh1", "dvhe", "av01", "vp09", "mp4a")
  has_iso <- vapply(iso, function(t) length(grepRaw(c(charToRaw(t), raw(6L), as.raw(c(0L, 1L))), data, fixed = TRUE)) > 0L, logical(1))
  mkv <- c("V_VP8", "V_VP9", "V_AV1", "A_OPUS", "A_VORBIS")
  has_mkv <- vapply(mkv, function(t) length(grepRaw(t, data, fixed = TRUE)) > 0L, logical(1))
  found <- c(iso[has_iso], mkv[has_mkv])
  notes <- character(0)
  if (any(c("hvc1", "hev1", "dvh1", "dvhe") %in% found) && !any(c("avc1", "avc3") %in% found))
    notes <- c(notes, paste("HEVC video: Chrome/Firefox on Windows and many Android phones will not play it.",
                            "Export as H.264 (iPhone: Settings > Camera > Formats > Most Compatible,",
                            "or share with the 'compatible' option)."))
  if (!length(found)) notes <- c(notes, "could not identify the codec; test the page in Firefox and Chrome")
  paste0(if (length(found)) paste0("codecs: ", paste(found, collapse = ", ")) else "codecs: unknown",
         if (length(notes)) paste0("; ", paste(notes, collapse = " ")) else "")
}

## ---- the page ------------------------------------------------------------------

OPEN_TAG <- '<script id="payload" type="application/json">'

read_page <- function(path) {
  txt <- readChar(path, file.info(path)$size, useBytes = TRUE)
  Encoding(txt) <- "UTF-8"
  txt
}

split_page <- function(txt) {
  parts <- strsplit(txt, OPEN_TAG, fixed = TRUE)[[1]]
  if (length(parts) != 2L) stop("Expected exactly one payload block in the page")
  close_at <- regexpr("</script>", parts[2], fixed = TRUE)
  if (close_at < 0) stop("Payload block is not closed")
  list(before = paste0(parts[1], OPEN_TAG),
       json = substr(parts[2], 1L, close_at - 1L),
       after = substr(parts[2], close_at, nchar(parts[2])))   # substring()'s default end is only 1e6 chars
}

# Returns list(payload = fields, ct = ciphertext || tag) from the page and its sidecar if any.
read_payload <- function(path) {
  json <- trimws(split_page(read_page(path))$json)
  nothing <- "The page has nothing behind the gate yet; run the script with a file or --text first."
  if (json %in% c("", "{}")) stop(nothing, call. = FALSE)
  payload <- tryCatch(fromJSON(json), error = function(e) stop("The payload block in the page is not valid JSON.", call. = FALSE))
  has <- function(k) !is.null(payload[[k]]) && nzchar(payload[[k]])
  if (!(has("salt") && has("iv") && (has("ct") || has("src")))) stop(nothing, call. = FALSE)
  if (has("src")) {
    side <- file.path(dirname(path), payload$src)
    if (!file.exists(side)) stop("The page refers to ", basename(side), ", which is missing next to it.", call. = FALSE)
    ct <- readBin(side, "raw", file.info(side)$size)
  } else {
    ct <- base64_decode(payload$ct)
  }
  list(payload = payload, ct = ct)
}

write_payload <- function(path, meta, ct) {
  p <- split_page(read_page(path))
  dir <- dirname(path)
  payload <- meta
  payload$iters <- as.integer(payload$iters)
  new_name <- NULL
  if (length(ct) > INLINE_MAX) {
    new_name <- paste0("payload-", substr(paste(sprintf("%02x", as.integer(sha256(ct))), collapse = ""), 1L, 12L), ".bin")
    writeBin(ct, file.path(dir, new_name))
    payload$src <- new_name
    payload$bytes <- length(ct)
    where <- sprintf("%s + %s (%s bytes)", path, new_name, format(length(ct), big.mark = ","))
  } else {
    payload$ct <- base64_encode(ct)
    where <- sprintf("%s (inline)", path)
  }
  json <- as.character(toJSON(payload, auto_unbox = TRUE))
  stopifnot(!grepl("</script", json, fixed = TRUE))
  out <- paste0(p$before, json, p$after)
  writeBin(charToRaw(out), path)   # exact bytes, whatever the locale
  old <- list.files(dir, pattern = "^payload-[0-9a-f]+\\.bin$", full.names = TRUE)
  old <- old[basename(old) != if (is.null(new_name)) "" else new_name]
  if (length(old)) file.remove(old)   # only after the page points at the new one
  where
}

repo_root <- function(path) {
  p <- normalizePath(path, winslash = "/", mustWork = FALSE)
  repeat {
    if (file.exists(file.path(p, ".git"))) return(p)
    parent <- dirname(p)
    if (identical(parent, p)) return(NULL)
    p <- parent
  }
}

check_extract_target <- function(extract, html) {
  if (dir.exists(extract)) stop("--extract needs a file name, not a folder: ", extract, call. = FALSE)
  if (!dir.exists(dirname(extract))) stop("Folder does not exist: ", dirname(extract), call. = FALSE)
  out <- file.path(normalizePath(dirname(extract), winslash = "/"), basename(extract))
  repo <- repo_root(dirname(html))
  if (!is.null(repo) && startsWith(tolower(paste0(out, "/")), tolower(paste0(repo, "/"))))
    stop("Refusing to write decrypted content inside the site repo (", repo,
         "); it could be committed and published. Choose a path outside it.", call. = FALSE)
  out
}

## ---- command line --------------------------------------------------------------

args <- commandArgs(trailingOnly = TRUE)
opt <- list(file = NULL, text = NULL, caption = NULL, verify = FALSE, extract = NULL, html = DEFAULT_HTML)
i <- 1L
take <- function(flag) {
  if (i + 1L > length(args)) stop("Missing value after ", flag, call. = FALSE)
  i <<- i + 1L
  args[i]
}
while (i <= length(args)) {
  a <- args[i]
  if (a == "--text") opt$text <- take(a)
  else if (a == "--caption") opt$caption <- take(a)
  else if (a == "--verify") opt$verify <- TRUE
  else if (a == "--extract") opt$extract <- take(a)
  else if (a == "--html") opt$html <- take(a)
  else if (a == "--max-side") { take(a); message("Note: --max-side is ignored by the R script (no re-encoding).") }
  else if (a == "--keep-original") message("Note: the R script always embeds the file bytes as they are.")
  else if (startsWith(a, "--")) stop("Unknown option: ", a, call. = FALSE)
  else if (is.null(opt$file)) opt$file <- a
  else stop("Unexpected argument: ", a, call. = FALSE)
  i <- i + 1L
}

modes <- sum(!is.null(opt$file), !is.null(opt$text), opt$verify)
if (modes != 1L) stop("Give exactly one of: a file, --text, or --verify", call. = FALSE)
if (!file.exists(opt$html) || dir.exists(opt$html)) stop("Page not found: ", opt$html, call. = FALSE)

if (opt$verify) {
  out <- if (!is.null(opt$extract)) check_extract_target(opt$extract, opt$html) else NULL
  pg <- read_payload(opt$html)
  pw <- get_passphrase(confirm = FALSE)
  message("Deriving the key (", format(ITERS, big.mark = ","), " PBKDF2 rounds in R; about a minute)...")
  res <- tryCatch(unpack(decrypt_payload(pg$payload, pg$ct, pw)), error = function(e) NULL)
  if (is.null(res)) stop("Decryption failed: wrong password, or the payload is damaged.", call. = FALSE)
  h <- res$header
  cat(sprintf("OK: %s %s (%s bytes; %s)%s\n", h$type, h$mime, format(length(res$body), big.mark = ","),
              if (!is.null(pg$payload$src)) paste("sidecar", pg$payload$src) else "inline",
              if (!is.null(h$caption)) paste0("  caption: ", h$caption) else ""))
  if (!is.null(out)) { writeBin(res$body, out); cat("wrote", out, "\n") }
  quit(status = 0)
}

if (!is.null(opt$text)) {
  header <- list(type = "text", mime = "text/plain")
  body <- charToRaw(enc2utf8(opt$text))
  note <- sprintf("text note (%d bytes)", length(body))
} else {
  if (!file.exists(opt$file) || dir.exists(opt$file)) stop("Not a file: ", opt$file, call. = FALSE)
  k <- kind_of(opt$file)
  body <- readBin(opt$file, "raw", file.info(opt$file)$size)
  header <- list(type = k$kind, mime = k$mime, name = basename(opt$file))
  if (!is.null(opt$caption)) header$caption <- opt$caption
  note <- if (k$kind == "video")
    sprintf("video %s (%.1f MB; %s)", basename(opt$file), length(body) / 1e6, sniff_video(body, k$mime))
  else
    sprintf("%s (%s bytes, embedded as-is)", basename(opt$file), format(length(body), big.mark = ","))
}
if (length(body) > GITHUB_MAX)
  stop(sprintf("The content is %.0f MB; GitHub Pages cannot host files over 100 MB. Trim it or export a smaller version.",
               length(body) / 1e6), call. = FALSE)

pw <- get_passphrase(confirm = TRUE)
message("Encrypting (", format(ITERS, big.mark = ","), " PBKDF2 rounds in R, then the authentication tag; ",
        "about a minute, longer for a video)...")
enc <- encrypt_payload(pack(header, body), pw)
where <- write_payload(opt$html, enc$meta, enc$ct)
cat(sprintf("Encrypted %s\n  -> %s\n", note, where))
if (length(enc$ct) > WARN_SIZE)
  cat(sprintf("Warning: %.0f MB is a lot to download and decrypt on a phone; a shorter or smaller export would be kinder.\n",
              length(enc$ct) / 1e6))
cat(NEXT_STEPS)
