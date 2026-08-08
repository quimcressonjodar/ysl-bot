FROM eclipse-temurin:21-jre

ARG LAVALINK_VERSION=4.2.2
WORKDIR /opt/lavalink

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL -o Lavalink.jar \
       "https://github.com/lavalink-devs/Lavalink/releases/download/${LAVALINK_VERSION}/Lavalink.jar"

COPY application.yml .

EXPOSE 2333
CMD ["java", "-Xms128M", "-Xmx512M", "-jar", "Lavalink.jar"]