import { type Report, urlOf } from "./atoms.ts";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow } from "./Table.tsx";

export function DownloadsSection() {
  return (
    <Section id="downloads">
      <SectionTitle>Downloads</SectionTitle>
      <SectionTable>
        <ReportTableHead title={"Data exports"} />
        <tbody>
          <ReportTableRow
            title="Ecosystem (CSV)"
            cell={(report) => <DownloadLink field="ecosystemCsvHref" report={report} />}
            textAlign="center"
          />
          <ReportTableRow
            title="Ecosystem (JSON)"
            cell={(report) => <DownloadLink field="ecosystemJsonHref" report={report} />}
            textAlign="center"
          />
        </tbody>
      </SectionTable>
    </Section>
  );
}

function DownloadLink({
  report,
  field,
}: {
  report: Report;
  field: "ecosystemCsvHref" | "ecosystemJsonHref";
}) {
  return (
    <a href={urlOf(report[field])} className="link">
      Download
    </a>
  );
}
