import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from m3u import parse


SAMPLE = """#EXTM3U
#EXTINF:-1 tvg-id="aj" tvg-name="Al Jazeera" tvg-logo="https://x/l.png" group-title="أخبار",الجزيرة
https://live.example.com/aj.m3u8
#EXTINF:-1 group-title="رياضة",قناة رياضية
https://live.example.com/sport.m3u8

# stray comment
#EXTINF:-1,قناة بدون رابط
#EXTINF:-1,تالية
https://live.example.com/next.m3u8
"""


class ParseTests(unittest.TestCase):
    def test_parses_three_channels(self):
        got = parse(SAMPLE)
        self.assertEqual(len(got), 3)

    def test_attributes(self):
        c = parse(SAMPLE)[0]
        self.assertEqual(c["name"], "الجزيرة")
        self.assertEqual(c["logo"], "https://x/l.png")
        self.assertEqual(c["group"], "أخبار")
        self.assertEqual(c["url"], "https://live.example.com/aj.m3u8")

    def test_second_entry(self):
        c = parse(SAMPLE)[1]
        self.assertEqual(c["name"], "قناة رياضية")
        self.assertEqual(c["group"], "رياضة")
        self.assertEqual(c["logo"], "")

    def test_falls_back_to_tvg_name_when_display_missing(self):
        txt = '#EXTM3U\n#EXTINF:-1 tvg-name="Fallback",\nhttps://x/y.m3u8\n'
        self.assertEqual(parse(txt)[0]["name"], "Fallback")

    def test_skips_entry_missing_url(self):
        txt = '#EXTM3U\n#EXTINF:-1,A\n#EXTINF:-1,B\nhttps://x/b.m3u8\n'
        got = parse(txt)
        self.assertEqual([c["name"] for c in got], ["B"])

    def test_rejects_non_http_url(self):
        txt = '#EXTM3U\n#EXTINF:-1,X\nfile:///etc/passwd\n'
        self.assertEqual(parse(txt), [])

    def test_empty_input(self):
        self.assertEqual(parse(""), [])


if __name__ == "__main__":
    unittest.main()
