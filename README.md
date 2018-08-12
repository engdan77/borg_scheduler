**Borg Scheduler**

Small dockerize project for scheduling Borg backups

1. Update ssh_config to include your hosts
2. Run following `docker build --build-arg UID=1004 -t borg_scheduler . && docker run -v /local_directory/borg_repo:/borg --name borg_scheduler borg_scheduler` where you specify where you'd like the backups to be stored, replace UID with the proper id if you like to share with other systems.
3. Update configuration.json within your borg_repo directory
4. Run `docker restart borg_scheduler`


