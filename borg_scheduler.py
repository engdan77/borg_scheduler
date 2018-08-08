import subprocess
import time
import pexpect
from logzero import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import os
import re

BORG_PASSPHRASE = os.environ.get('BORG_PASSPHRASE', 'none')
date = str(time.strftime("%Y-%m-%d_%H:%M:%S"))
SERVER_SSH_PORT = os.environ.get('SSH_PORT', 22)
BORG_SSH_PORT = os.environ.get('BORG_SSH_PORT', 9922)
CLIENT_USERNAME = os.environ.get('CLIENT_USERNAME', 'client_username')
SERVER_USERNAME = os.environ.get('SERVER_USERNAME', 'server_username')
BASE_REPO = os.environ.get('BASE_REPO', "/tmp/borg")

backup_include_default = []
backup_exclude_default = []

# backup_server_all = [
#   ("server1",  "1.1.1.1",  BORG_PASSPHRASE, [ "/var/www", "/var/vmail", "/data/backup_sql"], []),
#   ("server2",  "2.2.2.2",  BORG_PASSPHRASE, [ "/var/www", "/var/vmail", "/data/backup_sql"], []),
#   ("server3",  "3.3.3.3",  BORG_PASSPHRASE, [ "/var/www", "/var/vmail"], []),
#   ("server3",  "4.4.4.4",  BORG_PASSPHRASE, [], []),
# ]


# backup_server_all = [
#     ("server1", "127.0.0.1", 'xxx', ["/Users/edo/tmp/backup_dir"], []),
# ]


# backup_list = [{'name': 'server1',
#                 'username': 'edo',
#                 'address': 'xxx',
#                 'backup_dirs': ['/tmp'],
#                 'exclude_dirs': []}]

backup_list = [{'name': 'server1',
                'username': 'pi',
                'address': '10.1.1.1',
                'backup_dirs': ['/tmp'],
                'exclude_dirs': []}]


def exception_listener(event):
    if event.exception:
        log.error(f'~exception {event.exception}')
    else:
        log.info('~job executed successfully')

def connect_ssh(host_address, ssh_port, borg_ssh_port, ssh_username, cmd):
    ssh_cmd = '/usr/bin/ssh %s@%s -p %s -R %s:localhost:%s "%s"' % (ssh_username, host_address, ssh_port, borg_ssh_port, ssh_port, cmd)
    logger.debug(f'~cmd: {ssh_cmd}')
    output = pexpect.run(ssh_cmd)
    logger.debug(f'~output: {output}')
    if 'No such file' in str(output):
        logger.error(f'~no borg in /usr/bin/borg please install before proceeding')
        raise RuntimeError('Borg not installed on client')
    return


def backup(host_name, host_address, backup_include, backup_exclude, client_username):
    repository = "ssh://%s@localhost:%s/%s" % (SERVER_USERNAME, BORG_SSH_PORT, BASE_REPO + host_name)
    # borg_pass = "export BORG_PASSPHRASE='%s' && " % borg_passphrase
    borg_create = "/usr/bin/borg create --compression lz4 -v --stats %s::%s-%s %s %s" % (repository, host_name, date, " ".join(backup_include_default + backup_include), " --exclude ".join(backup_exclude_default + backup_exclude))
    borg_prune = "/usr/bin/borg prune -v %s --prefix %s --keep-daily=7 --keep-weekly=4 --keep-monthly=6" % (repository, host_name)

    connect_ssh(host_address, SERVER_SSH_PORT, BORG_SSH_PORT, client_username, borg_create)
    connect_ssh(host_address, SERVER_SSH_PORT, BORG_SSH_PORT, client_username, borg_prune)

def ssh_copy_id(client_username, server_username, host_address, server_ssh_port):
    logger.info('~copying ssh key from client to server')
    cmd = f'/usr/bin/ssh {client_username}@{host_address} -R {server_ssh_port}:localhost:22 -t "ssh-copy-id -p{server_ssh_port} {server_username}@localhost"'
    logger.info(f'~running: {cmd}')
    output = pexpect.run(cmd, events={'(?i)yes/no': 'yes\n'}, timeout=5)
    if any([word in str(output) for word in ['assword', 'failed', 'ERROR']]):
        logger.error(f'error or prompt occurred, please run command manually from within the docker container: {cmd}')
        raise RuntimeError('run manually')
    logger.debug(f'~output: {output}')
    return

def prepare_folder(folder):
    if not os.path.exists(folder):
        logger.info('~creating folder')
        os.makedirs(folder, exist_ok=True)
        (output, ret) = pexpect.run(f'/usr/bin/borg init -e none {folder}', withexitstatus=1)
        logger.info(f'~ret: {ret}, output: {output}')
        if ret != 0:
            raise RuntimeError('could not create and init borg folder')
    else:
        logger.info(f'~borg folder {folder} exists')
        return False
    return True

def prepare_client(folder, client_username, server_username, host_address, server_ssh_port):
    folder_prepared = prepare_folder(folder)
    if not folder_prepared:
        logger.info(f'~skipping ssh-copy for {host_address}')
    else:
        ssh_copy_id(client_username, server_username, host_address, server_ssh_port)

if __name__ == '__main__':
    logger.info('~starting borg_scheduler')
    scheduler = BlockingScheduler()
    scheduler.add_listener(exception_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    for c in backup_list:
        backup_args = (c['name'], c['address'], c['backup_dirs'], c['exclude_dirs'], c['username'])
        # logger.info(f'~adding job with {backup_args}')
        prepare_client(f'{BASE_REPO}/{c["name"]}', c['username'], SERVER_USERNAME, c['address'], BORG_SSH_PORT)
        backup(*backup_args)
        scheduler.add_job(backup, 'interval', args=backup_args, seconds=3600, id='job1')
        # backup(host_name, host_address, borg_passphrase, backup_include, backup_exclude)
    scheduler.start()


