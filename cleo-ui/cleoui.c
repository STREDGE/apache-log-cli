/*
 * CLEO UI - a new look for the CLEO menu of GTA San Andreas Android (arm64, CLEO ANDROID 64-260403 inside the APK).
 *
 * How CLEO draws (read from the library after its loader unpacked it, see tools/unpack_cleo.py): from its CHud::Draw
 * hook it calls two internal functions through pointers kept in its own data:
 *     rect(colour*, x1,y1, x2,y2, x3,y3, x4,y4)            - screen fractions 0..1, ends in CSprite2d::Draw2DPolygon
 *     text(gxt*, align, colour*, style, x, y, scale x, scale y) - ends in CFont::PrintString
 * The "OPEN CLEO MENU" button and every script menu (panel, title, close caption, page number, up to 8 rows, two page
 * arrows) are drawn with these two calls only.
 *
 * This mod changes no code, neither in the game nor in CLEO. A helper thread waits until CLEO has set the two pointers,
 * checks that it is exactly the expected build (version text, both pointer values, the first instructions of both
 * functions) and then puts its own two functions there. They recognise what is being drawn by the colour and place
 * CLEO uses, and draw the new look with CLEO's own original functions. Touch areas stay CLEO's: rows keep their places.
 * If anything differs, nothing is changed and cleoui_log.txt in the AML mods folder says why.
 */
typedef unsigned long u64;
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;

#define O_RDONLY 0
#define O_WRONLY 01
#define O_CREAT 0100
#define O_TRUNC 01000
#define RTLD_NOW 2
extern int open(const char *path, int flags, ...);
extern long read(int fd, void *buf, u64 n);
extern long write(int fd, const void *buf, u64 n);
extern int close(int fd);
struct phdr { u32 type, flags; u64 offset, vaddr, paddr, filesz, memsz, align; };
struct dl_phdr_info { u64 dlpi_addr; const char *dlpi_name; const struct phdr *dlpi_phdr; u16 dlpi_phnum; };
extern int dl_iterate_phdr(int (*cb)(struct dl_phdr_info *, u64, void *), void *data);
extern void *dlopen(const char *name, int flags);
extern void *dlsym(void *handle, const char *name);
extern int pthread_create(u64 *thread, const void *attr, void *(*fn)(void *), void *arg);
extern int usleep(u32 usec);
struct timespec { long tv_sec, tv_nsec; };
extern int clock_gettime(int clock, struct timespec *ts);

#define HIDDEN __attribute__((visibility("hidden")))
#define EXPORT __attribute__((visibility("default")))
HIDDEN void *memcpy(void *d, const void *s, u64 n) { u8 *a = d; const u8 *b = s; while (n--) *a++ = *b++; return d; }
HIDDEN void *memset(void *d, int c, u64 n) { u8 *a = d; while (n--) *a++ = (u8)c; return d; }
static u64 slen(const char *s) { u64 n = 0; while (s[n]) n++; return n; }

#define GAME_DIR "/storage/emulated/0/Android_unprotected/data/com.rockstargames.gtasa/"

/* ---------- the expected CLEO build (offsets inside libSAcleo64.so once loaded) ---------- */
#define CLEO_IMAGE 0x88000UL                       /* the unpacked library starts here */
#define CLEO_VERSION (CLEO_IMAGE + 0x1bc30UL)      /* "CLEO ANDROID (64-260403)" */
#define CLEO_RECT_FN (CLEO_IMAGE + 0x3659cUL)
#define CLEO_TEXT_FN (CLEO_IMAGE + 0x365dcUL)
#define CLEO_RECT_PTR (CLEO_IMAGE + 0x27d3b8UL)
#define CLEO_TEXT_PTR (CLEO_IMAGE + 0x27d3c0UL)
#define CLEO_MIN_SIZE (CLEO_IMAGE + 0x27e000UL)
static const char CLEO_VERSION_TEXT[] = "CLEO ANDROID (64-260403)";
static const u32 RECT_CODE[4] = {0xf0001228U, 0xf9420508U, 0x2d414510U, 0xf0001228U};
static const u32 TEXT_CODE[4] = {0xd102c3ffU, 0x6d0723e9U, 0xa9087bfdU, 0xa90957f6U};
#define GTA_RUSSIAN 0xce1771UL                     /* CFont::UsingRussianLanguage in the user's libGTASA.so */
static const u32 GTA_CHECK[2] = {0xd10143ffU, 0x6d0223e9U}; /* CFont::PrintString starts like this in that build */
#define GTA_PRINTSTRING 0x6cdeb0UL
#define GTA_STRWIDTH 0x6ce760UL                    /* CFont::GetStringWidth(unsigned short*, bool, bool) */
static const u32 GTA_WIDTH_CHECK[2] = {0x6db923e9U, 0xa9016ffcU};

/* ---------- log ---------- */
static char g_log[4096];
static u32 g_loglen;
static void lg(const char *s) { while (*s && g_loglen < sizeof(g_log) - 1) g_log[g_loglen++] = *s++; }
static void lghex(u64 v) { char b[19]; int i; b[0] = '0'; b[1] = 'x'; for (i = 0; i < 16; i++) { int d = (int)((v >> (60 - 4 * i)) & 15); b[2 + i] = (char)(d < 10 ? '0' + d : 'a' + d - 10); } b[18] = 0; lg(b); }
static void lgint(int v) { char b[12]; int n = 11; b[n] = 0; if (v < 0) { lg("-"); v = -v; } do { b[--n] = (char)('0' + v % 10); v /= 10; } while (v && n); lg(b + n); }
static void flush_log(void) {
    int fd = open(GAME_DIR "mods/cleoui_log.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, g_log, g_loglen); close(fd);
}

/* ---------- settings ---------- */
#define CFG GAME_DIR "configs/net.helicover.cleoui.ini"
static int g_on = 1, g_accent = 0, g_anim = 1, g_dim = 1;
static const u8 ACCENT[5][3] = {{255, 140, 0}, {60, 160, 255}, {70, 220, 90}, {235, 60, 60}, {235, 235, 235}};
static int cfg_value(const char *b, const char *key, int max, int def) {
    u64 k = slen(key), i, j;
    for (i = 0; b[i]; i++) {
        for (j = 0; j < k && b[i + j] == key[j]; j++) {}
        if (j == k) { for (i += k; b[i] == ' ' || b[i] == '\t' || b[i] == '='; i++) {} if (b[i] >= '0' && b[i] <= '0' + max) return b[i] - '0'; return def; }
    }
    return def;
}
static void load_config(void) {
    char b[256]; long n; int fd = open(CFG, O_RDONLY);
    if (fd < 0) return;
    n = read(fd, b, sizeof(b) - 1); close(fd);
    if (n <= 0) return;
    b[n] = 0;
    g_on = cfg_value(b, "Enabled", 1, 1); g_accent = cfg_value(b, "Accent", 4, 0); g_anim = cfg_value(b, "Animation", 1, 1); g_dim = cfg_value(b, "Dim", 1, 1);
}
static void save_config(void) {
    char t[128]; const char *a = "[Preferences]\nEnabled = "; u32 n = 0; int fd;
    while (*a) t[n++] = *a++;
    t[n++] = (char)('0' + g_on); a = "\nAccent = "; while (*a) t[n++] = *a++;
    t[n++] = (char)('0' + g_accent); a = "\nAnimation = "; while (*a) t[n++] = *a++;
    t[n++] = (char)('0' + g_anim); a = "\nDim = "; while (*a) t[n++] = *a++;
    t[n++] = (char)('0' + g_dim); t[n++] = '\n';
    fd = open(CFG, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, t, n); close(fd);
}

/* ---------- CLEO's two drawing functions and the data the look reads ---------- */
typedef void (*rect_fn)(const u8 *rgba, float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4);
typedef void (*text_fn)(const u16 *gxt, int align, const u8 *rgba, int style, float x, float y, float sx, float sy);
typedef float (*width_fn)(const u16 *gxt, u8 whole, u8 script);
typedef void (*style_fn)(u8 style);
static rect_fn g_rect;
static text_fn g_text;
static width_fn g_width;      /* CFont::GetStringWidth of the game, or 0 when its code is not the expected one */
static u64 g_gta, g_img;      /* libGTASA base; start of the unpacked CLEO image */
#define CLEO_RS 0x27d408UL        /* RsGlobal*: +8 screen width, +12 height */
#define CLEO_DETAILS 0x27d3f0UL   /* CFont::Details* */
#define CLEO_SETSTYLE 0x27d3f8UL  /* CFont::SetFontStyle */
#define CLEO_ROWS 0x27d850UL      /* std::vector of rows (24 bytes each): begin, end */
#define CLEO_PAGE 0x7cfccUL       /* page shown (int) */
#define CLEO_CLOSE_BOX 0x27d880UL /* touch box of the close caption: x1, y1, x2, y2 as screen fractions */

static float g_W = 1920.0f, g_H = 1080.0f;      /* screen size in pixels, re-read every frame */
static float clampf(float v, float lo, float hi) { return v < lo ? lo : v > hi ? hi : v; }
static float ease(float k) { k = clampf(k, 0.0f, 1.0f); return k * (2.0f - k); }                 /* fast start, soft stop */
static int near(float a, float b) { float d = a - b; return d < 0.004f && d > -0.004f; }
static int rgb_is(const u8 *c, int r, int g, int b) { return c[0] == r && c[1] == g && c[2] == b; }
/* a four-cornered shape given in pixels: top-left, top-right, bottom-left, bottom-right */
static void quad(float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4, const u8 *rgb, float a) {
    u8 c[4]; int ia = (int)a;
    if (ia <= 0) return;
    c[0] = rgb[0]; c[1] = rgb[1]; c[2] = rgb[2]; c[3] = (u8)(ia > 255 ? 255 : ia);
    g_rect(c, x1 / g_W, y1 / g_H, x2 / g_W, y2 / g_H, x3 / g_W, y3 / g_H, x4 / g_W, y4 / g_H);
}
static void box(float x1, float y1, float x2, float y2, const u8 *rgb, float a) { quad(x1, y1, x2, y1, x1, y2, x2, y2, rgb, a); }
/* A plate with the top-right and bottom-left corners cut by c pixels. fill: the plate itself. contour: its outline,
   t pixels thick, pushed e pixels outwards (several of them with falling alpha make the glow). */
static void plate_fill(float x1, float y1, float x2, float y2, float c, const u8 *top, const u8 *bottom, float a, int strips) {
    int i; float h = (y2 - c) - (y1 + c);
    quad(x1, y1, x2 - c, y1, x1, y1 + c, x2, y1 + c, top, a);
    for (i = 0; i < strips; i++) {
        u8 m[3]; float k = strips > 1 ? (float)i / (float)(strips - 1) : 0.0f; int j;
        for (j = 0; j < 3; j++) m[j] = (u8)((float)top[j] + ((float)bottom[j] - (float)top[j]) * k);
        box(x1, y1 + c + h * (float)i / (float)strips, x2, y1 + c + h * (float)(i + 1) / (float)strips, m, a);
    }
    quad(x1, y2 - c, x2, y2 - c, x1 + c, y2, x2, y2, bottom, a);
}
static void contour(float x1, float y1, float x2, float y2, float c, float e, float t, const u8 *rgb, float a) {
    float d = (e + t) * 0.7071f, g = e * 0.7071f;
    box(x1 - e - t, y1 - e - t, x2 - c + g, y1 - e, rgb, a);                                   /* top */
    box(x2 + e, y1 + c - g, x2 + e + t, y2 + e + t, rgb, a);                                   /* right */
    box(x1 + c - g, y2 + e, x2 + e, y2 + e + t, rgb, a);                                       /* bottom */
    box(x1 - e - t, y1 - e, x1 - e, y2 - c + g, rgb, a);                                       /* left */
    quad(x2 - c + d, y1 - d, x2 + d, y1 + c - d, x2 - c + g, y1 - g, x2 + g, y1 + c - g, rgb, a);                               /* top-right cut */
    quad(x1 - d, y2 - c + d, x1 - g, y2 - c + g, x1 + c - d, y2 + d, x1 + c - g, y2 + g, rgb, a);                               /* bottom-left cut */
}
static void glow(float x1, float y1, float x2, float y2, float c, float t, const u8 *rgb, float a) {
    contour(x1, y1, x2, y2, c, 0.0f, t, rgb, a);
    contour(x1, y1, x2, y2, c, t, t, rgb, a * 0.30f);
    contour(x1, y1, x2, y2, c, 2.0f * t, t * 1.5f, rgb, a * 0.14f);
    contour(x1, y1, x2, y2, c, 3.5f * t, t * 2.0f, rgb, a * 0.06f);
}

/* ---------- time and the state of the menu on screen ---------- */
static u64 now_ms(void) { struct timespec t; t.tv_sec = 0; t.tv_nsec = 0; clock_gettime(1 /* CLOCK_MONOTONIC */, &t); return (u64)t.tv_sec * 1000UL + (u64)t.tv_nsec / 1000000UL; }
#define GAP_MS 250            /* a pause this long between two panel draws = the menu was closed and is opened again */
#define OPEN_MS 140
#define SWITCH_MS 90
#define PRESS_SWEEP_MS 90
#define PRESS_HOLD_MS 120
#define PRESS_FADE_MS 220
static struct {
    u64 now, last, open_t, switch_t, press_t;
    float L, R, top, head, bottom, line, cut;   /* panel edges, header bottom, line thickness, corner cut: pixels */
    float press_y; u32 sig; int rows, have_sig;
} F;
static int menu_live(void) { return F.now - F.last < 60 || now_ms() - F.last < 60; }
static float row_alpha(float y) {       /* rows appear one after another when the menu opens, and blink in on a page change */
    float i = (y - 0.20f) / 0.09f, a = 1.0f, s;
    if (!g_anim) return 1.0f;
    if (F.now - F.open_t < 400) a = clampf(0.30f + ((float)(F.now - F.open_t) - 9.0f * i) / 60.0f, 0.22f, 1.0f);   /* readable from the very first frame */
    if (F.now - F.switch_t < SWITCH_MS) { s = 0.30f + 0.70f * ease((float)(F.now - F.switch_t) / (float)SWITCH_MS); if (s < a) a = s; }
    return a;
}

/* ---------- text width (the game measures, the mod only asks) ---------- */
static struct { u32 hash; int style; float per_sx; } g_wc[16];
static u32 g_wc_next;
static u32 hash16(const u16 *s) { u32 h = 2166136261U; int i; for (i = 0; s[i] && i < 300; i++) h = (h ^ s[i]) * 16777619U; return h ? h : 1; }
/* width of s as a fraction of the screen width when CLEO prints it with this style and x scale; < 0 = unknown */
static float text_width(const u16 *s, int style, float sx) {
    u32 h, i; u8 *det, save[0x40]; style_fn sf; float fx = 1.0f, fy = 1.0f, w;
    if (!g_width || !g_img || !s) return -1.0f;
    h = hash16(s);
    for (i = 0; i < 16; i++) if (g_wc[i].hash == h && g_wc[i].style == style) return g_wc[i].per_sx * sx;
    det = *(u8 *volatile *)(g_img + CLEO_DETAILS); sf = *(style_fn volatile *)(g_img + CLEO_SETSTYLE);
    if (!det || !sf) return -1.0f;
    memcpy(save, det, 0x40);                       /* the same preparation CLEO's own text function makes */
    if (style == 0) { sf(2); fx = 1.4f; fy = 1.3f; } else if (style == 1) { sf(3); fx = 1.9f; fy = 1.5f; } else sf(0);
    memcpy(det + 4, &fx, 4); memcpy(det + 8, &fy, 4); det[0x1d] = 1;
    w = g_width(s, 1, 0);
    memcpy(det, save, 0x40);
    if (!(w > 0.0f) || w > 4.0f * g_W) return -1.0f;
    i = g_wc_next++ & 15; g_wc[i].hash = h; g_wc[i].style = style; g_wc[i].per_sx = w / g_W;
    return g_wc[i].per_sx * sx;
}
/* the factor (<= 1) that makes the text fit into max (a fraction of the screen width) */
static float fit(const u16 *s, int style, float sx, float max) {
    float w = text_width(s, style, sx);
    if (w <= max || w <= 0.0f) return 1.0f;
    return clampf(max / w, 0.5f, 1.0f);
}

/* ---------- Russian ---------- */
static int game_russian(void) { return g_gta && *(volatile u8 *)(g_gta + GTA_RUSSIAN) == 1; }
/* The game's Russian font: capitals 0x80-0x9F, small letters 0xA0-0xBF (layout confirmed on the phone). A script may
   hand CLEO a text in UTF-8 or in CP1251; both are turned into those codes. Text already in game codes has no byte
   above 0xBF and passes unchanged. */
static u16 g_buf[260];
static const u16 *to_game_russian(const u16 *s) {
    int i, n = 0, utf8 = 0, cp = 0;
    /* which encoding: UTF-8 pairs (D0/D1 + 80-BF), else CP1251 if any byte is C0-FF, else nothing to do. Only then are
       0xA8 / 0xB8 the CP1251 letters IO / io - in the game's own codes they are two ordinary small letters. */
    for (i = 0; s[i]; i++) {
        if ((s[i] == 0xd0 || s[i] == 0xd1) && s[i + 1] >= 0x80 && s[i + 1] <= 0xbf) { utf8 = 1; i++; }
        else if (s[i] >= 0xc0 && s[i] <= 0xff) cp = 1;
    }
    if (!utf8 && !cp) return s;
    for (i = 0; s[i] && n < 258; i++) {
        u16 c = s[i], d = s[i + 1];
        if (utf8) {
            if ((c == 0xd0 || c == 0xd1) && d >= 0x80 && d <= 0xbf) {
                int u = ((c & 0x1f) << 6) | (d & 0x3f);
                i++;
                if (u >= 0x410 && u <= 0x44f) g_buf[n++] = (u16)(u - 0x390);
                else if (u == 0x401) g_buf[n++] = 0x85;                      /* IO -> IE: the font has no IO */
                else if (u == 0x451) g_buf[n++] = 0xa5;
                else g_buf[n++] = '?';
            } else g_buf[n++] = c;
        } else {
            if (c >= 0xc0 && c <= 0xff) g_buf[n++] = (u16)(c - 0x40);        /* CP1251 A..ya */
            else if (c == 0xa8) g_buf[n++] = 0x85;
            else if (c == 0xb8) g_buf[n++] = 0xa5;
            else g_buf[n++] = c;
        }
    }
    g_buf[n] = 0;
    return g_buf;
}
static int same(const u16 *s, const char *t) { int i; for (i = 0; t[i]; i++) if (s[i] != (u8)t[i]) return 0; return s[i] == 0; }
static const u16 RU_CLOSE[] = {0x87, 0x80, 0x8a, 0x90, 0x9b, 0x92, 0x9c, 0};                                  /* ZAKRYT' */
static const u16 RU_OPEN[] = {0x8c, 0x85, 0x8d, 0x9e, ' ', 'C', 'L', 'E', 'O', 0};                             /* MENYU CLEO */

/* ---------- the new look: "techno neon" ---------- */
#define BLUE(c) rgb_is(c, 0x37, 0x7f, 0xaf)   /* CLEO's menu colour (55,127,175): panel alpha 150, arrows 100 / 180 */
#define RED(c) rgb_is(c, 0xff, 0x0a, 0x0a)    /* the arrow of the OPEN CLEO MENU hint */
#define GREEN(c) rgb_is(c, 0x28, 0xeb, 0x18)  /* CLEO's colour for the row that was just pressed */
static const u8 C_BLACK[3] = {0, 0, 0}, C_WHITE[3] = {255, 255, 255}, C_HEAD[3] = {27, 29, 40}, C_TOP[3] = {21, 23, 32}, C_BOTTOM[3] = {8, 9, 13};
/* measured on the phone (2000 x 1250): a glyph is this tall per unit of CLEO's y scale, as a fraction of the screen height */
#define GLYPH_ROW 0.0089f     /* style 0: rows, page number */
#define GLYPH_HEAD 0.0108f    /* style 1: title, close caption */
#define GLYPH_TOP 0.003f      /* empty space above a glyph */

static void read_screen(void) {
    const u8 *rs = *(const u8 *volatile *)(g_img + CLEO_RS); int w, h;
    if (!rs) return;
    memcpy(&w, rs + 8, 4); memcpy(&h, rs + 12, 4);
    if (w >= 320 && h >= 200 && w <= 16384 && h <= 16384) { g_W = (float)w; g_H = (float)h; }
}
static int rows_on_page(void) {
    u64 b = *(volatile u64 *)(g_img + CLEO_ROWS), e = *(volatile u64 *)(g_img + CLEO_ROWS + 8); int page = *(volatile int *)(g_img + CLEO_PAGE), n;
    if (!b || e < b || page < 0) return 8;
    n = (int)((e - b) / 24) - page * 8;
    return n < 1 ? 1 : n > 8 ? 8 : n;
}
static void draw_panel(void) {
    const u8 *ac = ACCENT[g_accent]; u64 t = now_ms(); float dt, k, w, target, p, x, s; int reopened, i;
    read_screen();
    reopened = t - F.last > GAP_MS;
    dt = (float)(t - F.last); F.now = F.last = t; F.rows = rows_on_page();
    if (reopened) { F.open_t = t; F.press_y = -1.0f; F.have_sig = 0; }
    /* geometry: the width follows the shape of the screen, CLEO's touch columns (38 %-62 % of the width) stay inside,
       its page arrows (up to 33.5 % / from 66.5 %) stay outside; the height follows the number of rows */
    w = clampf(0.5f * g_H / g_W, 0.27f, 0.33f) * g_W;
    F.L = 0.5f * g_W - 0.5f * w; F.R = 0.5f * g_W + 0.5f * w;
    F.top = 0.075f * g_H; F.head = 0.175f * g_H;
    F.line = g_H / 540.0f < 2.0f ? 2.0f : (float)(int)(g_H / 540.0f + 0.5f);
    F.cut = 0.024f * g_H;
    target = (0.21f + 0.09f * (float)F.rows) * g_H;
    if (reopened || !g_anim || F.bottom < F.head) F.bottom = target;
    else { k = dt / (dt + 45.0f); F.bottom += (target - F.bottom) * k; if (F.bottom - target < 1.0f && target - F.bottom < 1.0f) F.bottom = target; }
    p = g_anim ? 0.55f + 0.45f * ease((float)(t - F.open_t) / (float)OPEN_MS) : 1.0f;
    if (g_dim) box(0.0f, 0.0f, g_W, g_H, C_BLACK, 105.0f * (g_anim ? 0.25f + 0.75f * ease((float)(t - F.open_t) / 180.0f) : 1.0f));
    /* shadow, body (header + gradient), outline with glow */
    plate_fill(F.L + 4.0f * F.line, F.top + 5.0f * F.line, F.R + 4.0f * F.line, F.bottom + 5.0f * F.line, F.cut, C_BLACK, C_BLACK, 110.0f * p, 1);
    plate_fill(F.L, F.top, F.R, F.bottom, F.cut, C_HEAD, C_BOTTOM, 238.0f * p, 1);
    box(F.L, F.top + F.cut, F.R, F.head, C_HEAD, 255.0f * p);
    {   /* body gradient under the header */
        float y0 = F.head, y1 = F.bottom - F.cut; int n = 6;
        for (i = 0; i < n; i++) {
            u8 m[3]; int j; float kk = (float)i / (float)(n - 1);
            for (j = 0; j < 3; j++) m[j] = (u8)((float)C_TOP[j] + ((float)C_BOTTOM[j] - (float)C_TOP[j]) * kk);
            box(F.L, y0 + (y1 - y0) * (float)i / (float)n, F.R, y0 + (y1 - y0) * (float)(i + 1) / (float)n, m, 255.0f * p);
        }
    }
    /* header: accent wedge fading to the right, three slanted stripes on the right, a running sheen */
    s = (F.head - F.top) * 0.45f;                                    /* slant of everything in the header */
    for (i = 0; i < 4; i++) {
        static const float A[4] = {120.0f, 74.0f, 40.0f, 17.0f};
        float xa = F.L + w * 0.075f * (float)i, xb = xa + w * 0.075f;
        quad(i ? xa + s : xa, F.top, xb + s, F.top, i ? xa : xa, F.head, xb, F.head, ac, A[i] * p);
    }
    box(F.L, F.top, F.L + 2.0f * F.line, F.head, ac, 255.0f * p);
    for (i = 0; i < 3; i++) {
        static const float A[3] = {150.0f, 92.0f, 46.0f};
        float xa = F.R - w * 0.20f + w * 0.050f * (float)i, xb = xa + w * 0.020f, yt = F.top + F.cut;
        quad(xa + s, yt, xb + s, yt, xa, F.head, xb, F.head, ac, A[i] * p);
    }
    if (g_anim) {
        u64 ph = t % 3400UL;
        if (ph < 650UL) {
            float bw = w * 0.16f, u = (float)ph / 650.0f;
            x = F.L - bw + (w + bw) * u;
            quad(clampf(x + s, F.L, F.R - F.cut), F.top, clampf(x + bw + s, F.L, F.R - F.cut), F.top, clampf(x, F.L, F.R), F.head, clampf(x + bw, F.L, F.R), F.head, C_WHITE, 24.0f * p);
            quad(clampf(x + bw * 0.35f + s, F.L, F.R - F.cut), F.top, clampf(x + bw * 0.60f + s, F.L, F.R - F.cut), F.top, clampf(x + bw * 0.35f, F.L, F.R), F.head, clampf(x + bw * 0.60f, F.L, F.R), F.head, C_WHITE, 30.0f * p);
        }
    }
    /* the glowing line under the header (it breathes a little) and the outline */
    k = g_anim ? 0.80f + 0.20f * ease((float)((t % 2400UL) < 1200UL ? t % 1200UL : 1200UL - t % 1200UL) / 1200.0f) : 1.0f;
    box(F.L, F.head - F.line, F.R, F.head + F.line, ac, 255.0f * p);
    box(F.L, F.head - 3.0f * F.line, F.R, F.head + 3.0f * F.line, ac, 70.0f * p * k);
    box(F.L, F.head - 6.0f * F.line, F.R, F.head + 6.0f * F.line, ac, 26.0f * p * k);
    glow(F.L, F.top, F.R, F.bottom, F.cut, F.line, ac, 215.0f * p);
}

HIDDEN void ui_rect(const u8 *c, float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4) {
    const u8 *ac = ACCENT[g_accent];
    if (!g_on || !c) { g_rect(c, x1, y1, x2, y2, x3, y3, x4, y4); return; }
    if (BLUE(c) && c[3] == 150 && near(x1, 0.35f) && near(y1, 0.12f) && near(x2, 0.65f) && near(y3, 0.92f)) { draw_panel(); return; }
    if (BLUE(c) && (c[3] == 100 || c[3] == 180)) {   /* a page arrow (CLEO draws the triangle as two shapes); brighter while pressed */
        float cx = (x1 + x2 + x3 + x4) * 0.25f, cy = (y1 + y2 + y3 + y4) * 0.25f, g = 1.22f; u8 n[4];
        n[0] = ac[0]; n[1] = ac[1]; n[2] = ac[2]; n[3] = (u8)(c[3] == 180 ? 90 : 46);
        g_rect(n, cx + (x1 - cx) * g, cy + (y1 - cy) * g, cx + (x2 - cx) * g, cy + (y2 - cy) * g, cx + (x3 - cx) * g, cy + (y3 - cy) * g, cx + (x4 - cx) * g, cy + (y4 - cy) * g);
        n[3] = (u8)(c[3] == 180 ? 255 : 205);
        g_rect(n, x1, y1, x2, y2, x3, y3, x4, y4);
        return;
    }
    if (RED(c)) { u8 n[4]; n[0] = ac[0]; n[1] = ac[1]; n[2] = ac[2]; n[3] = c[3]; g_rect(n, x1, y1, x2, y2, x3, y3, x4, y4); return; }
    g_rect(c, x1, y1, x2, y2, x3, y3, x4, y4);
}

static int marked(const u16 *s) { int n = 0; while (s[n]) n++; return n >= 3 && s[n - 3] == '[' && s[n - 2] == 'X' && s[n - 1] == ']'; }
static void put(const u16 *s, int align, int style, float x, float y, float sx, float sy, const u8 *rgb, float a) {
    u8 n[4]; int ia = (int)a;
    n[0] = rgb[0]; n[1] = rgb[1]; n[2] = rgb[2]; n[3] = (u8)(ia < 0 ? 0 : ia > 255 ? 255 : ia);
    g_text(s, align, n, style, x, y, sx, sy);
}
HIDDEN void ui_text(const u16 *s, int align, const u8 *c, int style, float x, float y, float sx, float sy) {
    const u8 *ac = ACCENT[g_accent]; float k, w = F.R - F.L, a;
    static const u8 C_TEXT[3] = {238, 238, 240}, C_DARK[3] = {14, 14, 18}, C_PLATE[3] = {20, 22, 30};
    if (!g_on || !s || !c) { g_text(s, align, c, style, x, y, sx, sy); return; }
    if (game_russian()) {
        if (same(s, "CLOSE")) s = RU_CLOSE;
        else if (same(s, "OPEN CLEO MENU")) s = RU_OPEN;
        else s = to_game_russian(s);
    }
    if (!menu_live()) { g_text(s, align, c, style, x, y, sx, sy); return; }
    if (align == 0 && style == 1 && near(x, 0.5f) && near(y, 0.09f)) {                    /* title: centred in the header */
        u32 sig = hash16(s) ^ ((u32)F.rows * 131U) ^ ((u32)*(volatile int *)(g_img + CLEO_PAGE) * 7919U);
        if (F.have_sig && sig != F.sig) { F.switch_t = F.now; F.press_y = -1.0f; }        /* another page or another menu, without closing */
        F.sig = sig; F.have_sig = 1;
        k = 0.90f * fit(s, style, sx * 0.90f, 0.80f * w / g_W);
        put(s, 0, style, 0.5f, (F.top + F.head) * 0.5f / g_H - GLYPH_TOP - 0.5f * GLYPH_HEAD * sy * k, sx * k, sy * k, C_TEXT, (float)c[3]);
        return;
    }
    if (align == 1 && near(x, 0.2f) && near(y, 0.87f)) {
        /* The close caption. CLEO keeps it far away in the bottom-left corner; here it is a tab on the right of the
           header. CLEO has just written the touch box of the caption into its data (it does so every frame, right
           before this call) and reads it when the screen is tapped - so the box is moved together with the picture. */
        float tw, x1, x2, y1 = F.top + 0.014f * g_H, y2 = F.head - 0.014f * g_H, cut = 0.016f * g_H, hit[4];
        k = 0.80f * fit(s, style, sx * 0.80f, 0.095f);
        tw = text_width(s, style, sx * k) * g_W;
        if (tw <= 0.0f) tw = 0.075f * g_W;
        x1 = F.R + 5.0f * F.line; x2 = x1 + tw + 0.030f * g_W;
        hit[0] = x1 / g_W - 0.004f; hit[1] = y1 / g_H - 0.012f; hit[2] = x2 / g_W + 0.012f; hit[3] = y2 / g_H + 0.012f;
        memcpy((void *)(g_img + CLEO_CLOSE_BOX), hit, 16);
        plate_fill(x1, y1, x2, y2, cut, C_PLATE, C_BOTTOM, 238.0f, 2);
        glow(x1, y1, x2, y2, cut, F.line, ac, 200.0f);
        put(s, 0, style, (x1 + x2) * 0.5f / g_W, (y1 + y2) * 0.5f / g_H - GLYPH_TOP - 0.5f * GLYPH_HEAD * sy * k, sx * k, sy * k, C_TEXT, (float)c[3]);
        return;
    }
    if (align == 0 && style == 0 && near(x, 0.5f) && near(sx, 0.75f) && y > 0.19f && y < 0.93f) {   /* a row */
        float y1 = (y + 0.010f) * g_H, y2 = (y + 0.080f) * g_H, sl = (y2 - y1) * 0.30f, dx;
        const u8 *col = C_TEXT; int mk = marked(s);
        a = row_alpha(y); dx = (1.0f - a) * 0.010f;
        if (GREEN(c) && (!near(F.press_y, y) || F.now - F.press_t > 500)) { F.press_y = y; F.press_t = F.now; }
        if (mk) {                                                                          /* the mode that is on: accent text, a tint and a marker */
            box(F.L + F.line, y1, F.R - F.line, y2, ac, 20.0f * a);
            quad(F.L + w * 0.045f + sl, y1 + (y2 - y1) * 0.22f, F.L + w * 0.062f + sl, y1 + (y2 - y1) * 0.22f, F.L + w * 0.045f, y2 - (y2 - y1) * 0.22f, F.L + w * 0.062f, y2 - (y2 - y1) * 0.22f, ac, 255.0f * a);
            col = ac;
        }
        /* a hairline under the row, brighter in the middle */
        box(F.L + w * 0.06f, y2 + 0.004f * g_H, F.R - w * 0.06f, y2 + 0.004f * g_H + 1.0f, C_WHITE, 14.0f * a);
        box(F.L + w * 0.22f, y2 + 0.004f * g_H, F.R - w * 0.22f, y2 + 0.004f * g_H + 1.0f, C_WHITE, 22.0f * a);
        if (near(F.press_y, y) && F.now - F.press_t < PRESS_SWEEP_MS + PRESS_HOLD_MS + PRESS_FADE_MS) {
            /* the press: an accent bar shoots from the left, holds, then fades (CLEO itself shows the press for 3 frames only) */
            float t = (float)(F.now - F.press_t), sw = g_anim ? ease(t / (float)PRESS_SWEEP_MS) : 1.0f;
            float pa = t < (float)(PRESS_SWEEP_MS + PRESS_HOLD_MS) ? 1.0f : 1.0f - (t - (float)(PRESS_SWEEP_MS + PRESS_HOLD_MS)) / (float)PRESS_FADE_MS;
            float xl = F.L + w * 0.035f, xr = xl + (F.R - w * 0.035f - sl - xl) * sw;
            quad(xl + sl - 3.0f * F.line, y1 - 3.0f * F.line, xr + sl + 3.0f * F.line, y1 - 3.0f * F.line, xl - 3.0f * F.line, y2 + 3.0f * F.line, xr + 3.0f * F.line, y2 + 3.0f * F.line, ac, 60.0f * pa);
            quad(xl + sl, y1, xr + sl, y1, xl, y2, xr, y2, ac, 240.0f * pa);
            quad(xr + sl - 2.0f * F.line, y1, xr + sl, y1, xr - 2.0f * F.line, y2, xr, y2, C_WHITE, 150.0f * pa);
            if (pa > 0.55f) col = C_DARK;
        }
        k = 1.12f * fit(s, style, sx * 1.12f, 0.84f * w / g_W);
        put(s, 0, style, 0.5f + dx, y + 0.045f - GLYPH_TOP - 0.5f * GLYPH_ROW * sy * k, sx * k, sy * k, col, (float)c[3] * a);
        return;
    }
    if (near(x, 0.61f) && near(y, 0.16f)) {                                               /* page number: under the header, right */
        put(s, 2, style, (F.R - w * 0.05f) / g_W, F.head / g_H + 0.010f, sx, sy, ac, (float)c[3]);
        return;
    }
    g_text(s, align, c, style, x, y, sx, sy);
}

/* ---------- Mods Settings (SAUtils) ---------- */
static const char *g_onoff[2] = {"Off", "On"};
static const char *g_colours[5] = {"Orange", "Blue", "Green", "Red", "White"};
static void set_on(int o, int v, void *d) { (void)o; (void)d; g_on = v != 0; save_config(); }
static void set_accent(int o, int v, void *d) { (void)o; (void)d; g_accent = v < 0 || v > 4 ? 0 : v; save_config(); }
static void set_anim(int o, int v, void *d) { (void)o; (void)d; g_anim = v != 0; save_config(); }
static void set_dim(int o, int v, void *d) { (void)o; (void)d; g_dim = v != 0; save_config(); }
static void add_menu_items(void) {
    typedef void *(*getif_fn)(const char *);
    typedef int (*add_fn)(void *self, int type, const char *name, int init, int min, int max, const char **sw, void (*cb)(int, int, void *));
    void *aml = dlopen("libAML.so", RTLD_NOW), *sa; getif_fn getif = aml ? (getif_fn)dlsym(aml, "GetInterface") : 0; add_fn add;
    sa = getif ? getif("SAUtils") : 0;
    if (!sa) { lg("SAUtils not found - no settings items (the look is on)\n"); return; }
    add = (add_fn)((*(void ***)sa)[3]);   /* ISAUtils::AddClickableItem, as Touch x4 uses it */
    add(sa, 5, "CLEO UI", g_on, 0, 1, g_onoff, set_on);
    add(sa, 5, "CLEO UI Colour", g_accent, 0, 4, g_colours, set_accent);
    add(sa, 5, "CLEO UI Animation", g_anim, 0, 1, g_onoff, set_anim);
    add(sa, 5, "CLEO UI Dim", g_dim, 0, 1, g_onoff, set_dim);
    lg("Mods Settings: CLEO UI, CLEO UI Colour, CLEO UI Animation, CLEO UI Dim\n");
}

/* ---------- install ---------- */
struct found { u64 base, size; };
static struct found g_cleo;
static int ends_with(const char *s, const char *tail) {
    u64 n, m = slen(tail), i;
    if (!s) return 0;
    n = slen(s);
    if (n < m) return 0;
    for (i = 0; i < m; i++) if (s[n - m + i] != tail[i]) return 0;
    return 1;
}
static int find_modules(struct dl_phdr_info *info, u64 size, void *data) {
    int i; u64 hi = 0;
    (void)size; (void)data;
    if (ends_with(info->dlpi_name, "libGTASA.so")) g_gta = info->dlpi_addr;
    else if (ends_with(info->dlpi_name, "libSAcleo64.so")) {
        for (i = 0; i < info->dlpi_phnum; i++) if (info->dlpi_phdr[i].type == 1 && info->dlpi_phdr[i].vaddr + info->dlpi_phdr[i].memsz > hi) hi = info->dlpi_phdr[i].vaddr + info->dlpi_phdr[i].memsz;
        g_cleo.base = info->dlpi_addr; g_cleo.size = hi;
    }
    return 0;
}
/* 0 = not ready yet, 1 = installed, -1 = this is not the CLEO build the mod knows */
static int try_install(void) {
    u64 b; const char *v; int i; volatile u64 *rp, *tp;
    g_cleo.base = 0;
    dl_iterate_phdr(find_modules, 0);
    if (!g_cleo.base || !g_gta) return 0;
    if (g_cleo.size < CLEO_MIN_SIZE) { lg("libSAcleo64.so is smaller than the known build - nothing changed\n"); return -1; }
    b = g_cleo.base;
    rp = (volatile u64 *)(b + CLEO_RECT_PTR); tp = (volatile u64 *)(b + CLEO_TEXT_PTR);
    if (!*rp || !*tp) return 0;                                    /* CLEO has not started yet */
    v = (const char *)(b + CLEO_VERSION);
    for (i = 0; CLEO_VERSION_TEXT[i]; i++) if (v[i] != CLEO_VERSION_TEXT[i]) { lg("another CLEO version - nothing changed\n"); return -1; }
    if (*rp != b + CLEO_RECT_FN || *tp != b + CLEO_TEXT_FN) { lg("CLEO's drawing pointers are not the expected ones (another mod?) - nothing changed\n"); return -1; }
    for (i = 0; i < 4; i++) if (((const u32 *)(b + CLEO_RECT_FN))[i] != RECT_CODE[i] || ((const u32 *)(b + CLEO_TEXT_FN))[i] != TEXT_CODE[i]) { lg("CLEO's drawing code differs - nothing changed\n"); return -1; }
    for (i = 0; i < 2; i++) if (((const u32 *)(g_gta + GTA_PRINTSTRING))[i] != GTA_CHECK[i]) { lg("another game version: Russian text conversion is off\n"); g_gta = 0; break; }
    g_rect = (rect_fn)(b + CLEO_RECT_FN); g_text = (text_fn)(b + CLEO_TEXT_FN); g_img = b + CLEO_IMAGE;
    g_width = 0;
    if (g_gta && ((const u32 *)(g_gta + GTA_STRWIDTH))[0] == GTA_WIDTH_CHECK[0] && ((const u32 *)(g_gta + GTA_STRWIDTH))[1] == GTA_WIDTH_CHECK[1]) g_width = (width_fn)(g_gta + GTA_STRWIDTH);
    else lg("the game's text measuring is not the expected code: texts keep CLEO's size\n");
    __atomic_store_n((u64 *)rp, (u64)&ui_rect, __ATOMIC_RELEASE);
    __atomic_store_n((u64 *)tp, (u64)&ui_text, __ATOMIC_RELEASE);
    lg("libSAcleo64.so base "); lghex(b); lg("\nnew look installed (two pointers in CLEO's data; no code changed)\n");
    return 1;
}
static void *waiter(void *arg) {
    int i, r = 0;
    (void)arg;
    for (i = 0; i < 600 && !(r = try_install()); i++) usleep(200000);   /* up to two minutes */
    if (!r) lg("CLEO did not start within two minutes - nothing changed\n");
    flush_log();
    return 0;
}

struct ModInfo { char guid[48]; char name[48]; char version[24]; char author[48]; u16 ver[4]; u8 reserved[336]; };
static struct ModInfo g_info __attribute__((aligned(16))) = {"net.helicover.cleoui", "CLEO UI", "0.2", "Helicover", {0, 2, 0, 0}, {0}};
static int g_done;
EXPORT struct ModInfo *__GetModInfo(void) { return &g_info; }
EXPORT void OnModPreLoad(void) {}
EXPORT void OnModLoad(void) {
    u64 th; int r;
    if (g_done) return;
    g_done = 1;
    lg("CLEO UI 0.2\n");
    load_config();
    add_menu_items();
    r = try_install();
    if (!r) { if (pthread_create(&th, 0, waiter, 0)) lg("cannot start the waiting thread - nothing changed\n"); else lg("waiting for CLEO to start\n"); }
    lgint(r); lg(" = state at load\n");
    flush_log();
}
