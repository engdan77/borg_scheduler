import subprocess
import time
from pexpect import pxssh
from logzero import logger

BORG_PASSPHRASE = "xxx"
date = str(time.strftime("%Y-%m-%d_%H:%M:%S"))
ssh_port = 22
borg_ssh_port = 9923
ssh_username = "edo"
borg_username = "edo"
base_repository = "/home/edo/tmp/borg/"

backup_include_default = []
backup_exclude_default = []

'''
backup_server_all = [
  ("server1",  "1.1.1.1",  BORG_PASSPHRASE, [ "/var/www", "/var/vmail", "/data/backup_sql"], []),
  ("server2",  "2.2.2.2",  BORG_PASSPHRASE, [ "/var/www", "/var/vmail", "/data/backup_sql"], []),
  ("server3",  "3.3.3.3",  BORG_PASSPHRASE, [ "/var/www", "/var/vmail"], []),
  ("server3",  "4.4.4.4",  BORG_PASSPHRASE, [], []),
]
'''
backup_server_all = [
    ("server1", "127.0.0.1", BORG_PASSPHRASE, ["/home/edo/tmp/backup_dir"], []),
]


def shell_cmd(cmd):
    logger.info("\nCMD: \n" + cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (output, err) = proc.communicate()
    if output is not None:
        if len(output) > 0:
            logger.info(output)
    if err is not None:
        if len(err) > 0:
            logger.info(err)
    return output


def connect_ssh(host_address, ssh_port, borg_ssh_port, ssh_username, cmd):
    ssh_cmd = '/usr/bin/ssh %s@%s -p %s -R %s:localhost:%s "%s"' % (ssh_username, host_address, ssh_port, borg_ssh_port, ssh_port, cmd)
    shell_cmd(ssh_cmd)


def backup(host_name, host_address, borg_passphrase, backup_include, backup_exclude):
    repository = "ssh://%s@localhost:%s/%s" % (borg_username, borg_ssh_port, base_repository + host_name)
    borg_pass = "export BORG_PASSPHRASE='%s' && " % borg_passphrase
    borg_create = "borg create --compression lz4 -v --stats %s::%s-%s %s %s" % (repository, host_name, date, " ".join(backup_include_default + backup_include), " --exclude ".join(backup_exclude_default + backup_exclude))
    borg_prune = "borg prune -v %s --prefix %s --keep-daily=7 --keep-weekly=4 --keep-monthly=6" % (repository, host_name)

    connect_ssh(host_address, ssh_port, borg_ssh_port, ssh_username, borg_pass + borg_create)
    connect_ssh(host_address, ssh_port, borg_ssh_port, ssh_username, borg_pass + borg_prune)

if __name__ == '__main__':
    for host_name, host_address, borg_passphrase, backup_include, backup_exclude in backup_server_all:
        backup(host_name, host_address, borg_passphrase, backup_include, backup_exclude)
