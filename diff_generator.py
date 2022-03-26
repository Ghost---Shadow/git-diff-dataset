import json
import os
import subprocess
import sys
from tqdm import tqdm


def run(cmd):
    stdout, stderr = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).communicate()
    stdout = stdout.decode("utf8")
    stderr = stderr.decode("utf8")

    if len(stderr) != 0:
        raise RuntimeError(stderr)

    return stdout


def get_commits(path_to_git):
    commits = run(f'git --git-dir {path_to_git} log --pretty=format:"%H %s"')
    commits = commits.split("\n")

    def _format_commit(commit):
        lst = commit.split()
        h = lst[0]
        msg = " ".join(lst[1:])
        return {
            "hash": h,
            "message": msg,
        }

    commits = map(_format_commit, commits)
    return list(commits)


def file_name_filter(file_name):
    if file_name in ["package.json", "package-lock.json", "README.md"]:
        return False

    if file_name.startswith("."):
        return False

    if "." not in file_name:
        return False

    return True


def get_tracked_files(path_to_git):
    files = run(
        # f"git --git-dir {path_to_git} ls-tree --full-tree --name-only -r HEAD"
        f"git --git-dir {path_to_git} ls-files --eol"
    )
    files = files.split("\n")
    files = filter(lambda file: len(file.strip()) > 0, files)
    file_objs = map(lambda file: file.split(), files)
    file_objs = filter(
        lambda file_obj: any(["lf" in file_obj[0], "crlf" in file_obj[0]]),
        file_objs,
    )
    files = map(lambda file_obj: file_obj[3], file_objs)
    files = filter(file_name_filter, files)
    return list(files)


def get_diffs_for_file(path_to_git, file, commits):
    diffs = []
    for current_commit, prev_commit in zip(commits, commits[1:]):
        prev_hash = prev_commit["hash"]
        current_hash = current_commit["hash"]
        try:
            diff = run(
                f"git --git-dir {path_to_git} diff {prev_hash}:{file} {current_hash}:{file}"
            ).strip()
            snapshot = run(
                f"git --git-dir {path_to_git} show {prev_hash}:{file}"
            ).strip()
            if len(diff) == 0:
                continue
            diffs.append(
                {
                    "prev_commit": prev_commit["hash"],
                    "current_commit": current_commit["hash"],
                    "prev_message": prev_commit["message"],
                    "current_message": current_commit["message"],
                    "file": file,
                    "diff": diff,
                    "snapshot": snapshot,
                }
            )
        except RuntimeError as e:
            if "does not exist in" in str(e):
                continue
            raise e

    return diffs


def main(directory):
    path_to_git = os.path.join(directory, ".git")
    commits = get_commits(path_to_git)
    files = get_tracked_files(path_to_git)

    with open("diffs.jsonl", "w") as f:
        pbar = tqdm(files)
        for file_name in pbar:
            pbar.set_description(file_name)
            diffs = get_diffs_for_file(path_to_git, file_name, commits)
            for diff in diffs:
                f.write(json.dumps(diff))
                f.write("\n")
            f.flush()


if __name__ == "__main__":
    if len(sys.argv) == 2:
        directory = sys.argv[1]
    else:
        directory = "."
    main(directory)
