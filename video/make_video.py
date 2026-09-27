import math, subprocess, imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

UP = '/root/.claude/uploads/80b324ba-fd62-5b10-8cea-1f803f76de3b/'
OUT = 'video/ouchi_kaji_note_short.mp4'
W, H, FPS = 1080, 1920, 30
FONT = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
ACCENT = (122, 200, 176)

def font(sz): return ImageFont.truetype(FONT, sz)

# ---------- home screen with mosaic (keep only おうち家事ノート) ----------
home = Image.open(UP + 'c2b662b4-image.jpg').convert('RGB')
hs = home.width / 924
keep = tuple(int(v * hs) for v in (462, 1272, 694, 1508))
small = home.resize((home.width // 36, home.height // 36), Image.BILINEAR)
mosaic = small.resize(home.size, Image.NEAREST).filter(ImageFilter.GaussianBlur(3))
home_m = mosaic.copy()
mask = Image.new('L', home.size, 0)
ImageDraw.Draw(mask).rounded_rectangle(keep, 30, fill=255)
home_m.paste(home, (0, 0), mask)
pass
icon_c = ((keep[0] + keep[2]) / 2, (keep[1] + keep[3]) / 2 - 20 * hs)

shots = {k: Image.open(UP + f).convert('RGB') for k, f in {
    'today': 'ce08f68a-image.jpg', 'recipe': '296967f8-image.jpg',
    'shop': '64de8f79-image.jpg', 'bento': 'c1d211e3-image.jpg'}.items()}

def ease(t): t = max(0, min(1, t)); return t * t * (3 - 2 * t)

def cover(img, zoom=1.0, cx=0.5, cy=0.5):
    """Scale img to cover W×H, apply zoom, centered on (cx,cy) fractional."""
    s = max(W / img.width, H / img.height) * zoom
    sw, sh = img.width * s, img.height * s
    x = min(max(cx * sw - W / 2, 0), sw - W)
    y = min(max(cy * sh - H / 2, 0), sh - H)
    box = (x / s, y / s, (x + W) / s, (y + H) / s)
    return img.resize((W, H), Image.LANCZOS, box=box)

def wrap(text, f, maxw):
    lines = []
    for para in text.split('\n'):
        cur = ''
        for ch in para:
            if f.getlength(cur + ch) > maxw and cur:
                lines.append(cur); cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines

def caption(frame, text, alpha, pos='bottom', size=64):
    if alpha <= 0 or not text: return frame
    while True:
        f = font(size)
        if all(f.getlength(l) <= W - 180 for l in text.split('\n')) or size <= 36: break
        size -= 2
    lines = wrap(text, f, W - 180)
    lh = int(size * 1.45)
    bh = lh * len(lines) + 70
    y0 = H - bh - 140 if pos == 'bottom' else 170
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    d.rounded_rectangle((50, y0, W - 50, y0 + bh), 36, fill=(255, 255, 255, int(235 * alpha)))
    d.rounded_rectangle((50, y0, 64, y0 + bh), 7, fill=ACCENT + (a,))
    for i, ln in enumerate(lines):
        tw = f.getlength(ln)
        d.text(((W - tw) / 2, y0 + 35 + i * lh + (lh - size) / 2), ln, font=f,
               fill=(40, 40, 40, a))
    out = frame.convert('RGBA'); out.alpha_composite(layer)
    return out.convert('RGB')

def tag(frame, text, alpha):
    if alpha <= 0: return frame
    f = font(46)
    tw = f.getlength(text)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0 = (W - tw) / 2 - 40
    d.rounded_rectangle((x0, 70, x0 + tw + 80, 160), 45, fill=ACCENT + (int(240 * alpha),))
    d.text((x0 + 40, 92), text, font=f, fill=(20, 40, 35, int(255 * alpha)))
    out = frame.convert('RGBA'); out.alpha_composite(layer)
    return out.convert('RGB')

def fade(t, dur, fi=0.4, fo=0.4):
    return min(1, t / fi if fi else 1, (dur - t) / fo if fo else 1)

# ---------- scenes: (duration, render(t)) ----------
BG = Image.new('RGB', (W, H))
for yy in range(H):
    k = yy / H
    ImageDraw.Draw(BG).line((0, yy, W, yy), fill=(int(40 + 20 * k), int(70 + 30 * k), int(62 + 26 * k)))
home_bg = cover(home_m, 1.0).filter(ImageFilter.GaussianBlur(30))
def home_frame(zoom, t_pulse=None):
    s = H / home_m.height * zoom
    iw, ih = int(home_m.width * s), int(home_m.height * s)
    # interpolate focus: zoom 1 -> center, higher -> icon
    k = (zoom - 1) / 1.6
    fx = (0.5 * home_m.width) * (1 - k) + icon_c[0] * k
    fy = (0.5 * home_m.height) * (1 - k) + icon_c[1] * k
    x = W / 2 - fx * s; y = H / 2 - fy * s
    x = min(max(x, W - iw), 0) if iw > W else (W - iw) / 2
    y = min(max(y, H - ih), 0)
    fr = home_bg.copy()
    fr.paste(home_m.resize((iw, ih), Image.LANCZOS), (int(x), int(y)))
    if t_pulse is not None:
        d = ImageDraw.Draw(fr)
        bx = [keep[0] * s + x, keep[1] * s + y, keep[2] * s + x, keep[3] * s + y]
        g = 8 + 10 * (0.5 + 0.5 * math.sin(t_pulse * 6))
        d.rounded_rectangle((bx[0] - g, bx[1] - g, bx[2] + g, bx[3] + g), 40,
                            outline=(255, 214, 102), width=10)
    return fr

def s1(t):  # home screen, zoom to icon
    z = 1 + 0.9 * ease((t - 0.8) / 2.2)
    fr = home_frame(z, t if t > 2.6 else None)
    return caption(fr, 'Claude Codeで\n「おうち家事ノート」作ったよ〜', fade(t, 4.5, 0.3), 'top', 64)

def s2(t):  # question
    fr = home_frame(1.9, t + 5).filter(ImageFilter.GaussianBlur(ease(t / 0.6) * 18))
    return caption(fr, '「面倒なこと」を\nAIに頼めばいいって\nなんだろう？って考えた。', fade(t, 4.0), 'top', 60)

def shot_scene(key, text, label, zoom=(1.0, 1.08), cy=(0.2, 0.5), dur=4.0, size=58):
    img = shots[key]
    def r(t):
        p = ease(t / dur)
        fr = BG.copy()
        cw, ch = 880, 1564
        global W, H
        W0, H0 = W, H; W, H = cw, ch
        card = cover(img, zoom[0] + (zoom[1] - zoom[0]) * p, 0.5, cy[0] + (cy[1] - cy[0]) * p)
        W, H = W0, H0
        m = Image.new('L', (cw, ch), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, cw, ch), 44, fill=255)
        fr.paste(card, ((W - cw) // 2, 200), m)
        a = fade(t, dur)
        fr = tag(fr, label, a)
        return caption(fr, text, a, 'bottom', size)
    return r

def s_end(t):
    fr = cover(shots['today'], 1.12, 0.5, 0.3).filter(ImageFilter.GaussianBlur(22))
    ov = Image.new('RGBA', (W, H), (18, 24, 22, 170))
    fr = fr.convert('RGBA'); fr.alpha_composite(ov); fr = fr.convert('RGB')
    d = ImageDraw.Draw(fr)
    a1 = ease(t / 0.8); a2 = ease((t - 1.3) / 0.8); a3 = ease((t - 2.8) / 0.8)
    def ctext(txt, y, sz, col, a):
        f = font(sz); tw = f.getlength(txt)
        c = tuple(int(v * a + 22 * (1 - a)) for v in col)
        d.text(((W - tw) / 2, y), txt, font=f, fill=c)
    ctext('家事は体力勝負だから、', 700, 64, (240, 240, 240), a1)
    ctext('少しでも', 820, 76, (240, 240, 240), a2)
    ctext('頭を軽くしよう。', 930, 92, (255, 214, 102), a2)
    ctext('おうち家事ノート', 1250, 56, ACCENT, a3)
    ctext('made with Claude Code', 1330, 40, (190, 190, 190), a3)
    return fr

scenes = [
    (4.5, s1),
    (4.0, s2),
    (4.5, shot_scene('today', '主婦でワーカーなわたしには、\nやっぱりワンオペの家事が\n負担なんだよね。',
                     '今日の家事がひと目でわかる', dur=4.5, size=54)),
    (3.5, shot_scene('recipe', '作り置きは「作る」を選ぶだけ', '作り置きプラン', cy=(0.2, 0.55), dur=3.5)),
    (3.5, shot_scene('shop', '買い物リストも自動でできる', '買い物リスト', cy=(0.2, 0.55), dur=3.5)),
    (3.5, shot_scene('bento', 'お弁当の中身も\n毎日自動で決めてくれる', '詰めるだけリスト', cy=(0.2, 0.55), dur=3.5)),
    (4.5, s_end),
]

total = sum(d for d, _ in scenes)
cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
       '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
       '-f', 'lavfi', '-t', str(total), '-i', 'anullsrc=r=44100:cl=stereo',
       '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'medium',
       '-c:a', 'aac', '-shortest', '-movflags', '+faststart', OUT]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
for dur, fn in scenes:
    for i in range(int(dur * FPS)):
        p.stdin.write(fn(i / FPS).tobytes())
p.stdin.close(); p.wait()
print('done', OUT, total, 's')
