FROM drachtio/drachtio-freeswitch-mrf:latest

USER root
# drachtio-freeswitch-mrf is based on Debian. 
# FreeSWITCH is installed in /usr/local/freeswitch.
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    curl \
    libwebsockets-dev \
    libjansson-dev \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/amigniter/mod_audio_stream/releases/download/v1.0.3/mod-audio-stream_1.0.3_amd64.deb \
    && dpkg-deb -x mod-audio-stream_1.0.3_amd64.deb /tmp/extracted \
    && cp /tmp/extracted/usr/lib/freeswitch/mod/mod_audio_stream.so /usr/local/freeswitch/mod/ \
    && rm -rf /tmp/extracted mod-audio-stream_1.0.3_amd64.deb

# Copy configuration to drachtio's conf path
# Actually drachtio-freeswitch-mrf allows overriding /usr/local/freeswitch/conf
# But docker-compose volume maps it to /etc/freeswitch. We will symlink it or just map it in docker-compose.
# Expose RTP ports
EXPOSE 16384-16484/udp

# Set up the run command
CMD ["freeswitch", "-nonat", "-nf", "-c"]
