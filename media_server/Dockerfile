FROM python:3.8.6
COPY . ./
RUN apt update && ffmpeg libsm6 libxext6  -y && \
    pip install -r ./requirements.txt && \
    pip install 'h5py<3.0.0'
CMD python WebRTCStreamingServer.py