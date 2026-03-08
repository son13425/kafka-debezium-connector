FROM confluentinc/cp-kafka-connect:7.7.1

USER root

# Устанавливаем unzip
RUN microdnf install -y unzip && microdnf clean all

# Скачиваем Debezium PostgreSQL Connector с официального сайта
RUN curl -sfL -o /tmp/debezium-postgres.zip \
    https://maven.repository.redhat.com/ga/io/debezium/debezium-connector-postgres/2.5.4.Final-redhat-00001/debezium-connector-postgres-2.5.4.Final-redhat-00001-plugin.zip || \
    curl -sfL -o /tmp/debezium-postgres.zip \
    https://oss.sonatype.org/service/local/artifact/maven/redirect?r=releases\&g=io.debezium\&a=debezium-connector-postgres\&v=2.5.4.Final\&c=plugin\&e=zip || \
    curl -sfL -o /tmp/debezium-postgres.zip \
    https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgres/2.5.4.Final/debezium-connector-postgres-2.5.4.Final-plugin.zip && \
    mkdir -p /usr/share/java/debezium-connector-postgresql && \
    unzip /tmp/debezium-postgres.zip -d /usr/share/java/debezium-connector-postgresql && \
    rm /tmp/debezium-postgres.zip

# Устанавливаем FileStream Connector (если нужен)
RUN mkdir -p /usr/share/java/connect-file && \
    curl -sL https://repo1.maven.org/maven2/org/apache/kafka/connect-file/3.7.1/connect-file-3.7.1.jar \
    -o /usr/share/java/connect-file/connect-file-3.7.1.jar
