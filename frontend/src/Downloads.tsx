import { type Report, urlOf } from "./atoms.ts";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow } from "./Table.tsx";

export function DownloadsSection() {
  return (
    <Section defaultOpen>
      <SectionTitle>Downloads</SectionTitle>
      <SectionTable>
        <ReportTableHead title={"Data exports"} />
        <tbody>
          <ReportTableRow
            title="Ecosystem (CSV)"
            cell={(props) => <DownloadLink field="ecosystemCsvHref" {...props} />}
          />
          <ReportTableRow
            title="Ecosystem (JSON)"
            cell={(props) => <DownloadLink field="ecosystemJsonHref" {...props} />}
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
