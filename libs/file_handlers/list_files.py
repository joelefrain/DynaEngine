import os


def list_relative_paths(base_path, output_path="paths.txt"):
    with open(output_path, "w", encoding="utf-8") as f:
        for root, dirs, files in os.walk(base_path):
            for fname in dirs + files:
                abs_path = os.path.join(root, fname)
                relative_path = os.path.relpath(abs_path, base_path)
                f.write(relative_path + "\n")


if __name__ == "__main__":
    base_path = "./var"
    output_path = "./paths.txt"
    list_relative_paths(base_path)
