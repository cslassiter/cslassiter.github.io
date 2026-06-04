# Publishes the already-rendered AI-jobs post to the live website.
#
# WHEN TO RUN:  AFTER you've sourced render_ai-jobs.R and looked at the HTML
#               to make sure it's right. This script is the "go live" step:
#               it runs git add + commit + push for you.
#
# HOW TO RUN (in RStudio):
#
#   # Option 1 - let it write a dated message automatically:
#   source("C:/Users/lassiter/vscode101/cslassiter.github.io/_publish/publish_ai-jobs.R")
#
#   # Option 2 - set your own commit message first, then source:
#   msg <- "Update figures in AI and jobs post"
#   source("C:/Users/lassiter/vscode101/cslassiter.github.io/_publish/publish_ai-jobs.R")
#
# After it finishes, the live site rebuilds in a minute or so:
#   https://cslassiter.github.io/

repo <- "C:/Users/lassiter/vscode101/cslassiter.github.io"

# If you didn't set `msg` yourself, use a sensible dated default.
if (!exists("msg") || !is.character(msg) || !nzchar(msg)) {
  msg <- paste("Update AI and jobs post -", format(Sys.time(), "%Y-%m-%d %H:%M"))
}

# Small helper: run a git command inside the repo and stop loudly if it fails.
# shQuote(type = "cmd") puts Windows-correct quotes around anything with spaces
# (like the commit message), so git sees it as a single argument.
git <- function(...) {
  args <- vapply(list(...), shQuote, character(1), type = "cmd")
  code <- system2("git", c("-C", shQuote(repo, type = "cmd"), args))
  if (code != 0) stop("git step failed: ", paste(..., collapse = " "), call. = FALSE)
  invisible(code)
}

# 1. Stage every change in the repo (edited HTML, new/updated figure PNGs, etc.).
git("add", "-A")

# 2. Only commit + push if something actually changed, so re-running is harmless.
nothing_staged <- system2(
  "git",
  c("-C", shQuote(repo, type = "cmd"), "diff", "--cached", "--quiet")
) == 0

if (nothing_staged) {
  message("Nothing new to publish - the repo already matches the last commit.")
} else {
  git("commit", "-m", msg)
  git("push")
  message("\nPublished! It will be live in a minute or so:\n  https://cslassiter.github.io/")
  rm(msg)  # clear the message so a later run can't accidentally reuse this one
}
