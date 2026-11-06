"""
Booth-wise votes polled from the scanned Form 20 result sheets (CEO Telangana), by OCR.

Form 20 gives, per polling station: votes for each candidate, total valid votes, rejected, NOTA,
total. It does NOT give electors per booth (only the AC total in the header). Votes polled is used
as the booth population measure: it counts adults who actually live there and turned out, so roll
entries of people who have moved away (common in Hyderabad) drop out.

Row rule, independent of the column layout of each AC's sheet:
  booth number = leftmost number of the row; total = largest number; valid = second largest.
  Checked: booth numbers run 1..N without gaps, and total - valid (rejected + NOTA) is small.

Runs in a separate env with PyMuPDF and RapidOCR (pip install pymupdf rapidocr-onnxruntime pandas).
Usage: <ocr-env python> 01_form20_ocr.py <year> <pdf>...
Output: data/processed/change/form20_<year>.csv  (ac, booth, total, valid, page) + form20_<year>_check.txt
"""
import sys, re
from pathlib import Path
import numpy as np, pandas as pd, pymupdf
from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parents[2]
OUTD = ROOT / "data" / "processed" / "change"; OUTD.mkdir(parents=True, exist_ok=True)
NUM = re.compile(r"^\d+$")
eng = RapidOCR()


def ocr(img):
    """OCR in overlapping horizontal strips: on whole pages the detector skips some rows."""
    h = img.shape[0]; n = 3; step = h // n; ov = 120; res = []
    for k in range(n):
        y0 = max(0, k * step - ov); y1 = min(h, (k + 1) * step + ov)
        r, _ = eng(np.ascontiguousarray(img[y0:y1]))
        for b, t, s in r or []:
            yc = np.mean([p[1] for p in b])
            if (k > 0 and yc < ov / 2) or (k < n - 1 and yc > y1 - y0 - ov / 2):
                continue                    # half of each overlap belongs to the neighbouring strip
            res.append(([[p[0], p[1] + y0] for p in b], t, s))
    return res


def boxes(img):
    res = ocr(img)
    pts = []
    for b, t, s in res or []:
        tok = t.replace("O", "0").replace("o", "0").split()
        if not tok or not all(NUM.match(x) for x in tok):
            continue
        xs = [p[0] for p in b]; ys = [p[1] for p in b]
        x0, x1, n = min(xs), max(xs), sum(len(x) for x in tok)
        pos = 0
        for x in tok:                       # OCR sometimes joins neighbouring cells: "25 25 433"
            xc = x0 + (x1 - x0) * (pos + len(x) / 2) / n; pos += len(x)
            pts.append((xc, np.mean(ys), int(x), max(ys) - min(ys)))
    return np.array(pts, float).reshape(-1, 4)


def rows_of(P, w):
    """Table rows anchored on the booth-number column; the scan tilt is estimated so that boxes far
    to the right are still matched to the right row."""
    if len(P) == 0:
        return []
    L = P[P[:, 0] < 0.12 * w]
    if len(L) == 0:
        return []
    A = L[L[:, 0] < np.percentile(L[:, 0], 5) + 0.015 * w]       # leftmost column: serial / booth numbers
    A = A[np.argsort(A[:, 1])]
    if len(A) < 3:
        return []
    sp = np.median(np.diff(A[:, 1]))                            # row spacing
    best = None
    for sl in np.linspace(-0.03, 0.03, 121):                   # tilt: dy per dx
        yy = P[:, 1] - sl * (P[:, 0] - A[:, 0].mean())
        d = np.abs(yy[:, None] - A[None, :, 1]).min(1)
        sc = (d < 0.25 * sp).sum()
        if best is None or sc > best[0]:
            best = (sc, sl)
    yy = P[:, 1] - best[1] * (P[:, 0] - A[:, 0].mean())
    d = np.abs(yy[:, None] - A[None, :, 1]); k = d.argmin(1); near = d.min(1) < 0.45 * sp
    rows = []
    for j, a in enumerate(A):
        r = P[near & (k == j)]
        rows.append((int(a[2]), r[np.argsort(r[:, 0])]))
    return rows


def parse(pdf, year):
    d = pymupdf.open(pdf)
    ac = int(re.match(r"0*(\d+)", Path(pdf).name).group(1))
    out = []
    for i in range(d.page_count):
        pix = d[i].get_pixmap(dpi=200)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
        for booth, r in rows_of(boxes(img), pix.w):
            if len(r) < 6:
                continue
            rest = r[1:]
            # second serial column (polling station no.), which can run a few behind the serial no.
            rest = rest[~((rest[:, 0] < 0.12 * pix.w) & (np.abs(rest[:, 2] - booth) <= 10) & (booth > 15))
                        & ~((rest[:, 0] < 0.12 * pix.w) & (rest[:, 2] == booth))]
            v = sorted(rest[:, 2].astype(int), reverse=True)
            if len(v) < 4:
                continue
            # candidates sum to valid and total = valid + rejected (+ NOTA when NOTA is outside valid),
            # so all numbers except the booth number and the total add up to valid + total in both layouts
            v_est = sum(v[1:]) - v[0]
            out.append({"ac": ac, "booth": booth, "total": v[0], "valid": v[1], "valid_from_sum": v_est,
                        "page": i, "n_boxes": len(r)})
        print(f"  {Path(pdf).name} page {i}: {len(out)} rows so far", flush=True)
    return pd.DataFrame(out)


def main():
    year = int(sys.argv[1])
    t = pd.concat([parse(p, year) for p in sys.argv[2:]], ignore_index=True)
    lines = []
    keep = []
    for ac, g in t.groupby("ac"):
        g = g[(g.booth < 2000) & (g.total < 3000)]           # drops the grand-total rows
        # repeated booth numbers: the grand-total row or a misread; keep the row with most boxes
        g = g.sort_values("n_boxes").drop_duplicates("booth", keep="last").sort_values("booth")
        n = int(g.booth.max()); miss = sorted(set(range(1, n + 1)) - set(g.booth))
        gap = (g.total - g.valid) / g.total
        ok_sum = (g.valid_from_sum - g.valid).abs() <= 2          # the row adds up: every number read right
        bad = g[(gap < 0) | (gap > 0.15) | (g.total < 30) | (g.total > 1500)]
        lines.append(f"AC {ac}: rows that add up exactly {ok_sum.mean():.1%}; plausible total but not adding up "
                     f"{(~ok_sum & ~g.booth.isin(bad.booth)).sum()}")
        lines.append(f"AC {ac}: {len(g)} booths read, max booth no. {n}, missing {len(miss)}: {miss[:30]}; "
                     f"total votes {g.total.sum():,}; suspicious rows {len(bad)}: {bad.booth.tolist()[:30]}")
        keep.append(g.assign(suspect=g.booth.isin(bad.booth), adds_up=ok_sum))
    t = pd.concat(keep)
    t.to_csv(OUTD / f"form20_{year}.csv", index=False)
    (OUTD / f"form20_{year}_check.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
