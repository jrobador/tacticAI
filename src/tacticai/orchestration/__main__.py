import sys

if sys.argv[1:2] == ["start"] and len(sys.argv) <= 3:  # the container entry: only jobs; the `run` process it spawns imports the pipeline
    from .jobs import start
    sys.exit(start(*sys.argv[2:]))

from .cli import main

sys.exit(main())
