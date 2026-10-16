import { Link } from "@tanstack/react-router";
import { ArrowUpRight } from "@phosphor-icons/react";
import syllabusArtwork from "../../../assets/illustrations/alignment/syllabus-check.svg";
import curriculumArtwork from "../../../assets/illustrations/alignment/curriculum-check.svg";

export function FacultyAlignmentChecks() {
  return (
    <section
      aria-labelledby="dashboard-alignment-heading"
      className="dashboard-alignment dashboard-panel"
    >
      <h2
        id="dashboard-alignment-heading"
        className="text-base font-semibold text-text"
      >
        Alignment checks
      </h2>
      <div className="dashboard-alignment-items mt-2">
        {[
          {
            to: "/syllabus-alignment",
            label: "Syllabus check",
            detail: "Course learning outcomes",
            artwork: syllabusArtwork,
          },
          {
            to: "/curriculum-alignment",
            label: "Curriculum check",
            detail: "Program requirements",
            artwork: curriculumArtwork,
          },
        ].map(({ to, label, detail, artwork }) => (
          <Link
            key={to}
            to={to}
            className="dashboard-alignment-link dashboard-link group"
          >
            <img
              src={artwork}
              width={80}
              height={80}
              alt=""
              className="size-10 shrink-0"
            />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-text group-hover:text-primary">
                {label}
              </span>
              <span className="mt-1 block text-sm leading-relaxed text-text-muted">
                {detail}
              </span>
            </span>
            <ArrowUpRight
              size={17}
              className="shrink-0 text-text-muted"
              aria-hidden="true"
            />
          </Link>
        ))}
      </div>
    </section>
  );
}
