FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openssh-server \
    sudo \
    curl \
    systemd \
    systemd-sysv \
    dbus \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash pilot && \
    echo 'pilot ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/pilot && \
    mkdir -p /home/pilot/.ssh && \
    chmod 700 /home/pilot/.ssh && \
    chown pilot:pilot /home/pilot/.ssh

RUN mkdir -p /run/sshd && \
    ssh-keygen -A

# Disable services that conflict with container systemd
RUN systemctl disable getty@tty1.service 2>/dev/null || true && \
    systemctl mask systemd-firstboot.service systemd-udevd.service 2>/dev/null || true

EXPOSE 22

STOPSIGNAL SIGRTMIN+3

CMD ["/sbin/init"]
