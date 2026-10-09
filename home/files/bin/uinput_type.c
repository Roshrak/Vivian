/* Reproducible implementation of the existing Minecraft helper protocol.
 * Input targeting/seat ownership checks remain in mc_chat_responder.py.
 * --check validates commands without opening or injecting into /dev/uinput.
 */
#include <linux/uinput.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

static int key(char c, int *shift) {
  const char *plain = "1234567890-=[];',./`\\";
  const char *upper = "!@#$%^&*()_+{}:\"<>?~|";
  int codes[] = {KEY_1,KEY_2,KEY_3,KEY_4,KEY_5,KEY_6,KEY_7,KEY_8,KEY_9,KEY_0,
    KEY_MINUS,KEY_EQUAL,KEY_LEFTBRACE,KEY_RIGHTBRACE,KEY_SEMICOLON,KEY_APOSTROPHE,
    KEY_COMMA,KEY_DOT,KEY_SLASH,KEY_GRAVE,KEY_BACKSLASH};
  int letters[] = {KEY_A,KEY_B,KEY_C,KEY_D,KEY_E,KEY_F,KEY_G,KEY_H,KEY_I,KEY_J,
    KEY_K,KEY_L,KEY_M,KEY_N,KEY_O,KEY_P,KEY_Q,KEY_R,KEY_S,KEY_T,KEY_U,KEY_V,
    KEY_W,KEY_X,KEY_Y,KEY_Z};
  *shift = 0;
  if(c >= 'a' && c <= 'z') return letters[c-'a'];
  if(c >= 'A' && c <= 'Z') { *shift=1; return letters[c-'A']; }
  if(c == ' ') return KEY_SPACE;
  for(size_t i=0; i<strlen(plain); ++i) {
    if(c == plain[i]) return codes[i];
    if(c == upper[i]) { *shift=1; return codes[i]; }
  }
  return -1;
}

static int validate(const char *s) {
  if(!strncmp(s,"type:",5)) {
    if(strlen(s+5)>500) return 0;
    for(const char *p=s+5;*p;++p) { int shift; if(key(*p,&shift)<0) return 0; }
    return 1;
  }
  if(!strncmp(s,"sleep:",6)) {
    if(!s[6]) return 0;
    for(const char *p=s+6;*p;++p) if(*p<'0'||*p>'9') return 0;
    return strlen(s+6)<=4 && strtoul(s+6,NULL,10)<=2000;
  }
  if(!strcmp(s,"enter")||!strcmp(s,"slash")) return 1;
  int shift;
  return strlen(s)==1 && key(s[0],&shift)>=0;
}

static int emit(int fd, int type, int code, int value) {
  struct input_event ev = { .type=type, .code=code, .value=value };
  return write(fd,&ev,sizeof(ev))==sizeof(ev) ? 0 : -1;
}
static int press(int fd, int code, int shift) {
  if(shift && emit(fd,EV_KEY,KEY_LEFTSHIFT,1)) return -1;
  if(emit(fd,EV_KEY,code,1)||emit(fd,EV_SYN,SYN_REPORT,0)) return -1;
  usleep(10000);
  if(emit(fd,EV_KEY,code,0)) return -1;
  if(shift && emit(fd,EV_KEY,KEY_LEFTSHIFT,0)) return -1;
  return emit(fd,EV_SYN,SYN_REPORT,0);
}

int main(int argc, char **argv) {
  int check=argc>1&&!strcmp(argv[1],"--check"), start=check?2:1;
  if(argc<=start || argc-start>100) { fputs("usage: uinput_type [--check] t slash enter type:TEXT sleep:MILLISECONDS\n",stderr); return 2; }
  for(int i=start;i<argc;++i) if(!validate(argv[i])) {
    fputs("Unsupported input token, non-ASCII text or excessive input. Nothing injected.\n",stderr); return 2;
  }
  if(check) return 0;
  int fd=open("/dev/uinput",O_WRONLY|O_CLOEXEC);
  if(fd<0) { perror("uinput permission/device"); return 1; }
  if(ioctl(fd,UI_SET_EVBIT,EV_KEY)<0) goto fail;
  for(int k=1;k<256;++k) if(ioctl(fd,UI_SET_KEYBIT,k)<0) goto fail;
  struct uinput_setup setup = { .id = { .bustype=BUS_USB, .vendor=0x1, .product=0x1, .version=1 } };
  snprintf(setup.name,UINPUT_MAX_NAME_SIZE,"Vivian guarded Minecraft keyboard");
  if(ioctl(fd,UI_DEV_SETUP,&setup)<0||ioctl(fd,UI_DEV_CREATE)<0) goto fail;
  usleep(150000);
  int failed=0;
  for(int i=start;i<argc&&!failed;++i) {
    const char *s=argv[i];
    if(!strncmp(s,"sleep:",6)) { usleep(strtoul(s+6,NULL,10)*1000); continue; }
    if(!strcmp(s,"enter")) { failed=press(fd,KEY_ENTER,0); continue; }
    if(!strcmp(s,"slash")) { failed=press(fd,KEY_SLASH,0); continue; }
    s=!strncmp(s,"type:",5)?s+5:s;
    for(;*s&&!failed;++s) { int shift=0; int k=key(*s,&shift); failed=press(fd,k,shift); }
  }
  ioctl(fd,UI_DEV_DESTROY); close(fd);
  if(failed) { fputs("Input write failed; completion unconfirmed.\n",stderr); return 1; }
  return 0;
fail:
  perror("uinput initialization"); close(fd); return 1;
}
