#include "MicroBit.h"
#include "tpbot.h"

MicroBit uBit;
TPBOT tp(uBit);

int main() {
    uBit.init();

    tp.setServo(3, 0);

    while (1) {
    tp.getDistanceCM();  // Will print just the number (duration_us) via serial
    uBit.sleep(500);
	}
    release_fiber();
    return 0;
}

