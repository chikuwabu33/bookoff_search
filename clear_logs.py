import shutil
from pathlib import Path

def clear_logs():
    """logsディレクトリ内のファイルとフォルダをすべて削除します。"""
    # .gitignoreで定義されているlogsディレクトリの絶対パス
    log_dir = Path(r"d:\apps\bookoff_search\logs")

    if not log_dir.exists():
        print(f"Directory {log_dir} does not exist.")
        return

    for item in log_dir.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
            print(f"Successfully deleted: {item}")
        except Exception as e:
            print(f"Failed to delete {item}. Reason: {e}")

if __name__ == "__main__":
    clear_logs()