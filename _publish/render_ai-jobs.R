# Renders AI-jobs.Rmd into the website's posts/ folder, styled to match the site.
#
# HOW TO RUN:  open this file in RStudio and click "Source" (or run the line below).
#              RStudio bundles pandoc, which the render step needs.
#
#   source("C:/Users/lassiter/vscode101/cslassiter.github.io/_publish/render_ai-jobs.R")
#
# Output:  posts/ai-and-jobs-in-academic-philosophy.html
#          posts/ai-and-jobs-in-academic-philosophy_files/   (the plot images)
# Both must be committed and pushed for the post to appear on the live site.

rmd  <- "C:/Users/lassiter/OneDrive - Gonzaga University/R data/PhilJobs_annual_data/AI-jobs.Rmd"
repo <- "C:/Users/lassiter/vscode101/cslassiter.github.io"
tpl  <- file.path(repo, "_publish", "post-template.html")
out  <- file.path(repo, "posts", "ai-and-jobs-in-academic-philosophy.html")

rmarkdown::render(
  input         = rmd,
  output_file   = out,
  output_format = rmarkdown::html_document(
    template       = tpl,
    self_contained = FALSE,   # plots go to a sibling _files/ folder; keeps ../style.css a live link
    theme          = NULL,    # drop Bootstrap; the template's CSS matches the site instead
    highlight      = NULL,
    mathjax        = NULL
  ),
  envir = new.env()           # render in a clean environment
)

message("\nDone. Open in a browser to check:\n  ", out)
