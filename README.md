**Borg Scheduler**

Small dockerize project for scheduling Borg backups

1. Update ssh_config to include your hosts
2. Run following `docker build -t borg_scheduler . && docker run -p 2222:22 -v /local_directory/borg_repo:/borg --name borg_scheduler borg_scheduler` where you specify where you'd like the backups to be stored
3. Run `docker start borg_scheduler`
4. Update configuration.json within your borg_repo directory
5. Run `docker restart borg_scheduler`


