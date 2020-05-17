#!/usr/bin/env python3

import argparse
import logging
import logging.handlers
import sys

import gpiozero


def initlogging():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    conshandl = logging.StreamHandler()
    conshandl.setFormatter(
        logging.Formatter('[Console] %(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    conshandl.setLevel(logging.INFO)
    logger.addHandler(conshandl)
    return logger


LOGGER = initlogging()


def main(args):
    parser = argparse.ArgumentParser(
        "Log the temperature of the Raspberry Pi to a remote syslog server")
    parser.add_argument("--syslog-server")
    parser.add_argument("--syslog-port", default=514, type=int)
    parser.add_argument("--local-syslog", action="store_true")
    parsed = parser.parse_args(args[1:])
    if parsed.syslog_server:
        udpsyslhandl = logging.handlers.SysLogHandler(
            address=(parsed.syslog_server, parsed.syslog_port))
        udpsyslhandl.setFormatter(
            logging.Formatter('%(message)s'))
        udpsyslhandl.setLevel(logging.INFO)
        LOGGER.addHandler(udpsyslhandl)
    if parsed.local_syslog:
        locsyslhandl = logging.handlers.SysLogHandler(address='/dev/log')
        locsyslhandl.setFormatter(
            logging.Formatter('%(message)s'))
        locsyslhandl.setLevel(logging.INFO)
        LOGGER.addHandler(locsyslhandl)
    cputemp = gpiozero.CPUTemperature().temperature
    LOGGER.info(f"Raspberry Pi CPU temperature: {cputemp}C")


if __name__ == '__main__':
    main(sys.argv)
