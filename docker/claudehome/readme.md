When running in claude mode, we give it its own homedir, mounted here.
We don't want to use the same dir for interactive mode, to prevent claude frmo contaminating it.
We do need to persist the claude homedir for the ~/.claude directory at least.
