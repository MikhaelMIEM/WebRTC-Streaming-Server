FROM python:3.8.6
COPY . ./
RUN apt update && apt install libgl1-mesa-glx && \
    pip install -r ./requirements.txt && \
    pip install 'h5py<3.0.0'
CMD python WebRTCStreamingServer.py