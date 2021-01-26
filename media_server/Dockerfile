FROM python:3.8.6
COPY . ./
RUN pip install -r ./requirements.txt && \
    pip install 'h5py<3.0.0'
CMD python WebRTCStreamingServer.py