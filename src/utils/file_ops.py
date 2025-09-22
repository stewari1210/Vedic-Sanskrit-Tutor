def load_file(file):
    with open(file, "r", encoding="utf-8") as f:
        text = f.read().strip()

    return text


def save_file(file, text):
    with open(file, "w", encoding="utf-8") as f:
        f.write(text)
