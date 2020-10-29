FROM python:3.8.6-alpine
COPY . ./
RUN pip install -r ./requirements.txt
CMD python main.py -p ${PORT} --nvr-token ${NVR_TOKEN} --ssl-key ${SSL_KEY} --ssl-cert ${SSL_CERT}