library(tidyverse)
library(scales)
library(knitr)
library(kableExtra)

plots_dir <- "plots"
dir.create(plots_dir, showWarnings = FALSE)

# CSVs live alongside this script; run R from this folder (or setwd() here).
data_dir <- "."

save_plot <- function(p, filename, width = 10, height = 6) {
  ggsave(file.path(plots_dir, filename), plot = p,
         width = width, height = height, dpi = 150)
}

# ── 1. AI proportion over time ────────────────────────────────────────────────

annual <- tribble(
  ~year, ~total_ads, ~ai_ads,
  2013, 953, 11,
  2014, 595,  7,
  2015, 572,  3,
  2016, 602,  9,
  2017, 577, 19,
  2018, 596, 19,
  2019, 634, 44,
  2020, 440, 52,
  2021, 700, 57,
  2022, 743, 69,
  2023, 722, 91,
  2024, 639, 91,
  2025, 536, 86,
  2026, 207, 48
) |>
  mutate(
    pct_ai   = ai_ads / total_ads,
    partial  = year == 2026
  )

# Table 1
annual |>
  mutate(
    year     = if_else(partial, "2026 (partial)", as.character(year)),
    pct_ai   = percent(pct_ai, accuracy = 0.1)
  ) |>
  select(Year = year, `Total Ads` = total_ads, `AI Ads` = ai_ads, `% AI` = pct_ai) |>
  kbl(align = c("l", "r", "r", "r"), caption = "Table 1. AI-Related Ads as a Proportion of All Philosophy Ads") |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE) |>
  print()

# Plot 1a: % AI over time
p1a <- ggplot(annual, aes(year, pct_ai)) +
  geom_line(linewidth = 1, colour = "#2166ac") +
  geom_point(aes(shape = partial), size = 3, colour = "#2166ac") +
  scale_shape_manual(values = c(`FALSE` = 16, `TRUE` = 1),
                     labels = c("Full year", "Partial (2026)"),
                     name = NULL) +
  scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, NA)) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 1A",
    title    = "AI-Related Philosophy Job Ads as a Share of All Ads",
    subtitle = "PhilJobs.org, 2013–2026",
    x        = NULL,
    y        = "% of all ads that mention AI"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p1a)
save_plot(p1a, "plot_1a_ai_proportion.png")

# Plot 1b: raw counts, stacked bars
p1b <- annual |>
  mutate(non_ai = total_ads - ai_ads) |>
  pivot_longer(c(ai_ads, non_ai), names_to = "type", values_to = "n") |>
  mutate(type = factor(type, levels = c("non_ai", "ai_ads"),
                       labels = c("Non-AI", "AI-related"))) |>
  ggplot(aes(year, n, fill = type, alpha = partial)) +
  geom_col() +
  scale_fill_manual(values = c("Non-AI" = "#d1e5f0", "AI-related" = "#2166ac"),
                    name = NULL) +
  scale_alpha_manual(values = c(`FALSE` = 1, `TRUE` = 0.6),
                     labels = c("Full year", "Partial (2026)"),
                     name = NULL) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 1B",
    title    = "Total Philosophy Ads by Year, AI vs. Non-AI",
    subtitle = "PhilJobs.org, 2013–2026",
    x        = NULL,
    y        = "Number of job ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p1b)
save_plot(p1b, "plot_1b_ai_counts_stacked.png")


# ── 2. Job-type breakdown ─────────────────────────────────────────────────────

# Section 2 reads std_category directly from the detail CSV (always in sync)
job_types <- read_csv(file.path(data_dir, "philjobs_ai_jobs_detail.csv"), show_col_types = FALSE) |>
  count(job_type = std_category, name = "count") |>
  mutate(
    pct      = count / sum(count),
    job_type = fct_reorder(job_type, count)
  )

n_ai_total <- sum(job_types$count)

# Table 2
job_types |>
  arrange(desc(count)) |>
  mutate(pct = percent(pct, accuracy = 0.1)) |>
  select(`Job Type` = job_type, Count = count, `%` = pct) |>
  kbl(align = c("l", "r", "r"),
      caption = glue::glue("Table 2. AI-Related Ads by Job Type (2013–2026, n = {n_ai_total})")) |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE) |>
  print()

# Plot 2
p2 <- ggplot(job_types, aes(job_type, count)) +
  geom_col(fill = "#4393c3") +
  geom_text(aes(label = percent(pct, accuracy = 0.1)),
            hjust = -0.1, size = 3.5) +
  coord_flip() +
  scale_y_continuous(expand = expansion(mult = c(0, 0.15))) +
  labs(
    tag      = "Plot 2",
    title    = "AI-Related Philosophy Ads by Job Type",
    subtitle = glue::glue("n = {n_ai_total} ads, 2013–2026"),
    x        = NULL,
    y        = "Number of ads"
  ) +
  theme_minimal(base_size = 13)

print(p2)
save_plot(p2, "plot_2_job_types.png", width = 9, height = 6)


# ── 3. Top 15 institutions overall ───────────────────────────────────────────

top15 <- tribble(
  ~institution,                          ~ai_ads,
  "Stanford University",                  16,
  "Eindhoven University of Technology",  16,
  "Lingnan University",                  14,
  "University of Oxford",                13,
  "University of Twente",                12,
  "Utrecht University",                  12,
  "Purdue University",                   12,
  "Umea University",                     11,
  "University of Amsterdam",             10,
  "University of Hong Kong",             10,
  "University of Cambridge",              9,
  "Tilburg University",                   9,
  "University of Florida",                9,
  "Northeastern University",              8,
  "Carnegie Mellon University",           8
) |>
  mutate(
    institution = fct_reorder(institution, ai_ads),
    wake_forest = FALSE  # Wake Forest removed: confirmed false positive
  )

# Table 3
top15 |>
  arrange(desc(ai_ads)) |>
  mutate(Rank = row_number()) |>
  select(Rank, Institution = institution, `AI Ads` = ai_ads) |>
  kbl(align = c("r", "l", "r"),
      caption = "Table 3. Top 15 Institutions by AI-Related Ads (2013–2026). 27 confirmed false-positive ads removed; 32 confirmed false-negative ads added before ranking.") |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE) |>
  print()

# Plot 3
p3 <- ggplot(top15, aes(institution, ai_ads, fill = wake_forest)) +
  geom_col() +
  geom_text(aes(label = ai_ads), hjust = -0.2, size = 3.5) +
  coord_flip() +
  scale_fill_manual(values = c(`FALSE` = "#2166ac", `TRUE` = "#b2182b"),
                    name   = NULL,
                    guide  = "none") +
  scale_y_continuous(expand = expansion(mult = c(0, 0.12))) +
  labs(
    tag      = "Plot 3",
    title    = "Top 15 Institutions: AI-Related Philosophy Ads",
    subtitle = "2013–2026  |  n = 606 ads after false-positive removal and false-negative recovery",
    x        = NULL,
    y        = "Number of AI-related ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

print(p3)
save_plot(p3, "plot_3_top15_institutions.png", width = 10, height = 7)


# ── 4. Period comparison: 2013-2019 vs 2020-2026 ─────────────────────────────

period_comp <- tribble(
  ~institution,                         ~early, ~late,
  "Lingnan University",                      0,    14,
  "Stanford University",                     3,    13,
  "Purdue University",                       1,    11,
  "University of Hong Kong",                 0,    10,
  "University of Oxford",                    2,    11,
  "Umea University",                         1,    10,
  "University of Florida",                   0,     9,
  "Carnegie Mellon University",              0,     8,
  "Tilburg University",                      1,     8,
  "Eindhoven University of Technology",      5,    11,
  "Utrecht University",                      3,     9,
  "University of Edinburgh",                 0,     6,
  "University of Western Ontario",           0,     6,
  "Hong Kong Baptist University",            0,     6,
  "London School of Economics",              0,     6
) |>
  mutate(
    change      = late - early,
    institution = fct_reorder(institution, late)
  )

# Table 4
period_comp |>
  arrange(desc(change)) |>
  select(Institution = institution,
         `2013–2019` = early,
         `2020–2026` = late,
         Change = change) |>
  kbl(align = c("l", "r", "r", "r"),
      caption = "Table 4. Institutions Driving the Recent Surge: Period Comparison") |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE) |>
  print()

# Plot 4a: dumbbell chart
p4a <- period_comp |>
  pivot_longer(c(early, late), names_to = "period", values_to = "ads") |>
  mutate(period = factor(period, levels = c("early", "late"),
                         labels = c("2013–2019", "2020–2026"))) |>
  ggplot(aes(ads, institution, colour = period, group = institution)) +
  geom_line(colour = "grey70", linewidth = 1) +
  geom_point(size = 4) +
  scale_colour_manual(values = c("2013–2019" = "#d1e5f0", "2020–2026" = "#2166ac"),
                      name = NULL) +
  labs(
    tag      = "Plot 4A",
    title    = "AI-Related Philosophy Ads: Early vs. Late Period",
    subtitle = "Each institution's change from 2013–2019 to 2020–2026",
    x        = "Number of AI-related ads",
    y        = NULL
  ) +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

print(p4a)
save_plot(p4a, "plot_4a_period_dumbbell.png", width = 10, height = 7)


# ── 5. Year-by-year for key institutions ─────────────────────────────────────

key_inst_wide <- tribble(
  ~institution,                        ~`2013`,~`2014`,~`2015`,~`2016`,~`2017`,~`2018`,~`2019`,~`2020`,~`2021`,~`2022`,~`2023`,~`2024`,~`2025`,~`2026`,
  "Lingnan University",                     0,     0,     0,     0,     0,     0,     0,     1,     1,     0,     3,     4,     4,     1,
  "Stanford University",                    1,     0,     0,     0,     0,     1,     1,     2,     2,     2,     3,     2,     2,     0,
  "Purdue University",                      0,     0,     0,     0,     0,     1,     0,     0,     0,     2,     4,     3,     0,     2,
  "University of Florida",                  0,     0,     0,     0,     0,     0,     0,     1,     1,     1,     3,     2,     0,     1,
  "University of Hong Kong",                0,     0,     0,     0,     0,     0,     0,     0,     1,     0,     1,     1,     4,     3,
  "Umea University",                        0,     0,     0,     0,     0,     0,     1,     1,     2,     1,     0,     2,     2,     2,
  "Carnegie Mellon University",             0,     0,     0,     0,     0,     0,     0,     0,     1,     1,     0,     0,     5,     1,
  "Utrecht University",                     0,     1,     0,     1,     0,     0,     1,     1,     1,     0,     6,     1,     0,     0,
  "Eindhoven University of Technology",     0,     0,     0,     0,     1,     1,     3,     2,     4,     2,     1,     1,     0,     1,
  "University of Amsterdam",                0,     0,     5,     0,     0,     0,     0,     0,     0,     0,     2,     0,     0,     3
)

key_inst <- key_inst_wide |>
  pivot_longer(-institution, names_to = "year", values_to = "ads") |>
  mutate(year = as.integer(year))

# Table 5
key_inst_wide |>
  kbl(align = c("l", rep("r", 14)),
      caption = "Table 5. Year-by-Year AI-Related Ads for Key Institutions") |>
  kable_styling(bootstrap_options = c("striped", "hover"),
                full_width = TRUE, font_size = 11) |>
  print()

# Plot 5a: heatmap
p5a <- ggplot(key_inst, aes(year, institution, fill = ads)) +
  geom_tile(colour = "white", linewidth = 0.5) +
  geom_text(aes(label = if_else(ads > 0, as.character(ads), "")),
            size = 3, colour = "white", fontface = "bold") +
  scale_fill_gradient(low = "#deebf7", high = "#08519c",
                      name = "Ads") +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 5A",
    title    = "AI-Related Philosophy Ads: Key Institutions by Year",
    subtitle = "Darker = more ads",
    x        = NULL,
    y        = NULL
  ) +
  theme_minimal(base_size = 12) +
  theme(axis.text.x = element_text(angle = 45, hjust = 1),
        panel.grid = element_blank())

print(p5a)
save_plot(p5a, "plot_5a_heatmap.png", width = 12, height = 6)

# Plot 5b: small-multiple line charts
p5b <- ggplot(key_inst, aes(year, ads)) +
  geom_line(colour = "#2166ac", linewidth = 0.8) +
  geom_point(size = 2, colour = "#2166ac") +
  facet_wrap(~institution, ncol = 3, scales = "free_y") +
  scale_x_continuous(breaks = c(2013, 2018, 2023, 2026),
                     labels = c("'13", "'18", "'23", "'26")) +
  labs(
    tag      = "Plot 5B",
    title    = "AI-Related Ads Over Time: Key Institutions",
    subtitle = "Note: y-axis scales vary by panel",
    x        = NULL,
    y        = "Number of ads"
  ) +
  theme_minimal(base_size = 11) +
  theme(strip.text = element_text(size = 9, face = "bold"))

print(p5b)
save_plot(p5b, "plot_5b_small_multiples.png", width = 12, height = 8)


# ── 6. Regional groupings ─────────────────────────────────────────────────────

region_yearly <- key_inst |>
  mutate(region = case_when(
    institution %in% c("Lingnan University",
                       "University of Hong Kong") ~ "Hong Kong",
    institution %in% c("Eindhoven Univ. of Technology",
                       "Utrecht University",
                       "University of Amsterdam") ~ "Netherlands",
    institution %in% c("Stanford University",
                       "Purdue University",
                       "University of Florida",
                       "Carnegie Mellon University") ~ "United States",
    TRUE ~ "Other"
  )) |>
  filter(region != "Other") |>
  group_by(region, year) |>
  summarise(ads = sum(ads), .groups = "drop") |>
  arrange(region, year) |>
  group_by(region) |>
  mutate(cumulative_ads = cumsum(ads)) |>
  ungroup()

p6 <- ggplot(region_yearly, aes(year, cumulative_ads, colour = region, group = region)) +
  geom_line(linewidth = 1.2) +
  geom_point(size = 3) +
  scale_colour_manual(
    values = c("Hong Kong"   = "#d6604d",
               "Netherlands" = "#4393c3",
               "United States" = "#1a7837"),
    name = NULL
  ) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 6",
    title    = "Cumulative AI-Related Philosophy Ads by Region (Selected Institutions)",
    subtitle = "Hong Kong = Lingnan + HKU  |  Netherlands = Eindhoven + Utrecht + Amsterdam  |  US = Stanford + Purdue + UF + CMU",
    x        = NULL,
    y        = "Cumulative number of ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x   = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p6)
save_plot(p6, "plot_6_regional_cumulative.png")


# ── 7. AOS analysis (reads philjobs_ai_jobs_detail.csv) ──────────────────────

detail <- read_csv(file.path(data_dir, "philjobs_ai_jobs_detail.csv"), show_col_types = FALSE) |>
  mutate(aos_lower = str_to_lower(aos))

# Keyword classifier — multi-label, returns one row per job × category hit
#
# Phil. of Science vs. Phil. of Technology split:
#   "Phil. of Science"     → explicit science keywords, plus "science and technology" as a
#                            paired phrase (analytic/STS tradition)
#   "Phil. of Technology"  → "philosophy of technology", post-phenomenology keywords, AND
#                            any job whose AOS contains "technolog" WITHOUT "science"
#                            (Continental / post-phenomenological tradition)
aos_keywords <- list(
  "Mind / Cog. Sci. / AI"      = c("mind", "cognitive", "cognition", "artificial intelligence",
                                     "\\bai\\b", "robotics", "neural", "machine learning",
                                     "deep learning", "llm", "natural language"),
  "Ethics / Applied Ethics"    = c("ethics", "ethical", "moral", "responsible", "bias",
                                     "fairness", "accountability", "value alignment"),
  "Phil. of Science"           = c("philosophy of science", "phil.*sci",
                                     "data science", "computing", "computational",
                                     "philosophy of information", "digital",
                                     "science and technology"),
  "Phil. of Technology"        = c("philosophy of technology", "post.phenomenolog",
                                     "phenomenolog.*technolog", "technolog.*phenomenolog"),
  "Logic / Formal Methods"     = c("logic", "formal", "predicate", "proof", "reasoning",
                                     "knowledge representation", "ontolog"),
  "Social / Political Phil."   = c("social", "political", "justice", "democracy", "power",
                                     "feminist", "race", "gender", "diversity"),
  "Epistemology"               = c("epistemo", "knowledge", "belief", "justification",
                                     "testimony", "trust"),
  "Open / Unspecified"         = c("^open$", "see job description", "no restriction",
                                     "^$", "not specified")
)

classify_aos <- function(df, kw_list) {
  map_dfr(names(kw_list), function(cat) {
    pattern <- paste(kw_list[[cat]], collapse = "|")
    df |>
      filter(str_detect(aos_lower, regex(pattern, ignore_case = TRUE))) |>
      mutate(aos_cat = cat)
  })
}

# Jobs where "technolog" appears WITHOUT "science" in the AOS string are
# classified as Phil. of Technology (not already caught by the explicit keywords above)
tech_no_sci <- detail |>
  filter(
    str_detect(aos_lower, "technolog"),
    !str_detect(aos_lower, "science")
  ) |>
  mutate(aos_cat = "Phil. of Technology")

classified <- classify_aos(detail, aos_keywords)

detail_long <- bind_rows(classified, tech_no_sci) |>
  distinct(job_id, aos_cat, .keep_all = TRUE) |>
  # jobs with no keyword hit → Other
  bind_rows(
    detail |>
      filter(!job_id %in% bind_rows(classified, tech_no_sci)$job_id) |>
      mutate(aos_cat = "Other / Unclassified")
  ) |>
  mutate(
    aos_cat = factor(aos_cat, levels = c(
      "Ethics / Applied Ethics",
      "Mind / Cog. Sci. / AI",
      "Phil. of Science",
      "Phil. of Technology",
      "Logic / Formal Methods",
      "Social / Political Phil.",
      "Epistemology",
      "Open / Unspecified",
      "Other / Unclassified"
    )),
    period = if_else(year <= 2019, "2013–2019", "2020–2026"),
    region = case_when(
      str_detect(location, "United States|USA") ~ "United States",
      str_detect(location, "United Kingdom|England|Scotland|Wales") ~ "UK",
      str_detect(location, "Hong Kong|China|Japan|Korea|Singapore|Taiwan|Asia") ~ "Asia",
      str_detect(location, "Canada") ~ "Canada",
      str_detect(location, "Australia|New Zealand") ~ "Aus / NZ",
      str_detect(location, "Netherlands|Germany|France|Belgium|Sweden|Denmark|Finland|Norway|Spain|Italy|Poland|Switzerland|Austria|Czech") ~ "Cont. Europe",
      TRUE ~ "Other"
    )
  )

n_jobs <- n_distinct(detail$job_id)

# ── Table 6: Overall AOS distribution ────────────────────────────────────────

detail_long |>
  distinct(job_id, aos_cat) |>
  count(aos_cat, name = "count") |>
  mutate(pct = percent(count / n_jobs, accuracy = 0.1)) |>
  arrange(desc(count)) |>
  select(`AOS Category` = aos_cat, Count = count, `% of jobs` = pct) |>
  kbl(align = c("l", "r", "r"),
      caption = glue::glue("Table 6. AOS Distribution Across {n_jobs} AI-Related Philosophy Ads (multi-label)")) |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE) |>
  print()

# ── Plot 7a: Overall AOS bar ──────────────────────────────────────────────────

aos_overall <- detail_long |>
  distinct(job_id, aos_cat) |>
  count(aos_cat) |>
  mutate(
    pct     = n / n_jobs,
    aos_cat = fct_reorder(aos_cat, n)
  )

p7a <- ggplot(aos_overall, aes(aos_cat, n)) +
  geom_col(fill = "#2166ac") +
  geom_text(aes(label = percent(pct, accuracy = 0.1)), hjust = -0.1, size = 3.5) +
  coord_flip() +
  scale_y_continuous(expand = expansion(mult = c(0, 0.15))) +
  labs(
    tag      = "Plot 7A",
    title    = "AOS Categories in AI-Related Philosophy Ads",
    subtitle = glue::glue("Multi-label; n = {n_jobs} jobs, 2013–2026"),
    x        = NULL,
    y        = "Number of ads"
  ) +
  theme_minimal(base_size = 13)

print(p7a)
save_plot(p7a, "plot_7a_aos_overall.png", width = 9, height = 6)

# ── Plot 7b: AOS share by year — line chart ───────────────────────────────────

aos_by_year <- detail_long |>
  distinct(job_id, year, aos_cat) |>
  count(year, aos_cat) |>
  left_join(count(detail, year, name = "total"), by = "year") |>
  mutate(pct = n / total) |>
  filter(aos_cat %in% c("Ethics / Applied Ethics",
                         "Mind / Cog. Sci. / AI",
                         "Phil. of Science",
                         "Phil. of Technology",
                         "Logic / Formal Methods",
                         "Open / Unspecified"))

p7b <- ggplot(aos_by_year, aes(year, pct, colour = aos_cat, group = aos_cat)) +
  geom_line(linewidth = 1.1) +
  geom_point(size = 2.5) +
  scale_y_continuous(labels = percent_format(accuracy = 1)) +
  scale_x_continuous(breaks = 2013:2026) +
  scale_colour_manual(
    values = c(
      "Ethics / Applied Ethics" = "#d6604d",
      "Mind / Cog. Sci. / AI"   = "#2166ac",
      "Phil. of Science"        = "#1b7837",
      "Phil. of Technology"     = "#74c476",
      "Logic / Formal Methods"  = "#762a83",
      "Open / Unspecified"      = "#878787"
    ),
    name = NULL
  ) +
  labs(
    tag      = "Plot 7B",
    title    = "AOS Share of AI-Related Ads by Year",
    subtitle = "Top 6 categories; share of all AI-related ads that year",
    x        = NULL,
    y        = "Share of AI-related ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x   = element_text(angle = 45, hjust = 1),
        legend.position = "bottom",
        legend.text     = element_text(size = 9))

print(p7b)
save_plot(p7b, "plot_7b_aos_by_year.png")

# ── Plot 7c: Period comparison — dumbbell ─────────────────────────────────────

aos_period <- detail_long |>
  distinct(job_id, period, aos_cat) |>
  count(period, aos_cat) |>
  left_join(
    detail_long |> distinct(job_id, period) |> count(period, name = "total"),
    by = "period"
  ) |>
  mutate(pct = n / total)

p7c <- ggplot(aos_period, aes(pct, aos_cat, colour = period, group = aos_cat)) +
  geom_line(colour = "grey70", linewidth = 1) +
  geom_point(size = 4) +
  scale_x_continuous(labels = percent_format(accuracy = 1)) +
  scale_colour_manual(values = c("2013–2019" = "#c6dbef", "2020–2026" = "#2166ac"),
                      name = NULL) +
  labs(
    tag      = "Plot 7C",
    title    = "AOS Share: Early vs. Late Period",
    subtitle = "Each dot = share of that period's AI-related ads",
    x        = "Share of AI-related ads",
    y        = NULL
  ) +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

print(p7c)
save_plot(p7c, "plot_7c_aos_period.png", width = 9, height = 6)

# ── Table 7: Period comparison ────────────────────────────────────────────────

aos_period |>
  mutate(label = glue::glue("{n} ({percent(pct, accuracy = 0.1)})")) |>
  select(aos_cat, period, label) |>
  pivot_wider(names_from = period, values_from = label) |>
  arrange(desc(as.integer(str_extract(`2020–2026`, "^\\d+")))) |>
  kbl(align = c("l", "r", "r"),
      col.names = c("AOS Category", "2013–2019", "2020–2026"),
      caption   = "Table 7. AOS by Period: Count (% of that period's AI-related ads)") |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE) |>
  print()

# ── Plot 7d: AOS by region — heatmap ─────────────────────────────────────────

region_order <- c("United States", "UK", "Cont. Europe", "Canada", "Asia", "Aus / NZ")

aos_region <- detail_long |>
  filter(region %in% region_order) |>
  distinct(job_id, region, aos_cat) |>
  count(region, aos_cat) |>
  left_join(
    detail_long |>
      filter(region %in% region_order) |>
      distinct(job_id, region) |>
      count(region, name = "total"),
    by = "region"
  ) |>
  mutate(
    pct    = n / total,
    region = factor(region, levels = region_order)
  )

p7d <- ggplot(aos_region, aes(region, aos_cat, fill = pct)) +
  geom_tile(colour = "white", linewidth = 0.6) +
  geom_text(aes(label = percent(pct, accuracy = 1)),
            size = 3.2, colour = "white", fontface = "bold") +
  scale_fill_gradient(low = "#deebf7", high = "#08519c",
                      labels = percent_format(accuracy = 1),
                      name   = "Share") +
  labs(
    tag      = "Plot 7D",
    title    = "AOS Profile by Region",
    subtitle = "Share of each region's AI-related ads falling in each category (multi-label)",
    x        = NULL,
    y        = NULL
  ) +
  theme_minimal(base_size = 12) +
  theme(panel.grid = element_blank(),
        axis.text.x = element_text(angle = 30, hjust = 1))

print(p7d)
save_plot(p7d, "plot_7d_aos_region.png", width = 10, height = 7)

# ── Plot 7e: Ethics vs. Logic share over time (focused comparison) ────────────

eth_logic <- aos_by_year |>
  filter(aos_cat %in% c("Ethics / Applied Ethics", "Logic / Formal Methods"))

p7e <- ggplot(eth_logic, aes(year, pct, colour = aos_cat, group = aos_cat)) +
  geom_ribbon(
    data = eth_logic |>
      select(year, aos_cat, pct) |>
      pivot_wider(names_from = aos_cat, values_from = pct) |>
      rename(ethics = `Ethics / Applied Ethics`, logic = `Logic / Formal Methods`),
    aes(x = year, ymin = logic, ymax = ethics),
    inherit.aes = FALSE,
    fill = "#fee0d2", alpha = 0.4
  ) +
  geom_line(linewidth = 1.2) +
  geom_point(size = 3) +
  scale_y_continuous(labels = percent_format(accuracy = 1), limits = c(0, NA)) +
  scale_x_continuous(breaks = 2013:2026) +
  scale_colour_manual(
    values = c("Ethics / Applied Ethics" = "#d6604d",
               "Logic / Formal Methods"  = "#762a83"),
    name = NULL
  ) +
  labs(
    tag      = "Plot 7E",
    title    = "The Ethics–Logic Crossover in AI Philosophy Hiring",
    subtitle = "Shaded area = gap between ethics and logic share of AI-related ads",
    x        = NULL,
    y        = "Share of AI-related ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x   = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p7e)
save_plot(p7e, "plot_7e_ethics_logic.png")


# ── 8. Phil-tech vs. AI trends (reads philjobs_philtech_final.csv) ───────────
#
# Columns used:
#   pass1_confirmed  – jobs whose full page text confirmed a phil-tech / STS AOS
#                      (100% precision; conservative lower bound on true count)
#   estimated_philtech – pass1_confirmed + recall-adjusted estimate of missed jobs
#   recall_lower / recall_upper – 95% Wilson CI bounds on estimated_philtech
#   philtech_and_ai  – confirmed PT jobs also in the AI job-ID set
#   philtech_only    – confirmed PT jobs NOT in the AI set
#   ai_only          – AI jobs NOT in the confirmed PT set

pt <- read_csv(file.path(data_dir, "philjobs_philtech_final.csv"), show_col_types = FALSE) |>
  mutate(
    partial             = year == max(year),
    # proportions of all ads
    pct_confirmed       = pass1_confirmed   / total_jobs,
    pct_est             = estimated_philtech / total_jobs,
    pct_recall_lo       = recall_lower      / total_jobs,
    pct_recall_hi       = recall_upper      / total_jobs,
    pct_pt_and_ai       = philtech_and_ai   / total_jobs,
    pct_pt_only         = philtech_only     / total_jobs,
    pct_ai_only         = ai_only           / total_jobs,
    pct_ai              = ai_jobs           / total_jobs,
    # AI capture rate: of confirmed PT ads, what share also mention AI?
    ai_capture_rate     = if_else(pass1_confirmed > 0,
                                  philtech_and_ai / pass1_confirmed,
                                  NA_real_)
  )

# ── Table 8: year-by-year confirmed counts + recall bounds ───────────────────

pt |>
  mutate(
    yr_label     = if_else(partial, paste0(year, "*"), as.character(year)),
    recall_range = glue::glue("[{recall_lower}, {recall_upper}]"),
    pct_conf     = percent(pct_confirmed, accuracy = 0.1),
    pct_pt_ai    = percent(pct_pt_and_ai, accuracy = 0.1),
    pct_ai       = percent(pct_ai,        accuracy = 0.1)
  ) |>
  select(
    Year                     = yr_label,
    Total                    = total_jobs,
    `Confirmed PT`           = pass1_confirmed,
    `Est. total PT`          = estimated_philtech,
    `95% CI`                 = recall_range,
    `PT + AI`                = philtech_and_ai,
    `AI only`                = ai_only,
    `% Conf. PT`             = pct_conf,
    `% PT + AI`              = pct_pt_ai,
    `% AI`                   = pct_ai
  ) |>
  kbl(align = c("l", rep("r", 9)),
      caption = paste(
        "Table 8. Phil-tech / STS vs. AI Ads by Year.",
        "Confirmed PT = explicit AOS/title match (100% precision lower bound).",
        "Est. total PT = confirmed + recall-adjusted estimate; 95% Wilson CI shown.",
        "* = partial year."
      )) |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE,
                font_size = 11) |>
  print()

# ── Plot 8a: confirmed PT vs AI — trend lines with recall ribbon ──────────────
# The ribbon spans [recall_lower, recall_upper] / total_jobs around the
# confirmed PT proportion, showing the range of plausible true values.

p8a <- ggplot(pt, aes(year)) +
  # Recall uncertainty ribbon around confirmed PT line
  geom_ribbon(aes(ymin = pct_recall_lo, ymax = pct_recall_hi),
              fill = "#74c476", alpha = 0.2) +
  # Confirmed PT line (solid lower bound)
  geom_line(aes(y = pct_confirmed, colour = "Phil-tech (confirmed)"),
            linewidth = 1.2) +
  geom_point(aes(y = pct_confirmed, colour = "Phil-tech (confirmed)",
                 shape = partial), size = 3) +
  # AI line
  geom_line(aes(y = pct_ai, colour = "AI"), linewidth = 1.2) +
  geom_point(aes(y = pct_ai, colour = "AI", shape = partial), size = 3) +
  scale_shape_manual(values = c(`FALSE` = 16, `TRUE` = 1),
                     labels = c("Full year", "Partial"), name = NULL) +
  scale_colour_manual(
    values = c("Phil-tech (confirmed)" = "#31a354", "AI" = "#2166ac"),
    name   = NULL
  ) +
  scale_y_continuous(labels = percent_format(accuracy = 1)) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 8A",
    title    = "Philosophy of Technology / STS vs. AI in the Job Market",
    subtitle = paste("Solid lines = confirmed counts (100% precision).",
                     "Green ribbon = 95% recall uncertainty band for phil-tech."),
    x        = NULL,
    y        = "Share of all philosophy ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x    = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p8a)
save_plot(p8a, "plot_8a_philtech_vs_ai.png")

# ── Plot 8b: PT+AI overlap — the headline finding ────────────────────────────
# Absolute confirmed counts; overlap bar highlighted in orange.

pt_bars <- pt |>
  filter(!partial) |>      # full years only for clean bar chart
  select(year,
         `Phil-tech only` = philtech_only,
         `Phil-tech + AI` = philtech_and_ai,
         `AI only`        = ai_only) |>
  pivot_longer(-year, names_to = "group", values_to = "n") |>
  mutate(group = factor(group,
                        levels = c("Phil-tech only", "Phil-tech + AI", "AI only")))

p8b <- ggplot(pt_bars, aes(year, n, fill = group)) +
  geom_col(position = "dodge") +
  scale_fill_manual(
    values = c(
      "Phil-tech only" = "#74c476",
      "Phil-tech + AI" = "#fd8d3c",
      "AI only"        = "#2166ac"
    ),
    name = NULL
  ) +
  scale_x_continuous(breaks = 2013:2025) +
  labs(
    tag      = "Plot 8B",
    title    = "Confirmed Phil-tech, AI, and Overlap Ads by Year",
    subtitle = "Phil-tech counts = Pass-1 confirmed; grouped bars, full years only",
    x        = NULL,
    y        = "Number of confirmed ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x    = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p8b)
save_plot(p8b, "plot_8b_overlap_bars.png")

# ── Plot 8c: PT+AI overlap as share of all ads — area emphasis ───────────────
# Stacks confirmed PT-only and PT+AI to show how the overlap has grown
# as a component of the broader phil-tech presence.

pt_stack <- pt |>
  select(year, partial,
         `Phil-tech only` = pct_pt_only,
         `Phil-tech + AI` = pct_pt_and_ai) |>
  pivot_longer(c(`Phil-tech only`, `Phil-tech + AI`),
               names_to = "group", values_to = "pct") |>
  mutate(group = factor(group, levels = c("Phil-tech only", "Phil-tech + AI")))

p8c <- ggplot(pt_stack, aes(year, pct, fill = group)) +
  geom_area(alpha = 0.85, colour = "white", linewidth = 0.4) +
  geom_vline(xintercept = 2019.5, linetype = "dashed",
             colour = "grey40", linewidth = 0.6) +
  annotate("text", x = 2019.7, y = 0.025,
           label = "ChatGPT era\nbegins ~2020", hjust = 0,
           size = 3, colour = "grey30") +
  scale_fill_manual(
    values = c("Phil-tech only" = "#74c476", "Phil-tech + AI" = "#fd8d3c"),
    name   = NULL
  ) +
  scale_y_continuous(labels = percent_format(accuracy = 0.1)) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 8C",
    title    = "Growth of the Phil-tech / AI Overlap",
    subtitle = "Stacked area: share of all philosophy ads that are confirmed phil-tech (split by AI overlap)",
    x        = NULL,
    y        = "Share of all philosophy ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x    = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p8c)
save_plot(p8c, "plot_8c_overlap_area.png")

# ── Plot 8d: AI capture rate ─────────────────────────────────────────────────
# Of confirmed phil-tech ads each year, what fraction also mention AI?
# Interpretive note in subtitle: this is a lower bound because missed
# phil-tech ads (false negatives) may also overlap with AI.

p8d <- ggplot(pt |> filter(!is.na(ai_capture_rate)),
              aes(year, ai_capture_rate)) +
  geom_col(aes(alpha = partial), fill = "#fd8d3c") +
  geom_text(aes(label = percent(ai_capture_rate, accuracy = 1)),
            vjust = -0.4, size = 3.2) +
  scale_alpha_manual(values = c(`FALSE` = 1, `TRUE` = 0.55),
                     labels = c("Full year", "Partial"), name = NULL) +
  scale_y_continuous(labels = percent_format(accuracy = 1),
                     expand = expansion(mult = c(0, 0.14))) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 8D",
    title    = "AI Capture Rate in Confirmed Phil-tech / STS Ads",
    subtitle = paste("Of confirmed phil-tech ads each year, share that also mention AI.",
                     "A lower bound: undetected phil-tech ads may also overlap with AI."),
    x        = NULL,
    y        = "Share of confirmed phil-tech ads also mentioning AI"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x    = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p8d)
save_plot(p8d, "plot_8d_ai_capture_rate.png")

# ── Plot 8e: period dumbbell — confirmed counts ───────────────────────────────

pt_period <- pt |>
  mutate(period = if_else(year <= 2019, "2013–2019", "2020–2026")) |>
  group_by(period) |>
  summarise(
    total           = sum(total_jobs),
    philtech_only   = sum(philtech_only),
    philtech_and_ai = sum(philtech_and_ai),
    ai_only         = sum(ai_only),
    .groups = "drop"
  ) |>
  mutate(across(c(philtech_only, philtech_and_ai, ai_only),
                list(pct = ~ .x / total))) |>
  select(period, ends_with("_pct")) |>
  pivot_longer(-period, names_to = "group", values_to = "pct") |>
  mutate(
    group = recode(group,
                   philtech_only_pct   = "Phil-tech only",
                   philtech_and_ai_pct = "Phil-tech + AI",
                   ai_only_pct         = "AI only"),
    group  = factor(group, levels = c("Phil-tech only", "Phil-tech + AI", "AI only")),
    period = factor(period, levels = c("2013–2019", "2020–2026"))
  )

p8e <- ggplot(pt_period, aes(pct, group, colour = period, group = group)) +
  geom_line(colour = "grey70", linewidth = 1) +
  geom_point(size = 5) +
  geom_text(aes(label = percent(pct, accuracy = 0.1)),
            nudge_y = 0.25, size = 3.2, show.legend = FALSE) +
  scale_x_continuous(labels = percent_format(accuracy = 0.1)) +
  scale_colour_manual(
    values = c("2013–2019" = "#c6dbef", "2020–2026" = "#2166ac"),
    name   = NULL
  ) +
  labs(
    tag      = "Plot 8E",
    title    = "Phil-tech, Overlap, and AI: Early vs. Late Period",
    subtitle = "Confirmed counts as share of all philosophy ads in each period",
    x        = "Share of all philosophy ads",
    y        = NULL
  ) +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

print(p8e)
save_plot(p8e, "plot_8e_period_dumbbell.png", width = 9, height = 6)

# ── Table 9: period summary ───────────────────────────────────────────────────

pt |>
  mutate(period = if_else(year <= 2019, "2013–2019", "2020–2026")) |>
  group_by(period) |>
  summarise(
    `Total ads`       = sum(total_jobs),
    `Phil-tech only`  = sum(philtech_only),
    `Phil-tech + AI`  = sum(philtech_and_ai),
    `AI only`         = sum(ai_only),
    .groups           = "drop"
  ) |>
  mutate(
    `% PT only` = percent(`Phil-tech only` / `Total ads`, accuracy = 0.1),
    `% PT + AI` = percent(`Phil-tech + AI`  / `Total ads`, accuracy = 0.1),
    `% AI only` = percent(`AI only`         / `Total ads`, accuracy = 0.1)
  ) |>
  kbl(align = c("l", rep("r", 6)),
      caption = paste(
        "Table 9. Confirmed Phil-tech / AI Hiring by Period",
        "(share of all philosophy ads; confirmed Pass-1 counts only)."
      )) |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE) |>
  print()


# ── 9. Job-type × contract-type breakdown for AI jobs ────────────────────────
# Source: philjobs_ai_jobs_detail.csv
# job_category field format: "Job type / Contract type"
# Focus groups: Junior/TT, Junior/FT, Postdoc/FT; remainder → Other

ai_detail <- read_csv(file.path(data_dir, "philjobs_ai_jobs_detail.csv"), show_col_types = FALSE)

CONTRACT_LEVELS <- c("Junior, tenure-track", "Junior, fixed-term",
                     "Postdoc, fixed-term", "Other")

ai_contract <- ai_detail |>
  mutate(
    jtype = str_to_lower(str_trim(str_extract(job_category, "^[^/]+"))),
    ctype = str_to_lower(str_trim(str_extract(job_category, "(?<=/)[^/]+$"))),
    group = case_when(
      str_detect(jtype, "junior")  & str_detect(ctype, "tenure") ~ "Junior, tenure-track",
      str_detect(jtype, "junior")  & str_detect(ctype, "fixed")  ~ "Junior, fixed-term",
      str_detect(jtype, "postdoc") & str_detect(ctype, "fixed")  ~ "Postdoc, fixed-term",
      TRUE                                                        ~ "Other"
    ),
    group = factor(group, levels = CONTRACT_LEVELS)
  ) |>
  count(year, group) |>
  group_by(year) |>
  mutate(total = sum(n), pct = n / total) |>
  ungroup()

# ── Table 10: year-by-year proportions ───────────────────────────────────────

ai_contract |>
  mutate(label = glue::glue("{n} ({percent(pct, accuracy = 0.1)})")) |>
  select(year, group, label) |>
  pivot_wider(names_from = group, values_from = label, values_fill = "0 (0.0%)") |>
  left_join(ai_detail |> count(year, name = "Total"), by = "year") |>
  arrange(year) |>
  kbl(align = c("l", rep("r", 5)),
      caption = "Table 10. AI Philosophy Job Ads by Type and Contract (count + % of year total)") |>
  kable_styling(bootstrap_options = c("striped", "hover"), full_width = FALSE,
                font_size = 11) |>
  print()

# ── Plot 9a: stacked proportional bar — all four groups ──────────────────────

p9a <- ggplot(ai_contract, aes(year, pct, fill = group)) +
  geom_col(width = 0.75) +
  scale_fill_manual(
    values = c(
      "Junior, tenure-track" = "#2166ac",
      "Junior, fixed-term"   = "#92c5de",
      "Postdoc, fixed-term"  = "#d6604d",
      "Other"                = "#d9d9d9"
    ),
    name = NULL
  ) +
  scale_y_continuous(labels = percent_format(accuracy = 1)) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 9A",
    title    = "AI Philosophy Jobs: Contract Profile by Year",
    subtitle = "Proportions of all AI-related ads; Junior = asst. prof. / instructor / lecturer",
    x        = NULL,
    y        = "Share of AI-related ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x    = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p9a)
save_plot(p9a, "plot_9a_contract_stacked.png")

# ── Plot 9b: line chart — three named groups only ────────────────────────────

ai_contract_lines <- ai_contract |>
  filter(group != "Other") |>
  mutate(partial = year == max(ai_detail$year))

p9b <- ggplot(ai_contract_lines, aes(year, pct, colour = group, group = group)) +
  geom_line(linewidth = 1.2) +
  geom_point(aes(shape = partial), size = 3) +
  scale_shape_manual(values = c(`FALSE` = 16, `TRUE` = 1),
                     labels = c("Full year", "Partial"), name = NULL) +
  scale_colour_manual(
    values = c(
      "Junior, tenure-track" = "#2166ac",
      "Junior, fixed-term"   = "#92c5de",
      "Postdoc, fixed-term"  = "#d6604d"
    ),
    name = NULL
  ) +
  scale_y_continuous(labels = percent_format(accuracy = 1)) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 9B",
    title    = "AI Philosophy Jobs: Three Contract Categories Over Time",
    subtitle = "Share of all AI-related ads each year",
    x        = NULL,
    y        = "Share of AI-related ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x    = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p9b)
save_plot(p9b, "plot_9b_contract_lines.png")

# ── Plot 9c: absolute counts — dodged bars ───────────────────────────────────

p9c <- ggplot(ai_contract |> filter(group != "Other"),
              aes(year, n, fill = group)) +
  geom_col(position = "dodge", width = 0.75) +
  scale_fill_manual(
    values = c(
      "Junior, tenure-track" = "#2166ac",
      "Junior, fixed-term"   = "#92c5de",
      "Postdoc, fixed-term"  = "#d6604d"
    ),
    name = NULL
  ) +
  scale_x_continuous(breaks = 2013:2026) +
  labs(
    tag      = "Plot 9C",
    title    = "AI Philosophy Jobs: Absolute Counts by Contract Category",
    subtitle = "Three focal categories; Other excluded",
    x        = NULL,
    y        = "Number of ads"
  ) +
  theme_minimal(base_size = 13) +
  theme(axis.text.x    = element_text(angle = 45, hjust = 1),
        legend.position = "bottom")

print(p9c)
save_plot(p9c, "plot_9c_contract_counts.png")

# ── Plot 9d: period dumbbell ──────────────────────────────────────────────────

ai_contract_period <- ai_contract |>
  filter(group != "Other") |>
  mutate(period = if_else(year <= 2019, "2013–2019", "2020–2026")) |>
  group_by(period, group) |>
  summarise(n = sum(n), .groups = "drop") |>
  group_by(period) |>
  mutate(pct = n / sum(n)) |>
  ungroup() |>
  mutate(period = factor(period, levels = c("2013–2019", "2020–2026")))

p9d <- ggplot(ai_contract_period, aes(pct, group, colour = period, group = group)) +
  geom_line(colour = "grey70", linewidth = 1) +
  geom_point(size = 5) +
  geom_text(aes(label = percent(pct, accuracy = 0.1)),
            nudge_y = 0.25, size = 3.2, show.legend = FALSE) +
  scale_x_continuous(labels = percent_format(accuracy = 1)) +
  scale_colour_manual(
    values = c("2013–2019" = "#c6dbef", "2020–2026" = "#2166ac"),
    name   = NULL
  ) +
  labs(
    tag      = "Plot 9D",
    title    = "AI Philosophy Job Contract Profile: Early vs. Late Period",
    subtitle = "As share of the three focal categories combined (Other excluded)",
    x        = "Share",
    y        = NULL
  ) +
  theme_minimal(base_size = 13) +
  theme(legend.position = "bottom")

print(p9d)
save_plot(p9d, "plot_9d_contract_period.png", width = 9, height = 6)
