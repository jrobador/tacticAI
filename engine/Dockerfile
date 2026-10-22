FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    git cmake build-essential libgl1-mesa-dev libegl1-mesa-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev libsdl2-gfx-dev \
    libboost-all-dev mesa-utils xvfb xauth python3 python3-dev python3-pip ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir numpy opencv-python-headless
COPY . /engine
WORKDIR /engine
RUN rm -f CMakeCache.txt && cmake . && make -j4 && ln -sf libtai_engine.so _tai_engine.so
ENV PYTHONPATH=/engine TAI_DATA_DIR=/engine/data TAI_FONT=/engine/fonts/AlegreyaSansSC-ExtraBold.ttf MESA_GL_VERSION_OVERRIDE=3.2 MESA_GLSL_VERSION_OVERRIDE=150
