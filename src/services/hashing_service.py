import hashlib

class HashingService:
    def sha256_file(self, path, chunk_size=8192):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
