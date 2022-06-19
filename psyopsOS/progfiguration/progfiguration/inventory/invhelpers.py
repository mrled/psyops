"""Helper functions for the inventory"""


class Bunch:
    """A nice little object wrapper.

    From <https://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/?in=user-97991>
    """

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
