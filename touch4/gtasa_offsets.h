/* generated from the user's arm64 libGTASA.so (same build as the crash logs) */
#define OFF_AND_TOUCH 0x31ec0cUL
#define OFF_MT2 0x32a6d4UL
#define OFF_MT4_STUB 0x32ab10UL
#define OFF_PROCESS_EVENTS 0x31e778UL
#define OFF_POINTS_GOT 0x851d38UL
#define OFF_POINTS 0x8b4ebcUL
#define POINTS_BYTES 56
#define POINT_STRIDE 0x1c
#define OFF_MAX_TOUCHES 0x85e748UL
static const unsigned int MT4_STUB_EXPECT[2]={0x320003e0U,0xd65f03c0U};
static const unsigned int MT2_PROLOGUE[4]={0xd101c3ffU,0xf90013f9U,0xa9035ff8U,0xa90457f6U};
static const unsigned int PE_PROLOGUE[4]={0xd10203ffU,0xa9026ffcU,0xa90367faU,0xa9045ff8U};
static const struct {unsigned long off;unsigned int expect,patch;} PATCHES[]={{0x320844UL,0x321f03e0U,0x52800080U},{0x320850UL,0x7100081fU,0x7100101fU},{0x326fecUL,0x7100041fU,0x71000c1fU},{0x327040UL,0x7100051fU,0x71000d1fU},{0x32706cUL,0x7100041fU,0x71000c1fU},{0x3270acUL,0x7100041fU,0x71000c1fU}};
#define NPATCHES 6
