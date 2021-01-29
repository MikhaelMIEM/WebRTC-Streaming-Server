import logging
import argparse
import asyncio
import json
import ssl
import os
from urllib.parse import urlparse

from aiohttp import web, ClientSession
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
import aiohttp_jinja2 as aiojinja2
import jinja2

# nn
from tensorflow.keras.applications.resnet50 import ResNet50
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet50 import preprocess_input, decode_predictions
from tensorflow.keras.utils import get_file
from ONVIFCameraControl import ONVIFCameraControl
import numpy as np
from datetime import datetime
import keras
from PIL import ImageDraw, Image, ImageFile
from urllib.parse import urlparse
from time import time
import requests
import io

model = ResNet50(weights='imagenet')

cam_class = {}
cam_onvif = {}
# nn


args = None
pcs = set()

cors_headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': "Origin, X-Requested-With, Content-Type, Accept"
}


def get_arguments():
    parser = argparse.ArgumentParser(description="WebRTC streaming server")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--host", default="0.0.0.0", help="Host for server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8181, help="Server port (default: 8181)")
    parser.add_argument("--nvr-token", help="NVR api token", required=True)
    parser.add_argument("--verbose", "-v", action="count")
    return parser.parse_args()


class VideoTransformTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, track, cam_id):
        super().__init__()
        self.track = track
        self.timestamp_sec = -1
        self.last_text = ''
        self.cam_id = cam_id

    async def recv(self):
        global cam_class
        frame = await self.track.recv()
        if datetime.now().second != self.timestamp_sec:
            im = frame.to_image()
            im = im.resize((224, 224))
            x = image.img_to_array(im)
            x = np.expand_dims(x, axis=0)
            x = preprocess_input(x)
            preds = model.predict(x)
            self.timestamp_sec = datetime.now().second
            self.last_text = '   '.join((i[1] for i in decode_predictions(preds, top=3)[0]))
            cam_class[self.cam_id] = self.last_text
        # frame = frame.reformat(width=320, height=240)
        return frame


async def offer(request):
    request_url = request.match_info['stream']
    streams = await get_streams(args.nvr_token)

    if request_url not in streams:
        raise web.HTTPNotFound(text='No rtsp source related to this url')

    play_from = streams[request_url]
    if not play_from:
        raise web.HTTPBadGateway(text='NVR response with cam rtsp link is empty. Contact NVR admins to fix it')

    url = urlparse(play_from)
    if url.scheme == 'rtsp':
        await check_rtsp_availability(play_from, timeout=10)

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print("ICE connection state is %s" % pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    player = MediaPlayer(play_from)

    await pc.setRemoteDescription(offer)
    for t in pc.getTransceivers():
        if t.kind == "audio" and player.audio:
            pc.addTrack(player.audio)
        elif t.kind == "video" and player.video:
            track = VideoTransformTrack(player.video, request_url)
            pc.addTrack(track)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        headers=cors_headers,
        text=json.dumps({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
    )


async def js_cors_preflight(request):
    headers = cors_headers
    return web.Response(headers=headers, text="ok")


async def get_cams(nvr_token):
    headers = {"key": nvr_token}

    async with ClientSession() as session:
        async with session.get('https://nvr.miem.hse.ru/api/sources/',
                               headers=headers) as resp:
            text = await resp.text()
            cams = json.loads(text)
    return cams


async def get_streams(nvr_token):
    cams = await get_cams(nvr_token)
    streams = {
        str(cam['id']): cam['rtsp']
        for cam in cams
    }
    return streams

async def check_rtsp_availability(rtsp_link, timeout):
    """
    This function needed because some rtsp links requires
    to authenticate and pyav lib may freeze in such cases.
    If some rtsp link require authentication contact NVR admins to replace it with working link.
    """
    url = urlparse(rtsp_link)
    ip = url.hostname
    port = url.port if url.port else 554
    reader = None
    writer = None

    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        is_available = bool(reader) and bool(writer)
    except asyncio.TimeoutError:
        raise web.HTTPBadGateway(text='Can not establish connection with rtsp media source')
    except OSError:
        raise web.HTTPBadGateway(text='Can not establish connection with rtsp media source')
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()

    if not is_available:
        raise web.HTTPBadGateway(text='Can not establish connection with rtsp media source')

    # message = f'DESCRIBE {rtsp_link} RTSP/1.0\nCSeq: 1\n\n'
    # writer.write(message.encode())
    # await writer.drain()
    #
    # data = await reader.read(1000)
    # writer.close()
    # await writer.wait_closed()
    #
    # describe_reply = data.decode().split()
    # if describe_reply[1] == '401':
    #     raise web.HTTPBadGateway(text='rtsp stream require authentication')


async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


@aiojinja2.template('index.html')
async def index(request):
    cams = await get_cams(args.nvr_token)
    return {'cams': cams}


async def classify(request):
    cam_id = request.match_info['stream']
    cams = await get_cams(args.nvr_token)
    cam_info = [cam for cam in cams if str(cam['id']) == cam_id]
    if not cam_info:
        raise web.HTTPNotFound(text='No rtsp source related to this url')
    cam_info = cam_info[0]
    play_from = cam_info['rtsp']

    if cam_id not in cam_onvif:
        cam_onvif[cam_id] = ONVIFCameraControl((cam_info['ip'], int(cam_info['port'])), 'admin', 'Supervisor')
    img_url = cam_onvif[cam_id].get_snapshot_uri()
    img_path = '/' + str(time())
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    session = requests.Session()
    session.auth = ('admin', 'Supervisor')
    auth = session.post(img_url)
    response = session.get(img_url)
    im = None
    with open(img_path, 'wb') as file:
        file.write(response.content)
        b = BytesIO()
        file.seek(15, 0)

        b.write(file.read())

        im = Image.open(b)
        im.load()
    im = im.resize((224, 224))
    # x = image.img_to_array(im)
    # img_path = get_file(str(time()), origin=img_url)
    # img = image.load_img(img_path, target_size=(224, 224))
    x = image.img_to_array(img)
    x = keras.preprocessing.image.img_to_array(img)
    x = np.expand_dims(x, axis=0)
    x = preprocess_input(x)
    preds = model.predict(x)
    text = str([i[1] for i in decode_predictions(preds, top=3)[0]])
    return web.Response(headers=cors_headers, text=text)


async def get_link(request):
    request_url = request.match_info['stream']
    streams = await get_streams(args.nvr_token)

    if request_url not in streams:
        raise web.HTTPNotFound(text='No rtsp source related to this url')

    play_from = streams[request_url]
    if not play_from:
        raise web.HTTPBadGateway(text='NVR response with cam rtsp link is empty. Contact NVR admins to fix it')

    return web.Response(headers=cors_headers, text=play_from)



if __name__ == "__main__":
    args = get_arguments()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    # media = web.Application()
    # media.router.add_post("/{stream}", offer)
    # media.router.add_options("/{stream}", js_cors_preflight)

    classifier = web.Application()
    classifier.router.add_post("/{stream}", classify)
    classifier.router.add_options("/{stream}", js_cors_preflight)

    link_getter = web.Application()
    link_getter.router.add_post("/{stream}", get_link)
    link_getter.router.add_options("/{stream}", js_cors_preflight)

    app = web.Application()
    # app.add_subapp("/media/", media)
    app.add_subapp("/classify/", classifier)
    app.add_subapp("/link/", link_getter)
    app.on_shutdown.append(on_shutdown)

    aiojinja2.setup(app, loader=jinja2.FileSystemLoader('/templates/'))
    app.router.add_get('/', index)
    app.router.add_static('/static/', path='/static')

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
