# Intro

I tried to use BBC Microbit Version of Micropython to implement Non Blocking Asynchronous Processing, by the asyncio version for Micropython was not available.

I looked at reverting back to Javascript, but concluded this was a wasted journey.

I also looked at creating a special version of Micropython with ujson and uasyncio - also a wasted journey

# Actual Approach

I have fallen back to basics and using C++

I want to make sure it is future proof and can be used for a while.

I looked at Thonny and VS Code, Thonny was impressive, but is now not being maintained.

To create a hex file to be sent to the Microbit one needs to compile it.

The wonderful people at https://github.com/lancaster-university/microbit-v2-samples have provided a repo and instructions to create sketches, compile them and upload them to the MB.

This opend up many async opportunities.

# The TP Bot Library

I used ChatGPT to reverse engineer the TPBot Library into C++

It was a good way to start, but created more complexity and excuses came thick and fast from ChatGPT.

My recommendation is always ask - simplify or take away unnecessary functionality when you start off.

Always be clear what the sensors are that the robot is using.

Persevere and say RUBBISH to ChatGPT until it really comes up with an alternative or you ask for this.

It said the Distance sensors were ineffective at >20cm!




