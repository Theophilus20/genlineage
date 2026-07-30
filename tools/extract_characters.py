"""Extract characters from reference GIFs with transparent backgrounds.

robot  (0_N.gif): remove white bg + flat blue circle + floating papers,
                  keep only the largest center component (the robot itself).
snow   (1_N.gif): remove flat blue-gray bg via border flood fill.
blob   (3_N.gif): remove flat cream bg via border flood fill.

Outputs:
  web/public/characters/<name>/f_###.png   transparent frames (for canvas scrub)
  web/public/characters/<name>.webp        animated transparent webp (for loops)
"""
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

UP = Path("/mnt/user-data/uploads")
OUT = Path("/home/claude/genlineage/web/public/characters")


def frames_of(path):
    im = Image.open(path)
    canvas = None
    for i in range(im.n_frames):
        im.seek(i)
        f = im.convert("RGBA")
        if canvas is None:
            canvas = f.copy()
        else:
            canvas = canvas.copy()
            canvas.paste(f, (0, 0), f)
        yield np.array(canvas)


def border_flood(rgb, bg, tol):
    """Mask of background pixels connected to the border (BFS)."""
    h, w, _ = rgb.shape
    near = (np.abs(rgb.astype(int) - np.array(bg)).sum(axis=2) < tol)
    mask = np.zeros((h, w), bool)
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if near[y, x] and not mask[y, x]:
                mask[y, x] = True
                dq.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if near[y, x] and not mask[y, x]:
                mask[y, x] = True
                dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
            if 0 <= ny < h and 0 <= nx < w and near[ny, nx] and not mask[ny, nx]:
                mask[ny, nx] = True
                dq.append((ny, nx))
    return mask


def largest_component(alive):
    """Keep only the largest 4-connected True component."""
    h, w = alive.shape
    seen = np.zeros((h, w), bool)
    best = None
    for sy in range(h):
        for sx in range(w):
            if alive[sy, sx] and not seen[sy, sx]:
                comp = []
                dq = deque([(sy, sx)])
                seen[sy, sx] = True
                while dq:
                    y, x = dq.popleft()
                    comp.append((y, x))
                    for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                        if 0 <= ny < h and 0 <= nx < w and alive[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            dq.append((ny, nx))
                if best is None or len(comp) > len(best):
                    best = comp
    keep = np.zeros((h, w), bool)
    if best:
        ys, xs = zip(*best)
        keep[list(ys), list(xs)] = True
    return keep


def fill_holes(keep):
    """True pixels + any False region not connected to the border."""
    h, w = keep.shape
    outside = border_flood(
        np.where(keep[..., None], 255, 0).repeat(3, axis=2).astype(np.uint8),
        (0, 0, 0), tol=10,
    )
    return keep | ~outside


def process_robot(arr):
    rgb = arr[..., :3]
    bg = border_flood(rgb, (255, 253, 255), tol=30)          # white backdrop
    dist_circle = np.abs(rgb.astype(int) - np.array((216, 232, 250))).sum(axis=2)
    dist_circle2 = np.abs(rgb.astype(int) - np.array((217, 233, 251))).sum(axis=2)
    circle = (dist_circle < 24) | (dist_circle2 < 24)         # flat circle fill
    alive = ~(bg | circle)
    keep = fill_holes(largest_component(alive))
    out = arr.copy()
    out[..., 3] = np.where(keep, 255, 0)
    return out


def process_flood(arr, bg_color, tol):
    rgb = arr[..., :3]
    bg = border_flood(rgb, bg_color, tol)
    out = arr.copy()
    out[..., 3] = np.where(bg, 0, 255)
    return out


def run(name, src, fn, step=2):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    kept = []
    for i, arr in enumerate(frames_of(UP / src)):
        if i % step:
            continue
        out = fn(arr)
        img = Image.fromarray(out)
        img.save(d / f"f_{len(kept):03d}.png", optimize=True)
        kept.append(img)
    kept[0].save(OUT / f"{name}.webp", save_all=True, append_images=kept[1:],
                 duration=125 * step, loop=0, lossless=False, quality=85)
    print(name, len(kept), "frames")


if __name__ == "__main__":
    run("robot", "0_N.gif", process_robot, step=2)
    run("snow", "1_N.gif", lambda a: process_flood(a, (221, 228, 240), tol=26), step=3)
    run("blob", "3_N.gif", lambda a: process_flood(a, (239, 233, 207), tol=26), step=3)
