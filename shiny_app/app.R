# =============================================================================
# SA Health Statistics — Alcohol and other drug-related hospitalisations
# DEMO v3 — 100% SYNTHETIC DATA. Do not interpret.
#
# This revision: Population groups shows ALL five breakdowns at once (chart
# type toggle only); pies use the selected measure and highlight the selected
# LHN; clicking a map area shows its population group breakdown (SEIFA,
# Remoteness, Indigenous status, Sex, Age group).
#
# Run: shiny::runApp()
# Packages: shiny, bslib, plotly, dplyr, DT, readr, leaflet, sf
# =============================================================================

library(shiny)
library(bslib)
library(plotly)
library(dplyr)
library(DT)
library(readr)
library(leaflet)

has_sf <- requireNamespace("sf", quietly = TRUE)

data_dir <- file.path("..", "data")
dat <- read_csv(file.path(data_dir, "sa_aod_hospitalisations.csv"),
                show_col_types = FALSE)
ref <- read_csv(file.path(data_dir, "diagnosis_ref.csv"),
                show_col_types = FALSE) |>
  rename(`Diagnosis Code` = diagnosis_code,
         `Diagnosis Description` = diagnosis_description,
         `Diagnosis Description Group` = diagnosis_group)

STATE  <- "South Australia (All LHNs)"
ALLDRUG <- "All drug-related"
LATEST <- "2024-25"; FIRST <- "2020-21"
yr_lv  <- unique(dat$financial_year)
lhn_all  <- c(STATE, sort(setdiff(unique(dat$lhn), STATE)))
drug_all <- c(ALLDRUG, sort(setdiff(unique(dat$drug_type), ALLDRUG)))

sa_blue <- "#00539f"; sa_teal <- "#00a9a5"; sa_grey <- "#5b6770"
palette10 <- c(sa_blue, sa_teal, "#e57200", "#7ab800", "#8f3f97",
               "#c60c30", "#00778b", "#d0d0ce", "#5b6770", "#f2a900")

meta_p <- file.path(data_dir, "data_metadata.json")
META <- if (file.exists(meta_p) &&
            requireNamespace("jsonlite", quietly = TRUE)) {
  jsonlite::fromJSON(meta_p)
} else list(data_as_of = "n/a", last_refresh = "n/a",
            reporting_period = "", version = "v4")
has_logo <- file.exists("www/logo.png")

app_css <- HTML("
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@500&display=swap');
body { background: #f6f8fa; }
h1, h2, h3, .nav-link { font-family: 'Archivo', sans-serif; }
.masthead { background: linear-gradient(100deg,#003a70 0%,#00539f 70%,#006ba6 100%);
  border-radius: 14px; padding: 20px 24px 16px 24px; margin-bottom: 12px;
  border-bottom: 4px solid #00a9a5; }
.masthead .eyebrow { color: #9fd9d7; font-family: 'IBM Plex Mono', monospace;
  font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; }
.masthead h1 { color: #fff; font-size: 1.5rem; margin: 2px 0 10px 0; }
.chip { display: inline-block; font-family: 'IBM Plex Mono', monospace;
  font-size: .70rem; padding: 3px 10px; border-radius: 999px; margin-right: 8px;
  background: rgba(255,255,255,.12); color: #e8f1f8;
  border: 1px solid rgba(255,255,255,.25); }
.chip-demo { background: #e57200; border-color: #e57200; color: #fff;
  font-weight: 600; }
.bslib-value-box { border: 1px solid #e3e8ee !important;
  border-left: 4px solid #00539f !important; border-radius: 10px;
  box-shadow: 0 1px 2px rgba(16,42,67,.06); }
.bslib-value-box .value-box-value { font-family: 'IBM Plex Mono', monospace; }
.nav-tabs .nav-link.active { border-bottom: 3px solid #00a9a5;
  color: #00539f; font-weight: 600; }
.footer { color: #5b6770; font-size: .75rem; text-align: center;
  padding: 16px 0 4px 0; font-family: 'IBM Plex Mono', monospace; }
")

MEASURES <- c("Rate per 100,000 population" = "rate_per_100k",
              "Number of hospitalisations"  = "count",
              "Mean length of stay (bed days)" = "mean_bed_days")
YLABS <- c(rate_per_100k = "Rate per 100,000", count = "Hospitalisations",
           mean_bed_days = "Mean bed days")

STRATS <- c("Sex" = "sex", "Age group" = "age_group",
            "Indigenous status" = "indigenous_status",
            "SEIFA quintile" = "seifa_quintile",
            "Remoteness" = "remoteness")
SHORT <- c("Q1 - most disadvantaged" = "Q1",
           "Q5 - least disadvantaged" = "Q5",
           "Major Cities of Australia" = "Major Cities",
           "Inner Regional Australia" = "Inner Regional",
           "Outer Regional Australia" = "Outer Regional",
           "Remote Australia" = "Remote",
           "Very Remote Australia" = "Very Remote")
shorten <- function(x) ifelse(x %in% names(SHORT), SHORT[x], x)

# ---- UI ---------------------------------------------------------------------
ui <- page_sidebar(
  title = tagList(
    if (has_logo) img(src = "logo.png", height = "34px",
                      style = "margin-right:12px;") else NULL,
    strong("SA Health Statistics"),
    span(" | Alcohol and other drug-related hospitalisations",
         style = "font-weight:300;")),
  theme = bs_theme(version = 5, preset = "shiny", primary = sa_blue,
                   secondary = sa_teal, base_font = font_google("Public Sans")),
  tags$head(tags$style(app_css)),

  div(class = "masthead",
    div(class = "eyebrow",
        "SA Health Statistics · Preventive Health SA (demo)"),
    h1("Alcohol and other drug-related hospitalisations"),
    span(class = "chip chip-demo", "DEMO · SYNTHETIC DATA"),
    span(class = "chip", paste("Data as of", META$data_as_of)),
    span(class = "chip", paste("Last refresh:", META$last_refresh)),
    span(class = "chip", textOutput("chip_sel", inline = TRUE))
  ),

  sidebar = sidebar(
    width = 330,
    h6("Indicator settings", class = "text-muted"),
    selectInput("drug", "Drug group (per diagnosis reference)",
                drug_all, ALLDRUG),
    radioButtons("measure", "Measure", MEASURES),
    selectInput("lhn", "Location (Local Health Network)", lhn_all, STATE),
    selectizeInput("extra_lhns", "Add LHNs to trend comparison",
                   setdiff(lhn_all, STATE), multiple = TRUE,
                   options = list(placeholder = "Select LHNs to overlay...")),
    helpText(sprintf("'%s' is always shown for reference.", STATE)),
    checkboxInput("ci", "Show 95% confidence intervals", TRUE),
    checkboxInput("show_map", "Show map side panel", TRUE),
    hr(),
    p(class = "small text-muted",
      "DEMO — synthetic data for prototyping only.
       Not actual SA hospitalisation statistics.")
  ),

  layout_columns(
    col_widths = c(4, 4, 4),
    value_box(title = paste0("Latest year (", LATEST, ")"),
              value = textOutput("vb1"), theme = "primary"),
    value_box(title = paste("Change vs", FIRST),
              value = textOutput("vb2"), theme = "secondary"),
    value_box(title = textOutput("vb3_title"),
              value = textOutput("vb3"), theme = "light")
  ),

  uiOutput("main_layout"),

  accordion(
    open = "Commentary — what can we learn from this data?",
    accordion_panel("Commentary — what can we learn from this data?",
                    uiOutput("commentary")),
    accordion_panel("Notes — technical details of this data",
                    uiOutput("notes"))
  ),

  div(class = "footer", sprintf(
    "SA AOD hospitalisations dashboard %s · reporting period %s ·
     data as of %s · last refresh %s · synthetic demonstration data",
    META$version, META$reporting_period, META$data_as_of,
    META$last_refresh))
)

# ---- Server -----------------------------------------------------------------
server <- function(input, output, session) {

  output$chip_sel <- renderText(paste(input$drug, "·", input$lhn))

  ycol <- reactive(input$measure)
  ylab <- reactive(YLABS[[input$measure]])
  is_rate <- reactive(input$measure == "rate_per_100k")

  totals <- dat |> filter(group_by == "Total")
  trend_lhns <- reactive(unique(c(STATE, input$lhn, input$extra_lhns)))
  trend <- reactive(totals |>
    filter(drug_type == input$drug, lhn %in% trend_lhns()) |>
    arrange(year_start))
  row_latest <- reactive(trend() |>
    filter(lhn == input$lhn, financial_year == LATEST))
  row_first <- reactive(trend() |>
    filter(lhn == input$lhn, financial_year == FIRST))

  output$vb1 <- renderText({
    if (nrow(row_latest()) == 0) return("n.p.")
    v <- row_latest()[[ycol()]]
    if (is_rate()) sprintf("%.1f per 100,000", v)
    else if (ycol() == "count") format(v, big.mark = ",")
    else sprintf("%.2f days", v)
  })
  output$vb2 <- renderText({
    if (nrow(row_latest()) == 0 || nrow(row_first()) == 0 ||
        row_first()[[ycol()]] == 0) return("n.p.")
    sprintf("%+.0f%%",
            (row_latest()[[ycol()]] / row_first()[[ycol()]] - 1) * 100)
  })
  output$vb3_title <- renderText(
    if (input$measure == "mean_bed_days")
      paste0("Hospitalisations, ", LATEST)
    else paste0("Mean bed days, ", LATEST))
  output$vb3 <- renderText({
    if (nrow(row_latest()) == 0) return("n.p.")
    if (input$measure == "mean_bed_days")
      format(row_latest()$count, big.mark = ",")
    else sprintf("%.2f", row_latest()$mean_bed_days)
  })

  # ---- Layout: tabs left, map right (toggle) ---------------------------------
  output$main_layout <- renderUI({
    strat_grid <- tagList(
      radioButtons("ct_strat", NULL,
                   c("Bar", "Line (trend by group)", "Pie"), inline = TRUE),
      p(class = "small text-muted", textOutput("strat_caption")),
      layout_columns(col_widths = c(6, 6),
                     plotlyOutput("strat_sex", height = "300px"),
                     plotlyOutput("strat_age_group", height = "300px")),
      layout_columns(col_widths = c(6, 6),
                     plotlyOutput("strat_indigenous_status", height = "300px"),
                     plotlyOutput("strat_seifa_quintile", height = "300px")),
      layout_columns(col_widths = c(6, 6),
                     plotlyOutput("strat_remoteness", height = "300px"), div())
    )
    tabs <- navset_card_tab(
      nav_panel("Trend",
        radioButtons("ct_trend", NULL, c("Line", "Bar"), inline = TRUE),
        plotlyOutput("trend_plot", height = "420px")),
      nav_panel("Population groups", strat_grid),
      nav_panel("Compare regions",
        radioButtons("ct_reg", NULL, c("Bar", "Pie"), inline = TRUE),
        plotlyOutput("reg_plot", height = "460px")),
      nav_panel("Data table",
        DTOutput("tbl"),
        downloadButton("dl", "Download data (CSV)", class = "btn-sm mt-2")),
      nav_panel("Diagnosis reference",
        p(strong("Diagnosis Reference Table"),
          " — ICD-10-AM codes defining each drug group."),
        DTOutput("ref_tbl"),
        downloadButton("dl_ref", "Download reference table (CSV)",
                       class = "btn-sm mt-2"))
    )
    if (isTRUE(input$show_map)) {
      layout_columns(col_widths = c(8, 4), tabs,
        card(card_header(
               radioButtons("map_level", NULL, c("SA3" = "sa3", "SA2" = "sa2"),
                            inline = TRUE)),
             uiOutput("map_ui"),
             uiOutput("area_detail")))
    } else tabs
  })

  output$strat_caption <- renderText(paste0(
    "All population group breakdowns — ", input$drug, ", ", input$lhn, ", ",
    tolower(ylab()),
    if (!identical(input$ct_strat, "Line (trend by group)"))
      paste0(", ", LATEST) else ""))

  # ---- Trend -------------------------------------------------------------------
  output$trend_plot <- renderPlotly({
    req(input$ct_trend)
    p <- plot_ly()
    for (i in seq_along(trend_lhns())) {
      l <- trend_lhns()[i]
      d <- trend() |> filter(lhn == l)
      if (nrow(d) == 0) next
      colr <- palette10[(i - 1) %% 10 + 1]
      if (input$ct_trend == "Line") {
        if (input$ci && is_rate() && l == input$lhn) {
          p <- p |> add_ribbons(data = d, x = ~factor(financial_year, yr_lv),
            ymin = ~rate_lcl, ymax = ~rate_ucl,
            fillcolor = "rgba(0,83,159,0.12)",
            line = list(color = "transparent"), hoverinfo = "skip",
            showlegend = FALSE)
        }
        p <- p |> add_trace(data = d, x = ~factor(financial_year, yr_lv),
          y = d[[ycol()]], type = "scatter", mode = "lines+markers", name = l,
          line = list(color = colr, width = 3,
                      dash = if (l == STATE) "dash" else "solid"),
          marker = list(color = colr, size = 7))
      } else {
        p <- p |> add_trace(data = d, x = ~factor(financial_year, yr_lv),
          y = d[[ycol()]], type = "bar", name = l,
          marker = list(color = colr))
      }
    }
    p |> layout(xaxis = list(title = "Financial year"),
                yaxis = list(title = ylab(), rangemode = "tozero"),
                barmode = "group", hovermode = "x unified",
                legend = list(orientation = "h", y = -0.25))
  })

  # ---- Regions: measure-aware, selected LHN highlighted --------------------------
  output$reg_plot <- renderPlotly({
    req(input$ct_reg)
    reg <- totals |>
      filter(drug_type == input$drug, financial_year == LATEST,
             lhn != STATE)
    if (input$ct_reg == "Bar") {
      reg <- reg |> arrange(.data[[ycol()]])
      cols <- ifelse(reg$lhn == input$lhn, sa_blue, sa_teal)
      p <- plot_ly(reg, x = reg[[ycol()]],
                   y = ~reorder(lhn, reg[[ycol()]]), type = "bar",
                   orientation = "h", marker = list(color = cols),
                   error_x = if (is_rate() && input$ci)
                     list(array = reg$rate_ucl - reg$rate_per_100k,
                          arrayminus = reg$rate_per_100k - reg$rate_lcl,
                          color = sa_grey) else NULL) |>
        layout(xaxis = list(title = ylab()), yaxis = list(title = ""),
               title = paste0("Local Health Networks, ", LATEST, " — ",
                              ylab()))
      sa_row <- totals |> filter(drug_type == input$drug,
                                 financial_year == LATEST, lhn == STATE)
      if (is_rate() && nrow(sa_row)) {
        v <- sa_row[[ycol()]]
        p <- p |> layout(
          shapes = list(list(type = "line", x0 = v, x1 = v, y0 = -0.5,
                             y1 = 8.5,
                             line = list(color = sa_blue, dash = "dash"))),
          annotations = list(list(x = v, y = 8.5, text = "SA average",
                                  showarrow = FALSE, yanchor = "bottom",
                                  font = list(color = sa_blue))))
      }
      p
    } else {
      plot_ly(reg, values = reg[[ycol()]], labels = ~lhn, type = "pie",
              pull = ifelse(reg$lhn == input$lhn, 0.12, 0),
              marker = list(colors = palette10,
                            line = list(color = "white", width = 1))) |>
        layout(title = paste0("Share of ", tolower(ylab()), " by LHN, ",
                              LATEST, " (selected LHN pulled out)"))
    }
  })

  # ---- Population groups: all five at once ------------------------------------------
  make_strat_plot <- function(strat_label, col) {
    renderPlotly({
      req(input$ct_strat)
      sd <- dat |> filter(group_by == strat_label,
                          drug_type == input$drug, lhn == input$lhn) |>
        mutate(label = shorten(.data[[col]]))
      lv <- shorten(sort(unique(sd[[col]])))
      latest_sd <- sd |> filter(financial_year == LATEST)

      p <- if (input$ct_strat == "Bar") {
        plot_ly(latest_sd, x = ~factor(label, lv),
                y = latest_sd[[ycol()]], type = "bar",
                marker = list(color = sa_teal),
                error_y = if (is_rate() && input$ci)
                  list(array = latest_sd$rate_ucl - latest_sd$rate_per_100k,
                       arrayminus = (latest_sd$rate_per_100k
                                     - latest_sd$rate_lcl),
                       color = sa_grey) else NULL) |>
          layout(showlegend = FALSE)
      } else if (input$ct_strat == "Line (trend by group)") {
        q <- plot_ly()
        for (i in seq_along(lv)) {
          d <- sd |> filter(label == lv[i]) |> arrange(year_start)
          if (nrow(d) == 0) next
          q <- q |> add_trace(data = d,
            x = ~factor(financial_year, yr_lv), y = d[[ycol()]],
            type = "scatter", mode = "lines+markers", name = lv[i],
            marker = list(size = 5),
            line = list(color = palette10[(i - 1) %% 10 + 1], width = 2))
        }
        q |> layout(hovermode = "x unified",
                    legend = list(orientation = "h", y = -0.3,
                                  font = list(size = 9)))
      } else {
        plot_ly(latest_sd, values = latest_sd[[ycol()]], labels = ~label,
                type = "pie", textinfo = "label+percent",
                marker = list(colors = palette10,
                              line = list(color = "white", width = 1))) |>
          layout(showlegend = FALSE)
      }
      p |> layout(title = list(text = strat_label, font = list(size = 13)),
                  margin = list(l = 10, r = 10, t = 40, b = 10),
                  xaxis = list(title = ""), yaxis = list(title = ""))
    })
  }
  for (nm in names(STRATS)) local({
    label <- nm; col <- STRATS[[nm]]
    output[[paste0("strat_", col)]] <- make_strat_plot(label, col)
  })

  # ---- Map side panel + click detail --------------------------------------------------
  clicked_area <- reactiveVal(NULL)
  observeEvent(input$map_level, clicked_area(NULL))

  map_files <- reactive({
    req(input$map_level)
    list(gj = file.path(data_dir, sprintf("sa_%s_boundaries.geojson",
                                          input$map_level)),
         mp = file.path(data_dir, sprintf("sa_%s_map.csv", input$map_level)),
         gr = file.path(data_dir, sprintf("sa_%s_groups.csv",
                                          input$map_level)))
  })
  map_ok <- reactive(file.exists(map_files()$gj) &&
                     file.exists(map_files()$mp) && has_sf)

  output$map_ui <- renderUI({
    if (!map_ok()) {
      div(class = "alert alert-info m-2", HTML(sprintf(
        "<b>%s map not available yet</b> (or package 'sf' missing).<br>
         Download the ABS ASGS Ed 3 (2021) %s shapefile from the
         <a href='https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files'
         target='_blank'>ABS boundary files</a> page, then run in
         <code>data/</code>:<br>
         <code>python prepare_geodata.py --shp &lt;path&gt; --level %s</code><br>
         <code>python generate_episodes.py</code><br>
         <code>python aggregate.py</code>",
        toupper(input$map_level), toupper(input$map_level),
        input$map_level)))
    } else tagList(
      leafletOutput("map_plot", height = "440px"),
      p(class = "small text-muted mt-1",
        "Hover an area for details; click an area for its population
         group breakdown."))
  })

  map_data <- reactive({
    req(map_ok())
    read_csv(map_files()$mp, show_col_types = FALSE) |>
      filter(drug_type == input$drug) |>
      mutate(area_code = as.character(area_code))
  })

  output$map_plot <- renderLeaflet({
    req(map_ok())
    LVL <- toupper(input$map_level)
    shp <- sf::st_read(map_files()$gj, quiet = TRUE) |>
      mutate(area_code = as.character(area_code)) |>
      left_join(map_data() |>
                  select(area_code, episodes, population, rate_per_100k,
                         seifa_quintile),
                by = "area_code")
    pal <- colorNumeric("YlGnBu", shp$rate_per_100k)
    labels <- sprintf(
      "<b>%s</b><br>Respective %s code: %s<br>Total %s Episodes: %s<br>
       %s Population (%s): %s<br>Rate per 100k (%s): %.1f<br>
       Quintile Details: %s",
      shp$area_name, LVL, shp$area_code, input$drug,
      format(shp$episodes, big.mark = ","), LVL, LATEST,
      format(shp$population, big.mark = ","), LATEST, shp$rate_per_100k,
      shp$seifa_quintile) |> lapply(HTML)
    leaflet(shp) |>
      addProviderTiles(providers$CartoDB.Positron) |>
      addPolygons(layerId = ~area_code,
                  fillColor = ~pal(rate_per_100k), fillOpacity = 0.75,
                  weight = 1, color = "#ffffff", label = labels,
                  highlightOptions = highlightOptions(
                    weight = 2, color = sa_blue, bringToFront = TRUE)) |>
      addLegend(pal = pal, values = ~rate_per_100k, title = "Rate /100k",
                position = "bottomright") |>
      setView(lng = 137.5, lat = -33.5, zoom = 5)
  })

  observeEvent(input$map_plot_shape_click,
               clicked_area(input$map_plot_shape_click$id))

  output$area_detail <- renderUI({
    req(map_ok(), clicked_area())
    m <- map_data() |> filter(area_code == clicked_area())
    req(nrow(m) == 1)
    tagList(
      hr(),
      h6(sprintf("%s (%s %s)", m$area_name, toupper(input$map_level),
                 m$area_code)),
      HTML(sprintf(
        "<p class='small'><b>SEIFA Score:</b> %s · <b>Remoteness:</b> %s<br>
         %s, %s: <b>%s episodes</b>, rate <b>%.1f</b> per 100,000</p>",
        m$seifa_quintile, m$remoteness, input$drug, LATEST,
        format(m$episodes, big.mark = ","), m$rate_per_100k)),
      plotlyOutput("area_groups", height = "420px"),
      p(class = "small text-muted",
        "Small counts would be suppressed (n < 5) in production.")
    )
  })

  output$area_groups <- renderPlotly({
    req(map_ok(), clicked_area(), file.exists(map_files()$gr))
    g <- read_csv(map_files()$gr, show_col_types = FALSE) |>
      mutate(area_code = as.character(area_code)) |>
      filter(area_code == clicked_area(), drug_type == input$drug)
    req(nrow(g) > 0)
    plots <- lapply(c("Sex", "Indigenous status", "Age group"), function(dim) {
      d <- g |> filter(dimension == dim) |> arrange(level)
      plot_ly(d, x = ~episodes, y = ~level, type = "bar",
              orientation = "h", marker = list(color = sa_teal),
              text = ~episodes, textposition = "outside",
              showlegend = FALSE) |>
        layout(annotations = list(list(
                 text = paste0("<b>", dim, " (episodes)</b>"),
                 xref = "paper", yref = "paper", x = 0, y = 1.15,
                 showarrow = FALSE, font = list(size = 11))),
               xaxis = list(visible = FALSE),
               yaxis = list(title = "", tickfont = list(size = 10)))
    })
    subplot(plots, nrows = 3, shareX = FALSE, margin = 0.09)
  })

  # ---- Tables + downloads ---------------------------------------------------------------
  tbl_data <- reactive(dat |>
    filter(drug_type == input$drug, lhn == input$lhn) |>
    select(-indicator))
  output$tbl <- renderDT(tbl_data(), options = list(pageLength = 12),
                         rownames = FALSE)
  output$ref_tbl <- renderDT(ref, rownames = FALSE, filter = "top",
                             options = list(pageLength = 12))
  output$dl <- downloadHandler(
    filename = \() sprintf("sa_aod_%s.csv", Sys.Date()),
    content  = \(f) write_csv(tbl_data(), f))
  output$dl_ref <- downloadHandler(
    filename = \() "diagnosis_ref.csv",
    content  = \(f) write_csv(ref, f))

  # ---- Commentary + Notes -----------------------------------------------------------------
  output$commentary <- renderUI({
    rl <- row_latest(); rf <- row_first()
    if (nrow(rl) == 0 || nrow(rf) == 0 || rf$rate_per_100k == 0) {
      return(HTML(sprintf(
        "<p>Counts for <b>%s</b> in %s are too small to report reliably for
         one or both comparison years (in production these cells would be
         suppressed, n &lt; 5). Select a larger group or region for
         commentary.</p>", input$drug, input$lhn)))
    }
    chg <- (rl$rate_per_100k / rf$rate_per_100k - 1) * 100
    dirn <- if (chg > 3) "increased" else if (chg < -3) "decreased" else
      "remained relatively stable"
    reg <- totals |> filter(drug_type == input$drug,
                            financial_year == LATEST, lhn != STATE,
                            count >= 5)
    ratio <- function(grp, col, num, den) {
      d <- dat |> filter(group_by == grp, drug_type == input$drug,
                         lhn == STATE, financial_year == LATEST)
      n <- d |> filter(.data[[col]] == num)
      dn <- d |> filter(.data[[col]] == den)
      if (nrow(n) && nrow(dn) && dn$rate_per_100k > 0 && n$count >= 5)
        n$rate_per_100k / dn$rate_per_100k else NA
    }
    fmt <- function(r, s) if (!is.na(r))
      sprintf("<b>%.1f times higher %s</b>", r, s) else
      sprintf("not reportable %s (small numbers)", s)
    r_ind <- ratio("Indigenous status", "indigenous_status",
                   "First Nations", "Non-Indigenous")
    r_sei <- ratio("SEIFA quintile", "seifa_quintile",
                   "Q1 - most disadvantaged", "Q5 - least disadvantaged")
    r_rem <- ratio("Remoteness", "remoteness",
                   "Very Remote Australia", "Major Cities of Australia")
    reg_html <- if (nrow(reg) >= 2) {
      hi <- reg |> slice_max(rate_per_100k, n = 1)
      lo <- reg |> slice_min(rate_per_100k, n = 1)
      if (lo$rate_per_100k > 0) sprintf(
        "<p>Across Local Health Networks in %s, rates were highest in
         <b>%s</b> (%.1f) and lowest in <b>%s</b> (%.1f) — a %.1f-fold
         difference.</p>", LATEST, hi$lhn, hi$rate_per_100k, lo$lhn,
        lo$rate_per_100k, hi$rate_per_100k / lo$rate_per_100k) else ""
    } else ""
    HTML(paste0(sprintf(
      "<p>In %s, the age-standardised rate of %s hospitalisations
       <b>%s by %+.0f%%</b> between %s and %s (%.1f to %.1f per 100,000).
       Episodes in this group averaged <b>%.1f bed days</b> in %s (same-day
       episodes counted as one day).</p>",
      input$lhn, tolower(input$drug), dirn, chg, FIRST, LATEST,
      rf$rate_per_100k, rl$rate_per_100k, rl$mean_bed_days, LATEST),
      reg_html,
      "<p>Statewide, hospitalisation rates were ",
      fmt(r_ind, "for First Nations people than non-Indigenous people"), ", ",
      fmt(r_sei, "in the most disadvantaged SEIFA quintile (Q1) than the least
           disadvantaged (Q5)"), ", and ",
      fmt(r_rem, "in Very Remote areas than Major Cities"),
      ". Persistent socioeconomic and geographic gradients suggest prevention
       effort should be weighted toward disadvantaged and remote
       communities.</p>
       <p class='small text-muted'>Commentary is generated automatically from
       the current selection — synthetic data, do not interpret.</p>"))
  })

  output$notes <- renderUI(HTML(sprintf(
    "<ul>
     <li><b>Source (intended):</b> SA admitted patient activity data (ISAAC);
       this demo uses synthetic unit-record episodes generated by
       <code>data/generate_episodes.py</code> (seed 2026) and aggregated by
       <code>data/aggregate.py</code>.</li>
     <li><b>Indicator definition:</b> episodes with a principal diagnosis
       mapped to one of 15 drug groups via the Diagnosis Reference Table (see
       tab); 'All drug-related' is the union of all groups.</li>
     <li><b>Bed days:</b> date of discharge (<code>DischSummaryDtm</code>)
       minus date of admission (<code>AdmDateTime</code>), with same-day
       episodes counted as <b>1 patient day</b> (AIHW convention); reported
       as the mean per episode.</li>
     <li><b>Rates:</b> directly age-standardised to the 2001 Australian
       standard population (label only in this demo), per 100,000; 95%% CIs
       assume Poisson counts.</li>
     <li><b>Geography:</b> LHNs per SA Health; SA2/SA3 per ABS ASGS Ed 3
       (2021); Remoteness per ASGS Remoteness Structure; SEIFA quintiles per
       ABS IRSD.</li>
     <li><b>Indigenous status</b> as recorded at admission; subject to
       under-identification.</li>
     <li><b>Diagnosis descriptions</b> are generated from standard ICD-10
       category wording; fifth-character (ICD-10-AM) subdivisions are
       labelled generically — replace with ACCD ICD-10-AM tabular list
       wording for production.</li>
     <li><b>Suppression (production rule):</b> counts under 5 suppressed
       ('n.p.'); rates on counts under 20 flagged as unstable.</li>
     <li><b>Reporting period:</b> financial years %s to %s.</li>
     </ul>", FIRST, LATEST)))
}

shinyApp(ui, server)
