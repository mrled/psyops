"""THE TEMPLATE TEMPLE

The Python documentation for string.Template
<https://docs.python.org/3/library/string.html>:

> Advanced usage: you can derive subclasses of Template to customize the placeholder syntax, delimiter character, or the entire regular expression used to parse template strings.

We use this to customize the delimiter character to be "{$}" instead of "$" so that we can use the dollar sign in our templates without escaping it.

We call it the Temple because it's a temple to the dollar sign --
just kidding, that was Copilot's idea;
we actually call it the Temple from a strong personal tradition that one places the templates in the temple.
"""

from string import Template


class Temple(Template):
    delimiter = "{$}"
