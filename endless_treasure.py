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

from PIL import Image, ImageTk, ImageDraw, ImageFilter

# ---- Card constants from your spec ----
CARD_W, CARD_H = 744, 1039
# Relative offsets (x, y) from the first (anchor) card:
OFF_BACK2 = (0, 578)
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


def script_dir() -> Path:
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path(os.getcwd()).resolve()


def extract_trailing_number(p: Path):
    """
    Extracts the trailing numeric run before the extension (e.g., 'foo_219.jpg' -> 219).
    Returns int or None.
    """
    m = re.search(r'(\d+)(?=\.(?:jpe?g)$)', p.name, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
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

    return canvas


class TreasureApp(tk.Tk):
    def __init__(self, folder: Path):
        super().__init__()
        self.title("Deck of Endless Treasure — Random Drawer")
        self.geometry("1200x860")
        self.minsize(980, 700)

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

        # Data
        self.folder = folder
        self.fronts, self.backs = scan_cards(self.folder)
        self.fullres_image = None       # Pillow Image
        self.tk_image = None            # ImageTk for display
        self.current_files = {}         # record selection for status text
        self._resize_job = None         # debounce for resize

        # Layout
        topbar = ttk.Frame(self)
        topbar.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(12, 8))

        hdr = ttk.Label(topbar, text="Deck of Endless Treasure — Random Drawer", style="Header.TLabel")
        hdr.pack(side=tk.LEFT)

        self.btn_new = ttk.Button(topbar, text="New Treasure", command=self.generate)
        self.btn_new.pack(side=tk.RIGHT, padx=(8, 0))

        # Display area (container frame; we swap contents for empty-state vs image)
        self.image_panel = ttk.Frame(self)
        self.image_panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        self.image_label = None  # created when we have an image to show

        self.status = ttk.Label(self, text="", style="Sub.TLabel")
        self.status.pack(side=tk.BOTTOM, anchor="w", padx=14, pady=(0, 10))

        # Re-render on window resize (debounced)
        self.bind("<Configure>", self._on_resize)

        # Initial checks and first render
        if len(self.backs) < 4 or len(self.fronts) < 1:
            self.btn_new.state(["disabled"])  # can't generate yet
            self.show_empty_state()
        else:
            self.btn_new.state(["!disabled"])
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
            self.folder = new_folder
            self.fronts, self.backs = fronts, backs
            # Enable and render
            self.btn_new.state(["!disabled"])
            self.generate()
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
            self.render_for_display(self.fullres_image)
            self.update_status()
        except Exception as e:
            messagebox.showerror("Error generating treasure", str(e), parent=self)

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

    def update_status(self):
        if not self.current_files:
            self.status.configure(text="")
            return

        def endnum(name):
            m = re.search(r'(\d+)(?=\.(?:jpe?g)$)', name, re.IGNORECASE)
            return m.group(1) if m else name

        text = "  • " + " | ".join(f"{k}: {endnum(v)}" for k, v in self.current_files.items())
        self.status.configure(text=text)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="endless_treasure.py",
        description=(
            "Deck of Endless Treasure — Random Drawer. "
            "Provide a folder of JPG/JPEG images whose filenames end in numbers 21–220. "
            "Odd numbers are fronts; even numbers are backs. If --cards is omitted or the folder "
            "does not contain enough images, a folder picker will be shown on startup."
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
    # Add -? as an alternative help switch
    parser.add_argument("-?", action="help", help="Show this help message and exit")

    args = parser.parse_args()

    base = Path(args.cards).expanduser().resolve() if args.cards else script_dir()
    app = TreasureApp(base)
    app.mainloop()


if __name__ == "__main__":
    main()
