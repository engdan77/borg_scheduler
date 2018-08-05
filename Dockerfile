FROM python:3.6-alpine

LABEL maintainer="Daniel Engvall"

ENV ROOT_PASSWORD root

RUN apk update	&& apk upgrade && apk add bash && apk add openssh \
		&& sed -i s/#PermitRootLogin.*/PermitRootLogin\ yes/ /etc/ssh/sshd_config \
		&& echo "root:${ROOT_PASSWORD}" | chpasswd \
		&& rm -rf /var/cache/apk/* /tmp/*

COPY entrypoint.sh /
COPY requirements.txt /app
COPY borg_scheduler.py /app

WORKDIR /app
RUN pip install -r requirements.tx

EXPOSE 22

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]