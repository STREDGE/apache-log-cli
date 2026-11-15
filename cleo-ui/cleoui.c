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
static int g_on = 1, g_accent = 0, g_anim = 1;
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
    g_on = cfg_value(b, "Enabled", 1, 1); g_accent = cfg_value(b, "Accent", 4, 0); g_anim = cfg_value(b, "Animation", 1, 1);
}
static void save_config(void) {
    char t[96]; const char *a = "[Preferences]\nEnabled = "; u32 n = 0; int fd;
    while (*a) t[n++] = *a++;
    t[n++] = (char)('0' + g_on); a = "\nAccent = "; while (*a) t[n++] = *a++;
    t[n++] = (char)('0' + g_accent); a = "\nAnimation = "; while (*a) t[n++] = *a++;
    t[n++] = (char)('0' + g_anim); t[n++] = '\n';
    fd = open(CFG, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return;
    write(fd, t, n); close(fd);
}

/* ---------- CLEO's two drawing functions ---------- */
typedef void (*rect_fn)(const u8 *rgba, float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4);
typedef void (*text_fn)(const u16 *gxt, int align, const u8 *rgba, int style, float x, float y, float sx, float sy);
static rect_fn g_rect;
static text_fn g_text;
static u64 g_gta;

static void box(float x1, float y1, float x2, float y2, int r, int g, int b, int a) {
    u8 c[4];
    if (a <= 0) return;
    c[0] = (u8)r; c[1] = (u8)g; c[2] = (u8)b; c[3] = (u8)(a > 255 ? 255 : a);
    g_rect(c, x1, y1, x2, y1, x1, y2, x2, y2);
}
static int near(float a, float b) { float d = a - b; return d < 0.004f && d > -0.004f; }
static int rgb_is(const u8 *c, int r, int g, int b) { return c[0] == r && c[1] == g && c[2] == b; }

/* ---------- animation clock ---------- */
static u64 now_ms(void) { struct timespec t; t.tv_sec = 0; t.tv_nsec = 0; clock_gettime(1 /* CLOCK_MONOTONIC */, &t); return (u64)t.tv_sec * 1000UL + (u64)t.tv_nsec / 1000000UL; }
static u64 g_panel_last, g_panel_open, g_frame_now;
static float g_p = 1.0f;      /* 0..1: how far the menu has opened */
static float g_dy;            /* current vertical slide of the whole menu */
#define OPEN_MS 160
#define GAP_MS 250            /* a pause this long between two panel draws = the menu was closed and is opened again */
static u64 g_sel_since; static float g_sel_y = -1.0f;
#define PRESS_MS 140

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

/* ---------- the new look ---------- */
#define BLUE(c) rgb_is(c, 0x37, 0x7f, 0xaf)   /* CLEO's menu colour (55,127,175): panel alpha 150, arrows 100 / 180 */
#define RED(c) rgb_is(c, 0xff, 0x0a, 0x0a)    /* the OPEN CLEO MENU button */
#define GREEN(c) rgb_is(c, 0x28, 0xeb, 0x18)  /* CLEO's colour for the row that was just pressed */
static int alpha_of(int a) { return (int)((float)a * g_p); }

HIDDEN void ui_rect(const u8 *c, float x1, float y1, float x2, float y2, float x3, float y3, float x4, float y4) {
    const u8 *ac = ACCENT[g_accent];
    if (!g_on || !c) { g_rect(c, x1, y1, x2, y2, x3, y3, x4, y4); return; }
    if (BLUE(c) && c[3] == 150 && near(x1, 0.35f) && near(y1, 0.12f) && near(x2, 0.65f) && near(y3, 0.92f)) {
        /* the panel of a script menu: first thing drawn in a frame while a menu is open */
        u64 t = now_ms();
        if (t - g_panel_last > GAP_MS) { g_panel_open = t; g_sel_y = -1.0f; }
        g_panel_last = g_frame_now = t;
        g_p = 1.0f;
        if (g_anim && t - g_panel_open < OPEN_MS) { float k = (float)(t - g_panel_open) / (float)OPEN_MS; g_p = k * (2.0f - k); if (g_p < 0.12f) g_p = 0.12f; }   /* ease out; the first frame is already faintly visible */
        g_dy = (1.0f - g_p) * 0.035f;
        {
            float l = 0.335f, r = 0.665f, top = 0.045f + g_dy, bot = 0.935f + g_dy, head = 0.165f + g_dy;
            box(l + 0.006f, top + 0.010f, r + 0.006f, bot + 0.010f, 0, 0, 0, alpha_of(90));          /* shadow */
            box(l, top, r, bot, 14, 15, 19, alpha_of(232));                                           /* body */
            box(l, top, r, head, 30, 32, 40, alpha_of(240));                                          /* header */
            box(l, head, r, head + 0.005f, ac[0], ac[1], ac[2], alpha_of(255));                       /* accent line */
            box(l, top, l + 0.0035f, head, ac[0], ac[1], ac[2], alpha_of(255));                       /* accent mark */
            box(l, bot - 0.003f, r, bot, ac[0], ac[1], ac[2], alpha_of(110));
        }
        return;
    }
    if (BLUE(c) && (c[3] == 100 || c[3] == 180)) {   /* a page arrow (triangle); brighter while pressed */
        u8 n[4]; n[0] = ac[0]; n[1] = ac[1]; n[2] = ac[2]; n[3] = (u8)alpha_of(c[3] == 180 ? 255 : 190);
        g_rect(n, x1, y1 + g_dy, x2, y2 + g_dy, x3, y3 + g_dy, x4, y4 + g_dy);
        return;
    }
    if (RED(c)) {                                     /* the OPEN CLEO MENU button: keeps its shape and its fade */
        u8 n[4];
        n[0] = 18; n[1] = 19; n[2] = 24; n[3] = (u8)(c[3] > 200 ? 235 : c[3] + 35);
        g_rect(n, x1, y1, x2, y2, x3, y3, x4, y4);
        {   /* an accent line along the top edge of whatever shape CLEO gave it */
            float h = 0.006f;
            n[0] = ac[0]; n[1] = ac[1]; n[2] = ac[2]; n[3] = 255;
            g_rect(n, x1, y1, x2, y2, x1, y1 + h, x2, y2 + h);
        }
        return;
    }
    g_rect(c, x1, y1, x2, y2, x3, y3, x4, y4);
}

HIDDEN void ui_text(const u16 *s, int align, const u8 *c, int style, float x, float y, float sx, float sy) {
    const u8 *ac = ACCENT[g_accent]; u8 n[4]; int menu;
    if (!g_on || !s || !c) { g_text(s, align, c, style, x, y, sx, sy); return; }
    if (game_russian()) {
        if (same(s, "CLOSE")) s = RU_CLOSE;
        else if (same(s, "OPEN CLEO MENU")) s = RU_OPEN;
        else s = to_game_russian(s);
    }
    menu = now_ms() - g_panel_last < 60;            /* drawn right after the panel: part of the menu */
    if (!menu) { g_text(s, align, c, style, x, y, sx, sy); return; }
    n[3] = (u8)alpha_of(c[3]);
    if (align == 0 && style == 1 && near(x, 0.5f) && near(y, 0.09f)) {                    /* title */
        n[0] = 245; n[1] = 245; n[2] = 245;
        g_text(s, align, n, style, x, y + g_dy - 0.008f, sx * 0.92f, sy * 0.92f);
        return;
    }
    if (align == 1 && near(x, 0.2f) && near(y, 0.87f)) {                                  /* the close caption, bottom left */
        box(0.19f, 0.862f + g_dy, 0.31f, 0.975f + g_dy, 14, 15, 19, alpha_of(225));
        box(0.19f, 0.862f + g_dy, 0.31f, 0.867f + g_dy, ac[0], ac[1], ac[2], alpha_of(255));
        n[0] = 235; n[1] = 235; n[2] = 235;
        g_text(s, align, n, style, x + 0.012f, y + g_dy + 0.004f, sx, sy);
        return;
    }
    if (align == 0 && style == 0 && near(x, 0.5f) && near(sx, 0.75f) && y > 0.19f && y < 0.92f) {   /* a row */
        if (GREEN(c)) {                                                                    /* the row just pressed */
            float w = 1.0f; u64 t = now_ms();
            if (!near(g_sel_y, y)) { g_sel_y = y; g_sel_since = t; }
            if (g_anim && t - g_sel_since < PRESS_MS) w = 0.35f + 0.65f * (float)(t - g_sel_since) / (float)PRESS_MS;
            box(0.5f - 0.152f * w, y + 0.012f + g_dy, 0.5f + 0.152f * w, y + 0.080f + g_dy, ac[0], ac[1], ac[2], alpha_of(235));
            n[0] = 16; n[1] = 16; n[2] = 20;
        } else {
            box(0.36f, y + 0.084f + g_dy, 0.64f, y + 0.0855f + g_dy, 255, 255, 255, alpha_of(22));   /* hairline under the row */
            n[0] = 236; n[1] = 236; n[2] = 236;
        }
        g_text(s, align, n, style, x, y + g_dy, sx, sy);
        return;
    }
    if (near(x, 0.61f) && near(y, 0.16f)) {                                               /* page number */
        n[0] = ac[0]; n[1] = ac[1]; n[2] = ac[2];
        g_text(s, align, n, style, x + 0.02f, y + g_dy - 0.055f, sx, sy);
        return;
    }
    n[0] = c[0]; n[1] = c[1]; n[2] = c[2];
    g_text(s, align, n, style, x, y + g_dy, sx, sy);
}

/* ---------- Mods Settings (SAUtils) ---------- */
static const char *g_onoff[2] = {"Off", "On"};
static const char *g_colours[5] = {"Orange", "Blue", "Green", "Red", "White"};
static void set_on(int o, int v, void *d) { (void)o; (void)d; g_on = v != 0; save_config(); }
static void set_accent(int o, int v, void *d) { (void)o; (void)d; g_accent = v < 0 || v > 4 ? 0 : v; save_config(); }
static void set_anim(int o, int v, void *d) { (void)o; (void)d; g_anim = v != 0; save_config(); }
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
    lg("Mods Settings: CLEO UI, CLEO UI Colour, CLEO UI Animation\n");
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
    g_rect = (rect_fn)(b + CLEO_RECT_FN); g_text = (text_fn)(b + CLEO_TEXT_FN);
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
static struct ModInfo g_info __attribute__((aligned(16))) = {"net.helicover.cleoui", "CLEO UI", "0.1", "Helicover", {0, 1, 0, 0}, {0}};
static int g_done;
EXPORT struct ModInfo *__GetModInfo(void) { return &g_info; }
EXPORT void OnModPreLoad(void) {}
EXPORT void OnModLoad(void) {
    u64 th; int r;
    if (g_done) return;
    g_done = 1;
    lg("CLEO UI 0.1\n");
    load_config();
    add_menu_items();
    r = try_install();
    if (!r) { if (pthread_create(&th, 0, waiter, 0)) lg("cannot start the waiting thread - nothing changed\n"); else lg("waiting for CLEO to start\n"); }
    lgint(r); lg(" = state at load\n");
    flush_log();
}
