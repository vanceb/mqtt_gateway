Build
=====

    sudo docker build -t vanceb/datalogger .

Run
===

    sudo docker run -d \
                    --restart=always \
                    --name datalogger \
                    --device=/dev/ttyUSB0:/dev/ttyUSB0 \
                    --volume=/data/weather:/data \
                    --link weather-logger:weather-logger \
                    vanceb/datalogger

Needs
=====

https://hub.docker.com/r/ansi/mosquitto/

## Get it
    sudo docker pull ansi/mosquitto

## Run it
    sudo docker run -d \
                    -p 1883:1883 \
                    --name mosquitto \
                    --restart=always \
                    ansi/mosquitto
