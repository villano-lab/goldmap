"""`python -m goldmap`: start the app and open it in the browser."""
import argparse
import os
import sys
import webbrowser
from pathlib import Path

from . import server


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="goldmap", description="Lay out a goldsluice processing in the browser (a local app).")
    p.add_argument("--registry", action="append", default=[], metavar="DIR", help="a folder of detector records (goldpan.registry); repeat for several. "
                   "GOLDPAN_REGISTRY is used too")
    p.add_argument("--series-list", metavar="CSV", help="a CSV with a `series` column and what is known about each series (HV, trigger, ...)")
    p.add_argument("--root", action="append", default=[], metavar="DIR", help="a folder of raw dumps to offer (default: ~/idx); repeat for several")
    p.add_argument("--folder", metavar="DIR", default=None, help="where the definition and the metadata are written (default: the current folder)")
    p.add_argument("--port", type=int, default=0, help="the port on 127.0.0.1 (default: any free one)")
    p.add_argument("--no-browser", action="store_true", help="only print the address")
    args = p.parse_args(argv)
    roots = args.root or [str(Path("~/idx").expanduser())]
    registry = args.registry + [r for r in os.environ.get("GOLDPAN_REGISTRY", "").split(os.pathsep) if r]
    srv = server.make_server(server.Config(registry, args.series_list, roots, args.folder), args.port)
    url = f"http://127.0.0.1:{srv.server_port}/"
    print(f"goldmap is at {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
