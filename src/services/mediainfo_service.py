from pymediainfo import MediaInfo

class MediaInfoService:
    def parse_media(self, path: str) -> dict:
        mi = MediaInfo.parse(path)
        result = {}
        for track in mi.tracks:
            cat = track.track_type or "Other"
            attrs = []
            data = track.to_data()
            for k, v in data.items():
                if k == "track_type":
                    continue
                attrs.append((k, str(v)))
            result.setdefault(cat, []).extend(attrs)
        return result
