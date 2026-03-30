"""Small file-emission helpers shared by generation code paths."""


def emit_to_file(parser, path, emitter, *args, **kwargs):
    """Run `emitter` while `parser.fd` points to an opened output file.

    The previous `parser.fd` value is restored after emission so callers can
    compose this helper safely inside larger generation workflows.
    """
    previous_fd = parser.fd
    try:
        with open(path, 'w') as stream:
            parser.fd = stream
            emitter(*args, **kwargs)
    finally:
        parser.fd = previous_fd
