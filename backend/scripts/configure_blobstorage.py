"""Wrap the generated zope.conf filestorage in a blobstorage.

``mkwsgiinstance`` writes a minimal ``zodb_db`` section holding a bare
``<filestorage>``. Plone stores every uploaded file as a ZODB blob, and a
FileStorage without a ``blob-dir`` cannot hold one, so the *first* file
upload fails at commit time with::

    ZODB.POSException.Unsupported: Storing Blobs in <...> is not supported.

The item is created before the commit fails, so the failure looks like a
redirect that did not happen rather than a storage problem -- which is what
made this hard to see.

Idempotent: running it against an already-wrapped config changes nothing.
"""

import pathlib
import re
import sys


BEFORE = re.compile(
    r"^(?P<indent>[ \t]*)<filestorage>\n"
    r"(?P<body>(?:.*\n)*?)"
    r"(?P=indent)</filestorage>\n",
    re.MULTILINE,
)


def wrap(source):
    if "<blobstorage>" in source:
        return source, False

    def replace(match):
        indent = match.group("indent")
        body = "".join(
            f"  {line}\n" if line.strip() else "\n"
            for line in match.group("body").splitlines()
        )
        return (
            f"{indent}<blobstorage>\n"
            f"{indent}  blob-dir $INSTANCE/var/blobstorage\n"
            f"{indent}  <filestorage>\n"
            f"{body}"
            f"{indent}  </filestorage>\n"
            f"{indent}</blobstorage>\n"
        )

    wrapped, count = BEFORE.subn(replace, source, count=1)
    return wrapped, bool(count)


def main(path):
    config = pathlib.Path(path)
    if not config.exists():
        print(f"{config}: not found, nothing to do")
        return 0

    source = config.read_text()
    wrapped, changed = wrap(source)
    if not changed:
        print(f"{config}: blobstorage already configured")
        return 0

    config.write_text(wrapped)
    print(f"{config}: wrapped filestorage in a blobstorage")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "instance/etc/zope.conf"))
