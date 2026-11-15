#!/usr/bin/env python3
"""Pictures of the CLEO menu as the mod draws it, made by running CLEO's real menu code with the mod in the emulator.

usage: python3 cleo-ui/tools/preview.py path/to/libSAcleo64.so.image out_dir [path/to/libCleoUI64.so]
The shapes are exactly what reaches the game; the text is drawn with a stand-in font, placed and sized by what was
measured on the phone (glyph height per scale unit, advance per character), so it shows the layout, not the game font.
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
image, out = sys.argv[1], sys.argv[2]
mod = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, '..', '..', 'build', 'cleo-ui', 'libCleoUI64.so')
sys.argv = ['test_cleoui.py', image, mod]
sys.path.insert(0, os.path.join(HERE, '..'))
import test_cleoui as T
from PIL import Image, ImageDraw, ImageFont
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
GAME = lambda s: [0x80 + 'АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'.index(c) if 'А' <= c <= 'Я' else 0xa0 + 'абвгдежзийклмнопрстуфхцчшщъыьэюя'.index(c) if 'а' <= c <= 'я' else ord(c) for c in s]
UNGAME = lambda cs: ''.join('АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'[c - 0x80] if 0x80 <= c <= 0x9f else 'абвгдежзийклмнопрстуфхцчшщъыьэюя'[c - 0xa0].upper() if 0xa0 <= c <= 0xbf else chr(c) for c in cs)

def background(W, H):
    img = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H; d.line([(0, y), (W, y)], fill=(int(70 + 60 * k), int(95 + 40 * k), int(120 - 30 * k)))
    for i in range(0, W, W // 9): d.rectangle([i, int(H * 0.45), i + W // 14, int(H * 0.8)], fill=(150, 120, 90))
    d.rectangle([0, int(H * 0.8), W, H], fill=(70, 70, 72))
    return img
def render(emu, polys, prints, name, scale=0.5):
    W, H = emu.W, emu.H
    img = background(W, H); d = ImageDraw.Draw(img, 'RGBA')
    for q in polys:
        x = q['p']; d.polygon([(x[0], x[1]), (x[2], x[3]), (x[6], x[7]), (x[4], x[5])], fill=q['c'])
    for x in prints:
        if x['c'][3] < 4: continue
        sy = x['scale'][1]
        gh = (0.0089 / 1.3 if x['style'] == 2 else 0.0108 / 1.5) * sy * H       # Details scale = CLEO scale x 1.3 / 1.5
        s = UNGAME(x['t']); f = ImageFont.truetype(FONT, 64)
        bb = f.getbbox(s); tw, th = max(1, bb[2] - bb[0]), max(1, bb[3] - bb[1])
        tile = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); ImageDraw.Draw(tile).text((-bb[0], -bb[1]), s, font=f, fill=x['c'])
        tile = tile.resize((max(1, int(x['w'])), max(1, int(gh))))
        px = x['x'] - x['w'] / 2 if x['align'] == 'centre' else x['x'] - x['w'] if x['align'] == 'right' else x['x']
        img.paste(tile, (int(px), int(x['y'] + 0.003 * H)), tile)
    img = img.resize((int(W * scale), int(H * scale)), Image.LANCZOS); img.save(os.path.join(out, name)); return img

ROWS_RU = [GAME(s) for s in ['ЛЕТЕТЬ ЗА МНОЙ [X]', 'ЖДАТЬ ЗДЕСЬ', 'ПАТРУЛЬ ВОКРУГ', 'ОГОНЬ СТРЕЛКОВ >', 'НА БОРТ ПО ВЕРЕВКЕ', 'ВЫСАДИТЬ ОТРЯД', 'НАСТРОЙКИ >', 'ОТПУСТИТЬ ВЕРТОЛЕТ']]
def menu(size, title, rows, russian=True, steps=(0, 120, 120, 160), sel=-1, cfg=None, name='x.png', measure=True):
    e = T.Emu(size=size, cfg=cfg, measure=measure); e.uc.mem_write(T.GTA + 0xce1771, bytes([1 if russian else 0])); e.load()
    e.set_menu(title, b'CLOSE', rows); p = t = None
    for i, dt in enumerate(steps):
        e.now += dt
        if sel >= 0 and i == len(steps) - 2: e.uc.mem_write(T.SELECTED, struct.pack('<i', sel)); e.uc.mem_write(T.FLASH, struct.pack('<i', 3))
        p, t = e.draw()
    return e, render(e, p, t, name)

if __name__ == '__main__':
    os.makedirs(out, exist_ok=True)
    title = bytes(GAME('HELICOVER / ЛЕТИТ ЗА ВАМИ'))
    for size in ((2000, 1250), (2400, 1080), (1280, 720), (1024, 768)):
        menu(size, title, ROWS_RU, name='menu_%dx%d.png' % size)
    menu((2000, 1250), b'CLEO MENU', [T.A('helicover'), T.A('vehiclespawn')], russian=True, name='list_2000x1250.png')
    menu((2000, 1250), title, ROWS_RU, steps=(0, 120, 120, 160, 16, 60), sel=1, name='press_2000x1250.png')
    for ms in (0, 40, 90):
        menu((2000, 1250), title, ROWS_RU, steps=(0, ms) if ms else (0,), name='open_%03dms.png' % ms)
    menu((2000, 1250), title, ROWS_RU, cfg=b'[Preferences]\nEnabled = 1\nAccent = 1\nAnimation = 1\nDim = 1\n', name='blue_2000x1250.png')
    menu((2000, 1250), b'HELICOVER / FOLLOWING', [T.A(s) for s in ['FOLLOW ME [X]', 'HOLD HERE', 'PATROL AROUND ME', 'GUNNER FIRE >', 'CLIMB ABOARD BY ROPE', 'DEPLOY SQUAD', 'SETTINGS >', 'DISMISS HELICOPTER']], russian=False, name='english_2000x1250.png')
    print('pictures in', out)
