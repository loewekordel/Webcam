import picamera2  # camera module for RPi camera
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, MJPEGEncoder
from picamera2.outputs import FileOutput, CircularOutput
import io

import subprocess
from flask import Flask, render_template, Response
from flask_restful import Resource, Api, reqparse, abort
from datetime import datetime
from threading import Condition
import time
from pathlib import Path
import logging

logger = logging.getlogger(__name__)

from libcamera import Transform

OUTPUT_DIR = Path(__file__).parent / "static"
OUTPUT_DIR_VIDEO = OUTPUT_DIR / "video"
OUTPUT_DIR_PICTURES = OUTPUT_DIR / "pictures"
OUTPUT_DIR_SOUND = OUTPUT_DIR / "sound"

app = Flask(__name__, template_folder="template", static_url_path="/static")
api = Api(app)

encoder = H264Encoder()
output = CircularOutput()


class Camera:
    def __init__(self):
        self.camera = picamera2.Picamera2()
        self.camera.configure(
            self.camera.create_video_configuration(main={"size": (800, 600)})
        )
        self.still_config = self.camera.create_still_configuration()
        self.encoder = MJPEGEncoder(10000000)
        self.streamOut = StreamingOutput()
        self.streamOut2 = FileOutput(self.streamOut)
        self.encoder.output = [self.streamOut2]
        self.output_dir_video = OUTPUT_DIR_VIDEO
        self.output_dir_pictures = OUTPUT_DIR_PICTURES

        self.camera.start_encoder(self.encoder)
        self.camera.start_recording(encoder, output)

    def get_frame(self):
        self.camera.start()
        with self.streamOut.condition:
            self.streamOut.condition.wait()
            self.frame = self.streamOut.frame
        return self.frame

    def VideoSnap(self):
        logger.info("Snap")
        timestamp = datetime.now().isoformat("_", "seconds")
        logger.info(timestamp)
        self.still_config = self.camera.create_still_configuration()
        self.file_output = self.output_dir_pictures / f"snap_{timestamp}.jpg"
        time.sleep(1)
        self.job = self.camera.switch_mode_and_capture_file(
            self.still_config, self.file_output, wait=False
        )
        self.metadata = self.camera.wait(self.job)


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


# defines the function that generates our frames
camera = Camera()


# capture_config = camera.create_still_configuration()
def genFrames():
    while True:
        frame = camera.get_frame()
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n\r\n")


# defines the route that will access the video feed and call the feed function
class VideoFeed(Resource):
    def get(self):
        return Response(
            genFrames(), mimetype="multipart/x-mixed-replace; boundary=frame"
        )


# Timestamp
def show_time():
    """Show current date time in text format"""
    rightNow = datetime.now()
    logger.info(rightNow)
    currentTime = rightNow.strftime("%d-%m-%Y_%H:%M:%S")
    logger.info("date and time =", currentTime)

    return currentTime


@app.route("/")
def index():
    """Video streaming home page."""

    return render_template("index.html")


@app.route("/home", methods=["GET", "POST"])
def home_func():
    """Video streaming home page."""

    return render_template("index.html")


@app.route("/info.html")
def info():
    """Info Pane"""

    return render_template("info.html")


@app.route("/startRec.html")
def startRec():
    """Start Recording Pane"""
    logger.info("Video Record")
    basename = show_time()
    directory = basename
    output.fileoutput = OUTPUT_DIR_VIDEO / f"{directory}.h264"
    output.start()

    return render_template("startRec.html")


@app.route("/stopRec.html")
def stopRec():
    """Stop Recording Pane"""
    logger.info("Video Stop")
    output.stop()

    return render_template("stopRec.html")


@app.route("/srecord.html")
def srecord():
    """Sound Record Pane"""
    logger.info("Recording Sound")
    timestamp = datetime.now().isoformat("_", "seconds")
    logger.info(timestamp)
    subprocess.Popen(
        f'arecord -D dmic_sv -d 30 -f S32_LE {OUTPUT_DIR_SOUND}/cam_$(date "+%b-%d-%y-%I:%M:%S-%p").wav -c 2',
        shell=True,
    )

    return render_template("srecord.html")


@app.route("/snap.html")
def snap():
    """Snap Pane"""
    logger.info("Taking a photo")
    camera.VideoSnap()

    return render_template("snap.html")


api.add_resource(VideoFeed, "/cam")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    OUTPUT_DIR_VIDEO.mkdir(exist_ok=True, parents=True)
    OUTPUT_DIR_PICTURES.mkdir(exist_ok=True, parents=True)
    OUTPUT_DIR_SOUND.mkdir(exist_ok=True, parents=True)
    app.run(debug=False, host="0.0.0.0", port=5000)
