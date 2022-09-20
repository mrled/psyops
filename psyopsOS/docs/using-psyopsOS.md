# Using psyopsOS

- [Updating the operating system](./operating-system-update.md) is a manual process
- To apply the latest progfiguration
    - `apk update`
    - `apk upgrade progfiguration`
    - `. /etc/psyopsOS/psyops-secret.env`
    - `psyopsOS-progfiguration --syslog-exception apply "$PSYOPSOS_NODENAME"`
