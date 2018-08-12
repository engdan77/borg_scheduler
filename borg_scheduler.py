#!/usr/bin/env python

"""borg_scheduler: Small project for scheduling Borg backups."""

__author__      = "Daniel Engvall"
__email__       = "daniel@engvalls.eu"

import time
import pexpect
from logzero import logger
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import os
import json

SERVER_SSH_PORT = os.environ.get('SSH_PORT', 22)
BORG_SSH_PORT = os.environ.get('BORG_SSH_PORT', 9922)
SERVER_USERNAME = os.environ.get('SERVER_USERNAME', 'appuser')
BASE_REPO = os.environ.get('BASE_REPO', "/borg")
MINUTES_BETWEEN_BACKUPS = 1440
PEXPECT_TIMEOUT_SECONDS = 21600
COMPRESSION = 'none'
# COMPRESSION = 'lz4'

backup_include_default = []
backup_exclude_default = []

default_backup_list = [{'name': 'server1',
                        'username': 'xxx',
                        'password': 'yyy',
                        'address': '10.1.1.1',
                        'backup_dirs': ['/tmp'],
                        'exclude_dirs': []}]


def exception_listener(event):
    """This function is for catching exception and produce logs in apscheduler.

    :param event:
    :return:
    """
    if event.exception:
        logger.error(f'~job {event.job_id} exception {event.exception}')
    else:
        logger.info(f'~job {event.job_id} executed successfully')


def get_backup_list():
    """Get list of servers to backup from the configuration.

    :return:
    """
    conf_file = f'{BASE_REPO}/borg_scheduler.json'
    if not os.path.isfile(conf_file):
        json.dump(default_backup_list, open(conf_file, 'w'), indent=4)
    with open(conf_file, 'r') as f:
        config = json.load(f)
    return config


def connect_ssh(host_address, ssh_port, borg_ssh_port, ssh_username, password, cmd):
    """Function for connecting to client and process output by using pexpect.

    :param host_address:
    :param ssh_port:
    :param borg_ssh_port:
    :param ssh_username:
    :param password:
    :param cmd:
    :return:
    """
    ssh_cmd = '/usr/bin/ssh %s@%s -p %s -R %s:localhost:%s "%s"' % (ssh_username, host_address, ssh_port, borg_ssh_port, ssh_port, cmd)
    logger.debug(f'~cmd: {ssh_cmd}')
    output = pexpect.run(ssh_cmd, timeout=PEXPECT_TIMEOUT_SECONDS, events={'(?i)Password:': password + '\n', '(?i)yes/no': 'yes\n'})
    logger.debug(f'~output: {output}')
    if 'No such file' in str(output):
        logger.error(f'~no borg in /usr/bin/borg please install before proceeding')
        raise RuntimeError('Borg not installed on client')


def ssh_copy_id(client_username, server_username, host_address, server_ssh_port, client_password):
    """Function for automatically copying the ssh_key to the client for allowing borg to backup over ssh.

    :param client_username:
    :param server_username:
    :param host_address:
    :param server_ssh_port:
    :param client_password:
    :return:
    """
    logger.info('~copying ssh key from client to server')
    copy_key_cmd = f'/usr/bin/ssh {client_username}@{host_address} -R {server_ssh_port}:localhost:22 -t "ssh-copy-id -p{server_ssh_port} {server_username}@localhost"'
    remove_key_cmd = f'/usr/bin/ssh pi@10.1.1.1 "ssh-keygen -f /home/{client_username}/.ssh/known_hosts -R [localhost]:9922"'

    logger.info(f'~running: {remove_key_cmd}')
    output = pexpect.run(remove_key_cmd,
                         events={'(?i)yes/no': 'yes\n', f'(?i){host_address}.*?password:': f'{client_password}\n',
                                 '(?i)localhost.*?password:': 'root\n'}, timeout=5)
    logger.debug(f'~output: {output}')

    logger.info(f'~running: {copy_key_cmd}')
    output = pexpect.run(copy_key_cmd,
                         events={'(?i)yes/no': 'yes\n', f'(?i){host_address}.*?password:': f'{client_password}\n',
                                 '(?i)localhost.*?password:': 'root\n'}, timeout=5)
    logger.debug(f'~output: {output}')

    # if any([word in str(output) for word in ['assword', 'failed', 'ERROR', 't be established']]):
    #     logger.error(f'error or prompt occurred, please run command manually from within the docker container followed by a docker restart: {remove_key_cmd} && {copy_key_cmd}')
    #     raise RuntimeError('run manually')
    return


def prepare_folder(folder):
    """Preparing the folder for storing the backups.

    :param folder:
    :return:
    """
    if not os.path.exists(folder):
        logger.info('~creating folder')
        os.makedirs(folder, exist_ok=True)
        (output, ret) = pexpect.run(f'/usr/bin/borg init -e none {folder}', withexitstatus=1)
        logger.info(f'~ret: {ret}, output: {output}')
        if ret != 0:
            raise RuntimeError('could not create and init borg folder')
    else:
        logger.info(f'~borg folder {folder} exists')


def prepare_client(folder, client_username, server_username, host_address, server_ssh_port, client_password):
    """Function for preparing the client machine before connection.

    :param folder:
    :param client_username:
    :param server_username:
    :param host_address:
    :param server_ssh_port:
    :param client_password:
    :return:
    """
    prepare_folder(folder)
    ssh_copy_id(client_username, server_username, host_address, server_ssh_port, client_password)


def backup(host_name, host_address, backup_include, backup_exclude, client_username, client_password):
    """Backup function used for initiate a backup using borg.

    :param host_name:
    :param host_address:
    :param backup_include:
    :param backup_exclude:
    :param client_username:
    :param client_password:
    :return:
    """
    repository = "ssh://%s@localhost:%s/%s" % (SERVER_USERNAME, BORG_SSH_PORT, f'{BASE_REPO}/{host_name}')
    date = str(time.strftime("%Y-%m-%d_%H:%M:%S"))
    borg_create = "export BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK=yes && /usr/bin/borg create --compression %s -v --stats %s::%s-%s %s %s" % (COMPRESSION, repository, host_name, date, " ".join(backup_include_default + backup_include), " --exclude ".join(backup_exclude_default + backup_exclude))
    borg_prune = "export BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK=yes && /usr/bin/borg prune -v --list --keep-hourly=2 %s --prefix %s --keep-daily 7 --keep-weekly 4 --keep-monthly 6" % (repository, host_name)

    connect_ssh(host_address, SERVER_SSH_PORT, BORG_SSH_PORT, client_username, client_password, borg_create)
    connect_ssh(host_address, SERVER_SSH_PORT, BORG_SSH_PORT, client_username, client_password, borg_prune)


def show_user():
    """
    Function for displaying current user
    :return:
    """
    output = pexpect.run('whoami')
    logger.info(f'~running as user {output}')


if __name__ == '__main__':
    logger.info('~starting borg_scheduler')
    show_user()

    scheduler = BlockingScheduler(timezone='Europe/Stockholm')
    scheduler.add_listener(exception_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    backup_list = get_backup_list()

    for c in backup_list:
        backup_args = (c['name'], c['address'], c['backup_dirs'], c['exclude_dirs'], c['username'], c['password'])
        prepare_client(f'{BASE_REPO}/{c["name"]}', c['username'], SERVER_USERNAME, c['address'], BORG_SSH_PORT,
                       c['password'])

    for c in backup_list:
        backup_args = (c['name'], c['address'], c['backup_dirs'], c['exclude_dirs'], c['username'], c['password'])
        backup(*backup_args)
        scheduler.add_job(backup, 'interval', args=backup_args, minutes=MINUTES_BETWEEN_BACKUPS, id=f'job_{c["name"]}')
    scheduler.start()