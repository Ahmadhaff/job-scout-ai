#!/usr/bin/env python3
"""Scan startup job feeds, score them with Claude, and alert on strong matches."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import DEVELOPER_PROFILE, PROJECT_ROOT, ConfigError, Settings, job_targets_stack
from src.evaluator import EvaluationError, JobEvaluator
from src.fetchers import FetchError, JobListing, fetch_jobs
from src.notifier import NotifierError, TelegramNotifier
from src.resume_facts import ResumeError, assemble, resume_filename
from src.resume_pdf import render_resume
from src.resume_tailor import ResumeTailor
from src.state import SeenJobStore, StateError

logger = logging.getLogger("job_scout")


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 10):
        print("job-scout-ai requires Python 3.10 or newer.", file=sys.stderr)
        return 1
    args = _parse_args(argv)
    _configure_logging(args.verbose)
    try:
        settings = Settings.from_env(require_credentials=not (args.dry_run or args.sample_resume))
    except ConfigError as exc:
        logger.error("%s", exc)
        return 1

    if args.sample_resume:
        return _write_sample_resume()

    try:
        return _run(settings, args)
    except (FetchError, StateError) as exc:
        logger.error("%s", exc)
        return 1


def _run(settings: Settings, args: argparse.Namespace) -> int:
    fetched = fetch_jobs(settings.feeds)
    jobs = [job for job in fetched if job_targets_stack(job.title, job.description)]
    logger.info(
        "Kept %s of %s listings for React, Next.js, Node.js, NestJS, PostgreSQL, or AI.",
        len(jobs),
        len(fetched),
    )
    store = SeenJobStore(settings.seen_jobs_path)
    store.load()
    cap = args.limit if args.limit is not None else settings.max_jobs_per_run

    if args.dry_run:
        return _dry_run(jobs, store, cap)

    unseen = [job for job in jobs if not store.contains(job.id)]
    pending = unseen[:cap]
    if not pending:
        logger.info("No new listings to evaluate (fetched %s).", len(jobs))
        return 0
    if len(unseen) > len(pending):
        logger.info(
            "Evaluating %s of %s new listings. The rest wait for the next run.",
            len(pending),
            len(unseen),
        )

    evaluator = JobEvaluator(settings.anthropic_api_key, model=settings.model)
    tailor = ResumeTailor(settings.anthropic_api_key, model=settings.model)
    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    resumes_dir = PROJECT_ROOT / "data" / "resumes"
    evaluated = 0
    alerts = 0
    failures = 0
    alert_failures = 0

    for index, job in enumerate(pending):
        if index > 0 and settings.request_delay_seconds > 0:
            time.sleep(settings.request_delay_seconds)
        try:
            evaluation = evaluator.evaluate(job, DEVELOPER_PROFILE)
        except EvaluationError as exc:
            logger.error("Evaluation failed for %r: %s", job.title, exc)
            failures += 1
            continue

        should_alert = evaluation.match_score >= settings.match_threshold
        logger.info(
            "scored %s | match=%s startup=%s alert=%s",
            job.title,
            evaluation.match_score,
            evaluation.is_startup,
            should_alert,
        )
        logger.info("summary: %s", evaluation.summary)

        if should_alert:
            try:
                pdf_path = _build_resume(tailor, job, resumes_dir)
                notifier.send_job_alert(job, evaluation, resume_attached=True)
                notifier.send_document(pdf_path, caption=f"Tailored resume for {job.title}")
            except (ResumeError, NotifierError) as exc:
                logger.error("Notification failed for %r: %s", job.title, exc)
                alert_failures += 1
                continue
            alerts += 1
            logger.info("Sent alert and résumé for %s", job.title)

        store.add(job.id)
        store.save()
        evaluated += 1

    logger.info(
        "Finished. fetched=%s new=%s evaluated=%s alerts=%s failures=%s",
        len(jobs),
        len(unseen),
        evaluated,
        alerts,
        failures,
    )
    if alert_failures or (pending and evaluated == 0):
        return 1
    return 0


def _build_resume(tailor: ResumeTailor, job: JobListing, resumes_dir: Path) -> Path:
    copy = None
    try:
        copy = tailor.tailor(job)
    except ResumeError as exc:
        logger.warning("Using the base résumé for %s: %s", job.title, exc)
    document = assemble(copy)
    destination = resumes_dir / resume_filename(job.title, job.id)
    return render_resume(document, destination)


def _write_sample_resume() -> int:
    destination = PROJECT_ROOT / "data" / "resumes" / "Ahmad_Haffoudhi.pdf"
    try:
        path = render_resume(assemble(), destination)
    except ResumeError as exc:
        logger.error("%s", exc)
        return 1
    logger.info("Wrote sample résumé to %s", path)
    return 0


def _dry_run(jobs: list[JobListing], store: SeenJobStore, cap: int) -> int:
    preview = jobs[:cap]
    logger.info("Dry run: %s listings, showing %s.", len(jobs), len(preview))
    for job in preview:
        status = "seen" if store.contains(job.id) else "new"
        logger.info("[%s] %s | %s", status, job.title, job.link or "(no link)")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="job-scout-ai",
        description=(
            "Score React, Next.js, Node.js, NestJS, PostgreSQL, and AI engineer roles, "
            "then send a Telegram alert and a tailored PDF résumé for matches of 8/10 or higher."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch feeds and print listings only.",
    )
    parser.add_argument(
        "--sample-resume",
        action="store_true",
        help="Write the base one-page résumé PDF and exit.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of listings to show or evaluate this run.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    return args


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    if verbose:
        for name in ("urllib3", "httpx", "httpcore", "anthropic"):
            logging.getLogger(name).setLevel(logging.WARNING)


if __name__ == "__main__":
    raise SystemExit(main())
