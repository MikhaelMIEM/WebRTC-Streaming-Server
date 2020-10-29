FROM python:3.8.6-alpine
COPY . ./
ARG PORT=${PORT}
ARG NVR_TOKEN=${NVR_TOKEN}
ARG SSL_KEY=${SSL_KEY}
ARG SSL_CERT=${SSL_CERT}
RUN pip install -r ./requirements.txt
CMD python main.py -p $PORT --nvr-token $NVR_TOKEN --ssl-key $SSL_KEY --ssl-cert $SSL_CERT