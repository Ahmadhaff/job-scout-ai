"""Parsers for Keejob, Tanitjobs, and Free-Work listing pages."""

from __future__ import annotations

import unittest

from src.boards import _parse_freework, _parse_keejob_cards, _parse_tanit, _text_inside_class, is_board_url
from src.config import DEFAULT_FEEDS


KEEJOB_HTML = """
<h2 class="text-base">
  <a href="/offres-emploi/247584/senior-full-stack-developer/?source=search" class="font-bold">
    Full Stack Developer
  </a>
</h2>
<p class="text-sm">
  <a href="/offres-emploi/entreprises/9/linkers-it/">LINKERS IT</a>
</p>
"""

TANIT_HTML = """
<div class="sj-job-card">
  <a href="https://www.tanitjobs.com/job/2061416/technicien-systemes/"><img alt="Logo"></a>
  <div class="sj-card-title">
    <a href="https://www.tanitjobs.com/job/2061416/technicien-systemes/">Développeur React</a>
  </div>
  <div class="sj-card-company">
    <a href="https://www.tanitjobs.com/job/2061416/technicien-systemes/">Sodedif Neopro</a>
    <span>Tunis, Tunisie</span>
  </div>
  <div class="sj-card-desc">
    APIs Node.js et PostgreSQL pour une plateforme web.
  </div>
</div>
"""

FREEWORK_HTML = """
<a href="/fr/tech-it/job-mission/developpeur-front-end/developpeur-front-end-next-js-react" class="after:absolute">
  <span class="fw-text-highlight"><!--[-->Développeur front-end Next.js / <!--]--><span class="fw-text-highlight-part">React</span><!--[--> TypeScript<!--]--></span>
</a>
<div id="tags-1-skills"><span class="tag relative inline-flex">NestJS</span><span class="tag relative inline-flex">React</span></div>
"""


class BoardParserTests(unittest.TestCase):
    def test_default_feeds_include_the_three_boards(self) -> None:
        joined = " ".join(DEFAULT_FEEDS)
        self.assertIn("keejob.com", joined)
        self.assertIn("tanitjobs.com", joined)
        self.assertIn("free-work.com", joined)

    def test_board_urls_are_not_treated_as_rss(self) -> None:
        self.assertTrue(is_board_url("https://www.keejob.com/offres-emploi/"))
        self.assertTrue(is_board_url("https://www.tanitjobs.com/categories/705/informatique-jobs/"))
        self.assertFalse(is_board_url("https://www.tanitjobs.com/rss/"))
        self.assertFalse(is_board_url("https://hnrss.org/jobs"))

    def test_keejob_card(self) -> None:
        cards = _parse_keejob_cards("https://www.keejob.com/offres-emploi/", KEEJOB_HTML)
        self.assertEqual(len(cards), 1)
        title, link, description = cards[0]
        self.assertEqual(title, "Full Stack Developer")
        self.assertEqual(link, "https://www.keejob.com/offres-emploi/247584/senior-full-stack-developer/")
        self.assertIn("LINKERS IT", description)

    def test_tanit_card(self) -> None:
        jobs = _parse_tanit("https://www.tanitjobs.com/categories/705/informatique-jobs/", TANIT_HTML)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Développeur React")
        self.assertIn("PostgreSQL", jobs[0].description)
        self.assertIn("Sodedif", jobs[0].description)
        self.assertTrue(jobs[0].link.startswith("https://www.tanitjobs.com/job/2061416/"))

    def test_freework_card(self) -> None:
        jobs = _parse_freework("https://www.free-work.com/fr/tech-it/jobs?query=react", FREEWORK_HTML)
        self.assertEqual(len(jobs), 1)
        self.assertIn("Next.js", jobs[0].title)
        self.assertIn("React", jobs[0].title)
        self.assertIn("React", jobs[0].description)
        self.assertTrue(jobs[0].link.startswith("https://www.free-work.com/fr/tech-it/job-mission/"))

    def test_prose_block_is_the_longest_match(self) -> None:
        html = '<div class="prose">Short.</div><div class="prose dark:prose-invert"><p>NestJS and PostgreSQL.</p></div>'
        self.assertIn("PostgreSQL", _text_inside_class(html, "prose"))


if __name__ == "__main__":
    unittest.main()
