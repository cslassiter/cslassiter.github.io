# setup_favicon.R
# ----------------
# R equivalent of setup_favicon.py: generates the favicon assets for
# cslassiter.github.io and injects the favicon <link> tags into every page.
#
# Design: a "CL" monogram on the site's navy (#1a1a2e) ground, cream serif
# letters (#f4f3ef), and the signature dark-red (#8B0000) accent bar across
# the bottom -- the same bar used on the header and every content card.
#
# Outputs (written to the repo root):
#   - favicon.svg          scalable, used by modern browsers
#   - favicon.ico          multi-size (16/32/48), legacy + broad support
#   - apple-touch-icon.png 180x180, iOS home-screen icon
#
# Requires: magick (install.packages("magick")); the SVG rasterisation step
# needs librsvg, which ships with the magick binaries on Windows/macOS.

library(magick)

root <- tryCatch(dirname(normalizePath(sys.frame(1)$ofile)), error = function(e) getwd())

# ---------------------------------------------------------------- SVG --------
# `rounded` controls the corner radius: 9 for the favicon, 0 for apple-touch
# (iOS applies its own rounding, so the source should be full-bleed).
svg_text <- function(radius = 9) {
  sprintf(
    paste0(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label="Charles Lassiter">\n',
      '  <defs>\n',
      '    <clipPath id="rounded"><rect width="64" height="64" rx="%d"/></clipPath>\n',
      '  </defs>\n',
      '  <g clip-path="url(#rounded)">\n',
      '    <rect width="64" height="64" fill="#1a1a2e"/>\n',
      '    <text x="32" y="42" text-anchor="middle"\n',
      '          font-family="Georgia, \'Times New Roman\', serif"\n',
      '          font-weight="600" font-size="36" fill="#f4f3ef">CL</text>\n',
      '    <rect x="0" y="55" width="64" height="9" fill="#8B0000"/>\n',
      '  </g>\n',
      '</svg>\n'
    ),
    radius
  )
}

render <- function(svg, px) {
  img <- image_read_svg(svg, width = px * 4, height = px * 4)  # supersample 4x
  image_resize(img, paste0(px, "x", px))
}

build_assets <- function() {
  # scalable favicon
  writeLines(svg_text(9), file.path(root, "favicon.svg"), useBytes = TRUE)
  message("wrote favicon.svg")

  # multi-size .ico (rounded; transparent corners)
  ico <- c(render(svg_text(9), 16),
           render(svg_text(9), 32),
           render(svg_text(9), 48))
  image_write(image_join(ico), file.path(root, "favicon.ico"), format = "ico")
  message("wrote favicon.ico (16/32/48)")

  # iOS home-screen icon: full-bleed, opaque, 180x180
  apple <- image_background(render(svg_text(0), 180), "#1a1a2e", flatten = TRUE)
  image_write(apple, file.path(root, "apple-touch-icon.png"), format = "png")
  message("wrote apple-touch-icon.png (180x180)")
}

# --------------------------------------------------------------- HTML --------
links <- c(
  '<link rel="icon" href="/favicon.ico" sizes="any">',
  '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
  '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
)

inject_links <- function() {
  files <- list.files(root, pattern = "\\.html$", recursive = TRUE, full.names = TRUE)
  changed <- 0L
  for (f in files) {
    lines <- readLines(f, warn = FALSE)
    if (any(grepl('rel="icon"', lines, fixed = TRUE))) next  # idempotent
    idx <- grep("<meta charset", lines, ignore.case = TRUE)[1]
    if (is.na(idx)) next
    indent <- sub("\\S.*$", "", lines[idx])           # leading whitespace
    block <- paste0(indent, links)
    out <- append(lines, block, after = idx)
    writeLines(out, f, useBytes = TRUE)
    changed <- changed + 1L
    message("updated ", sub(paste0(root, .Platform$file.sep), "", f, fixed = TRUE))
  }
  message("\n", changed, " HTML file(s) updated")
}

build_assets()
inject_links()
