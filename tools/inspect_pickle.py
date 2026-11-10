"""Statically list the globals a torch .pt checkpoint's pickle imports, and show the
context around any builtins.getattr call. Never unpickles (no code runs).

Usage: python -I tools/inspect_pickle.py <file.pt>
"""
import io
import pickletools
import sys
import zipfile


def main(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith("data.pkl"))
        data = z.read(name)
    ops = list(pickletools.genops(io.BytesIO(data)))
    globals_seen = set()
    recent_strings = []
    for i, (op, arg, pos) in enumerate(ops):
        if op.name in ("SHORT_BINUNICODE", "BINUNICODE", "UNICODE"):
            recent_strings.append(arg)
            recent_strings = recent_strings[-4:]
        if op.name == "GLOBAL":
            globals_seen.add(arg.replace(" ", "."))
            if arg.endswith("getattr"):
                ctx = [(o.name, a) for (o, a, p) in ops[i + 1:i + 14] if a is not None]
                print("getattr context:", ctx)
        if op.name == "STACK_GLOBAL" and len(recent_strings) >= 2:
            g = f"{recent_strings[-2]}.{recent_strings[-1]}"
            globals_seen.add(g)
            if g.endswith("getattr"):
                # show the next few string args, i.e. what getattr is applied to
                ctx = [a for (o, a, p) in ops[i:i + 25] if o.name in ("SHORT_BINUNICODE", "BINUNICODE", "UNICODE", "STACK_GLOBAL")]
                print("getattr context:", ctx[:10])
    print("globals:")
    for g in sorted(globals_seen):
        print("  ", g)


if __name__ == "__main__":
    main(sys.argv[1])
