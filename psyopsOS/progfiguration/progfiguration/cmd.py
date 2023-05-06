"""Command execution"""

import io
import select
import subprocess
import sys

from progfiguration import logger


def run(cmd: str | list, print_output=True, log_output=False, check=True, *args, **kwargs) -> subprocess.Popen:
    """Run a command, with superpowers

    * cmd: The command to run. If a string, it will be passed to a shell.
    * print_output: Print the command's stdout/stderr in to the controlling terminal's stdout/stderr in real time.
        stdout/stderr is always captured and returned, whether this is True or False (superpowers).
        The .stdout and .stderr properties are always strings, not bytes
        (which is required because we must use universal_newlines=True).
        * <https://gist.github.com/nawatts/e2cdca610463200c12eac2a14efc0bfb>
        * <https://stackoverflow.com/questions/4417546/constantly-print-subprocess-output-while-process-is-running>
    * log_output: Log the command's stdout/stderr in a single log message (each) after the command completes.
    * check: Raise an exception if the command returns a non-zero exit code.
        Unlike subprocess.run, this is True by default.
    * *args, **kwargs: Passed to subprocess.Popen
        Do not pass the following arguments, as they are used internally:
        * shell: Determined automatically based on the type of cmd
        * stdout: Always subprocess.PIPE
        * stderr: Always subprocess.PIPE
        * universal_newlines: Always True
        * bufsize: Always 1

    The Popen object is always returned.
    """
    shell = isinstance(cmd, str)

    logger.debug(f"Running command: {cmd}")
    process = subprocess.Popen(
        cmd,
        shell=shell,
        bufsize=1,  # Output is line buffered, required to print output in real time
        universal_newlines=True,  # Required for line buffering
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        *args,
        **kwargs,
    )

    stdoutbuf = io.StringIO()
    stderrbuf = io.StringIO()

    stdout_fileno = process.stdout.fileno()
    stderr_fileno = process.stderr.fileno()

    # This returns None until the process terminates
    while process.poll() is None:

        # select() waits until there is data to read (or an "exceptional case") on any of the streams
        readready, writeready, exceptionready = select.select(
            [process.stdout, process.stderr],
            [],
            [process.stdout, process.stderr],
            0.5,
        )

        # Check if what is ready is a stream, and if so, which stream.
        # Copy the stream to the buffer so we can use it,
        # and print it to stdout/stderr in real time if print_output is True.
        for stream in readready:
            if stream.fileno() == stdout_fileno:
                line = process.stdout.readline()
                stdoutbuf.write(line)
                if print_output:
                    sys.stdout.write(line)
            elif stream.fileno() == stderr_fileno:
                line = process.stderr.readline()
                stderrbuf.write(line)
                if print_output:
                    sys.stderr.write(line)
            else:
                raise Exception(f"Unknown file descriptor in select result. Fileno: {stream.fileno()}")

        # If what is ready is an exceptional situation, blow up I guess;
        # I haven't encountered this and this should probably do something more sophisticated.
        for stream in exceptionready:
            if stream.fileno() == stdout_fileno:
                raise Exception("Exception on stdout")
            elif stream.fileno() == stderr_fileno:
                raise Exception("Exception on stderr")
            else:
                raise Exception(f"Unknown exception in select result. Fileno: {stream.fileno()}")

    # We'd like to just seek(0) on the stdout/stderr buffers, but "underlying stream is not seekable",
    # So we create new buffers above, write to them line by line, and replace the old ones with these.
    process.stdout.close()
    stdoutbuf.seek(0)
    process.stdout = stdoutbuf
    process.stderr.close()
    stderrbuf.seek(0)
    process.stderr = stderrbuf

    if check and process.returncode != 0:
        msg = f"Command failed with exit code {process.returncode}: {cmd}"
        logger.error(msg)
        logger.info(f"stdout: {process.stdout.getvalue()}")
        logger.info(f"stderr: {process.stderr.getvalue()}")
        raise Exception(msg)

    logger.info(f"Command completed with return code {process.returncode}: {cmd}")

    # The user may have already seen the output in std out/err,
    # but logging it here also logs it to syslog (if configured).
    if log_output:
        # Note that .getvalue() is not (always?) available on normal Popen stdout/stderr,
        # but it is available on our StringIO objects.
        # .getvalue() doesn't change the seek position.
        logger.info(f"stdout: {process.stdout.getvalue()}")
        logger.info(f"stderr: {process.stderr.getvalue()}")

    return process
