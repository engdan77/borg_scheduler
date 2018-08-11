FROM python:3.6-alpine

LABEL maintainer="Daniel Engvall"

ENV ROOT_PASSWORD root

# Update according to local environment or use --build-arg UID=xxx at build
ENV UID 1004
ENV GID 100

RUN adduser -u ${UID} -D -g '' appuser

RUN apk update	&& apk upgrade && apk add bash && apk add openssh \
		&& sed -i s/#PermitRootLogin.*/PermitRootLogin\ yes/ /etc/ssh/sshd_config \
		&& echo "root:${ROOT_PASSWORD}" | chpasswd \
		&& rm -rf /var/cache/apk/* /tmp/*

RUN apk add supervisor

RUN mkdir /etc/supervisor.d; \
    mkdir /etc/init-scripts; \
    mkdir /etc/settings.d

RUN apk add borgbackup

COPY supervisord.conf /etc/supervisord.conf
COPY sshd.conf /etc/supervisor.d/sshd.conf
COPY borg_scheduler.conf /etc/supervisor.d/borg_scheduler.conf

COPY entrypoint.sh /
COPY requirements.txt /app/
COPY borg_scheduler.py /app/
RUN chown -R appuser /app

WORKDIR /app
RUN pip install -r requirements.txt

RUN mkdir -p /borg
RUN chown -R appuser /borg

RUN echo appuser:root | chpasswd

# USER appuser
COPY ssh_config /home/appuser/.ssh/config
RUN chown -R appuser /home/appuser

EXPOSE 22

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]