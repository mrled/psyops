make_ansi_motd() {
    printf '\033[90m'
    printf '  “You don’t think there’s anyone here, do you?”\n'
    printf '  — \033[3mRorschach\033[23m, in \033[3mBlindsight\033[23m by Peter Watts\n'
    printf '\e[0m'
}

make_ansi_motd
