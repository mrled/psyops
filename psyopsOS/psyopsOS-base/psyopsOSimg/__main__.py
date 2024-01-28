import sys
from psyopsOSimg.cmd import broken_pipe_handler, main

broken_pipe_handler(main, *sys.argv)
