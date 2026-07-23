# install.packages("readxl")
# install.packages("DescTools")

rm(list = ls())

library(readxl)
library(DescTools)

# set the working directory to this script's own folder (code/), whether the
# script is run via Rscript or sourced inside RStudio; data paths below are
# relative to it (../output, ../modified_data).
args <- commandArgs(trailingOnly = FALSE)
script <- sub("^--file=", "", args[grep("^--file=", args)])
script <- gsub("~\\+~", " ", script)   # Rscript encodes spaces in --file= as ~+~
here <- if (length(script)) dirname(script) else dirname(rstudioapi::getActiveDocumentContext()$path)
setwd(here)

# Paired design: each paragraph is coded twice — surface (dictionary) and deeper (LLM).
cats <- c("addiction", "attachment", "both", "neither")

# ==============================================================================
# STUDY 1: LEGAL COMPLAINTS
# ==============================================================================

legal <- read_excel("../output/legal_paragraphs_llm.xlsx")   # production = pass 2
cat("\nLegal paragraphs:", nrow(legal), "\n")

# ---- within-LLM reliability: pass 1 vs pass 2 (production), few-shots excluded ----
legal_p1 <- read_excel("../output/legal_paragraphs_llm_p1.xlsx")
w <- merge(legal_p1[, c("case", "para_seq", "deeper_meaning", "is_fewshot")],
           legal[, c("case", "para_seq", "deeper_meaning")],
           by = c("case", "para_seq"), suffixes = c("_p1", "_p2"))
w <- w[!as.logical(w$is_fewshot), ]
cat(sprintf("Within-LLM kappa (two runs): %.2f\n",
    CohenKappa(table(factor(w$deeper_meaning_p1, cats), factor(w$deeper_meaning_p2, cats)))))

# ---- human vs LLM reliability: stratified N=150 consensus vs LLM ----
cons <- read_excel("../modified_data/CODED Legal IRR v7 STRATIFIED N150.xlsx", sheet = "Consensus")
cons$final_code <- tolower(trimws(cons$final_code))
irr <- merge(cons[, c("case", "para_seq", "final_code")],
             legal[, c("case", "para_seq", "deeper_meaning")],
             by = c("case", "para_seq"), all.x = TRUE)
irr$deeper_meaning <- tolower(trimws(irr$deeper_meaning))
cat(sprintf("Human vs LLM: N = %d, kappa = %.3f, raw = %.1f%%\n", nrow(irr),
    CohenKappa(table(factor(irr$final_code, cats), factor(irr$deeper_meaning, cats))),
    100 * mean(irr$final_code == irr$deeper_meaning)))

# ---- surface counts + ratio (addiction 2.29x attachment) ----
surf <- table(factor(legal$surface_meaning, levels = cats))
cat("\nSurface counts:\n"); print(surf)
cat(sprintf("Surface addiction/attachment: %.4f\n", surf["addiction"] / surf["attachment"]))

# ---- deeper counts + ratio (attachment 3.75x addiction) ----
deep <- table(factor(legal$deeper_meaning, levels = cats))
cat("\nDeeper counts:\n"); print(deep)
cat(sprintf("Deeper attachment/addiction: %.4f\n", deep["attachment"] / deep["addiction"]))

# ---- per-complaint addiction vs attachment counts (attachment dominates in 12 of 14) ----
# One row per complaint; addiction/attachment paragraph counts at both levels.
per_case <- function(col) {
  t <- table(legal$case, factor(legal[[col]], levels = cats))
  data.frame(addiction = t[, "addiction"], attachment = t[, "attachment"])
}
s_pc <- per_case("surface_meaning"); d_pc <- per_case("deeper_meaning")
case_tab <- data.frame(case = rownames(d_pc),
                       surface_addict = s_pc$addiction, surface_attach = s_pc$attachment,
                       deeper_addict  = d_pc$addiction, deeper_attach  = d_pc$attachment,
                       row.names = NULL)
case_tab <- case_tab[order(-case_tab$deeper_attach), ]
cat("\nPer-complaint addiction vs attachment counts:\n")
print(case_tab, row.names = FALSE)
cat(sprintf("Deeper attachment > addiction in %d of %d complaints.\n",
            sum(case_tab$deeper_attach > case_tab$deeper_addict), nrow(case_tab)))

# ---- surface x deeper crosstab (Panel C; ~5% of no-vocab paragraphs -> attachment) ----
sq <- table(surface = factor(legal$surface_meaning, levels = cats),
            deeper  = factor(legal$deeper_meaning,  levels = cats))
cat("\nSurface (rows) x Deeper (cols):\n"); print(sq)

# ---- Stuart-Maxwell test of marginal homogeneity ----
sm <- StuartMaxwellTest(sq)
cat(sprintf("\nStuart-Maxwell: chi2 = %.2f, df = %d, p = %.3g, w = %.3f\n",
            sm$statistic, sm$parameter, sm$p.value, sqrt(as.numeric(sm$statistic) / sum(sq))))

# ---- per-category McNemar post-hoc (continuity-corrected + exact), Holm-adjusted ----
N <- sum(sq); res <- data.frame(); praw <- numeric(0)
for (c in cats) {
  n_cc  <- sq[c, c]
  out_c <- sum(sq[c, ]) - n_cc            # surface = c, deeper != c (moved out)
  in_c  <- sum(sq[, c]) - n_cc            # surface != c, deeper = c (moved in)
  m     <- matrix(c(n_cc, out_c, in_c, N - out_c - in_c - n_cc), 2, byrow = TRUE)
  mc    <- suppressWarnings(mcnemar.test(m, correct = TRUE))
  praw  <- c(praw, mc$p.value)
  res   <- rbind(res, data.frame(
    category = c, moved_out = out_c, moved_in = in_c,
    direction = ifelse(in_c > out_c, "deeper > surface", "surface > deeper"),
    chi2 = round(as.numeric(mc$statistic), 3),
    p_raw = mc$p.value, p_exact = binom.test(out_c, out_c + in_c, 0.5)$p.value,
    cohen_g = round(abs(out_c / (out_c + in_c) - 0.5), 4)))
}
res$p_holm <- p.adjust(praw, method = "holm")   # Holm across the 4 categories
cat("\nPer-category McNemar (Holm-corrected):\n")
print(res, row.names = FALSE, digits = 4)

# ==============================================================================
# STUDY 2: MEDIA ARTICLES
# ==============================================================================

media <- read_excel("../output/media_paragraphs_llm.xlsx")

# Keep unique-usable paragraphs (usable article, not a cross-search duplicate).
keep <- as.logical(media$article_usable) & !as.logical(media$is_duplicate)
keep[is.na(keep)] <- FALSE
media <- media[keep, ]
cat("\nMedia paragraphs:", nrow(media), "\n")

# ---- within-LLM reliability: pass 1 vs pass 2 (production), few-shots excluded ----
media_p1 <- read_excel("../output/media_paragraphs_llm_p1.xlsx")
media_p1 <- media_p1[as.logical(media_p1$article_usable) & !as.logical(media_p1$is_duplicate), ]
w <- merge(media_p1[, c("document_id", "para_idx", "deeper_meaning", "is_fewshot")],
           media[, c("document_id", "para_idx", "deeper_meaning")],
           by = c("document_id", "para_idx"), suffixes = c("_p1", "_p2"))
w <- w[!as.logical(w$is_fewshot), ]
cat(sprintf("Within-LLM kappa (two runs): %.2f\n",
    CohenKappa(table(factor(w$deeper_meaning_p1, cats), factor(w$deeper_meaning_p2, cats)))))

# ---- human vs LLM reliability: stratified N=150 consensus vs LLM ----
cons <- read_excel("../modified_data/CODED fixed Media IRR v7 STRATIFIED N150.xlsx", sheet = "Consensus")
cons$final_code <- tolower(trimws(cons$final_code))
irr <- merge(cons[, c("document_id", "para_idx", "final_code")],
             media[, c("document_id", "para_idx", "deeper_meaning")],
             by = c("document_id", "para_idx"), all.x = TRUE)
irr$deeper_meaning <- tolower(trimws(irr$deeper_meaning))
cat(sprintf("Human vs LLM: N = %d, kappa = %.3f, raw = %.1f%%\n", nrow(irr),
    CohenKappa(table(factor(irr$final_code, cats), factor(irr$deeper_meaning, cats))),
    100 * mean(irr$final_code == irr$deeper_meaning)))

# ---- surface counts + ratio (addiction 1.27x attachment) ----
surf <- table(factor(media$surface_meaning, levels = cats))
cat("\nSurface counts:\n"); print(surf)
cat(sprintf("Surface addiction/attachment: %.4f\n", surf["addiction"] / surf["attachment"]))

# ---- deeper counts + ratio (attachment 7.84x addiction) ----
deep <- table(factor(media$deeper_meaning, levels = cats))
cat("\nDeeper counts:\n"); print(deep)
cat(sprintf("Deeper attachment/addiction: %.4f\n", deep["attachment"] / deep["addiction"]))

# ---- surface x deeper crosstab (Panel C; ~5% of no-vocab paragraphs -> attachment) ----
sq <- table(surface = factor(media$surface_meaning, levels = cats),
            deeper  = factor(media$deeper_meaning,  levels = cats))
cat("\nSurface (rows) x Deeper (cols):\n"); print(sq)

# ---- Stuart-Maxwell test of marginal homogeneity ----
sm <- StuartMaxwellTest(sq)
cat(sprintf("\nStuart-Maxwell: chi2 = %.2f, df = %d, p = %.3g, w = %.3f\n",
            sm$statistic, sm$parameter, sm$p.value, sqrt(as.numeric(sm$statistic) / sum(sq))))

# ---- per-category McNemar post-hoc (continuity-corrected + exact), Holm-adjusted ----
N <- sum(sq); res <- data.frame(); praw <- numeric(0)
for (c in cats) {
  n_cc  <- sq[c, c]
  out_c <- sum(sq[c, ]) - n_cc            # surface = c, deeper != c (moved out)
  in_c  <- sum(sq[, c]) - n_cc            # surface != c, deeper = c (moved in)
  m     <- matrix(c(n_cc, out_c, in_c, N - out_c - in_c - n_cc), 2, byrow = TRUE)
  mc    <- suppressWarnings(mcnemar.test(m, correct = TRUE))
  praw  <- c(praw, mc$p.value)
  res   <- rbind(res, data.frame(
    category = c, moved_out = out_c, moved_in = in_c,
    direction = ifelse(in_c > out_c, "deeper > surface", "surface > deeper"),
    chi2 = round(as.numeric(mc$statistic), 3),
    p_raw = mc$p.value, p_exact = binom.test(out_c, out_c + in_c, 0.5)$p.value,
    cohen_g = round(abs(out_c / (out_c + in_c) - 0.5), 4)))
}
res$p_holm <- p.adjust(praw, method = "holm")   # Holm across the 4 categories
cat("\nPer-category McNemar (Holm-corrected):\n")
print(res, row.names = FALSE, digits = 4)
