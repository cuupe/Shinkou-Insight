ARG BASE_IMAGE_REGISTRY=docker.io
FROM ${BASE_IMAGE_REGISTRY}/library/maven:3.9-eclipse-temurin-21 AS build
ARG MAVEN_MIRROR_URL=https://repo.maven.apache.org/maven2
WORKDIR /build
COPY docker-settings.xml .
COPY pom.xml .
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -ntp -s docker-settings.xml dependency:go-offline
COPY src ./src
RUN --mount=type=cache,target=/root/.m2 \
    mvn -B -ntp -s docker-settings.xml -DskipTests package

FROM ${BASE_IMAGE_REGISTRY}/library/eclipse-temurin:21-jre-jammy
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 shinkou
WORKDIR /app
COPY --from=build /build/target/backend-*.jar ./app.jar
USER shinkou
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=12 \
    CMD curl --fail --silent http://127.0.0.1:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
