"""
===============================================================================
 REGULATOR CONSTRUCTION MODEL  -  Python port of the HTML training aid
 Prepared for: Engr. Arup Chakraborty, Executive Engineer (Civil),
               Engineering Academy, BPDB-BWDB, Kaptai
===============================================================================

 Four views, eleven construction stages, two tide states - the same content as
 the HTML file, but driven by a parameter list instead of fixed coordinates.

     from regulator import Regulator
     r = Regulator()                       # default 3-vent structure
     r.section(11, tide="low").show()      # one view, one stage
     r.export_frames("frames")             # 48 PNGs, 1920x1080
     r.export_plates("plates.pdf")         # every stage on one PDF
     r.export_video("regulator.mp4")       # needs ffmpeg on PATH

 Change the structure, not the drawing code:

     r = Regulator(n_vent=2, vent_span=1.5, pile_len=15.0,
                   floor_c_len=8.5, floor_r_len=10.5)

 Dimensions are metres, levels are m PWD.
 Matplotlib only - no other packages required.
===============================================================================
"""

from dataclasses import dataclass, field, replace
import math, os, subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle, Circle, FancyArrow
from matplotlib.backends.backend_pdf import PdfPages


# ----------------------------------------------------------------- palette
class P:
    sheet   = "#cdd9dd"
    sheet2  = "#c2d0d5"
    room    = "#0d1a20"
    ink     = "#16242e"
    line    = "#2b4453"
    conc    = "#b4b8b2"
    concd   = "#8d938d"
    beyond  = "#c7cbc5"
    soil    = "#b0966c"
    water   = "#3d8494"
    steel   = "#9e4630"
    spile   = "#4f7386"
    accent  = "#2f7d50"
    brick   = "#aeb3ae"
    dim     = "#6b7a83"


# -------------------------------------------------------------- parameters
@dataclass
class Params:
    # vents ------------------------------------------------------------------
    n_vent: int = 3
    vent_span: float = 1.5        # clear span of one vent
    pier_t: float = 0.60
    abut_t: float = 1.20
    box_len: float = 6.00         # length of the box along the flow

    # levels, m PWD ----------------------------------------------------------
    el_deck: float = 6.20         # EL E3
    el_wing: float = 4.50         # EL E4, top of wing and return walls
    el_hfl: float = 3.98          # high flood level, river side
    el_bank: float = 2.20         # crest of the pitched side slope
    el_floor_c: float = -1.65     # EL E1, country side floor
    el_floor_r: float = -2.80     # EL E2, river side floor / basin
    el_ltl: float = -1.50         # low tide level
    el_ret: float = 1.60          # retained irrigation level

    # floor and foundation ---------------------------------------------------
    slab_t: float = 0.90
    blind_t: float = 0.25
    floor_c_len: float = 6.50     # country floor, box face to its end
    glacis_len: float = 4.00
    floor_r_len: float = 14.5     # river floor: longer, it holds the jump
    cut_c_len: float = 7.00       # U/S cut-off, shorter
    cut_r_len: float = 9.00       # D/S cut-off, driven deeper
    pile_len: float = 18.0        # bearing pile, set by bearing capacity
    pile_spac: float = 1.50
    toe_t: float = 0.90
    toe_d: float = 1.40

    # protection works -------------------------------------------------------
    apron_len: float = 9.30       # launching apron = pitched slope length
    apron_t: float = 0.60
    filter_t: float = 0.30
    slope_bank: float = 2.0
    slope_emb_c: float = 2.0
    slope_emb_r: float = 3.0

    # energy dissipation, from the block detail sheet (mm -> m) --------------
    chute_len: float = 2.40
    baffle_base: float = 0.96
    baffle_ht: float = 0.80
    baffle_top: float = 0.16
    sill_base: float = 1.35
    sill_ht: float = 0.60
    sill_top: float = 0.15
    baffle_off: float = 4.50

    # superstructure ---------------------------------------------------------
    deck_t: float = 0.45
    girder_d: float = 0.80
    rail_ht: float = 1.10
    gate_ht: float = 2.60
    lift_travel: float = 2.30

    credit: str = ("Prepared by: Engr. Arup Chakraborty, Executive Engineer (Civil), "
                   "Engineering Academy, BPDB-BWDB, Kaptai")


# ------------------------------------------------------------- stage wording
STAGES = [
    ("SETTING OUT", "Setting out and dewatering",
     "Centre line and chainage pegs are fixed from the approved layout. A trapezoidal"
     " earthen closure is raised across the khal on both sides and the pit is kept dry by"
     " pumping for the whole concreting period.",
     [
      "Closure crest above spring high tide, with freeboard",
      "Standby pump and fuel on site before excavation starts",
      "Centre line transferred to permanent reference pillars",
     ]),
    ("EXCAVATION", "Excavation to foundation level",
     "The pit is cut to foundation level and the bed dressed and checked. Nothing is laid"
     " on the bed yet — pile driving comes next, and the sand filling and blinding follow"
     " only once the piles are in.",
     [
      "Founding level checked against the drawing, not by eye",
      "Soft pockets removed and replaced, not covered over",
      "Side slopes stable; no surcharge close to the cut edge",
     ]),
    ("BEARING PILES", "Bearing piles",
     "A grid of piles is driven under the floor, piers and abutments to carry the"
     " structural load down to firm strata. Their length is set by bearing capcacity of the"
     " soil or sub-soil investigation report, They can be cast-insitu or precast, so they"
     " run considerably deeper than the cut-off wall that follows.",
     [
      "Termination by set or depth as specified, whichever governs",
      "Driving record kept for every pile, with any redrive noted",
      "Cut-off level and head condition checked before capping",
     ]),
    ("CUT-OFF WALL", "U-type sheet piles",
     "A single line of U-type steel sheet piles is driven at each end of the RCC floor to"
     " form the cut-off wall. These are interlocking plate sections, not round bearing"
     " piles, and they carry no structural load — their depth being set by the seepage"
     " check alone. The downstream line is driven deeper than the upstream one, because the"
     " exit gradient is critical on the river side. They lengthen the path seepage must"
     " travel and hold the exit gradient within safe limits, which is what protects the"
     " floor against piping.",
     [
      "Depth as designed from the seepage check, not shortened to suit driving",
      "Interlocks engaged over the full length — one sprung joint defeats the cut-off",
      "Driven true to line before floor concrete, never after",
      "Head left projecting above the blinding, ready to be cast into the floor",
     ]),
    ("SAND & BLINDING", "Sand filling and CC blinding",
     "Only once all driving is finished and the pile heads are trimmed to cut-off level is"
     " the bed made up: sand filling first, then a lean concrete blinding layer over it,"
     " worked around the pile heads and the cut-off wall. This gives the base reinforcement"
     " a clean, true bed and stops the earth drawing water out of the base concrete.",
     [
      "Laid after driving is complete — driving over finished blinding breaks it up",
      "Sand filling compacted in layers to the specified thickness",
      "Blinding true to level and set before reinforcement is placed on it",
     ]),
    ("RCC BASE", "RCC base slab",
     "The base slab is cast on the blinding, monolithic with the pile heads, at three"
     " levels: the country-side apron, the sill floor under the gates, and the depressed"
     " stilling basin downstream of the glacis. It is cast over the head of each cut-off"
     " wall, so the sheet pile top finishes inside the concrete — shown here in dashed"
     " hidden lines. The river-side portion is longer than the country-side portion,"
     " because the stilling basin has to contain the hydraulic jump.",
     [
      "Sheet pile heads cleaned and embedded the full designed depth into the floor",
      "Cover to reinforcement maintained on blocks, not pebbles",
      "Construction joints only where shown, with water bars in place",
      "Each bay poured continuously; curing for the full specified period",
     ]),
    ("PIERS & SILL", "Piers, abutments and sill",
     "The piers and the abutment walls are built up from the base slab. The gate grooves,"
     " the sill beam and the fixings for the gate seals are all formed while this concrete"
     " is being cast. They cannot be cut out later, so a mistake made here stays in the"
     " structure.",
     [
      "Grooves plumb and to the correct width for the full height",
      "Embedded parts fixed to a template and held tight during the pour",
      "Grooves cleaned out, with no mortar left inside",
      "Use steel shutter for RCC casting; proper curing needed with potable water",
     ]),
    ("ENERGY WORKS", "Energy dissipation and protection",
     "Chute blocks are cast at the head of the inclined slab to split and lift the"
     " incoming jet. Baffle blocks stand in a transverse row on the flat slab to take out"
     " the residual energy, and the end sill closes the basin. The flared wing walls go up"
     " at the same time. Each one stops just short of the cut-off line and turns through"
     " 90° into a return wall, which is why the return wall appears end-on in this section"
     " and face-on in the elevations. Each wing is cast monolithic with the abutment —"
     " there is no joint between the wing wall and the box. Beyond the cut-off at each end"
     " a toe wall is cast, and the launching apron of CC blocks is laid on an inverted"
     " filter out to the end of the wing. The key plan shows the flare and the apron"
     " extent.",
     [
      "Chute blocks at the start of the slope, height and spacing as drawn",
      "Baffle row square to flow and clear of the inclined slab toe",
      "Toe wall founded below apron level at the end of the RCC floor",
      "Filter or geotextile laid before CC blocks; apron thickness held to the outer edge",
     ]),
    ("BRIDGE DECK", "Bridge deck and hoist platform",
     "Girders are placed across the piers, then the deck slab, the operating platform,"
     " hoist supports and railing. The deck gives access across the regulator and carries"
     " the hoisting arrangement.",
     [
      "Bearing seating level and clean before girders are placed",
      "Deck level and camber checked against the drawing",
      "Hoist centre line exactly over the gate centre line",
     ]),
    ("GATES", "Gate installation",
     "Two gates go into the grooves at each vent. The vertical lift gate on the country"
     " side is hoisted from the deck: it is held shut to retain fresh water for irrigation"
     " and raised to pass drainage. The flap gate on the river side is top hinged and needs"
     " no operator — it swings outward, away from the structure and toward the river.",
     [
      "Seal contact checked all round under a light test head",
      "Lift gate travels free over its full range, both directions",
      "Flap swings without binding; hinge greased and free",
     ]),
    ("BACKFILL & TRIAL", "Backfilling and trial operation",
     "Earth is filled behind the wings in compacted layers. The embankment falls away from"
     " the deck at 2:1 on the country side and 3:1 on the river side, and beyond each"
     " return wall the bank falls to the bed on a 2:1 trapezoidal slope. All of these are"
     " pitched, and the pitching on each bank slope runs the same length as the launching"
     " blocks laid on the bed beside it.Every gate is trial operated before the closure is"
     " cut and the structure handed over. Use the tide control to see how the two gates"
     " work together.",
     [
      "Filling in layers of specified thickness, each one compacted",
      "Slopes dressed to 2:1 and 3:1 before pitching is laid",
      "Pitching bedded on a filter, no voids behind walls or under the apron edge",
      "All gates operated and the trial recorded before handover",
     ]),
]

TIDE_TEXT = {
    "low":  "The river has fallen below the country-side level. The lift gate has been raised from the deck (during the irrigation period gate kept closed to store water for irrigation and during monsoon and non-irrigation period it is raised up), and the internal head swings the flap outward toward the river on its own, so drainage runs out by gravity.",
    "high": "The river has risen above the country-side level. The tide presses the flap back against its frame and holds it shut, so saline water is kept out. No operator is involved — the head difference does the work.",
}


# =============================================================== the model
class Regulator:

    def __init__(self, **kw):
        self.p = Params(**kw)
        self._stations()

    # ---------------------------------------------------- derived geometry
    def _stations(self):
        p = self.p
        s = {}
        s["box_c"] = -p.box_len / 2
        s["box_r"] = p.box_len / 2
        s["floor_c"] = s["box_c"] - p.floor_c_len
        s["glac_c"] = s["box_r"]
        s["glac_r"] = s["box_r"] + p.glacis_len
        s["floor_r"] = s["glac_r"] + p.floor_r_len
        s["wing_c"] = s["floor_c"] + 1.2          # stops short of the cut-off
        s["wing_r"] = s["floor_r"] - 1.2
        s["apron_c"] = s["floor_c"] - p.apron_len
        s["apron_r"] = s["floor_r"] + p.apron_len
        s["cut_c"] = s["floor_c"] + 0.6
        s["cut_r"] = s["floor_r"] - 0.6
        self.s = s

    @property
    def width(self):
        p = self.p
        return p.n_vent * p.vent_span + (p.n_vent - 1) * p.pier_t + 2 * p.abut_t

    def bed(self, x):
        """bed level along the centreline"""
        p, s = self.p, self.s
        if x <= s["glac_c"]:
            return p.el_floor_c
        if x >= s["glac_r"]:
            return p.el_floor_r
        t = (x - s["glac_c"]) / (s["glac_r"] - s["glac_c"])
        return p.el_floor_c + t * (p.el_floor_r - p.el_floor_c)

    # ------------------------------------------------------- drawing atoms
    @staticmethod
    def _poly(ax, pts, fc=P.conc, ec=P.line, lw=1.0, z=2, **kw):
        ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=ec,
                             linewidth=lw, zorder=z, **kw))

    @staticmethod
    def _rect(ax, x, y, w, h, fc=P.conc, ec=P.line, lw=1.0, z=2, **kw):
        ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec,
                               linewidth=lw, zorder=z, **kw))

    @staticmethod
    def _txt(ax, x, y, t, size=7.0, ha="left", va="bottom", col=P.ink, z=9, **kw):
        ax.text(x, y, t, fontsize=size, ha=ha, va=va, color=col, zorder=z,
                path_effects=_halo(), **kw)

    @staticmethod
    def _lead(ax, x0, y0, x1, y1, z=8):
        ax.plot([x0, x1], [y0, y1], color=P.ink, lw=0.6, alpha=.75, zorder=z)

    def _batter(self, ax, x0, y0, x1, y1, ybase, n=18, z=6):
        """alternating long and short ticks: a pitched slope seen in projection"""
        ax.plot([x0, x1], [y0, y1], color=P.line, lw=1.2, zorder=z)
        for i in range(n):
            t = i / (n - 1.0)
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            f = 0.55 if i % 2 == 0 else 0.28
            ax.plot([x, x], [y, max(ybase, y - (y - ybase) * f)],
                    color=P.line, lw=0.5, zorder=z)

    # =================================================== view 1: section
    def section(self, stage=11, tide="low", labels=True, fig=None):
        p, s = self.p, self.s
        on = lambda k: stage >= k
        upto = lambda k: stage <= k

        xlo, xhi = s["apron_c"] - 16, s["apron_r"] + 16
        ytop = p.el_deck + 4.0
        ybot = p.el_floor_r - p.slab_t - p.pile_len - 2.0

        fig, ax = _canvas(fig, xlo, xhi, ybot, ytop)

        # ground ------------------------------------------------------------
        gx = [xlo, s["glac_c"], s["glac_r"], xhi, xhi, xlo]
        gy = [p.el_floor_c, p.el_floor_c, p.el_floor_r, p.el_floor_r, ybot, ybot]
        self._poly(ax, list(zip(gx, gy)), fc=P.soil, ec="none", z=1)
        self._poly(ax, list(zip(gx, gy)), fc="none", ec="#8a7148", lw=0.0,
                   hatch="///", alpha=.35, z=1)
        ax.plot(gx[:4], gy[:4], color=P.line, lw=1.3, zorder=3)

        # 8  wing walls beyond the plane, embankment slopes -------------------
        if on(8):
            emb_c = s["box_c"] - (p.el_deck - p.el_wing) * p.slope_emb_c
            emb_r = s["box_r"] + (p.el_deck - p.el_wing) * p.slope_emb_r
            self._poly(ax, [(s["wing_c"], p.el_wing), (emb_c, p.el_wing),
                            (s["box_c"], p.el_deck), (s["box_c"], p.el_floor_c),
                            (s["wing_c"], p.el_floor_c)], fc=P.beyond, z=2)
            self._poly(ax, [(s["wing_r"], p.el_wing), (emb_r, p.el_wing),
                            (s["box_r"], p.el_deck), (s["box_r"], p.el_floor_r),
                            (s["wing_r"], p.el_floor_r)], fc=P.beyond, z=2)
            for x in _seq(s["wing_c"] + 2, emb_c - 1, 3):
                ax.plot([x, x], [p.el_wing, p.el_floor_c], color=P.line, lw=.4, zorder=3)
            for x in _seq(emb_r + 1, s["wing_r"] - 2, 3):
                ax.plot([x, x], [p.el_wing, p.el_floor_r], color=P.line, lw=.4, zorder=3)
            # return walls: square to the flow, so seen end-on here
            self._rect(ax, s["wing_c"] - .9, p.el_floor_c, .9, p.el_wing - p.el_floor_c,
                       lw=1.4, z=4)
            self._rect(ax, s["wing_r"], p.el_floor_r, .9, p.el_wing - p.el_floor_r,
                       lw=1.4, z=4)

        # 1  closure and dewatering ------------------------------------------
        if on(1) and upto(10):
            for xc in (s["apron_c"] - 7, s["apron_r"] + 7):
                z0 = self.bed(xc)
                h, b = 2.2, 4.4
                self._poly(ax, [(xc - b, z0), (xc - 1, z0 + h),
                                (xc + 1, z0 + h), (xc + b, z0)], fc="#9a8557", z=5)
            z0 = p.el_floor_c
            self._rect(ax, s["apron_c"] - 3.2, z0, 1.2, 1.1, fc=P.steel, ec="none", z=5)
            ax.annotate("", xy=(s["apron_c"] - 12, z0 + 3), xytext=(s["apron_c"] - 2.6, z0 + 1.1),
                        arrowprops=dict(arrowstyle="-|>", color=P.steel, lw=1.6), zorder=6)
            if labels:
                self._txt(ax, s["apron_c"] - 13, z0 + 3.4, "Trapezoidal earthen closure")

        # 2  excavation --------------------------------------------------------
        if on(2) and upto(7):
            fb = p.el_floor_c - p.slab_t - p.blind_t
            rb = p.el_floor_r - p.slab_t - p.blind_t
            self._poly(ax, [(s["floor_c"] - 1, p.el_floor_c), (s["floor_c"] - 1, fb),
                            (s["glac_c"], fb), (s["glac_r"], rb),
                            (s["floor_r"] + 1, rb), (s["floor_r"] + 1, p.el_floor_r)],
                       fc=P.sheet2, ec=P.line, lw=1.0, linestyle=(0, (5, 4)), z=2)

        # 3  bearing piles -----------------------------------------------------
        if on(3):
            for x in self._pile_xs():
                top = (p.el_floor_c if x < s["glac_r"] else p.el_floor_r) - p.slab_t + .3
                self._rect(ax, x - .16, top - p.pile_len, .32, p.pile_len,
                           fc=P.concd, lw=.4, z=3)

        # 4  cut-off wall, no load, D/S deeper ---------------------------------
        if on(4):
            for x, fl, L in ((s["cut_c"], p.el_floor_c, p.cut_c_len),
                             (s["cut_r"], p.el_floor_r, p.cut_r_len)):
                self._rect(ax, x - .22, fl - .35 - L, .44, L, fc=P.spile, lw=.9, z=4)

        # 5  sand filling and blinding ------------------------------------------
        if on(5):
            self._rect(ax, s["floor_c"], p.el_floor_c - p.slab_t - p.blind_t,
                       s["glac_c"] - s["floor_c"], p.blind_t, fc="#c9cdc7", lw=.5, z=3)
            self._rect(ax, s["glac_r"], p.el_floor_r - p.slab_t - p.blind_t,
                       s["floor_r"] - s["glac_r"], p.blind_t, fc="#c9cdc7", lw=.5, z=3)
            # carried down the incline so the layer is continuous
            self._poly(ax, [(s["glac_c"], p.el_floor_c - p.slab_t),
                            (s["glac_r"], p.el_floor_r - p.slab_t),
                            (s["glac_r"], p.el_floor_r - p.slab_t - p.blind_t),
                            (s["glac_c"], p.el_floor_c - p.slab_t - p.blind_t)],
                       fc="#c9cdc7", ec=P.line, lw=.5, z=3)

        # 6  RCC base slab ------------------------------------------------------
        if on(6):
            self._poly(ax, [(s["floor_c"], p.el_floor_c), (s["glac_c"], p.el_floor_c),
                            (s["glac_r"], p.el_floor_r), (s["floor_r"], p.el_floor_r),
                            (s["floor_r"], p.el_floor_r - p.slab_t),
                            (s["glac_r"], p.el_floor_r - p.slab_t),
                            (s["glac_c"], p.el_floor_c - p.slab_t),
                            (s["floor_c"], p.el_floor_c - p.slab_t)], lw=1.3, z=4)
            for x, fl in ((s["cut_c"], p.el_floor_c), (s["cut_r"], p.el_floor_r)):
                self._rect(ax, x - .22, fl - .35, .44, .35, fc="none", ec=P.line,
                           lw=.7, linestyle=(0, (4, 3)), z=5)

        # 7  piers, abutments, grooves -------------------------------------------
        if on(7):
            self._rect(ax, s["box_c"], p.el_floor_c, p.box_len,
                       p.el_deck - p.deck_t - p.girder_d - p.el_floor_c,
                       fc=P.beyond, lw=1.1, z=5)
            for g in (s["box_c"] + 1.8, s["box_r"] - 1.8):
                self._rect(ax, g - .22, p.el_floor_c, .44,
                           p.el_deck - p.deck_t - p.girder_d - .3 - p.el_floor_c,
                           fc="#9aa4ab", ec="none", z=6)

        # 8  blocks, sills, toe walls, aprons -------------------------------------
        if on(8):
            gy_at = lambda x: self.bed(x)
            x0 = s["glac_c"] + 0.6
            x1 = x0 + p.chute_len
            self._poly(ax, [(x0, gy_at(x0)), (x1, gy_at(x0)), (x1, gy_at(x1))], lw=1.1, z=6)
            bx = s["glac_r"] + p.baffle_off
            self._poly(ax, [(bx, p.el_floor_r), (bx, p.el_floor_r + p.baffle_ht),
                            (bx + p.baffle_top, p.el_floor_r + p.baffle_ht),
                            (bx + p.baffle_base, p.el_floor_r)], lw=1.1, z=6)
            sx = s["floor_r"] - p.sill_base
            self._poly(ax, [(sx, p.el_floor_r), (sx, p.el_floor_r + p.sill_ht),
                            (sx + p.sill_top, p.el_floor_r + p.sill_ht),
                            (s["floor_r"], p.el_floor_r)], lw=1.1, z=6)
            self._rect(ax, s["floor_c"] - p.toe_t, p.el_floor_c - p.toe_d, p.toe_t,
                       p.toe_d, fc=P.concd, z=5)
            self._rect(ax, s["floor_r"], p.el_floor_r - p.toe_d, p.toe_t, p.toe_d,
                       fc=P.concd, z=5)
            for xa, xb, fl in ((s["apron_c"], s["floor_c"] - p.toe_t, p.el_floor_c),
                               (s["floor_r"] + p.toe_t, s["apron_r"], p.el_floor_r)):
                self._rect(ax, xa, fl - p.apron_t - p.filter_t, xb - xa, p.filter_t,
                           fc="#c8b48f", lw=.5, z=4)
                self._rect(ax, xa, fl - p.apron_t, xb - xa, p.apron_t, fc=P.brick, lw=.8, z=4)
                for x in _seq(xa, xb, .9):
                    ax.plot([x, x], [fl - p.apron_t, fl], color=P.line, lw=.4, zorder=5)

        # 9  deck, railing, hoist --------------------------------------------------
        if on(9):
            d0, d1 = s["box_c"] - .6, s["box_r"] + .6
            self._rect(ax, d0 + .3, p.el_deck - p.deck_t - p.girder_d, d1 - d0 - .6,
                       p.girder_d, fc=P.concd, lw=1.1, z=6)
            self._rect(ax, d0, p.el_deck - p.deck_t, d1 - d0, p.deck_t, lw=1.1, z=6)
            for x in (d0, d1):
                ax.plot([x, x], [p.el_deck, p.el_deck + p.rail_ht], color=P.concd,
                        lw=1.6, zorder=6)
            for f in (1.0, .55):
                ax.plot([d0, d1], [p.el_deck + p.rail_ht * f] * 2, color=P.concd,
                        lw=1.6, zorder=6)
            hx = s["box_c"] + 1.8
            self._rect(ax, hx - 1.1, p.el_deck + 1.5, 2.2, .4, z=6)
            self._rect(ax, hx - .55, p.el_deck + 1.9, 1.1, .8, fc=P.steel, ec="none", z=6)

        # 10  gates ----------------------------------------------------------------
        if on(10):
            lift_x, flap_x = s["box_c"] + 1.8, s["box_r"] - 1.8
            rise = p.lift_travel if (stage >= 11 and tide == "low") else 0.0
            self._rect(ax, lift_x - .22, p.el_floor_c + rise, .44, p.gate_ht,
                       fc=P.steel, ec=P.ink, lw=.5, z=7)
            ax.plot([lift_x, lift_x], [p.el_floor_c + p.gate_ht + rise, p.el_deck + 2.1],
                    color=P.steel, lw=1.6, zorder=7)
            ang = -32 if (stage >= 11 and tide == "low") else 0
            th = math.radians(ang)
            hy = p.el_floor_c + p.gate_ht
            ax.plot([flap_x, flap_x + math.sin(-th) * p.gate_ht],
                    [hy, hy - math.cos(th) * p.gate_ht],
                    color=P.steel, lw=4.5, solid_capstyle="butt", zorder=7)
            ax.plot([flap_x], [hy], marker="o", ms=3, color=P.ink, zorder=8)

        # 11  pitching, water, flow --------------------------------------------------
        if on(11):
            self._batter(ax, s["floor_c"] - p.toe_t, p.el_bank, s["apron_c"],
                         p.el_floor_c + .4, p.el_floor_c)
            self._batter(ax, s["floor_r"] + p.toe_t, p.el_bank, s["apron_r"],
                         p.el_floor_r + .4, p.el_floor_r)
            wl_r = p.el_ltl if tide == "low" else p.el_hfl
            self._rect(ax, xlo, p.el_floor_c, s["box_c"] + 1.8 - xlo, p.el_ret - p.el_floor_c,
                       fc=P.water, ec="none", alpha=.55, z=7)
            ax.plot([xlo, s["box_c"] + 1.8], [p.el_ret] * 2, color="#1d5a68", lw=1.1, zorder=8)
            self._rect(ax, s["box_r"] - 1.8, p.el_floor_r, xhi - s["box_r"] + 1.8,
                       wl_r - p.el_floor_r, fc=P.water, ec="none", alpha=.55, z=7)
            ax.plot([s["box_r"] - 1.8, xhi], [wl_r] * 2, color="#1d5a68", lw=1.1, zorder=8)
            if tide == "low":
                ax.annotate("", xy=(s["glac_r"] + 8, p.el_floor_c + 1.2),
                            xytext=(s["box_c"] - 5, p.el_floor_c + 1.2),
                            arrowprops=dict(arrowstyle="-|>", color="#1d5a68", lw=2), zorder=8)
                if labels:
                    self._txt(ax, s["glac_r"] + 8.4, p.el_floor_c + 1.4, "Drainage to river")
            else:
                ax.annotate("", xy=(s["box_r"] + .6, p.el_floor_r + 3.4),
                            xytext=(s["glac_r"] + 8, p.el_floor_r + 3.4),
                            arrowprops=dict(arrowstyle="-|>", color="#1d5a68", lw=2), zorder=8)
                if labels:
                    self._txt(ax, s["glac_r"] + 8.4, p.el_floor_r + 3.6, "Saline water held out")
            if labels:
                self._txt(ax, s["apron_c"] + .5, p.el_bank + .5,
                          "Pitched slope %g:1 (H:V)" % p.slope_bank, size=6.4)
                self._txt(ax, s["floor_r"] + 1.5, p.el_bank + .5,
                          "Pitched slope %g:1 (H:V)" % p.slope_bank, size=6.4)

        if labels:
            self._section_labels(ax, stage, xlo, xhi)
        _footer(ax, self.p, xlo, xhi, ybot,
                "SECTION A-A THROUGH ONE VENT", stage)
        return fig

    def _pile_xs(self):
        """pile stations, kept clear of both cut-off lines"""
        s, p = self.s, self.p
        xs, x = [], s["floor_c"] + 1.6
        while x <= s["floor_r"] - 1.6:
            if abs(x - s["cut_c"]) > .8 and abs(x - s["cut_r"]) > .8:
                xs.append(x)
            x += p.pile_spac
        return xs

    def _section_labels(self, ax, stage, xlo, xhi):
        p, s = self.p, self.s
        on = lambda k: stage >= k

        def el(x0, x1, y, t):
            ax.plot([x0, x1], [y, y], color=P.line, lw=.8, zorder=8)
            self._txt(ax, x1, y + .35, t, ha="right", size=6.4)

        if on(2):
            self._lead(ax, s["floor_c"] - 3, p.el_floor_c - 4.5, s["floor_c"], p.el_floor_c - .2)
            self._txt(ax, s["floor_c"] - 3.2, p.el_floor_c - 5.1,
                      "Excavated to foundation level", ha="right", size=6.4)
        if on(3):
            self._txt(ax, s["box_c"] - 4, p.el_floor_c - p.slab_t - p.pile_len - 1.4,
                      "Bearing piles %.0f m, driven to set" % p.pile_len, size=6.4)
        if on(4):
            self._lead(ax, s["cut_c"] - 4, p.el_floor_c - p.cut_c_len,
                       s["cut_c"], p.el_floor_c - p.cut_c_len + 1.5)
            self._txt(ax, s["cut_c"] - 4.3, p.el_floor_c - p.cut_c_len - .2,
                      "Cut-off wall, U-type sheet piles (%.0f m)" % p.cut_c_len,
                      ha="right", size=6.4)
            self._txt(ax, s["cut_r"] + 1.2, p.el_floor_r - p.cut_r_len,
                      "Deeper on the river side (%.0f m)" % p.cut_r_len, size=6.4)
        if on(6):
            el(s["box_c"] - 9, s["box_c"] - 5, p.el_floor_c, "EL E1  %+.2f" % p.el_floor_c)
            el(s["glac_r"] + 1, s["glac_r"] + 5, p.el_floor_r, "EL E2  %+.2f" % p.el_floor_r)
            self._txt(ax, s["floor_c"] + 1.5, p.el_floor_c - p.slab_t / 2 - .2,
                      "RCC base slab", size=6.4)
        if on(8):
            el(s["wing_c"] + 1, s["wing_c"] + 5, p.el_wing, "EL E4  %+.2f" % p.el_wing)
            self._txt(ax, s["wing_c"] - 7.5, p.el_wing + 1.1, "Return wall - end-on", size=6.4)
            self._lead(ax, s["wing_c"] - 2.4, p.el_wing + 1.0, s["wing_c"] - .5, p.el_wing - .4)
            self._txt(ax, s["box_c"] - 6, p.el_wing - 1.6, "Wing wall", size=6.4)
            self._txt(ax, s["glac_c"] - 2.5, p.el_floor_c + 3.0, "Chute blocks", size=6.4)
            self._lead(ax, s["glac_c"] + .5, p.el_floor_c + 2.9, s["glac_c"] + 1.6, p.el_floor_c - .2)
            self._txt(ax, s["glac_r"] + p.baffle_off - 3.4, p.el_floor_r + 2.6,
                      "Baffle blocks", size=6.4)
            self._lead(ax, s["glac_r"] + p.baffle_off + .3, p.el_floor_r + 2.5,
                       s["glac_r"] + p.baffle_off + .5, p.el_floor_r + .9)
            self._txt(ax, s["floor_r"] - 6.5, p.el_floor_r + 1.6, "D/S end sill", size=6.4)
            self._txt(ax, s["apron_r"] - 6, p.el_floor_r - 3.0,
                      "Launching apron on the bed", size=6.4)
        if on(9):
            el(s["box_r"] + 2, s["box_r"] + 6, p.el_deck, "EL E3  %+.2f" % p.el_deck)
        if on(10):
            yg = p.el_floor_c + p.gate_ht
            self._txt(ax, s["box_c"] - 14, yg + 3.0, "Vertical lift gate, country side", size=6.4)
            self._lead(ax, s["box_c"] - 5, yg + 2.9, s["box_c"] + 1.6, yg - .4)
            self._txt(ax, s["box_r"] + 4, yg + 3.0, "Flap gate, river side", size=6.4)
            self._lead(ax, s["box_r"] + 4, yg + 2.9, s["box_r"] - 1.6, yg - .4)

        self._txt(ax, xlo + 1, p.el_deck + 2.4, "COUNTRY SIDE - KHAL", size=6.6, col=P.dim)
        self._txt(ax, xhi - 1, p.el_deck + 2.4, "RIVER SIDE - TIDAL", size=6.6,
                  ha="right", col=P.dim)

    # =================================================== view 2: plan (drone)
    def plan(self, stage=11, tide="low", labels=True, fig=None):
        p, s = self.p, self.s
        on = lambda k: stage >= k
        hw = self.width / 2
        wl = s["box_c"] - s["wing_c"]
        widen = 3.0

        def hw_at(x):
            return hw + widen * min(1.0, max(0.0, (abs(x) - p.box_len / 2) / wl))

        xlo, xhi = s["apron_c"] - 6, s["apron_r"] + 6
        fig, ax = _canvas(fig, xlo, xhi, -hw - 12, hw + 12)

        self._rect(ax, xlo, -hw - 12, xhi - xlo, 2 * (hw + 12), fc=P.soil, ec="none", z=1)
        xs = _seq(xlo, xhi, (xhi - xlo) / 200.0)
        band = [(x, hw_at(x)) for x in xs] + [(x, -hw_at(x)) for x in reversed(xs)]
        self._poly(ax, band, fc=P.sheet2, ec=P.line, lw=.9, z=2)
        ax.plot([xlo, xhi], [0, 0], color=P.ink, lw=.7, ls=(0, (12, 3, 2, 3)), zorder=3)

        if on(1) and stage <= 10:
            for xc in (s["apron_c"] - 4, s["apron_r"] + 4):
                self._rect(ax, xc - 1.6, -hw_at(xc), 3.2, 2 * hw_at(xc), fc="#9a8557", z=3)
        if on(3):
            for x in self._pile_xs():
                for y in _seq(-hw + .8, hw - .8, 1.4):
                    ax.add_patch(Circle((x, y), .22, facecolor=P.concd, edgecolor=P.line,
                                        lw=.3, zorder=4))
        if on(6):
            full = [(x, hw_at(x)) for x in _seq(s["floor_c"], s["floor_r"], .5)]
            full += [(x, -hw_at(x)) for x in reversed(_seq(s["floor_c"], s["floor_r"], .5))]
            self._poly(ax, full, lw=1.2, z=5)
        if on(4):
            for x in (s["cut_c"], s["cut_r"]):
                ax.plot([x, x], [-hw_at(x), hw_at(x)], color=P.spile, lw=3,
                        solid_capstyle="butt",
                        zorder=6 if not on(6) else 6)
                if on(6):
                    ax.plot([x, x], [-hw_at(x), hw_at(x)], color=P.line, lw=.8,
                            ls=(0, (5, 3)), zorder=7)
        if on(7):
            y = -hw
            self._rect(ax, s["box_c"], y, p.box_len, p.abut_t, fc=P.concd, z=7)
            y += p.abut_t
            for i in range(p.n_vent):
                y += p.vent_span
                if i < p.n_vent - 1:
                    self._rect(ax, s["box_c"], y, p.box_len, p.pier_t, fc=P.concd, z=7)
                    y += p.pier_t
            self._rect(ax, s["box_c"], hw - p.abut_t, p.box_len, p.abut_t, fc=P.concd, z=7)
        if on(8):
            for sg in (-1, 1):
                for x0, x1 in ((s["box_c"], s["wing_c"]), (s["box_r"], s["wing_r"])):
                    y1 = sg * hw_at(x1)
                    ax.plot([x0, x1], [sg * hw, y1], color=P.concd, lw=5,
                            solid_capstyle="butt", zorder=8)
                    # return wall: square to the flow
                    ax.plot([x1, x1], [y1, y1 + sg * 3.2], color=P.ink, lw=5,
                            solid_capstyle="butt", zorder=8)
            for xa, xb in ((s["apron_c"], s["floor_c"] - p.toe_t),
                           (s["floor_r"] + p.toe_t, s["apron_r"])):
                band = [(x, hw_at(x)) for x in _seq(xa, xb, .5)]
                band += [(x, -hw_at(x)) for x in reversed(_seq(xa, xb, .5))]
                self._poly(ax, band, fc=P.brick, lw=.8, z=6)
            ys = _lin(-hw + 1.0, hw - 1.0, 2 * p.n_vent + 1)
            for y in ys[0::2]:
                self._rect(ax, s["glac_c"] + .6, y - .3, p.chute_len, .6, lw=.6, z=8)
            for y in ys[1::2]:
                self._rect(ax, s["glac_r"] + p.baffle_off, y - .35, p.baffle_base, .7,
                           lw=.6, z=8)
            self._rect(ax, s["floor_r"] - p.sill_base, -hw_at(s["floor_r"]), p.sill_base,
                       2 * hw_at(s["floor_r"]), lw=.8, z=8)
        if on(9):
            self._rect(ax, s["box_c"] - .6, -hw, p.box_len + 1.2, 2 * hw,
                       fc=P.conc, alpha=.6, lw=1.1, z=9)
        if on(10):
            y = -hw + p.abut_t
            for _ in range(p.n_vent):
                self._rect(ax, s["box_c"] + 1.6, y, .4, p.vent_span, fc=P.steel, lw=.4, z=10)
                self._rect(ax, s["box_r"] - 2.0, y, .4, p.vent_span, fc=P.steel, lw=.4, z=10)
                y += p.vent_span + p.pier_t
        if on(11):
            for xa, xb in ((s["apron_c"], s["floor_c"]), (s["floor_r"], s["apron_r"])):
                for sg in (-1, 1):
                    strip = [(x, sg * hw_at(x)) for x in _seq(xa, xb, .5)]
                    strip += [(x, sg * (hw_at(x) - 1.8)) for x in reversed(_seq(xa, xb, .5))]
                    self._poly(ax, strip, fc="#a9aeaa", lw=.6, z=7)
            for y in _lin(-hw + p.abut_t + p.vent_span / 2,
                          hw - p.abut_t - p.vent_span / 2, p.n_vent):
                if tide == "low":
                    ax.annotate("", xy=(s["glac_r"] + 7, y), xytext=(s["box_c"] - 6, y),
                                arrowprops=dict(arrowstyle="-|>", color="#1d5a68", lw=1.6),
                                zorder=11)
                else:
                    ax.annotate("", xy=(s["box_r"] + 1.2, y), xytext=(s["glac_r"] + 7, y),
                                arrowprops=dict(arrowstyle="-|>", color="#1d5a68", lw=1.6),
                                zorder=11)
        if labels:
            self._txt(ax, s["box_c"] - 6, hw + 8.5,
                      "Wing wall flares, then the return wall turns square to the flow", size=6.4)
            self._txt(ax, s["apron_c"], -hw - 8,
                      "Launching apron, the same length as the pitching", size=6.4)
            self._txt(ax, xlo + 2, hw + 4.5, "COUNTRY SIDE", size=6.6, col=P.dim)
            self._txt(ax, xhi - 2, hw + 4.5, "RIVER SIDE", size=6.6, ha="right", col=P.dim)
        _footer(ax, self.p, xlo, xhi, -hw - 12,
                "PLAN - %d VENTS OF %.2f m" % (p.n_vent, p.vent_span), stage)
        return fig

    # ============================================= views 3 and 4: elevations
    def elevation(self, side="river", stage=11, tide="low", labels=True, fig=None):
        p, s = self.p, self.s
        on = lambda k: stage >= k
        river = side == "river"
        bed = p.el_floor_r if river else p.el_floor_c
        cut = p.cut_r_len if river else p.cut_c_len
        hw = self.width / 2

        xlo, xhi = -hw - 9, hw + 9
        ytop, ybot = p.el_deck + 4, bed - p.slab_t - p.pile_len - 2
        fig, ax = _canvas(fig, xlo, xhi, ybot, ytop)

        self._rect(ax, xlo, ybot, xhi - xlo, bed - ybot, fc=P.soil, ec="none", z=1)
        ax.plot([xlo, xhi], [bed, bed], color=P.line, lw=1.2, zorder=3)
        ax.plot([0, 0], [ytop - 1.5, bed - 1], color=P.ink, lw=.6,
                ls=(0, (12, 3, 2, 3)), zorder=3)

        vents = self._vent_bands()
        if on(2) and stage <= 7:
            self._rect(ax, -hw - 2, bed - p.slab_t - p.blind_t - .4, 2 * hw + 4,
                       p.slab_t + p.blind_t + .4, fc=P.sheet2, ec=P.line, lw=.9,
                       linestyle=(0, (5, 4)), z=2)
        if on(3):
            for off, al in ((.5, .30), (.25, .5)):
                for y in _seq(-hw + .8, hw - .8, 1.4):
                    self._rect(ax, y + off - .16, bed - p.slab_t - p.pile_len + .6, .32,
                               p.pile_len - 1.2, fc=P.concd, ec="none", alpha=al, z=3)
            for y in _seq(-hw + .8, hw - .8, 1.4):
                self._rect(ax, y - .16, bed - p.slab_t - p.pile_len, .32, p.pile_len,
                           fc=P.concd, lw=.4, z=4)
        if on(4):
            # the cut-off stands between viewer and piles, so it is drawn as a
            # cutaway - otherwise it hides the whole pile grid behind it
            self._rect(ax, -hw, bed - p.slab_t - cut, 2 * hw, cut, fc=P.spile,
                       lw=.9, alpha=.55, z=5)
        if on(5):
            self._rect(ax, -hw - .4, bed - p.slab_t - p.blind_t, 2 * hw + .8, p.blind_t,
                       fc="#c9cdc7", lw=.5, z=5)
        if on(6):
            self._rect(ax, -hw - .4, bed - p.slab_t, 2 * hw + .8, p.slab_t, lw=1.2, z=6)
        if on(7):
            for a, b in vents:
                self._rect(ax, a, bed, b - a, p.el_deck - p.deck_t - p.girder_d - bed,
                           fc=P.ink, ec="none", alpha=.3, z=6)
            for a, b in self._wall_bands():
                self._rect(ax, a, bed, b - a, p.el_deck - p.deck_t - p.girder_d - bed,
                           lw=1.1, z=7)
        if on(8):
            for sg in (-1, 1):
                self._poly(ax, [(sg * hw, p.el_wing), (sg * (hw + 5), p.el_wing - 1.2),
                                (sg * (hw + 5), bed), (sg * hw, bed)], fc=P.beyond, lw=1.1, z=6)
                self._rect(ax, sg * (hw + 6.4) - .6, bed, 1.2, p.el_wing - 1.6 - bed,
                           lw=1.3, z=7)
            if river:
                for y in _lin(-hw + 1.4, hw - 1.4, 2 * p.n_vent):
                    self._poly(ax, [(y, bed), (y, bed + p.baffle_ht),
                                    (y + p.baffle_top, bed + p.baffle_ht),
                                    (y + p.baffle_base, bed)], lw=.8, z=8)
        if on(9):
            self._rect(ax, -hw - .6, p.el_deck - p.deck_t - p.girder_d, 2 * hw + 1.2,
                       p.girder_d, fc=P.concd, lw=1.1, z=8)
            self._rect(ax, -hw - .8, p.el_deck - p.deck_t, 2 * hw + 1.6, p.deck_t, lw=1.1, z=8)
            for f in (1.0, .55):
                ax.plot([-hw - .8, hw + .8], [p.el_deck + p.rail_ht * f] * 2,
                        color=P.concd, lw=1.4, zorder=8)
            for x in _lin(-hw, hw, 6):
                ax.plot([x, x], [p.el_deck, p.el_deck + p.rail_ht], color=P.concd,
                        lw=1.2, zorder=8)
            if not river:
                for a, b in vents:
                    c = (a + b) / 2
                    self._rect(ax, c - 1.0, p.el_deck + 1.5, 2.0, .4, z=9)
                    self._rect(ax, c - .5, p.el_deck + 1.9, 1.0, .8, fc=P.steel, ec="none", z=9)
        if on(10):
            rise = p.lift_travel if (stage >= 11 and tide == "low" and not river) else 0
            shut = (tide == "high") or stage < 11
            for a, b in vents:
                if river:
                    h = p.gate_ht if shut else p.gate_ht * .55
                    self._rect(ax, a + .12, bed + (0 if shut else p.gate_ht - h), b - a - .24,
                               h, fc=P.steel, ec=P.ink, lw=.4, z=9)
                    ax.plot([a + .12, b - .12], [bed + p.gate_ht + .12] * 2,
                            color=P.steel, lw=2.4, zorder=9)
                else:
                    self._rect(ax, a + .12, bed + rise, b - a - .24, p.gate_ht,
                               fc=P.steel, ec=P.ink, lw=.4, z=9)
                    c = (a + b) / 2
                    ax.plot([c, c], [bed + p.gate_ht + rise, p.el_deck + 1.9],
                            color=P.steel, lw=1.4, zorder=9)
        if on(11):
            wl = (p.el_ltl if tide == "low" else p.el_hfl) if river else p.el_ret
            self._rect(ax, xlo, bed, xhi - xlo, wl - bed, fc=P.water, ec="none",
                       alpha=.5, z=10)
            ax.plot([xlo, xhi], [wl, wl], color="#1d5a68", lw=1.1, zorder=11)
            for sg in (-1, 1):
                self._batter(ax, sg * (hw + 5.2), p.el_wing - 1.4, sg * (hw + 9),
                             bed + .4, bed, n=10, z=7)
        if labels:
            self._txt(ax, xlo + .8, p.el_deck + 2.6,
                      "VIEWED FROM THE %s SIDE" % ("RIVER" if river else "COUNTRY"),
                      size=6.6, col=P.dim)
            if on(4):
                self._txt(ax, xlo + .8, bed - p.slab_t - cut - .8,
                          "Cut-off wall, continuous across the width (%.0f m)" % cut, size=6.4)
            if on(7):
                self._txt(ax, 0, bed + 1.2, "%d VENTS" % p.n_vent, size=6.4, ha="center")
            if on(8):
                self._txt(ax, -hw - 8.6, p.el_wing - .4, "Return wall", size=6.4)
                self._txt(ax, -hw + .6, p.el_wing - 2.2, "Wing wall", size=6.4)
            if on(10):
                self._txt(ax, xlo + .8, p.el_deck - 1.2,
                          "Flap gate in every vent" if river else
                          "Vertical lift gate in every vent", size=6.4)
        _footer(ax, self.p, xlo, xhi, ybot,
                "%s ELEVATION" % ("FRONT - RIVER SIDE" if river else "REAR - COUNTRY SIDE"),
                stage)
        return fig

    def _vent_bands(self):
        p = self.p
        y = -self.width / 2 + p.abut_t
        out = []
        for i in range(p.n_vent):
            out.append((y, y + p.vent_span))
            y += p.vent_span + p.pier_t
        return out

    def _wall_bands(self):
        p = self.p
        hw = self.width / 2
        out = [(-hw, -hw + p.abut_t), (hw - p.abut_t, hw)]
        y = -hw + p.abut_t + p.vent_span
        for _ in range(p.n_vent - 1):
            out.append((y, y + p.pier_t))
            y += p.pier_t + p.vent_span
        return out

    # ------------------------------------------------------------- outputs
    VIEWS = ("section", "drone", "river", "country")

    def _draw(self, view, stage, tide):
        if view == "section":
            return self.section(stage, tide)
        if view == "drone":
            return self.plan(stage, tide)
        return self.elevation("river" if view == "river" else "country", stage, tide)

    def export_frames(self, outdir="frames_py", dpi=160):
        for v in self.VIEWS:
            d = os.path.join(outdir, v)
            os.makedirs(d, exist_ok=True)
            for st in range(1, 12):
                fig = self._draw(v, st, "low")
                fig.savefig(os.path.join(d, "%s_%02d.png" % (v, st)),
                            dpi=dpi, facecolor=P.sheet)
                plt.close(fig)
            fig = self._draw(v, 11, "high")
            fig.savefig(os.path.join(d, "%s_12_high_tide.png" % v), dpi=dpi,
                        facecolor=P.sheet)
            plt.close(fig)
        print("frames written to", os.path.abspath(outdir))
        return outdir

    def export_plates(self, path="regulator_plates.pdf"):
        with PdfPages(path) as pdf:
            for v in self.VIEWS:
                for st in range(1, 12):
                    fig = self._draw(v, st, "low")
                    pdf.savefig(fig, facecolor=P.sheet)
                    plt.close(fig)
                fig = self._draw(v, 11, "high")
                pdf.savefig(fig, facecolor=P.sheet)
                plt.close(fig)
        print("plates written to", os.path.abspath(path))
        return path

    def export_video(self, path="regulator.mp4", seconds=3.6, cover=None):
        """needs ffmpeg on PATH"""
        d = self.export_frames("_video_frames")
        lst = os.path.join(d, "concat.txt")
        with open(lst, "w") as f:
            if cover:
                f.write("file '%s'\nduration 5.0\n" % os.path.abspath(cover))
            last = None
            for v in self.VIEWS:
                for fn in sorted(os.listdir(os.path.join(d, v))):
                    if fn.endswith(".png"):
                        last = os.path.abspath(os.path.join(d, v, fn))
                        f.write("file '%s'\nduration %.2f\n" % (last, seconds))
            f.write("file '%s'\n" % last)
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-vf", "fps=30,format=yuv420p,scale=1920:1080",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                        path], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("video written to", os.path.abspath(path))
        return path

    def notes(self, path="stage_notes.txt"):
        with open(path, "w", encoding="utf-8") as f:
            for i, (label, title, text, checks) in enumerate(STAGES, 1):
                f.write("STAGE %d  %s\n%s\n%s\n" % (i, label, title, text))
                for c in checks:
                    f.write("  - %s\n" % c)
                f.write("\n")
            for k, v in TIDE_TEXT.items():
                f.write("TIDE %s\n%s\n\n" % (k.upper(), v))
        return path


# ------------------------------------------------------------------ helpers
def _halo():
    import matplotlib.patheffects as pe
    return [pe.withStroke(linewidth=2.2, foreground=P.sheet)]


def _seq(a, b, step):
    out, x = [], a
    while x <= b + 1e-9:
        out.append(x)
        x += step
    return out


def _lin(a, b, n):
    if n == 1:
        return [(a + b) / 2]
    return [a + (b - a) * i / (n - 1.0) for i in range(n)]


def _canvas(fig, xlo, xhi, ybot, ytop):
    if fig is None:
        fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    fig.patch.set_facecolor(P.sheet)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(P.sheet)
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ybot, ytop)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def _footer(ax, p, xlo, xhi, ybot, what, stage):
    label, title = STAGES[min(max(stage, 1), 11) - 1][:2]
    ax.text(xlo + 1, ybot + 1.0,
            "REGULATOR - CONSTRUCTION SEQUENCE   |   %s   |   STAGE %02d/11   %s"
            % (what, stage, title),
            fontsize=7, color=P.line, ha="left", va="bottom", zorder=12)
    ax.text(xhi - 1, ybot + 1.0, p.credit, fontsize=5.6, color=P.dim,
            ha="right", va="bottom", zorder=12)


# ------------------------------------------------------------------- demo
if __name__ == "__main__":
    r = Regulator()
    r.export_frames("frames_py")
    r.export_plates("regulator_plates.pdf")
    r.notes("stage_notes.txt")
    print("vents:", r.p.n_vent, "| structure width: %.2f m" % r.width)
