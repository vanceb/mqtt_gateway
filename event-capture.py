import paho.mqtt.client as mqtt
import urllib.request as request
import json
import os
import glob
import shutil
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
        if not grabbing:
            # Block waiting for an incoming message
            print("Blocking waiting for a message")
            msg = in_q.get()
            # We got a message so start a new event
            now = datetime.datetime.now()
            print("Frame Grabber, got Message: " + str(msg))
            print(msg["logtime"])
            last_event_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(msg["logtime"], "%Y-%m-%dT%H:%M:%S.%f")))
            end_grab = last_event_time + datetime.timedelta(seconds=GRAB_FOR_SECS)
            print("End of event: " + str(end_grab))
            grabbing = True
            next_grab = now
            dt = msg["logtime"].split('T')
            event_dir =  EVENT_DIR + '/' + '/'.join(dt)
            os.makedirs(event_dir, exist_ok=True)
        else:
            now = datetime.datetime.now()
            # Check to see whether we have another message during the event
            if not in_q.empty():
                # We are already handling an event so extend the event time
                msg = in_q.get()
                print("Frame Grabber, got Message: " + str(msg))
                last_event_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(msg["logtime"], "%Y-%m-%dT%H:%M:%S.%f")))
                end_grab = last_event_time + datetime.timedelta(seconds=GRAB_FOR_SECS)
                print("End of event extended: " + str(end_grab))

        # Should we grab the next frame?
        if grabbing and now > next_grab:
            # we need to get a frame
            base_filename = event_dir + "/" + str(event_seq).zfill(4)
            print("Requesting: " + base_filename + ".jpg")
            request.urlretrieve(IMAGE_URL, base_filename + ".jpg")
            print("Got it!")
            next_grab = next_grab + frame_interval
            event_seq += 1

        # Check to see whether we should end the event
        if grabbing == True and now > end_grab:
            print("End of event capture")
            # Finished grabbing the event
            # Signal to make video thread to do its stuff
            out_q.put(event_dir)
            # Reset
            grabbing = False
            event_seq = 0
            event_dir = None

def make_video(in_q):
    while True:
        # Block waiting for an incoming message
        msg = in_q.get()
        print("Got path: " + str(msg))

        # Convert video
        result = call(VIDEO_CONVERT, cwd=msg)
        if result == 0:
            # The conversion was successful so move the video and remove the jpgs
            pp = str(msg).split('/')
            newpath = '/'.join(pp[:-1])
            vidfile = newpath + '/' + pp[-1].split('.')[0] + ".mp4"
            print("Moving video event file to " + vidfile)
            os.rename(msg + "/event.mp4", vidfile)
            shutil.rmtree(msg)

            #files = glob.glob(msg + "/*.jpg")
            #print("Removing: " + str(files))
            #for file in files:
            #    os.remove(file)



if __name__ == "__main__":
    q1 = Queue()
    q2 = Queue()
    t1 = Thread(target=frame_grabber, args=(q1,q2, IMAGE_URL,))
    t2 = Thread(target=mqtt_listner, args=(q1,))
    t3 = Thread(target=make_video, args=(q2,))
    t1.start()
    t2.start()
    t3.start()

