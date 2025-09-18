#!/usr/bin/env python3
"""
Deck of Endless Treasure — Random Drawer (Display-Fit, No Save)
----------------------------------------------------------------
Drop this script into the folder that contains your Paizo JPGs whose filenames
end in numbers 21..220. On launch, it composes a random treasure layout:

1) Back card (anchor)
2) Back card at (0, +578) relative to the first
3) Back card at (-234, +144) relative to the first
4) Front card at (0, +144) relative to the first
5) A standalone back card cropped to (238, 233) - (738, 575)

Changes from previous version:
- Removed "Save Image..." feature entirely.
- Display auto-resizes to fit the current window (downscales as needed).

Requires: Python 3.9+ and Pillow 10+   pip install pillow
"""

import os
import re
import random
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import scrolledtext as tkst

from PIL import Image, ImageTk, ImageDraw, ImageFilter
from functools import lru_cache
import webbrowser

# ---- Card constants from your spec ----
CARD_W, CARD_H = 744, 1039
# Relative offsets (x, y) from the first (anchor) card:
#OFF_BACK2 = (0, 578)
OFF_BACK2 = (0, 595)
OFF_BACK3 = (-234, 144)
OFF_FRONT = (0, 144)
# Crop box for the standalone back card (left, top, right, bottom)
CROP_BOX = (238, 233, 738, 575)  # -> 500 x 342

# ---- Visual polish ----
BG_COLOR = (16, 59, 44)  # deep felt green
OUTER_MARGIN = 40
RIGHT_GAP = 60  # space between the stacked cluster and the cropped panel
SHADOW_OFFSET = (10, 10)
SHADOW_BLUR = 10
SHADOW_ALPHA = 90  # 0..255

# ---- App metadata ----
APP_TITLE = "Deck of Endless Treasure"
APP_VERSION = "dev"


def script_dir() -> Path:
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path(os.getcwd()).resolve()


def extract_trailing_number(p: Path):
    """
    Extract a card number from a filename.
    - Strict: digits immediately before the extension (e.g., 'foo219.jpg' -> 219).
    - Relaxed: digits followed by an optional small suffix right before the extension
      (e.g., 'foo_001_front.jpg' -> 1, 'bar-12a.jpeg' -> 12).
    Does NOT consider numbers that are not near the extension to avoid product codes.
    Returns int or None.
    """
    name = p.name
    # Strict: digits just before extension
    m = re.search(r'(\d+)(?=\.(?:jpe?g)$)', name, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    # Relaxed: digits + optional short suffix immediately before extension
    m = re.search(r'(\d+)[ _-]*(?:front|back|a|b)?(?=\.(?:jpe?g)$)', name, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def scan_cards(folder: Path):
    """
    Scan for JPG/JPEG files ending with a number in [21, 220].
    Odd -> fronts, Even -> backs.
    Returns (front_paths, back_paths) as lists[Path].
    """
    jpgs = list(folder.glob("*.jpg")) + list(folder.glob("*.JPG")) + \
           list(folder.glob("*.jpeg")) + list(folder.glob("*.JPEG"))

    fronts, backs = [], []
    for p in jpgs:
        n = extract_trailing_number(p)
        if n is None:
            continue
        if 21 <= n <= 220:
            if n % 2 == 1:
                fronts.append(p)
            else:
                backs.append(p)
    return fronts, backs


def paste_with_shadow(canvas_img: Image.Image, card_img: Image.Image, xy):
    """
    Paste a card with a subtle soft shadow for a nicer tabletop look.
    """
    x, y = xy
    # Shadow
    shadow = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    radius = 28  # rounded corner feel
    sd.rounded_rectangle((0, 0, CARD_W, CARD_H), radius=radius, fill=(0, 0, 0, SHADOW_ALPHA))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))
    canvas_img.alpha_composite(shadow, (x + SHADOW_OFFSET[0], y + SHADOW_OFFSET[1]))
    # Card
    canvas_img.alpha_composite(card_img, (x, y))


def compose_treasure(back1: Path, back2: Path, back3: Path, back_for_crop: Path, front: Path) -> Image.Image:
    """
    Build the full-resolution composite as an RGBA Pillow image.
    """
    def load_card(pth: Path) -> Image.Image:
        im = Image.open(pth).convert("RGBA")
        # Ensure consistent size
        if im.width != CARD_W or im.height != CARD_H:
            im = im.resize((CARD_W, CARD_H), Image.LANCZOS)
        return im

    im_back1 = load_card(back1)
    im_back2 = load_card(back2)
    im_back3 = load_card(back3)
    im_front = load_card(front)

    # Anchor chosen so left-shifted third card keeps a margin
    base_x = OUTER_MARGIN + abs(OFF_BACK3[0])  # ensures OUTER_MARGIN at left-most
    base_y = OUTER_MARGIN

    # Positions
    p1 = (base_x, base_y)                               # back #1
    p2 = (base_x + OFF_BACK2[0], base_y + OFF_BACK2[1]) # back #2
    p3 = (base_x + OFF_BACK3[0], base_y + OFF_BACK3[1]) # back #3
    p4 = (base_x + OFF_FRONT[0], base_y + OFF_FRONT[1]) # front

    # Cluster bounds
    left = min(p1[0], p2[0], p3[0], p4[0])
    right = max(p1[0], p2[0], p3[0], p4[0]) + CARD_W
    top = min(p1[1], p2[1], p3[1], p4[1])
    bottom = max(p1[1], p2[1], p3[1], p4[1]) + CARD_H

    # Position for the standalone cropped back on the right
    crop_w = CROP_BOX[2] - CROP_BOX[0]  # 500
    crop_h = CROP_BOX[3] - CROP_BOX[1]  # 342
    panel_x = right + RIGHT_GAP
    panel_y = OUTER_MARGIN

    # Overall canvas size
    canvas_w = panel_x + crop_w + OUTER_MARGIN
    canvas_h = max(bottom + OUTER_MARGIN, panel_y + crop_h + OUTER_MARGIN)

    # Create background
    canvas = Image.new("RGBA", (canvas_w, canvas_h), BG_COLOR + (255,))

    # Paint sequence (z-order)
    paste_with_shadow(canvas, im_back1, p1)
    paste_with_shadow(canvas, im_back2, p2)
    paste_with_shadow(canvas, im_back3, p3)
    paste_with_shadow(canvas, im_front, p4)

    # Cropped standalone back with subtle mat + shadow
    im_crop_src = load_card(back_for_crop)
    im_crop = im_crop_src.crop(CROP_BOX)
    mat_pad = 16
    mat_w, mat_h = im_crop.width + mat_pad * 2, im_crop.height + mat_pad * 2
    mat = Image.new("RGBA", (mat_w, mat_h), (238, 234, 216, 255))  # light parchment tone

    shadow = Image.new("RGBA", (mat_w, mat_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((0, 0, mat_w, mat_h), radius=20, fill=(0, 0, 0, SHADOW_ALPHA))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))
    canvas.alpha_composite(shadow, (panel_x + SHADOW_OFFSET[0], panel_y + SHADOW_OFFSET[1]))

    canvas.alpha_composite(mat, (panel_x, panel_y))
    canvas.alpha_composite(im_crop, (panel_x + mat_pad, panel_y + mat_pad))

    # Subtle overlay on the front card: show its number and side
    try:
        front_num = extract_trailing_number(front)
        if front_num is not None:
            draw = ImageDraw.Draw(canvas)
            label = f"#{front_num} Front"
            bbox = draw.textbbox((0, 0), label)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            pad_x, pad_y = 10, 6
            box_w = tw + pad_x * 2
            box_h = th + pad_y * 2
            inset = 8
            x = p4[0] + CARD_W - inset - box_w
            y = p4[1] + CARD_H - inset - box_h
            box = (x, y, x + box_w, y + box_h)
            draw.rounded_rectangle(box, radius=10, fill=(0, 0, 0, 120))
            draw.text((x + pad_x, y + pad_y), label, fill=(240, 240, 240, 255))
    except Exception:
        pass

    return canvas


def index_all_cards(folder: Path):
    """
    Index JPG/JPEG files ending with a trailing number 1..220.
    Returns a dict[int, Path] choosing a deterministic (sorted) path when multiple exist.
    """
    jpgs = list(folder.glob("*.jpg")) + list(folder.glob("*.JPG")) + \
           list(folder.glob("*.jpeg")) + list(folder.glob("*.JPEG"))
    buckets = {}
    unnumbered = []
    for p in jpgs:
        n = extract_trailing_number(p)
        if n is None:
            # Keep track of unnumbered candidates for special cases (e.g., first card front)
            unnumbered.append(p)
            continue
        if 1 <= n <= 220:
            buckets.setdefault(n, []).append(p)
    chosen = {}
    for n, paths in buckets.items():
        paths_sorted = sorted(paths, key=lambda q: q.name.lower())
        chosen[n] = paths_sorted[0]

    # Special-case pairing: if #1 is missing but #2 exists and there is a file
    # whose stem matches the #2 file stem with trailing digits removed, treat it as #1.
    def _strip_trailing_digits(stem: str) -> str:
        return re.sub(r"\d+$", "", stem)

    if 1 not in chosen and 2 in chosen and unnumbered:
        base = _strip_trailing_digits(chosen[2].stem)
        # Prefer exact stem match among unnumbered
        candidates = [p for p in unnumbered if _strip_trailing_digits(p.stem) == base]
        if candidates:
            chosen[1] = sorted(candidates, key=lambda q: q.name.lower())[0]
    return chosen


class RandomFrame(ttk.Frame):
    def __init__(self, master, app, folder: Path):
        super().__init__(master)
        self.app = app
        self.folder = folder

        # Data
        self.fronts, self.backs = scan_cards(self.folder)
        self.fullres_image = None
        self.tk_image = None
        self.current_files = {}
        self.current_paths = {}
        self._resize_job = None
        self._has_fit_once = False  # fit window size only on first successful generate

        # Layout
        self.topbar = ttk.Frame(self)
        self.topbar.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(12, 8))

        hdr = ttk.Label(self.topbar, text="Deck of Endless Treasure — Random Drawer", style="Header.TLabel")
        hdr.pack(side=tk.LEFT)

        # Right-side vertical button stack (New, Edit)
        right = ttk.Frame(self.topbar)
        right.pack(side=tk.RIGHT)
        self.btn_new = ttk.Button(right, text="New Treasure", command=self.generate)
        self.btn_new.pack(side=tk.TOP, padx=(8, 0))
        self.btn_edit = ttk.Button(right, text="Edit", command=self._cmd_edit_to_custom)
        self.btn_edit.pack(side=tk.TOP, padx=(8, 0), pady=(6, 0))

        self.image_panel = ttk.Frame(self)
        self.image_panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.image_label = None

        self.status = ttk.Label(self, text="", style="Sub.TLabel")
        self.status.pack(side=tk.BOTTOM, anchor="w", padx=14, pady=(0, 10))

        # Resize handling
        self.bind("<Configure>", self._on_resize)

        # Keyboard shortcuts (active when Random tab selected)
        self.bind_all("<space>", self._kb_new)
        self.bind_all("n", self._kb_new)
        self.bind_all("N", self._kb_new)
        self.bind_all("<Return>", self._kb_new)

        # Initial render
        if len(self.backs) < 4 or len(self.fronts) < 1:
            self.btn_new.state(["disabled"])  # can't generate yet
            self.btn_edit.state(["disabled"])  # can't edit yet
            self.show_empty_state()
        else:
            self.btn_new.state(["!disabled"])
            self.btn_edit.state(["!disabled"])
            self.generate()

    def show_empty_state(self):
        """Show message + prominent button to select the cards folder."""
        # Clear panel
        for child in self.image_panel.winfo_children():
            child.destroy()

        # Add generous padding so the text doesn't feel cramped against the green
        wrap_margin = 240  # total horizontal margin reserved for padding
        wrap = min(max(self.winfo_width() - wrap_margin, 520), 980)
        c = ttk.Frame(self.image_panel, padding=32)
        c.pack(fill=tk.BOTH, expand=True)

        inner = ttk.Frame(c, padding=16)
        inner.pack(expand=True)

        msg = ("A folder must be selected that contains \nyour 'Deck of Endless Treasure' JPG images.")
        lbl = ttk.Label(inner, text=msg, style="Sub.TLabel", justify=tk.CENTER, wraplength=wrap, padding=(18, 12))
        lbl.pack(padx=24, pady=(14, 22))

        btn = ttk.Button(inner, text="Select Folder…", command=self.select_folder_via_dialog)
        btn.configure(width=28)
        btn.pack(pady=(0, 10))

    def select_folder_via_dialog(self):
        chosen = filedialog.askdirectory(
            title="Select folder with Endless Treasure JPGs",
            initialdir=str(self.folder),
            mustexist=True,
            parent=self,
        )
        if not chosen:
            return
        new_folder = Path(chosen)
        fronts, backs = scan_cards(new_folder)
        if len(backs) >= 4 and len(fronts) >= 1:
            # Propagate selection to the whole app (updates both tabs)
            self.app.set_folder(new_folder)
        else:
            messagebox.showwarning(
                "Not enough images",
                "The selected folder does not contain enough valid JPGs.\n\n"
                "Requirements:\n"
                "- Filenames end with numbers 21..220\n"
                "- Even numbers are backs (need 4+)\n"
                "- Odd numbers are fronts (need 1+)",
                parent=self,
            )

    def pick_random(self):
        back_choices = random.sample(self.backs, 4)
        front_choice = random.choice(self.fronts)
        return back_choices, front_choice

    def generate(self):
        try:
            backs, front = self.pick_random()
            b1, b2, b3, b_crop = backs
            self.fullres_image = compose_treasure(b1, b2, b3, b_crop, front)
            self.current_files = {
                "Back #1": b1.name,
                "Back #2": b2.name,
                "Back #3": b3.name,
                "Front": front.name,
                "Cropped Back": b_crop.name
            }
            self.current_paths = {
                "Back #1": b1,
                "Back #2": b2,
                "Back #3": b3,
                "Front": front,
                "Cropped Back": b_crop,
            }
            # Fit window size only once (on first render) to establish default size
            if not self._has_fit_once:
                self.fit_window_to_image(self.fullres_image)
                self._has_fit_once = True
            else:
                # Keep current window size; just re-render to fit existing panel
                self.render_for_display(self.fullres_image)
            self.update_status()
        except Exception as e:
            messagebox.showerror("Error generating treasure", str(e), parent=self)

    def _card_num_from_path(self, p: Path):
        try:
            return extract_trailing_number(p)
        except Exception:
            return None

    def _item_num_for_card(self, n: int):
        if n is None:
            return None
        if 21 <= n <= 220:
            odd = n if n % 2 == 1 else n - 1
            return ((odd - 21) // 2) + 1
        return None

    def _cmd_edit_to_custom(self):
        # Compute item numbers from the last generated selection and open Custom tab
        if not self.current_paths:
            return
        get_item = lambda key: self._item_num_for_card(self._card_num_from_path(self.current_paths.get(key)))
        front_item = get_item("Front")
        b1_item = get_item("Back #1")
        b2_item = get_item("Back #2")
        b3_item = get_item("Back #3")
        plot_item = get_item("Cropped Back")
        try:
            if hasattr(self.app, 'custom_tab') and self.app.custom_tab:
                self.app.custom_tab.set_items(front_item=front_item, passive=b1_item, active=b2_item, quirk=b3_item, plot_hook=plot_item, render=True)
                # Switch to the Custom tab
                self.app.notebook.select(self.app.custom_tab)
        except Exception:
            # Fallback: just switch to Custom
            try:
                self.app.notebook.select(self.app.custom_tab)
            except Exception:
                pass

    # Keyboard helpers
    def _is_active(self):
        try:
            sel = self.app.notebook.select()
            widget = self.app.nametowidget(sel)
            return widget is self
        except Exception:
            return True

    def _kb_new(self, event):
        if self._is_active():
            # Only when generation is enabled
            state = self.btn_new.state()
            if 'disabled' not in state:
                self.generate()

    def _on_resize(self, event):
        # Debounce resize events for smoother behavior
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._do_resize)

    def _do_resize(self):
        self._resize_job = None
        if self.fullres_image is not None:
            self.render_for_display(self.fullres_image)

    def render_for_display(self, im: Image.Image):
        """
        Resize for display to fit the current window (downscale as needed).
        """
        # Ensure image label exists and panel is cleared of empty-state
        if self.image_label is None or not self.image_label.winfo_exists():
            for child in self.image_panel.winfo_children():
                child.destroy()
            self.image_label = ttk.Label(self.image_panel)
            self.image_label.pack(fill=tk.BOTH, expand=True)

        # Determine available drawing area inside the image panel
        panel_w = self.image_panel.winfo_width()
        panel_h = self.image_panel.winfo_height()

        # When the window first opens, these can be tiny (1x1); estimate from window
        if panel_w <= 1 or panel_h <= 1:
            panel_w = max(self.winfo_width() - 40, 200)
            panel_h = max(self.winfo_height() - 160, 200)

        # Keep aspect ratio; no upscaling beyond 1.0 for crispness
        scale = min(panel_w / im.width, panel_h / im.height, 1.0)
        new_w = max(1, int(im.width * scale))
        new_h = max(1, int(im.height * scale))
        disp = im if (new_w == im.width and new_h == im.height) else im.resize((new_w, new_h), Image.LANCZOS)

        self.tk_image = ImageTk.PhotoImage(disp)
        self.image_label.configure(image=self.tk_image)

    def fit_window_to_image(self, im: Image.Image):
        """Resize the main window to closely match the space needed for the image.
        Prefers 1:1 scale of the composed image; if screen is smaller, scales down.
        """
        # Ensure widgets have computed sizes
        self.update_idletasks()

        # Known paddings from pack configs
        PADX_TOPBAR = 14
        PADY_TOPBAR = (12, 8)
        PADX_PANEL = 12
        PADY_PANEL = 8
        PADX_STATUS = 14
        PADY_STATUS = (0, 10)

        # Requested sizes of header and status
        topbar_w = getattr(self, 'topbar', self).winfo_reqwidth()
        topbar_h = getattr(self, 'topbar', self).winfo_reqheight()
        status_w = self.status.winfo_reqwidth()
        status_h = self.status.winfo_reqheight()

        # Max allowed total window size (leave a small margin from screen edges)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        max_win_w = max(400, screen_w - 40)
        max_win_h = max(300, screen_h - 80)

        # Overhead height excluding the image area
        overhead_h = (topbar_h + PADY_TOPBAR[0] + PADY_TOPBAR[1]) + (PADY_PANEL * 2) + (status_h + PADY_STATUS[0] + PADY_STATUS[1])

        # Width contributions of other rows
        non_img_row_w = max(topbar_w + PADX_TOPBAR * 2, status_w + PADX_STATUS * 2)

        # Target image display size (prefer full size, clamp to available screen space)
        max_img_w = max_win_w  # window width is max of image width+panel pad vs other rows; clamp later via max()
        max_img_h = max_win_h - overhead_h
        max_img_h = max(100, max_img_h)

        scale = min(max_img_w / im.width, max_img_h / im.height, 1.0)
        disp_w = max(1, int(im.width * scale))
        disp_h = max(1, int(im.height * scale))

        # Compute final window size
        win_w = max(disp_w + PADX_PANEL * 2, non_img_row_w)
        win_h = overhead_h + disp_h

        # Clamp to screen just in case
        win_w = min(win_w, max_win_w)
        win_h = min(win_h, max_win_h)

        # On the first sizing, make the window a bit shorter (~10%)
        try:
            if hasattr(self, "_has_fit_once") and self._has_fit_once is False:
                win_h = max(300, int(win_h * 0.9))
        except Exception:
            pass

        # Apply and render
        # Apply to the toplevel window hosting this frame
        toplevel = self.winfo_toplevel()
        toplevel.geometry(f"{win_w}x{win_h}")
        toplevel.update_idletasks()
        self.render_for_display(im)

    def update_status(self):
        if not self.current_files:
            self.status.configure(text="")
            return

        def endnum(name):
            m = re.search(r'(\d+)(?=\.(?:jpe?g)$)', name, re.IGNORECASE)
            return m.group(1) if m else name

        text = "  • " + " | ".join(f"{k}: {endnum(v)}" for k, v in self.current_files.items())
        # Add quick hint for keyboard usage
        text += "   —   Press N or Space for new"
        self.status.configure(text=text)


class BrowserFrame(ttk.Frame):
    """Basic single-card browser scaffold (Step 2)."""
    SECTIONS = [
        ("Instructions (1–12)", 1, 12),
        ("Damage by Level (13–14)", 13, 14),
        ("DC by Level (15–16)", 15, 16),
        ("Misc. (17–20)", 17, 20),
        ("Items (21–220)", 21, 220),
    ]

    def __init__(self, master, app, folder: Path):
        super().__init__(master)
        self.app = app
        self.folder = folder
        self.index = index_all_cards(self.folder)
        self.current_section = 4  # default to Items
        self.current_num = self._first_available_in_section(self.current_section) or 21
        self.tk_image = None
        self._resize_job = None

        # Top bar (multi-row to avoid overflow on narrow windows)
        self.topbar = ttk.Frame(self)
        self.topbar.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(12, 8))

        # Row 1: Title
        row1 = ttk.Frame(self.topbar)
        row1.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(row1, text="Card Browser", style="Header.TLabel").pack(side=tk.LEFT)

        # Row 2: Section selector
        row2 = ttk.Frame(self.topbar)
        row2.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))
        ttk.Label(row2, text="Section:", style="Sub.TLabel").pack(side=tk.LEFT)
        self.section_var = tk.StringVar()
        names = [s[0] for s in self.SECTIONS]
        self.section_cb = ttk.Combobox(row2, values=names, textvariable=self.section_var, state="readonly", width=26)
        self.section_cb.current(self.current_section)
        self.section_cb.pack(side=tk.LEFT, padx=(8, 0))
        try:
            self.section_cb.configure(font=("Segoe UI", 10))
        except tk.TclError:
            pass
        self.section_cb.bind("<<ComboboxSelected>>", self._on_section_change)

        # Row 3: Navigation
        row3 = ttk.Frame(self.topbar)
        row3.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))
        ttk.Label(row3, text="Item #", style="Sub.TLabel").pack(side=tk.LEFT)
        self.jump_var = tk.StringVar()
        self.jump_entry = ttk.Entry(row3, textvariable=self.jump_var, width=6)
        self.jump_entry.pack(side=tk.LEFT)
        try:
            self.jump_entry.configure(font=("Segoe UI", 10))
        except tk.TclError:
            pass
        self.jump_entry.bind("<Return>", self._on_jump)
        self.jump_entry.bind("<KP_Enter>", self._on_jump)
        ttk.Button(row3, text="Go", command=self._on_jump, style="Toolbar.TButton").pack(side=tk.LEFT, padx=(6, 12))

        self.btn_prev = ttk.Button(row3, text="Prev", command=self._prev, style="Toolbar.TButton")
        self.btn_prev.pack(side=tk.LEFT)
        self.btn_next = ttk.Button(row3, text="Next", command=self._next, style="Toolbar.TButton")
        self.btn_next.pack(side=tk.LEFT, padx=(6, 0))
        self.btn_flip = ttk.Button(row3, text="Flip", command=self._flip, style="Toolbar.TButton")
        self.btn_flip.pack(side=tk.LEFT, padx=(12, 0))

        # Display and status
        self.image_panel = ttk.Frame(self)
        self.image_panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.image_label = None

        self.status = ttk.Label(self, text="", style="Sub.TLabel")
        self.status.pack(side=tk.BOTTOM, anchor="w", padx=14, pady=(0, 10))

        self.bind("<Configure>", self._on_resize)

        # Keyboard navigation (scoped by checking active tab)
        self.bind_all("<Left>", self._kb_prev)
        self.bind_all("<Right>", self._kb_next)
        self.bind_all("<Home>", self._kb_home)
        self.bind_all("<End>", self._kb_end)
        self.bind_all("<Control-l>", self._kb_focus_jump)
        self._render_current()

    def set_folder(self, folder: Path):
        self.folder = folder
        self.index = index_all_cards(self.folder)
        # Stay in the same section, jump to first available
        n = self._first_available_in_section(self.current_section)
        if n:
            self.current_num = n
        self._render_current()

    def _on_resize(self, event):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._do_resize)

    def _do_resize(self):
        self._resize_job = None
        if self.tk_image is not None and hasattr(self, "_last_pillow"):
            self._render_image(self._last_pillow)

    def _section_bounds(self, idx):
        _, a, b = self.SECTIONS[idx]
        return a, b

    def _first_available_in_section(self, idx):
        a, b = self._section_bounds(idx)
        for n in range(a, b + 1):
            if n in self.index:
                return n
        return None

    def _nearest_available(self, target, a, b, step=1):
        # Search from target outward within [a,b]
        if target in self.index:
            return target
        # step positive for forward, negative for backward search
        forward = range(target + (1 if step >= 0 else -1), b + 1 if step >= 0 else a - 1, 1 if step >= 0 else -1)
        for n in forward:
            if a <= n <= b and n in self.index:
                return n
        backward = range(target - (1 if step >= 0 else -1), a - 1 if step >= 0 else b + 1, -1 if step >= 0 else 1)
        for n in backward:
            if a <= n <= b and n in self.index:
                return n
        return None

    def _on_section_change(self, event=None):
        self.current_section = self.section_cb.current()
        n = self._first_available_in_section(self.current_section)
        if n is not None:
            self.current_num = n
        self._render_current()

    def _on_jump(self, event=None):
        """Interpret entry as Item # and go to that item's card.
        Item #1 corresponds to card 21 (front), Item #2 -> 23 (front), etc.
        """
        txt = self.jump_var.get().strip()
        try:
            item = int(txt)
        except ValueError:
            return
        # Clamp to valid item range 1..100
        item = max(1, min(100, item))
        n = self._card_num_for_item(item)
        if n is None:
            # Find nearest item with available card
            for delta in range(1, 100):
                up = item + delta
                down = item - delta
                if up <= 100:
                    n = self._card_num_for_item(up)
                    if n is not None:
                        item = up
                        break
                if down >= 1:
                    n = self._card_num_for_item(down)
                    if n is not None:
                        item = down
                        break
        if n is not None:
            self.current_num = n
            # Ensure section shows Items
            self.current_section = 4
            self.section_cb.current(4)
            self._render_current()

    def _prev(self):
        if not self.index:
            return
        # Browse across all cards with wrap-around
        current = self.current_num
        n = current - 1
        while n >= 1:
            if n in self.index:
                self.current_num = n
                self._sync_section_to_number(n)
                self._render_current()
                return
            n -= 1
        # Wrap to max and go downward
        n = 220
        while n > current:
            if n in self.index:
                self.current_num = n
                self._sync_section_to_number(n)
                self._render_current()
                return
            n -= 1

    def _next(self):
        if not self.index:
            return
        # Browse across all cards with wrap-around
        current = self.current_num
        n = current + 1
        while n <= 220:
            if n in self.index:
                self.current_num = n
                self._sync_section_to_number(n)
                self._render_current()
                return
            n += 1
        # Wrap to min and go upward
        n = 1
        while n < current:
            if n in self.index:
                self.current_num = n
                self._sync_section_to_number(n)
                self._render_current()
                return
            n += 1

    def _render_current(self):
        p = self.index.get(self.current_num)
        if not p:
            # Clear or show empty-state
            for child in self.image_panel.winfo_children():
                child.destroy()
            self.image_label = None
            # Empty state with folder picker reuse from Random tab
            c = ttk.Frame(self.image_panel, padding=32)
            c.pack(fill=tk.BOTH, expand=True)
            inner = ttk.Frame(c, padding=16)
            inner.pack(expand=True)
            ttk.Label(inner, text="No images available in this section.", style="Sub.TLabel").pack(pady=(0, 10))
            ttk.Button(inner, text="Select Folder…", command=self._delegate_folder_dialog).pack()
            self.status.configure(text="")
            return
        im = self._compose_single_card(p)
        self._last_pillow = im
        self._render_image(im)
        side = "Front" if (self.current_num % 2 == 1) else "Back"
        self.status.configure(text=f"Card #{self.current_num} {side} — {p.name}")
        # Update controls state
        self._update_controls()
        # Reflect Item # in the entry when viewing an item card; blank otherwise
        item_no = self._item_num_for_card(self.current_num)
        self.jump_var.set(str(item_no) if item_no is not None else "")

    def _update_controls(self):
        # In loop mode, enable prev/next if there's more than one card available overall
        enabled = len(self.index) > 1
        self.btn_prev.state(("!disabled",) if enabled else ("disabled",))
        self.btn_next.state(("!disabled",) if enabled else ("disabled",))
        # Flip enablement
        pair = self.current_num + 1 if (self.current_num % 2 == 1) else self.current_num - 1
        self.btn_flip.state(("!disabled",) if (1 <= pair <= 220 and pair in self.index) else ("disabled",))

    def _compose_single_card(self, path: Path) -> Image.Image:
        im = _load_rgba_card_cached(str(path))
        # Build a canvas with margins like the random view
        margin = OUTER_MARGIN
        canvas = Image.new("RGBA", (CARD_W + margin * 2, CARD_H + margin * 2), BG_COLOR + (255,))
        paste_with_shadow(canvas, im, (margin, margin))
        # Subtle number overlay (bottom-right)
        try:
            draw = ImageDraw.Draw(canvas)
            side = "Front" if (self.current_num % 2 == 1) else "Back"
            label = f"#{self.current_num} {side}"
            # Measure text box
            bbox = draw.textbbox((0, 0), label)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            pad_x, pad_y = 10, 6
            box_w = tw + pad_x * 2
            box_h = th + pad_y * 2
            x = canvas.width - margin - 8 - box_w
            y = canvas.height - margin - 8 - box_h
            # Semi-opaque background
            box = (x, y, x + box_w, y + box_h)
            ImageDraw.Draw(canvas).rounded_rectangle(box, radius=10, fill=(0, 0, 0, 120))
            # Text
            draw.text((x + pad_x, y + pad_y), label, fill=(240, 240, 240, 255))
        except Exception:
            pass
        return canvas

    def _render_image(self, im: Image.Image):
        if self.image_label is None or not self.image_label.winfo_exists():
            for child in self.image_panel.winfo_children():
                child.destroy()
            self.image_label = ttk.Label(self.image_panel)
            self.image_label.pack(fill=tk.BOTH, expand=True)

        panel_w = self.image_panel.winfo_width()
        panel_h = self.image_panel.winfo_height()
        if panel_w <= 1 or panel_h <= 1:
            panel_w = max(self.winfo_width() - 40, 200)
            panel_h = max(self.winfo_height() - 160, 200)
        scale = min(panel_w / im.width, panel_h / im.height, 1.0)
        new_w = max(1, int(im.width * scale))
        new_h = max(1, int(im.height * scale))
        disp = im if (new_w == im.width and new_h == im.height) else im.resize((new_w, new_h), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(disp)
        self.image_label.configure(image=self.tk_image)

    # Item mapping helpers
    def _item_num_for_card(self, n: int):
        if 21 <= n <= 220:
            # Pair: (21,22)->1, (23,24)->2, ...
            odd = n if n % 2 == 1 else n - 1
            return ((odd - 21) // 2) + 1
        return None

    def _card_num_for_item(self, item: int):
        # Preferred front card for an item
        front = 21 + (item - 1) * 2
        back = front + 1
        if front in self.index:
            return front
        if back in self.index:
            return back
        return None

    def _flip(self):
        # Flip between front/back pair numbers
        pair = self.current_num + 1 if (self.current_num % 2 == 1) else self.current_num - 1
        if 1 <= pair <= 220 and pair in self.index:
            # Update section to whatever contains the pair
            self.current_num = pair
            self._sync_section_to_number(pair)
            self._render_current()

    def _sync_section_to_number(self, n: int):
        # Adjust combobox to the section that contains n
        for i, (_, a, b) in enumerate(self.SECTIONS):
            if a <= n <= b:
                if i != self.current_section:
                    self.current_section = i
                    self.section_cb.current(i)
                return

    def _delegate_folder_dialog(self):
        # Reuse the Random tab's folder picker
        if hasattr(self.app, "random_tab"):
            self.app.random_tab.select_folder_via_dialog()

    # Keyboard helpers
    def _is_active(self):
        try:
            sel = self.app.notebook.select()
            widget = self.app.nametowidget(sel)
            return widget is self
        except Exception:
            return True

    def _kb_prev(self, event):
        if self._is_active():
            self._prev()

    def _kb_next(self, event):
        if self._is_active():
            self._next()

    def _kb_home(self, event):
        if self._is_active():
            n = self._first_available_in_section(self.current_section)
            if n is not None:
                self.current_num = n
                self._render_current()

    def _kb_end(self, event):
        if self._is_active():
            a, b = self._section_bounds(self.current_section)
            for n in range(b, a - 1, -1):
                if n in self.index:
                    self.current_num = n
                    self._render_current()
                    break

    def _kb_focus_jump(self, event):
        if self._is_active():
            self.jump_entry.focus_set()


@lru_cache(maxsize=32)
def _load_rgba_card_cached(path: str) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    if im.size != (CARD_W, CARD_H):
        im = im.resize((CARD_W, CARD_H), Image.LANCZOS)
    return im


class CustomFrame(ttk.Frame):
    """Compose a treasure from specific item numbers.

    Lets you pick item numbers for:
      - Front (prefers front; falls back to back if needed)
      - Back #1, Back #2, Back #3 (prefer backs)
      - Plot Hook (prefer back)

    Uses the same layout and styling as the Random tab.
    """

    def __init__(self, master, app, folder: Path):
        super().__init__(master)
        self.app = app
        self.folder = folder
        self.index = index_all_cards(self.folder)

        self.fullres_image = None
        self.tk_image = None
        self.image_label = None
        self._resize_job = None
        self._has_fit_once = False

        # Top bar
        self.topbar = ttk.Frame(self)
        self.topbar.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(12, 8))
        ttk.Label(self.topbar, text="Custom Treasure", style="Header.TLabel").pack(side=tk.LEFT)

        # Inputs row
        self.ctrl_row = ttk.Frame(self)
        self.ctrl_row.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(0, 4))

        def labeled_entry(parent, label, width=6):
            f = ttk.Frame(parent)
            f.pack(side=tk.LEFT, padx=(0, 12))
            ttk.Label(f, text=label, style="Sub.TLabel").pack(side=tk.TOP, anchor="w")
            var = tk.StringVar()
            e = ttk.Entry(f, textvariable=var, width=width)
            try:
                e.configure(font=("Segoe UI", 10))
            except tk.TclError:
                pass
            e.pack(side=tk.TOP)
            return var, e

        self.front_var, self.front_entry = labeled_entry(self.ctrl_row, "Front Item #")
        self.b1_var, self.b1_entry = labeled_entry(self.ctrl_row, "Passive")
        self.b2_var, self.b2_entry = labeled_entry(self.ctrl_row, "Active")
        self.b3_var, self.b3_entry = labeled_entry(self.ctrl_row, "Quirk")
        self.bc_var, self.bc_entry = labeled_entry(self.ctrl_row, "Plot Hook")

        # Buttons row
        btns = ttk.Frame(self)
        btns.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(0, 4))
        self.btn_render = ttk.Button(btns, text="Render", command=self.render_custom, style="Toolbar.TButton")
        self.btn_render.pack(side=tk.LEFT)
        ttk.Button(btns, text="Sync Plot Hook", command=self._sync_plot_hook, style="Toolbar.TButton").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="Random Backs", command=self._randomize_backs, style="Toolbar.TButton").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="Random Front", command=self._random_front, style="Toolbar.TButton").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btns, text="Full Random", command=self._full_random, style="Toolbar.TButton").pack(side=tk.LEFT, padx=(8, 0))

        # Display area
        self.image_panel = ttk.Frame(self)
        self.image_panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.status = ttk.Label(self, text="", style="Sub.TLabel")
        self.status.pack(side=tk.BOTTOM, anchor="w", padx=14, pady=(0, 10))

        # Bindings
        self.bind("<Configure>", self._on_resize)
        for ent in (self.front_entry, self.b1_entry, self.b2_entry, self.b3_entry, self.bc_entry):
            ent.bind("<Return>", lambda e: self.render_custom())
            ent.bind("<KP_Enter>", lambda e: self.render_custom())

        self._init_defaults()
        self._try_initial_render()

    def set_folder(self, folder: Path):
        self.folder = folder
        self.index = index_all_cards(self.folder)
        self._try_initial_render()

    def set_items(self, *, front_item=None, passive=None, active=None, quirk=None, plot_hook=None, render=True):
        # Accept ints or strings; ignore None values
        def set_if(var, value):
            if value is None:
                return
            try:
                n = int(value)
            except Exception:
                return
            var.set(str(n))
        set_if(self.front_var, front_item)
        set_if(self.b1_var, passive)
        set_if(self.b2_var, active)
        set_if(self.b3_var, quirk)
        set_if(self.bc_var, plot_hook)
        if render:
            self.render_custom()

    # Availability helpers
    def _available_items_any(self):
        items = []
        for item in range(1, 101):
            if self._path_for_item(item, prefer_front=True) or self._path_for_item(item, prefer_front=False):
                items.append(item)
        return items

    def _available_items_with_back(self):
        items = []
        for item in range(1, 101):
            if self._path_for_item(item, prefer_front=False):
                items.append(item)
        return items

    def _init_defaults(self):
        any_items = self._available_items_any()
        back_items = self._available_items_with_back()
        self.front_var.set(str(any_items[0] if any_items else 1))
        if len(back_items) >= 3:
            self.b1_var.set(str(back_items[0]))
            self.b2_var.set(str(back_items[1]))
            self.b3_var.set(str(back_items[2]))
            self.bc_var.set(str(back_items[0]))
        elif back_items:
            self.b1_var.set(str(back_items[0]))
            self.b2_var.set(str(back_items[min(1, len(back_items)-1)]))
            self.b3_var.set(str(back_items[min(2, len(back_items)-1)]))
            self.bc_var.set(str(back_items[0]))
        else:
            self.b1_var.set("1"); self.b2_var.set("2"); self.b3_var.set("3"); self.bc_var.set("1")

    def _try_initial_render(self):
        if self._available_items_with_back() and self._available_items_any():
            try:
                self.render_custom()
            except Exception:
                self._show_empty_state()
        else:
            self._show_empty_state()

    def _show_empty_state(self):
        for child in self.image_panel.winfo_children():
            child.destroy()
        c = ttk.Frame(self.image_panel, padding=32)
        c.pack(fill=tk.BOTH, expand=True)
        inner = ttk.Frame(c, padding=16)
        inner.pack(expand=True)
        ttk.Label(inner, text="Select a folder with valid JPGs to render.", style="Sub.TLabel").pack(pady=(0, 10))
        ttk.Button(inner, text="Select Folder…", command=self._delegate_folder_dialog).pack()
        self.status.configure(text="")

    def _delegate_folder_dialog(self):
        if hasattr(self.app, "random_tab"):
            self.app.random_tab.select_folder_via_dialog()

    def _parse_item(self, s: str):
        try:
            n = int(s.strip())
        except Exception:
            return None
        return n if 1 <= n <= 100 else None

    def _front_card_num_for_item(self, item: int):
        return 21 + (item - 1) * 2

    def _path_for_item(self, item: int, prefer_front: bool):
        front = self._front_card_num_for_item(item)
        back = front + 1
        if prefer_front:
            return self.index.get(front) or self.index.get(back)
        else:
            return self.index.get(back) or self.index.get(front)

    def _on_resize(self, event):
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._do_resize)

    def _do_resize(self):
        self._resize_job = None
        if self.fullres_image is not None:
            self.render_for_display(self.fullres_image)

    def _rand_sample_backs(self, k=3):
        pool = self._available_items_with_back()
        if len(pool) >= k:
            return random.sample(pool, k)
        elif pool:
            out = []
            idx = 0
            while len(out) < k:
                out.append(pool[idx % len(pool)])
                idx += 1
            return out
        else:
            return [1, 2, 3]

    def _randomize_backs(self):
        b1, b2, b3 = self._rand_sample_backs(3)
        self.b1_var.set(str(b1))
        self.b2_var.set(str(b2))
        self.b3_var.set(str(b3))
        self.bc_var.set(str(b1))
        self.render_custom()

    def _available_items_with_front(self):
        items = []
        for item in range(1, 101):
            n = self._front_card_num_for_item(item)
            if n in self.index:
                items.append(item)
        return items

    def _random_front(self):
        pool = self._available_items_with_front()
        if not pool:
            pool = self._available_items_any()
        if not pool:
            messagebox.showwarning("No items", "No items available to set as Front.", parent=self)
            return
        self.front_var.set(str(random.choice(pool)))
        self.render_custom()

    def _full_random(self):
        # Randomize front and backs together
        pool_f = self._available_items_with_front() or self._available_items_any()
        pool_b = self._available_items_with_back()
        if not pool_f or not pool_b:
            messagebox.showwarning("Not enough images", "Need at least one front and some backs to randomize.", parent=self)
            return
        self.front_var.set(str(random.choice(pool_f)))
        b1, b2, b3 = self._rand_sample_backs(3)
        self.b1_var.set(str(b1))
        self.b2_var.set(str(b2))
        self.b3_var.set(str(b3))
        self.bc_var.set(str(b1))
        self.render_custom()

    def _sync_plot_hook(self):
        # Copy the Quirk item number into Plot Hook
        item = self._parse_item(self.b3_var.get()) or 1
        self.bc_var.set(str(item))
        self.render_custom()

    def render_custom(self):
        labels = [
            ("Front", self.front_var.get(), True),
            ("Back #1", self.b1_var.get(), False),
            ("Back #2", self.b2_var.get(), False),
            ("Back #3", self.b3_var.get(), False),
            ("Plot Hook", self.bc_var.get(), False),
        ]
        resolved = {}
        missing = []
        for name, txt, prefer_front in labels:
            item = self._parse_item(txt)
            if item is None:
                missing.append(f"{name}: invalid item # '{txt}' (1–100)")
                continue
            path = self._path_for_item(item, prefer_front=prefer_front)
            if not path:
                side = "front" if prefer_front else "back"
                missing.append(f"{name}: item {item} has no {side} card found")
            else:
                resolved[name] = (item, path)

        if missing:
            messagebox.showwarning("Missing cards", "\n".join(missing), parent=self)
            if not self.fullres_image:
                self._show_empty_state()
            return

        back1 = resolved["Back #1"][1]
        back2 = resolved["Back #2"][1]
        back3 = resolved["Back #3"][1]
        back_crop = resolved["Plot Hook"][1]
        front = resolved["Front"][1]

        self.fullres_image = compose_treasure(back1, back2, back3, back_crop, front)

        if not self._has_fit_once:
            self.fit_window_to_image(self.fullres_image)
            self._has_fit_once = True
        else:
            self.render_for_display(self.fullres_image)

        def card_num(p: Path):
            m = extract_trailing_number(p)
            return str(m) if m is not None else p.name

        summary = [
            f"Front: item {resolved['Front'][0]} (#{card_num(resolved['Front'][1])})",
            f"Passive: item {resolved['Back #1'][0]} (#{card_num(resolved['Back #1'][1])})",
            f"Active: item {resolved['Back #2'][0]} (#{card_num(resolved['Back #2'][1])})",
            f"Quirk: item {resolved['Back #3'][0]} (#{card_num(resolved['Back #3'][1])})",
            f"Plot Hook: item {resolved['Plot Hook'][0]} (#{card_num(resolved['Plot Hook'][1])})",
        ]
        self.status.configure(text="  • " + " | ".join(summary))

    # Display helpers
    def render_for_display(self, im: Image.Image):
        if self.image_label is None or not self.image_label.winfo_exists():
            for child in self.image_panel.winfo_children():
                child.destroy()
            self.image_label = ttk.Label(self.image_panel)
            self.image_label.pack(fill=tk.BOTH, expand=True)

        panel_w = self.image_panel.winfo_width()
        panel_h = self.image_panel.winfo_height()
        if panel_w <= 1 or panel_h <= 1:
            panel_w = max(self.winfo_width() - 40, 200)
            panel_h = max(self.winfo_height() - 160, 200)

        scale = min(panel_w / im.width, panel_h / im.height, 1.0)
        new_w = max(1, int(im.width * scale))
        new_h = max(1, int(im.height * scale))
        disp = im if (new_w == im.width and new_h == im.height) else im.resize((new_w, new_h), Image.LANCZOS)

        self.tk_image = ImageTk.PhotoImage(disp)
        self.image_label.configure(image=self.tk_image)

    def fit_window_to_image(self, im: Image.Image):
        self.update_idletasks()

        PADX_TOPBAR = 14
        PADY_TOPBAR = (12, 8)
        PADX_PANEL = 12
        PADY_PANEL = 8
        PADX_STATUS = 14
        PADY_STATUS = (0, 10)

        topbar_w = getattr(self, 'topbar', self).winfo_reqwidth()
        topbar_h = getattr(self, 'topbar', self).winfo_reqheight()
        status_w = self.status.winfo_reqwidth()
        status_h = self.status.winfo_reqheight()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        max_win_w = max(400, screen_w - 40)
        max_win_h = max(300, screen_h - 80)

        # Include control rows in overhead height
        ctrl_h = self.ctrl_row.winfo_reqheight() + 32
        overhead_h = (topbar_h + PADY_TOPBAR[0] + PADY_TOPBAR[1]) + ctrl_h + (PADY_PANEL * 2) + (status_h + PADY_STATUS[0] + PADY_STATUS[1])

        non_img_row_w = max(topbar_w + PADX_TOPBAR * 2, status_w + PADX_STATUS * 2)

        max_img_w = max_win_w
        max_img_h = max_win_h - overhead_h
        max_img_h = max(100, max_img_h)

        scale = min(max_img_w / im.width, max_img_h / im.height, 1.0)
        disp_w = max(1, int(im.width * scale))
        disp_h = max(1, int(im.height * scale))

        win_w = max(disp_w + PADX_PANEL * 2, non_img_row_w)
        win_h = overhead_h + disp_h

        win_w = min(win_w, max_win_w)
        win_h = min(win_h, max_win_h)

        try:
            if hasattr(self, "_has_fit_once") and self._has_fit_once is False:
                win_h = max(300, int(win_h * 0.9))
        except Exception:
            pass

        toplevel = self.winfo_toplevel()
        toplevel.geometry(f"{win_w}x{win_h}")
        toplevel.update_idletasks()
        self.render_for_display(im)


class AboutFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        # Top bar
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(12, 8))
        ttk.Label(top, text=f"About — {APP_TITLE}", style="Header.TLabel").pack(side=tk.LEFT)

        # Quick links
        links = ttk.Frame(top)
        links.pack(side=tk.RIGHT)
        ttk.Button(links, text="Open README", command=self._open_readme, style="Toolbar.TButton").pack(side=tk.LEFT, padx=(0,6))
        ttk.Button(links, text="Open LICENSE", command=self._open_license, style="Toolbar.TButton").pack(side=tk.LEFT, padx=(0,6))
        ttk.Button(links, text="Visit Valley Websites", command=lambda: self._open_url("https://valleywebsites.net/"), style="Toolbar.TButton").pack(side=tk.LEFT, padx=(0,6))
        ttk.Button(links, text="Tip on Patreon", command=lambda: self._open_url("https://www.patreon.com/c/backroomsdotnet/membership"), style="Toolbar.TButton").pack(side=tk.LEFT)

        # Scrolling content
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        txt = tkst.ScrolledText(body, wrap=tk.WORD, height=20)
        txt.pack(fill=tk.BOTH, expand=True)

        content = self._build_content()
        try:
            txt.configure(font=("Segoe UI", 10))
        except tk.TclError:
            pass
        txt.insert(tk.END, content)
        self._linkify(txt)
        txt.configure(state=tk.DISABLED)

    def _open_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            messagebox.showinfo("Open URL", url, parent=self)

    def _open_readme(self):
        path = script_dir() / "README.md"
        try:
            webbrowser.open(path.as_uri())
        except Exception:
            messagebox.showinfo("README.md", str(path), parent=self)

    def _open_license(self):
        path = script_dir() / "LICENSE"
        try:
            webbrowser.open(path.as_uri())
        except Exception:
            messagebox.showinfo("LICENSE", str(path), parent=self)

    def _linkify(self, text_widget: tk.Text):
        # Style for links
        text_widget.tag_configure("url", foreground="#4FA3FF", underline=True)
        text_widget.tag_bind("url", "<Enter>", lambda e: text_widget.config(cursor="hand2"))
        text_widget.tag_bind("url", "<Leave>", lambda e: text_widget.config(cursor=""))

        def open_current_url(event):
            index = text_widget.index(f"@{event.x},{event.y}")
            # Find the tagged range under the cursor
            ranges = list(text_widget.tag_ranges("url"))
            for i in range(0, len(ranges), 2):
                start = ranges[i]
                end = ranges[i + 1]
                if text_widget.compare(start, "<=", index) and text_widget.compare(index, "<", end):
                    url = text_widget.get(start, end)
                    self._open_url(url)
                    break

        text_widget.tag_bind("url", "<Button-1>", open_current_url)

        # Regex find and apply tags
        pattern = r"https?://[^\s)>\]}]+"
        idx = "1.0"
        count = tk.IntVar()
        while True:
            pos = text_widget.search(pattern, idx, stopindex=tk.END, regexp=True, count=count)
            if not pos:
                break
            length = count.get() or 0
            if length <= 0:
                break
            end = f"{pos}+{length}c"
            text_widget.tag_add("url", pos, end)
            idx = end

    def _build_content(self) -> str:
        # Load MIT license text
        lic_path = script_dir() / "LICENSE"
        try:
            license_text = lic_path.read_text(encoding="utf-8")
        except Exception:
            license_text = (
                "MIT License\n\n"
                "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
                "of this software and associated documentation files (the 'Software'), to deal\n"
                "in the Software without restriction...\n"
            )

        cup_block = (
            "PF Endless Treasure uses trademarks and/or copyrights owned by Paizo Inc., "
            "used under Paizo's Community Use Policy (paizo.com/licenses/communityuse). "
            "We are expressly prohibited from charging you to use or access this content. "
            "PF Endless Treasure is not published, endorsed, or specifically approved by Paizo. "
            "For more information about Paizo Inc. and Paizo products, visit paizo.com."
        )

        lines = []
        add = lines.append
        add(f"{APP_TITLE} — {APP_VERSION}")
        add("")
        add("Community Use Policy (CUP)")
        add("—" * 32)
        add(cup_block)
        add("")
        add("Legally Purchased Cards Required")
        add("—" * 32)
        add("This software does not include any Paizo content. You must supply your own, legally purchased JPGs of the Deck of Endless Treasure. The app runs locally and never uploads your files.")
        add("")
        add("Free, Open Source Software")
        add("—" * 32)
        add("This app is free to use under the MIT License. No paywalls, subscriptions, or DRM.")
        add("")
        add("Releases and Compatibility")
        add("—" * 32)
        add("If Paizo re-releases or republishes the deck with different layout, resolution, or file naming conventions, parts of this app may stop working until updated.")
        add("")
        add("Tips and Professional Services")
        add("—" * 32)
        add("If this app helps you, tips are appreciated: https://www.patreon.com/c/backroomsdotnet/membership")
        add("Need custom software or web work? Hire Valley Websites: https://valleywebsites.net/")
        add("")
        add("Some of my sites include ...")
        add("Backrooms Wiki: https://backrooms.com/")
        add("Backrooms Novel Game: https://backrooms.net/")
        add("T. Gene Davis (Author): https://tgenedavis.com/")
        add("The original OSR RPG: https://becmi.net/")
        add("Japanese Chess (Shogi) game: https://japanesechess.org/")
        add("Solo RPG: https://solorpg.net/")
        add("Speculative Blog: https://freesciencefiction.com/")
        add("")
        add("Acknowledgments")
        add("—" * 32)
        add("Thanks to Paizo and the Pathfinder community. Pathfinder, Deck of Endless Treasure, and related marks are © Paizo Inc., used per CUP.")
        add("")
        add("License (MIT)")
        add("—" * 32)
        add(license_text.strip())
        add("")

        return "\n".join(lines)



class TreasureApp(tk.Tk):
    def __init__(self, folder: Path):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x860")

        # Style
        self.configure(bg="#0c3024")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", padding=8, font=("Segoe UI", 11))
        style.configure("Header.TLabel", foreground="#eaeaea", background="#0c3024", font=("Segoe UI", 14, "bold"))
        style.configure("Sub.TLabel", foreground="#cfd9d2", background="#0c3024", font=("Segoe UI", 10))
        style.configure("Toolbar.TButton", padding=(6, 2), font=("Segoe UI", 10))

        self.folder = folder

        # Notebook with tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.random_tab = RandomFrame(self.notebook, app=self, folder=self.folder)
        self.custom_tab = CustomFrame(self.notebook, app=self, folder=self.folder)
        self.browser_tab = BrowserFrame(self.notebook, app=self, folder=self.folder)
        self.about_tab = AboutFrame(self.notebook, app=self)
        self.notebook.add(self.random_tab, text="Random")
        self.notebook.add(self.custom_tab, text="Custom")
        self.notebook.add(self.browser_tab, text="Browser")
        self.notebook.add(self.about_tab, text="About")

    def set_folder(self, folder: Path):
        self.folder = folder
        # Update Random tab
        self.random_tab.folder = folder
        self.random_tab.fronts, self.random_tab.backs = scan_cards(folder)
        if len(self.random_tab.backs) >= 4 and len(self.random_tab.fronts) >= 1:
            self.random_tab.btn_new.state(["!disabled"])
            self.random_tab.btn_edit.state(["!disabled"])
            # Reset first-fit so the window sizes once after selecting a folder
            self.random_tab._has_fit_once = False
            self.random_tab.generate()
        else:
            self.random_tab.btn_new.state(["disabled"])
            self.random_tab.btn_edit.state(["disabled"])
            self.random_tab.show_empty_state()
        # Update Browser tab
        self.browser_tab.set_folder(folder)
        # Update Custom tab
        if hasattr(self, 'custom_tab'):
            self.custom_tab.set_folder(folder)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="endless_treasure.py",
        description=(
            "Deck of Endless Treasure — Random Drawer, Custom Composer, and Browser. "
            "Provide a folder of JPG/JPEG images whose filenames end in numbers 1–220. "
            "Odd numbers are fronts; even numbers are backs. If --cards is omitted or the folder "
            "does not contain enough images for random draw, a folder picker will be shown."
        )
    )
    parser.add_argument(
        "-c", "--cards",
        metavar="FOLDER",
        help=(
            "Path to folder containing Endless Treasure JPGs. "
            "If not provided, defaults to the script's directory."
        ),
    )
    parser.add_argument("-?", action="help", help="Show this help message and exit")

    args = parser.parse_args()

    base = Path(args.cards).expanduser().resolve() if args.cards else script_dir()
    app = TreasureApp(base)
    app.mainloop()


if __name__ == "__main__":
    main()
