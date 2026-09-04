"""Colors, type and chart furniture for the Power BI report.

Every visual in powerbi/grid_stress.Report reads its styling from here, via
the generated theme file. Change a color or a font size in this file, run
`make powerbi`, and it changes on all six pages at once. Nothing in the report
definition sets its own colors.
"""

# --- palette ---------------------------------------------------------------
NAVY = "#123A5F"      # headings and the header band
INK = "#1B2A38"       # body text
SLATE = "#5A6B7C"     # secondary text and axis labels
LINE = "#DCE2E8"      # card borders
GRIDLINE = "#EDF0F4"  # value-axis gridlines
PAGEBG = "#F2F4F7"    # page background behind the cards
OUTSPACE = "#E4E9EF"  # the area outside the canvas
CARD = "#FFFFFF"
STRIPBG = "#E9EDF2"   # footer band
HEADER_SUB = "#9FB6CC"

BLUE = "#2E6DA4"      # series 1, always the normal-hours measure
DEEP = "#12405F"      # series 2, always the stress-hours measure
AMBER = "#C8992A"
RED = "#B4413C"       # only ever a zero reference line
GREY = "#B9C2CB"
TEAL = "#4E8098"

# Order matters: the first measure dropped on a chart takes the first color.
DATA_COLORS = [BLUE, DEEP, AMBER, TEAL, GREY, RED, "#7A9BB8", "#8C6D1F"]

# --- type ------------------------------------------------------------------
FONT = "Segoe UI"
FONT_BOLD = "Segoe UI Semibold"
FONT_LIGHT = "Segoe UI Light"

PT_VISUAL_TITLE = 11      # the name of the chart
PT_KPI_LABEL = 8.5        # the small label above a KPI number
PT_KPI_VALUE = 24         # the KPI number itself
PT_KPI_CONTEXT = 8        # the unit line under a KPI number
PT_AXIS = 9
PT_BODY = 9
PT_HEADER_TITLE = 14.5
PT_HEADER_EYEBROW = 8.5
PT_FOOTER = 7.5


def _solid(c):
    return {"solid": {"color": c}}


def build_theme():
    return {
        "name": "Grid Stress",
        "dataColors": DATA_COLORS,
        "foreground": INK,
        "foregroundNeutralSecondary": SLATE,
        "foregroundNeutralTertiary": GREY,
        "background": CARD,
        "backgroundLight": PAGEBG,
        "backgroundNeutral": STRIPBG,
        "tableAccent": BLUE,
        "good": "#2E7D5B",
        "neutral": AMBER,
        "bad": RED,
        "maximum": DEEP,
        "center": GREY,
        "minimum": "#E4EAF0",
        "textClasses": {
            "title":   {"fontFace": FONT_BOLD, "fontSize": PT_VISUAL_TITLE, "color": NAVY},
            "header":  {"fontFace": FONT_BOLD, "fontSize": 10, "color": NAVY},
            "label":   {"fontFace": FONT, "fontSize": PT_AXIS, "color": SLATE},
            "callout": {"fontFace": FONT_LIGHT, "fontSize": PT_KPI_VALUE, "color": NAVY},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": _solid(CARD), "transparency": 0}],
                    "border": [{"show": True, "color": _solid(LINE), "radius": 4}],
                    "padding": [{"top": 10, "bottom": 10, "left": 12, "right": 12}],
                    "dropShadow": [{"show": False}],
                    "title": [{"show": True, "fontColor": _solid(NAVY),
                               "fontSize": PT_VISUAL_TITLE, "fontFamily": FONT_BOLD,
                               "alignment": "left", "titleWrap": True,
                               "background": _solid(CARD)}],
                    "spacing": [{"customizeSpacing": True, "spaceBelowTitle": 6}],
                    "categoryAxis": [{"show": True, "showAxisTitle": False,
                                      "gridlineShow": False, "fontSize": PT_AXIS,
                                      "fontFamily": FONT, "labelColor": _solid(SLATE),
                                      "lineColor": _solid(LINE),
                                      "concatenateLabels": False}],
                    "valueAxis": [{"show": True, "showAxisTitle": False,
                                   "gridlineShow": True,
                                   "gridlineColor": _solid(GRIDLINE),
                                   "gridlineThickness": 1, "gridlineStyle": "solid",
                                   "fontSize": PT_AXIS, "fontFamily": FONT,
                                   "labelColor": _solid(SLATE)}],
                    "legend": [{"show": True, "position": "TopLeft", "showTitle": False,
                                "fontSize": PT_AXIS, "fontFamily": FONT,
                                "labelColor": _solid(SLATE)}],
                    "labels": [{"fontSize": PT_AXIS, "fontFamily": FONT, "color": _solid(INK)}],
                    "visualHeader": [{"show": True,
                                      "showVisualInformationButton": False,
                                      "showVisualWarningButton": False,
                                      "showPinButton": False,
                                      "showSmartNarrativeButton": False,
                                      "showCommentButton": False,
                                      "showDrillToggleButton": False,
                                      "showSeeDataLayoutToggleButton": False,
                                      "transparency": 100, "foreground": _solid(SLATE)}],
                }
            },
            "page": {
                "*": {
                    "background": [{"color": _solid(PAGEBG), "transparency": 0}],
                    "outspace": [{"color": _solid(OUTSPACE), "transparency": 0}],
                    "outspacePane": [{"backgroundColor": _solid(CARD),
                                      "foregroundColor": _solid(INK),
                                      "borderColor": _solid(LINE)}],
                }
            },
            "card": {
                "*": {
                    "labels": [{"fontSize": PT_KPI_VALUE, "fontFamily": FONT_LIGHT,
                                "color": _solid(NAVY)}],
                    "categoryLabels": [{"show": True, "fontSize": PT_KPI_CONTEXT,
                                        "fontFamily": FONT, "color": _solid(SLATE)}],
                    "wordWrap": [{"show": True}],
                }
            },
            "tableEx": {
                "*": {
                    "grid": [{"gridVertical": False, "gridHorizontal": True,
                              "gridHorizontalColor": _solid(GRIDLINE),
                              "gridHorizontalWeight": 1, "rowPadding": 3,
                              "outlineColor": _solid(LINE), "outlineWeight": 1}],
                    "columnHeaders": [{"fontColor": _solid(NAVY), "backColor": _solid(CARD),
                                       "fontSize": PT_AXIS, "fontFamily": FONT_BOLD,
                                       "wordWrap": True, "outline": "BottomOnly",
                                       "autoSizeColumnWidth": True}],
                    "values": [{"fontColor": _solid(INK), "fontSize": PT_AXIS,
                                "fontFamily": FONT, "backColor": _solid(CARD),
                                "backColorSecondary": _solid("#F7F9FB"),
                                "urlIcon": False, "wordWrap": True}],
                    "total": [{"fontColor": _solid(NAVY), "backColor": _solid(CARD),
                               "fontSize": PT_AXIS, "fontFamily": FONT_BOLD,
                               "outline": "TopOnly"}],
                }
            },
            "slicer": {
                "*": {
                    "header": [{"show": False}],
                    "items": [{"fontColor": _solid(INK), "background": _solid(CARD),
                               "fontSize": PT_AXIS, "fontFamily": FONT, "outline": "None"}],
                    "padding": [{"top": 6, "bottom": 6, "left": 10, "right": 10}],
                }
            },
            "textbox": {"*": {"padding": [{"top": 12, "bottom": 12, "left": 14, "right": 14}]}},
            "lineChart": {"*": {"lineStyles": [{"strokeWidth": 2, "showMarker": False}]}},
            "scatterChart": {"*": {"fillPoint": [{"show": True}],
                                   "categoryLabels": [{"show": True, "fontSize": PT_AXIS,
                                                       "color": _solid(SLATE)}]}},
        },
    }
