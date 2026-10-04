"""One isolated process per document; output is a single JSON result."""

import json
from pathlib import Path
import signal
import sys

from .engine import ConversionError, convert_pdf


def cancel(_signal, _frame):
    raise KeyboardInterrupt


def main(source, folder):
    signal.signal(signal.SIGTERM, cancel)
    try:
        result = convert_pdf(Path(source), Path(folder))
        message = {"ok": True, **result.to_dict()}
        code = 0
    except KeyboardInterrupt:
        message, code = {"ok": False, "error": "已取消", "cancelled": True}, 130
    except ConversionError as error:
        message, code = {"ok": False, "error": str(error)}, 1
    except PermissionError:
        message, code = {"ok": False, "error": "无法读取或保存文件，请检查文件夹权限。"}, 1
    except Exception:
        message, code = {"ok": False, "error": "转换未完成，请重试或换一份 PDF。"}, 1
    print(json.dumps(message, ensure_ascii=False), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
