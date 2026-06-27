# app_containers

# Introduction

This collection of containers starts to create a multiple service app

I am using it for home assistant, but can be used as a starting point for any app.

# Notes on using it with Home Assistant

## Docker Containers are Run as Root

sudo su

## start up the containers

cd /opt/data/app_containers/compose

docker compose -f ha_compose.yml up -d

## how to stop containers

docker compose -f ha_compose.yml down

## login to home assistant

localhost:8123


## login to esphome

localhost:6052

edit

install

Plug into Computer running ESPHome Device Builder

update

wirelessly it works once it has been setup using the above

## shutdown containers

docker compose down


## using arduino ide

could not use code and platformio

cd /home/pi5ha/Software/arduino-1.8.19


run arduino using

./home/pi5ha/Software/arduino-1.8.19/arduino


## References

https://roelofjanelsinga.com/articles/mqtt-discovery-with-an-arduino/
