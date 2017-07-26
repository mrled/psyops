#!/bin/bash

# If psecretsctl exits with an error, including from ctrl-c, dot-sourcing
# here it prevents it from killing the whole shell
# Then running it in a subshell prevents its variables from polluting my shell
(. /usr/local/bin/psecretsctl unlock)

exec /bin/bash -i
