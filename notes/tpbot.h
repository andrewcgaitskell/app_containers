#pragma once
#include "codal_target_hal.h"
#include "MicroBit.h"

#define TPBOT_ADDR 0x10

enum TrackingState {
    BOTH_WHITE = 0,
    LEFT_BLACK_RIGHT_WHITE = 10,
    LEFT_WHITE_RIGHT_BLACK = 1,
    BOTH_BLACK = 11,
    TRACKING_ERROR = -1
};

class TPBOT {
public:
    TPBOT(MicroBit &uBit)
        : uBit(uBit),
          pinL(uBit.io.P13),
          pinR(uBit.io.P14),
          pinT(uBit.io.P16),
          pinE(uBit.io.P15)
    {
        pinL.setPull(PullMode::None);
        pinR.setPull(PullMode::None);
    }

    void setMotorsSpeed(int left, int right) {
        if (left < -100 || left > 100 || right < -100 || right > 100)
            return;
        uint8_t direction = 0;
        if (left <= 0) direction |= 0x01;
        if (right <= 0) direction |= 0x02;
        uint8_t l = abs(left);
        uint8_t r = abs(right);
        uint8_t buf[4] = {0x01, l, r, direction};
        uBit.i2c.write(TPBOT_ADDR, buf, 4);
    }

    void setCarLight(uint8_t R, uint8_t G, uint8_t B) {
        uint8_t buf[4] = {0x20, R, G, B};
        uBit.i2c.write(TPBOT_ADDR, buf, 4);
    }

    float getDistanceCM(int unit = 0) {
	    // Wait for echo to be LOW before starting
	    while (pinE.getDigitalValue() == 1) {}

	    // Trigger the pulse
	    pinT.setDigitalValue(0);
	    target_wait_us(2);
	    pinT.setDigitalValue(1);
	    target_wait_us(10);
	    pinT.setDigitalValue(0);

	    // Wait for echo HIGH
	    uint32_t wait_start = (uint32_t)system_timer_current_time_us();
	    uint32_t timeout = wait_start + 30000;
	    while (pinE.getDigitalValue() == 0) {
		if ((uint32_t)system_timer_current_time_us() > timeout) {
		    uBit.serial.printf("-1\n");
		    return -1.0f;
		}
	    }
	    uint32_t echo_start = (uint32_t)system_timer_current_time_us();

	    // Wait for echo LOW
	    timeout = (uint32_t)system_timer_current_time_us() + 30000;
	    while (pinE.getDigitalValue() == 1) {
		if ((uint32_t)system_timer_current_time_us() > timeout) {
		    uBit.serial.printf("-1\n");
		    return -1.0f;
		}
	    }
	    uint32_t echo_end = (uint32_t)system_timer_current_time_us();

	    int duration_us = (int)(echo_end - echo_start);

	    float distance_cm = duration_us / 58.0f;
	    int int_cm = (int)distance_cm;
	    int frac_cm = (int)((distance_cm - int_cm) * 100);

	    // Print both raw duration and calculated cm
	    uBit.serial.printf("duration_us: %d, distance_cm: %d.%02d\n", duration_us, int_cm, frac_cm);

	    return distance_cm;
	}

    float getDistanceSimple(int unit = 0) {
	    // Wait for echo to be LOW before starting
	    while (pinE.getDigitalValue() == 1) {}

	    // Trigger the pulse
	    pinT.setDigitalValue(0);
	    target_wait_us(2);
	    pinT.setDigitalValue(1);
	    target_wait_us(10);
	    pinT.setDigitalValue(0);

	    // Wait for echo HIGH
	    uint32_t wait_start = (uint32_t)system_timer_current_time_us();
	    uint32_t timeout = wait_start + 30000;
	    while (pinE.getDigitalValue() == 0) {
		if ((uint32_t)system_timer_current_time_us() > timeout) {
		    uBit.serial.printf("-1\n");
		    return -1.0f;
		}
	    }
	    uint32_t echo_start = (uint32_t)system_timer_current_time_us();

	    // Wait for echo LOW
	    timeout = (uint32_t)system_timer_current_time_us() + 30000;
	    while (pinE.getDigitalValue() == 1) {
		if ((uint32_t)system_timer_current_time_us() > timeout) {
		    uBit.serial.printf("-1\n");
		    return -1.0f;
		}
	    }
	    uint32_t echo_end = (uint32_t)system_timer_current_time_us();

	    int duration_us = (int)(echo_end - echo_start);

	    // Output just the raw duration in microseconds (or use this as your "distance")
	    uBit.serial.printf("%d\n", duration_us);

	    // Return as float
	    return (float)duration_us;
	}

    TrackingState getTracking() {
        int l = pinL.getDigitalValue();
        int r = pinR.getDigitalValue();
        if (l == 1 && r == 1) return BOTH_WHITE;
        if (l == 0 && r == 1) return LEFT_BLACK_RIGHT_WHITE;
        if (l == 1 && r == 0) return LEFT_WHITE_RIGHT_BLACK;
        if (l == 0 && r == 0) return BOTH_BLACK;
        return TRACKING_ERROR;
    }

    void setServo(int servo, int angle) {
        if (servo < 1 || servo > 4 || angle < 0 || angle > 180)
            return;
        uint8_t s = servo - 1;
        uint8_t buf[4] = {uint8_t(0x10 + s), uint8_t(angle), 0, 0};
        uBit.i2c.write(TPBOT_ADDR, buf, 4);
    }

private:
    MicroBit &uBit;
    MicroBitPin &pinL;
    MicroBitPin &pinR;
    MicroBitPin &pinT;
    MicroBitPin &pinE;
};

