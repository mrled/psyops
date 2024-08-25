#!/usr/bin/env python3

"""A post-receive hook for the me.micahrl.com CI system.

This script should be deployed from the psyops repo to the CI host,
which serves at Git server and builds the site on every push.
It is outside of the site's repo,
so that the site's repo can't break the CI system so badly that it requires manual intervention.

The script creates a separate build directory for each commit, runs the build
process, and if successful, queues the commit for deployment. It also handles
cleanup of build directories and logging of all major events to a file.
Before exiting, it sends an email with the build log or saves an error log if email fails.

It relies on a few existing items on the filesystem:
- A queue directory for build jobs
- A build directory for storing build artifacts
- A deploy lock file to ensure only one deployment is running at a time

It also assumes that the repository has a Makefile with the following targets:
- micahrlci-build: Perform tasks that can be done in parallel with other builds
- micahrlci-deploy: Perform deployment tasks that should only be done for one build at a time

The --action flag can be used to run only a specific part of the build process.
'all' is the default, for normal script operation,
but the other steps can be run individually for debugging or testing.
- checkout: Check out the repository at the given commit hash
- container: Build the micahrlci container for the given commit hash
- decrypt: Decrypt the secrets directory in the micahrlci checkout
- build: Run the micahrlci-build target for the given commit hash
- deploy: Run the micahrlci-deploy target for the given commit hash
- all: Run all of the above (default)

"""


import argparse
import atexit
import fcntl
import io
import logging
import os
import pdb
import select
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
import traceback
from typing import Any, Optional


logger: logging.Logger


def idb_excepthook(type, value, tb):
    """Call an interactive debugger in post-mortem mode

    If you do "sys.excepthook = idb_excepthook", then an interactive debugger
    will be spawned at an unhandled exception
    """
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        traceback.print_exception(type, value, tb)
        print
        pdb.pm()


def setup_logging(log_dir: Path, commit_hash: str) -> tuple[logging.Logger, Path]:
    """Set up logging to a file and stdout."""
    logger = logging.getLogger("BuildDeploySystem")
    logger.setLevel(logging.INFO)

    # File handler
    log_file = log_dir / f"{commit_hash}.log"
    if log_file.exists():
        log_file.unlink()
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_formatter = logging.Formatter("MICAHRLCI %(levelname)s - %(message)s")
    stdout_handler.setFormatter(stdout_formatter)
    logger.addHandler(stdout_handler)

    return logger, log_file


class MagicPopen(subprocess.Popen):
    """A subprocess.Popen with superpowers"""

    stdout: io.StringIO
    stderr: io.StringIO


def magicrun(
    cmd: str | list, print_output=True, log_output=False, check=True, *args, **kwargs
) -> MagicPopen:
    """Run a command, with superpowers

    See <https://me.micahrl.com/blog/magicrun/>
    for more documentation and a heavily commented version.
    """
    shell = isinstance(cmd, str)

    msg = f"Running command: {cmd}"
    if kwargs.get("cwd"):
        msg += f" from directory {kwargs['cwd']}"
    logger.info(msg)

    process = subprocess.Popen(  # type: ignore
        cmd,
        shell=shell,
        bufsize=1,
        universal_newlines=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        *args,
        **kwargs,
    )

    stdoutbuf = io.StringIO()
    stderrbuf = io.StringIO()

    stdout_fileno = process.stdout.fileno()  # type: ignore
    stderr_fileno = process.stderr.fileno()  # type: ignore

    while process.poll() is None:
        readready, writeready, exceptionready = select.select(
            [process.stdout, process.stderr],
            [],
            [process.stdout, process.stderr],
            0.5,
        )
        for stream in readready:
            if stream.fileno() == stdout_fileno:
                line = process.stdout.readline()  # type: ignore
                stdoutbuf.write(line)
                if print_output:
                    sys.stdout.write(line)
            elif stream.fileno() == stderr_fileno:
                line = process.stderr.readline()  # type: ignore
                stderrbuf.write(line)
                if print_output:
                    sys.stderr.write(line)
            else:
                raise Exception(
                    f"Unknown file descriptor in select result. Fileno: {stream.fileno()}"
                )
        for stream in exceptionready:
            if stream.fileno() == stdout_fileno:
                raise Exception("Exception on stdout")
            elif stream.fileno() == stderr_fileno:
                raise Exception("Exception on stderr")
            else:
                raise Exception(
                    f"Unknown exception in select result. Fileno: {stream.fileno()}"
                )

    for stream in [process.stdout, process.stderr]:
        for line in stream.readlines():
            if stream.fileno() == stdout_fileno:
                stdoutbuf.write(line)
                if print_output:
                    sys.stdout.write(line)
            elif stream.fileno() == stderr_fileno:
                stderrbuf.write(line)
                if print_output:
                    sys.stderr.write(line)

    process.stdout.close()  # type: ignore
    stdoutbuf.seek(0)
    process.stdout = stdoutbuf
    process.stderr.close()  # type: ignore
    stderrbuf.seek(0)
    process.stderr = stderrbuf

    if check and process.returncode != 0:
        msg = f"Command failed with exit code {process.returncode}: {cmd}"
        logger.error(msg)
        raise subprocess.CalledProcessError(
            process.returncode,
            cmd,
            process.stdout.getvalue(),
            process.stderr.getvalue(),
        )

    logger.info(f"Command completed with return code {process.returncode}: {cmd}")

    if log_output:
        logger.info(f"stdout: {process.stdout.getvalue()}")
        logger.info(f"stderr: {process.stderr.getvalue()}")

    magic_process: MagicPopen = process

    return magic_process


def signal_handler(signum, frame):
    """Handle signal a signal.

    atexit.register(...) does not handle signals UNLESS the signal is caught by a handler.
    So we need to a define a handler that just logs and calls sys.exit(),
    and let atexit do any cleanup.
    """
    logger.warning(f"Received signal {signum}, cleaning up and exiting.")
    sys.exit(128 + signum)


def send_email(
    subject: str,
    body: str,
    to_address: str,
    commit_hash: str,
    log_dir: Path,
) -> None:
    """Send an email using msmtp."""
    try:
        cmd = ["msmtp", "-a", "default", to_address]
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        email_content = f"Subject: {subject}\n\n{body}"
        stdout, stderr = process.communicate(input=email_content)
        if process.returncode != 0:
            logger.error(
                f"Failed to send email: {process.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}\n"
            )
            raise subprocess.CalledProcessError(process.returncode, cmd)
    except Exception as e:
        logger.error(f"An error occurred while sending email: {e}")
        error_file = log_dir / f"{commit_hash}.MAILFAIL"
        with open(error_file, "w") as f:
            f.write(
                f"Failed to send email: {str(e)}\n\nOriginal email content:\n{email_content}"
            )
        logger.error(f"Email content saved to {error_file}")


def acquire_lock(lock_file: str) -> Optional[int]:
    """Attempt to acquire a lock file."""
    lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except IOError:
        os.close(lock_fd)
        return None


def release_lock(lock_fd: int) -> None:
    """Release a previously acquired lock."""
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    os.close(lock_fd)


def process_exists(pid: int) -> bool:
    """Check if a process with the given pid exists.

    Send the null signal to a PID to determine existence.
    Unix-only.
    """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate_process(pid: int) -> None:
    """Attempt to terminate a process gracefully, falling back to forceful termination if necessary."""
    try:
        # Send SIGTERM
        os.kill(pid, signal.SIGTERM)

        # Wait for up to 10 seconds for the process to exit
        for _ in range(10):
            time.sleep(1)
            if not process_exists(pid):
                logger.info(f"Process {pid} terminated gracefully")
                return

        # If process still exists, send SIGKILL
        os.kill(pid, signal.SIGKILL)
        logger.warning(f"Process {pid} forcefully terminated with SIGKILL")
    except ProcessLookupError:
        logger.info(f"Process {pid} no longer exists")
    except Exception as e:
        logger.error(f"Error terminating process {pid}: {e}")


def terminate_older_builds(
    current_commit: str, queue_dir: Path, checkouts_dir: Path
) -> None:
    """Terminate build processes for commits older than the current one."""
    current_time = os.path.getmtime(queue_dir / f"{current_commit}.job")
    for job_file in queue_dir.glob("*.job"):
        if job_file.stat().st_mtime < current_time:
            try:
                with job_file.open() as f:
                    pid = int(f.read().strip())
                terminate_process(pid)
            except ValueError:
                logger.error(f"Invalid PID in job file {job_file}")
            finally:
                job_file.unlink(missing_ok=True)
                shutil.rmtree(checkouts_dir / job_file.stem, ignore_errors=True)


def acquire_lock_or_wait(
    deploy_lock: Path,
    commit_hash: str,
    queue_dir: Path,
    checkouts_dir: Path,
    max_wait_time: int,
) -> Optional[int]:
    """Attempt to acquire the deploy lock, terminating older builds if necessary."""
    start_time = time.time()
    while True:
        lock_fd = acquire_lock(str(deploy_lock))
        if lock_fd is not None:
            return lock_fd

        terminate_older_builds(commit_hash, queue_dir, checkouts_dir)

        if time.time() - start_time > max_wait_time:
            logger.error(
                f"Failed to acquire deploy lock after {max_wait_time} seconds. Exiting."
            )
            return None

        time.sleep(1)


def checkout_repo(repo_path: str, commit_hash: str, checkout_path: Path):
    """Check out the repository at the given commit hash.

    We'd like to use a shallow clone for this,
    in order to save disk space,
    but this doesn't work well with git-annex.

    TODOs:
    - Consider using a fixed set of worktrees to save time
    """
    checkout_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Cloning repository from {repo_path} to {checkout_path}")
    magicrun(
        ["git", "clone", "--no-checkout", f"file://{repo_path}", str(checkout_path)]
    )

    logger.info("Configuring git")
    configs = [
        # It seems that setting user.name and user.email is required for git-annex to work properly
        ["git", "config", "user.name", "micahrlci"],
        ["git", "config", "user.email", "psyops@micahrl.com"],
        ["git", "config", "advice.detachedHead", "false"],
        ["git", "config", "annex.thin", "true"],
    ]
    for config in configs:
        magicrun(config, cwd=str(checkout_path))

    logger.info(f"Checking out commit {commit_hash}")
    magicrun(["git", "checkout", commit_hash], cwd=str(checkout_path))

    logger.info("Initializing git-annex")
    magicrun(
        ["git", "annex", "init", "--verbose", f"micahrlci-{commit_hash}"],
        cwd=str(checkout_path),
    )

    logger.info("Enabling origin remote for git-annex")
    magicrun(["git", "annex", "enableremote", "origin"], cwd=str(checkout_path))

    logger.info("Retrieving git-annex files")
    magicrun(["git", "annex", "get", "."], cwd=str(checkout_path))

    logger.info(
        "Unlocking git-annex files (replacing git-annex symlinks with real files, which is required for Hugo)"
    )
    magicrun(["git", "annex", "unlock", "."], cwd=str(checkout_path))

    logging.info(
        f"Forcibly allowing writes to {checkout_path} (git-annex write protects some files which is annoying)..."
    )
    magicrun(["chmod", "-R", "+w", str(checkout_path)], check=False)

    logger.info("Showing git-annex files")
    magicrun(["git", "annex", "list"], cwd=str(checkout_path), check=True)

    checkout_files = "\n".join(sorted([f.name for f in list(checkout_path.iterdir())]))
    logger.info(
        f"Successfully checked out commit {commit_hash} and retrieved git-annex files. Repository files:\n{checkout_files}"
    )


def signal_handler(signum: int, frame: Any):
    """Handle signal a signal.

    atexit.register(...) does not handle signals UNLESS the signal is caught by a handler.
    So we need to a define a handler that just logs and calls sys.exit(),
    and let atexit do any cleanup.
    """
    logger.warning(f"Received signal {signum}, cleaning up and exiting.")
    sys.exit(128 + signum)


def cleanup_builddir_factory(
    commit_hash: str,
    job_file: Path,
    checkout_path: Path,
    keep_checkout: bool,
):
    """Return a cleanup function that will be registered with atexit."""

    def cleanup():
        """Clean up the build directory and release the deploy lock."""

        logging.info(f"Starting cleanup for commit {commit_hash}...")

        if keep_checkout:
            logging.warning(f"Keeping checkout directory {checkout_path}")
        else:
            logging.info(f"Removing {checkout_path}...")
            shutil.rmtree(checkout_path, ignore_errors=True)
            if checkout_path.exists():
                logging.error(f"Failed to clean up {checkout_path}")

        logging.info(f"Removing {job_file}...")
        job_file.unlink(missing_ok=True)
        if job_file.exists():
            logging.error(f"Failed to clean up {job_file}")

    return cleanup


def cleanup_factory_lock(lock_fd: int):
    """Return a cleanup function that will be registered with atexit."""

    def cleanup():
        """Clean up the build directory and release the deploy lock."""
        logging.info(
            f"Releasing deploy lock (this is safe even if we don't have the lock)..."
        )
        release_lock(lock_fd)

    return cleanup


def process_commit(
    commit_hash: str,
    job_file: Path,
    checkout_path: Path,
    container_tag: str,
    age_secret_key: str,
    queue_dir: Path,
    checkouts_dir: Path,
    deploy_lock: Path,
    max_lock_wait_time: int,
    repo_path: str,
    make_jobs: int,
    keep_checkout: bool,
) -> None:
    """Process a single commit: checkout, build, deploy if successful, and clean up.

    Arguments:
    - commit_hash: The commit hash to process
    - job_file: Path to the job file
    - checkout_path: Path to the checkout directory
    - container_tag: Tag for the micahrlci container
    - age_secret_key: Path to the age secret key
    - queue_dir: Path to the queue directory (parent of job_file)
    - checkouts_dir: Path to the checkouts directory (parent of checkout_path)
    - deploy_lock: Path to the deploy lock file
    - max_lock_wait_time: Maximum time to wait for the deploy lock in seconds
    - repo_path: Local path to the repository we clone from
    - make_jobs: Number of make jobs to run
    - keep_checkout: Whether to keep the checkout directory after completion/failure
    """

    if keep_checkout:
        logger.warning(
            f"Keeping checkout directory {checkout_path} after completion. THIS LEAVES ANY DECRYPTED SECRETS ON DISK."
        )

    # Register our signal handler
    for sig in [
        signal.SIGHUP,
        signal.SIGINT,
        signal.SIGQUIT,
        signal.SIGPIPE,
        signal.SIGTERM,
    ]:
        signal.signal(sig, signal_handler)

    # Register cleanup function for build directory
    atexit.register(
        cleanup_builddir_factory(commit_hash, job_file, checkout_path, keep_checkout)
    )

    # Create job file with PID
    with job_file.open("w") as f:
        f.write(str(os.getpid()))

    checkout_repo(repo_path, commit_hash, checkout_path)

    build_micahrlci_container(checkout_path, container_tag)
    make_micahrlci_build(checkout_path, container_tag, make_jobs)
    decrypt_repo_micahrlci_secrets(checkout_path, age_secret_key)

    # Try to acquire deploy lock
    logger.info("Acquiring deploy lock")
    lock_fd = acquire_lock_or_wait(
        deploy_lock,
        commit_hash,
        queue_dir,
        checkouts_dir,
        max_lock_wait_time,
    )
    if lock_fd is None:
        logger.error("Exiting due to failure to acquire deploy lock")
        return  # Exit if we couldn't acquire the lock

    # Register cleanup function for lock
    atexit.register(cleanup_factory_lock(lock_fd))

    # Deploy
    make_micahrlci_deploy(checkout_path, container_tag, make_jobs)


def decrypt_repo_micahrlci_secrets(checkout_path: Path, secret_key: str):
    """Decrypt the secrets directory in the micahrlci checkout.

    It decrypts them to the checkout directory,
    and relies on the script cleaning that up before exiting.
    """
    secrets_dir = checkout_path / ".micahrlci" / "secrets"
    logger.info(f"Decrypting secrets to {secrets_dir}...")
    for encrypted_secret in secrets_dir.glob("*.age"):
        decrypted_secret = encrypted_secret.with_suffix("")
        cmd = [
            "age",
            "--decrypt",
            "--identity",
            secret_key,
            "--output",
            str(decrypted_secret),
            str(encrypted_secret),
        ]
        magicrun(cmd, cwd=str(secrets_dir))
    logger.info("Secrets decrypted.")


def build_micahrlci_container(checkout_path: Path, container_tag: str) -> None:
    """Build the micahrlci container for the given commit hash."""
    logger.info("Building micahrlci container...")
    magicrun(
        ["podman", "build", "-t", container_tag, "."],
        cwd=str(checkout_path / ".micahrlci"),
    )
    logger.info("micahrlci container built.")


def make_micahrlci_build(
    checkout_path: Path, container_tag: str, make_jobs: int
) -> None:
    """Run the micahrlci-build target for the given commit hash."""
    logger.info("Running make micahrlci-build...")
    cmd = [
        "podman",
        "run",
        "--rm",
        "--volume",
        f"{checkout_path}:/src",
        container_tag,
        "sh",
        "-c",
        f"set -x; whoami; pwd; ls -alF; make -j {make_jobs} micahrlci-build",
    ]
    magicrun(cmd, cwd=str(checkout_path))
    logger.info("micahrlci-build complete.")


def make_micahrlci_deploy(
    checkout_path: Path, container_tag: str, make_jobs: int
) -> None:
    """Run the micahrlci-deploy target for the given commit hash."""
    logger.info("Running make micahrlci-deploy...")
    cmd = [
        "podman",
        "run",
        "--rm",
        "--volume",
        f"{checkout_path}:/src",
        container_tag,
        "sh",
        "-c",
        f"set -x; whoami; pwd; ls -alF; make -j {make_jobs} micahrlci-deploy",
    ]
    magicrun(cmd, cwd=str(checkout_path))
    logger.info("micahrlci-deploy complete.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commit_hash", help="Hash of the commit to build and deploy")
    parser.add_argument("repo_path", help="Path to the Git repository")
    parser.add_argument(
        "--action",
        choices=["checkout", "container", "decrypt", "build", "deploy", "all"],
        nargs="+",
        default=["all"],
        help="Action to perform; anything except 'all' --keep-checkout, and only the 'all' action will send email at the end of a run.",
    )
    parser.add_argument(
        "--buildroot",
        default=os.path.expanduser("~/micahrlci"),
        help="Root directory for all build-related directories",
    )
    parser.add_argument(
        "--max-lock-wait-time",
        type=int,
        default=30,
        help="Maximum time to wait for deploy lock in minutes",
    )
    parser.add_argument(
        "--email",
        default="psyops@micahrl.com",
        help="Email address to send build logs to",
    )
    parser.add_argument(
        "--age-secret-key",
        default=os.path.expanduser("~/micahrlci/secrets/secret.age"),
        help="Age secret key",
    )
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "--keep-checkout",
        "-K",
        action="store_true",
        help="Keep the checkout directory after completion/failure. THIS LEAVES ANY DECRYPTED SECRETS ON DISK.",
    )
    parser.add_argument(
        "--make-jobs",
        type=int,
        default=os.cpu_count(),
        help="Number of make jobs to run; defaults to the number of CPUs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.debug:
        sys.excepthook = idb_excepthook

    buildroot = Path(args.buildroot)
    queue_dir = buildroot / "queue"
    checkouts_dir = buildroot / "checkouts"
    deploy_lock = buildroot / "deploy.lock"
    log_dir = buildroot / "logs"
    max_lock_wait_time = args.max_lock_wait_time * 60  # Convert minutes to seconds

    job_file = queue_dir / f"{args.commit_hash}.job"
    checkout_path = checkouts_dir / args.commit_hash
    container_tag = f"micahrlci:{args.commit_hash}"

    # A CI build should have a restricted umask, especially for secrets
    os.umask(0o077)

    # Create directories if they don't exist
    for directory in [queue_dir, checkouts_dir, log_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Set up logging
    global logger
    logger, log_file = setup_logging(log_dir, args.commit_hash)

    # The post-commit hook will have this set to the bare repo path.
    # However, it interferes with the git commands we run in this script like 'git checkout' etc etc.
    # If we don't unset it, we get REALLY CONFUSING errors like
    #   fatal: not a git repository: '.'
    # even when doing something like
    #   subprocess.run(["git", "status"], cwd="/definitely/a/valid/repo/path")
    if "GIT_DIR" in os.environ:
        logger.warning(f"GIT_DIR is set to {os.environ['GIT_DIR']}, unsetting it.")
        os.environ.pop("GIT_DIR")

    if "all" in args.action:
        try:
            process_commit(
                args.commit_hash,
                job_file,
                checkout_path,
                container_tag,
                args.age_secret_key,
                queue_dir,
                checkouts_dir,
                deploy_lock,
                max_lock_wait_time,
                args.repo_path,
                args.make_jobs,
                args.keep_checkout,
            )
        finally:
            # Send email with build log
            with open(log_file, "r") as f:
                log_content = f.read()

            subject = f"Build Log for Commit {args.commit_hash}"
            send_email(subject, log_content, args.email, args.commit_hash, log_dir)
    else:
        if "checkout" in args.action:
            checkout_repo(args.repo_path, args.commit_hash, checkout_path)
        if "container" in args.action:
            build_micahrlci_container(checkout_path, container_tag)
        if "decrypt" in args.action:
            decrypt_repo_micahrlci_secrets(checkout_path, args.age_secret_key)
        if "build" in args.action:
            make_micahrlci_build(checkout_path, container_tag, args.make_jobs)
        if "deploy" in args.action:
            make_micahrlci_deploy(checkout_path, container_tag, args.make_jobs)


if __name__ == "__main__":
    main()
