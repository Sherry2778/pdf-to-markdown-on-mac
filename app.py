"""Entry point used both from source and by the frozen macOS app."""

import sys

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        from pdf_to_markdown.worker import main
        raise SystemExit(main(sys.argv[2], sys.argv[3]))
    from pdf_to_markdown.gui import run
    raise SystemExit(run())
