/* The compiler may emit calls to these even in a freestanding build (struct copies, zero initialisers). */
typedef unsigned long hcb_size;
__attribute__((visibility("hidden"))) void *memcpy(void *d, const void *s, hcb_size n) {
    unsigned char *a = d; const unsigned char *b = s;
    while (n--) *a++ = *b++;
    return d;
}
__attribute__((visibility("hidden"))) void *memmove(void *d, const void *s, hcb_size n) {
    unsigned char *a = d; const unsigned char *b = s;
    if (a < b) while (n--) *a++ = *b++;
    else { a += n; b += n; while (n--) *--a = *--b; }
    return d;
}
__attribute__((visibility("hidden"))) void *memset(void *d, int c, hcb_size n) {
    unsigned char *a = d;
    while (n--) *a++ = (unsigned char)c;
    return d;
}
