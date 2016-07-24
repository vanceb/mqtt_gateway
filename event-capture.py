import paho.mqtt.client as mqtt
import urllib.request as request
import json
import os
import glob
import datetime
import time
from queue import Queue
from threading import Thread
from subprocess import call

IMAGE_URL = "http://192.168.37.21/oneshotimage.jpg"
MQTT_HOST = "localhost"
MQTT_PORT = 1883
EVENT_DIR = "/cctv/events"
GRAB_FOR_SECS = 30
FPS = 1
VIDEO_CONVERT = ["avconv", "-r", "1", "-i", "%4d.jpg", "event.mp4"]


def on_connect(client, userdata, rc):
    print("Connected!")
    # Subscribe to any mqtt channels here
    client.subscribe("GateGuard/Event")


def on_message(client, userdata, msg):
    print("Message received")
    print(str(msg.payload))
    # Parse the message as json
    json_msg = json.loads(msg.payload.decode("utf-8"))
    userdata.put(json_msg)

def mqtt_listner(out_q):
    client = mqtt.Client(userdata = out_q)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever()

def frame_grabber(in_q, out_q, frameURL):
    print("Frame Grabber started: " + frameURL)
    event_dir = None
    event_seq = 0
    grabbing = False
    next_grab = datetime.datetime.now()
    end_grab = next_grab
    frame_interval = datetime.timedelta(seconds=1/FPS)
    while True:
        now = datetime.datetime.now()
        if not in_q.empty():
            msg = in_q.get()
            print("Frame Grabber, got Message: " + str(msg))
            print(msg["logtime"])
            last_event_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(msg["logtime"], "%Y-%m-%dT%H:%M:%S.%f")))
            end_grab = last_event_time + datetime.timedelta(seconds=GRAB_FOR_SECS)
            if not grabbing:
                grabbing = True
                next_grab = now
                dt = msg["logtime"].split('T')
                event_dir =  EVENT_DIR + '/' + '/'.join(dt)
                os.makedirs(event_dir, exist_ok=True)
        if now < end_grab and now >= next_grab:
            # we need to get a frame
            base_filename = event_dir + "/" + str(event_seq).zfill(4)
            request.urlretrieve(IMAGE_URL, base_filename + ".jpg")
            next_grab = next_grab + frame_interval
            event_seq += 1

        if grabbing == True and now > end_grab:
            # Finished grabbing the event
            # Signal to make video thread to do its stuff
            out_q.put(event_dir)
            # Reset
            grabbing = False
            event_seq = 0
            event_dir = None

def make_video(in_q):
    while True:
        if not in_q.empty():
            msg = in_q.get()
            print("Got path: " + str(msg))

            result = call(VIDEO_CONVERT, cwd=msg)
            if result == 0:
                # The conversion was successful so remove the jpgs
                files = glob.glob(msg + "/*.jpg")
                print("Removing: " + str(files))
                for file in files:
                    os.remove(file)

        time.sleep(1)


if __name__ == "__main__":
    q1 = Queue()
    q2 = Queue()
    t1 = Thread(target=frame_grabber, args=(q1,q2, IMAGE_URL,))
    t2 = Thread(target=mqtt_listner, args=(q1,))
    t3 = Thread(target=make_video, args=(q2,))
    t1.start()
    t2.start()
    t3.start()

