#!/usr/bin/env python3
"""
Endless Treasure Drawer
-----------------------
Drop this script into the folder that contains your Paizo "Deck of Endless Treasure Cards" JPGs
(files whose names end with numbers 21..220). On launch, it composes a random treasure layout:

  1) Back card (anchor)
  2) Back card at (0, +578) relative to the first
  3) Back card at (-234, +144) relative to the first
  4) Front card at (0, +144) relative to the first
  5) A standalone back card cropped to (238, 233) - (738, 575)

GUI controls:
  • New Treasure – draws a new random set and re-renders.
  • Save Image…  – saves the current full-resolution composite as a PNG.

Requires: Python 3.9+ and Pillow 10+   pip install pillow
"""

import os
import re
import sys
import random
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from PIL import Image, ImageTk, ImageDraw, ImageFilter

# ---- Constants from your spec ----
CARD_W, CARD_H = 744, 1039
# Relative offsets (x, y) from the first (anchor) card:
OFF_BACK2 = (0, 578)
OFF_BACK3 = (-234, 144)
OFF_FRONT = (0, 144)
# Crop box for the standalone back card (left, top, right, bottom)
CROP_BOX = (238, 233, 738, 575)  # yields 500 x 342

# ---- Visual polish ----
BG_COLOR = (16, 59, 44)  # deep felt green
OUTER_MARGIN = 40
RIGHT_GAP = 60  # space between the stacked cluster and the cropped panel
SHADOW_OFFSET = (10, 10)
SHADOW_BLUR = 10
SHADOW_ALPHA = 90  # 0..255

# Max displayed size (the saved image is always full resolution)
DISPLAY_MAX_W = 1480
DISPLAY_MAX_H = 980


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
    # Rounded rectangle to soften corners a bit
    radius = 28
    sd.rounded_rectangle((0, 0, CARD_W, CARD_H), radius=radius, fill=(0, 0, 0, SHADOW_ALPHA))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))
    canvas_img.alpha_composite(shadow, (x + SHADOW_OFFSET[0], y + SHADOW_OFFSET[1]))

    # Card
    canvas_img.alpha_composite(card_img, (x, y))


def compose_treasure(back1: Path, back2: Path, back3: Path, back_for_crop: Path, front: Path) -> Image.Image:
    """
    Build the full-resolution composite as an RGBA Pillow image.
    """
    # Load the chosen images
    def load_card(pth: Path) -> Image.Image:
        im = Image.open(pth).convert("RGBA")
        # Optional: sanity check dimensions (Paizo spec says 744x1039)
        if im.width != CARD_W or im.height != CARD_H:
            # If sizes differ, we force-resize to the expected card size for consistent layout
            im = im.resize((CARD_W, CARD_H), Image.LANCZOS)
        return im

    im_back1 = load_card(back1)
    im_back2 = load_card(back2)
    im_back3 = load_card(back3)
    im_front = load_card(front)

    # Base anchor location chosen so the left-shifted third card still has a margin
    base_x = OUTER_MARGIN + abs(OFF_BACK3[0])  # ensures leftmost has OUTER_MARGIN
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
    panel_y = OUTER_MARGIN  # top-aligned

    # Overall canvas size
    canvas_w = panel_x + crop_w + OUTER_MARGIN
    canvas_h = max(bottom + OUTER_MARGIN, panel_y + crop_h + OUTER_MARGIN)

    # Create background (RGBA so we can alpha_composite shadows/cards cleanly)
    canvas = Image.new("RGBA", (canvas_w, canvas_h), BG_COLOR + (255,))

    # Place in the specified sequence (z-order == paint order):
    paste_with_shadow(canvas, im_back1, p1)
    paste_with_shadow(canvas, im_back2, p2)
    paste_with_shadow(canvas, im_back3, p3)
    paste_with_shadow(canvas, im_front, p4)

    # Cropped standalone back
    im_crop_src = load_card(back_for_crop)
    im_crop = im_crop_src.crop(CROP_BOX)
    # Give the crop a small shadow and a subtle “mat” behind it for polish
    mat_pad = 16
    mat_w, mat_h = im_crop.width + mat_pad * 2, im_crop.height + mat_pad * 2
    mat = Image.new("RGBA", (mat_w, mat_h), (238, 234, 216, 255))  # light parchment tone
    # Shadow under mat
    shadow = Image.new("RGBA", (mat_w, mat_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((0, 0, mat_w, mat_h), radius=20, fill=(0, 0, 0, SHADOW_ALPHA))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))
    canvas.alpha_composite(shadow, (panel_x + SHADOW_OFFSET[0], panel_y + SHADOW_OFFSET[1]))

    # Paste mat and crop
    canvas.alpha_composite(mat, (panel_x, panel_y))
    canvas.alpha_composite(im_crop, (panel_x + mat_pad, panel_y + mat_pad))

    return canvas  # RGBA full-res


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

        # Layout
        topbar = ttk.Frame(self)
        topbar.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(12, 8))

        hdr = ttk.Label(topbar, text="Deck of Endless Treasure — Random Drawer", style="Header.TLabel")
        hdr.pack(side=tk.LEFT)

        btn_new = ttk.Button(topbar, text="New Treasure", command=self.generate)
        btn_new.pack(side=tk.RIGHT, padx=(8, 0))
        btn_save = ttk.Button(topbar, text="Save Image…", command=self.save_image)
        btn_save.pack(side=tk.RIGHT, padx=(8, 0))

        # Display area
        self.image_panel = ttk.Label(self)
        self.image_panel.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        self.status = ttk.Label(self, text="", style="Sub.TLabel")
        self.status.pack(side=tk.BOTTOM, anchor="w", padx=14, pady=(0, 10))

        # Initial checks and first render
        if len(self.backs) < 4 or len(self.fronts) < 1:
            messagebox.showerror(
                "Not enough cards found",
                "This folder needs at least 4 EVEN-numbered back JPGs and 1 ODD-numbered front JPG "
                "with file names ending in 21..220 (e.g., Anything_021.jpg … Anything_220.jpg)."
            )
        else:
            self.generate()

    def pick_random(self):
        back_choices = random.sample(self.backs, 4)
        front_choice = random.choice(self.fronts)
        return back_choices, front_choice

    def generate(self):
        try:
            backs, front = self.pick_random()
            # Map the 4 backs to the usage described (3 stacked + 1 for the crop panel)
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
            messagebox.showerror("Error generating treasure", str(e))

    def render_for_display(self, im: Image.Image):
        """Resize for display if needed, but keep original full-res for saving."""
        w, h = im.width, im.height
        scale = min(DISPLAY_MAX_W / w, DISPLAY_MAX_H / h, 1.0)
        if scale < 1.0:
            disp = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        else:
            disp = im
        self.tk_image = ImageTk.PhotoImage(disp)
        self.image_panel.configure(image=self.tk_image)

    def update_status(self):
        if not self.current_files:
            self.status.configure(text="")
            return
        # Show last digits (21..220) if available for quick reference
        def endnum(name):
            m = re.search(r'(\d+)(?=\.(?:jpe?g)$)', name, re.IGNORECASE)
            return m.group(1) if m else name

        text = "  • " + " | ".join(
            f"{k}: {endnum(v)}" for k, v in self.current_files.items()
        )
        self.status.configure(text=text)

    def save_image(self):
        if self.fullres_image is None:
            return
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        default = f"treasure_{ts}.png"
        fn = filedialog.asksaveasfilename(
            title="Save Composite Image",
            initialdir=str(self.folder),
            initialfile=default,
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")]
        )
        if not fn:
            return
        try:
            # Always save as PNG to preserve quality; background is solid so RGBA is fine
            self.fullres_image.save(fn, format="PNG")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))


def main():
    base = script_dir()
    app = TreasureApp(base)
    app.mainloop()


if __name__ == "__main__":
    main()

