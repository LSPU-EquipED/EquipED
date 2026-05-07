import {
  ArrowDown,
  ChevronDown,
  FileText,
  Folder,
  MoreHorizontal,
  Plus,
  Search,
  Upload,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from '@/shared/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';

const documents = [
  {
    name: 'TEA SIS.docx',
    author: 'Marc Justin Alberto',
    created: '05/04/2026',
    evaluation: 'Completed',
    scores: { coordinator: 88, sme: 92, gad: 85, itso: 90 },
  },
  {
    name: 'Geographic Information System SLM.pdf',
    author: 'Marc Justin Alberto',
    created: '05/04/2026',
    evaluation: 'Completed',
    scores: { coordinator: 84, sme: 86, gad: 80, itso: 78 },
  },
  {
    name: 'Healthcare privacy and compliance module.pdf',
    author: 'Marc Justin Alberto',
    created: '05/04/2026',
    evaluation: 'In review',
    scores: { coordinator: 74, sme: 77, gad: 82, itso: 71 },
  },
  {
    name: 'System performance and optimization SLM.pdf',
    author: 'Marc Justin Alberto',
    created: '05/04/2026',
    evaluation: 'In review',
    scores: { coordinator: 68, sme: 72, gad: 70, itso: 65 },
  },
  {
    name: 'Curriculum mapping reference.pdf',
    author: 'LSPU SCC CCS',
    created: '05/03/2026',
    evaluation: 'Reference',
    scores: { coordinator: null, sme: null, gad: null, itso: null },
  },
];

function ScoreRing({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="text-muted-foreground">-</span>;
  }

  const color = value >= 85 ? 'oklch(0.53 0.13 150)' : value >= 75 ? 'oklch(0.66 0.14 75)' : 'oklch(0.58 0.19 25)';

  return (
    <div className="flex items-center gap-2">
      <span
        className="grid size-7 place-items-center rounded-full"
        style={{ background: `conic-gradient(${color} ${value * 3.6}deg, var(--muted) 0deg)` }}
        aria-hidden="true"
      >
        <span className="size-5 rounded-full bg-card" />
      </span>
      <span className="text-sm">{value}%</span>
    </div>
  );
}

export function DocumentDashboard() {
  return (
    <section className="mx-auto grid w-full max-w-[108rem] gap-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Folder className="size-8 fill-foreground text-foreground" aria-hidden="true" />
            <h2 className="text-3xl font-semibold tracking-normal">Documents</h2>
          </div>
          <div className="relative w-full max-w-md">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-12 rounded-lg bg-card pl-11 text-base" placeholder="Search name or author" />
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button variant="outline" className="h-11 gap-2 px-4">
            <Plus className="size-4" aria-hidden="true" />
            New folder
          </Button>
          <Button variant="outline" className="h-11 gap-2 px-4">
            <FileText className="size-4" aria-hidden="true" />
            New evaluation
          </Button>
          <Button className="h-11 gap-2 px-4">
            <Upload className="size-4" aria-hidden="true" />
            Upload files
          </Button>
        </div>
      </div>

      <Card className="rounded-lg py-0">
        <div className="flex flex-wrap gap-3 border-b px-6 py-5">
          {['Created', 'Evaluation'].map((filter) => (
            <Button key={filter} variant="outline" className="h-9 gap-2 rounded-lg px-3">
              {filter}
              <ChevronDown className="size-4 text-muted-foreground" aria-hidden="true" />
            </Button>
          ))}
        </div>

        <CardContent className="px-6 py-7">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-12">
                  <input className="size-5 rounded border border-input" type="checkbox" aria-label="Select all documents" />
                </TableHead>
                <TableHead className="min-w-[18rem]">
                  <span className="inline-flex items-center gap-1">
                    Name <ArrowDown className="size-4 text-muted-foreground" aria-hidden="true" />
                  </span>
                </TableHead>
                <TableHead>Author</TableHead>
                <TableHead>
                  <span className="inline-flex items-center gap-1">
                    Created <ArrowDown className="size-4 text-muted-foreground" aria-hidden="true" />
                  </span>
                </TableHead>
                <TableHead>Evaluation</TableHead>
                <TableHead>Program Coordinator</TableHead>
                <TableHead>SME</TableHead>
                <TableHead>GAD</TableHead>
                <TableHead>ITSO</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((document) => (
                <TableRow key={document.name}>
                  <TableCell>
                    <input className="size-5 rounded border border-input" type="checkbox" aria-label={`Select ${document.name}`} />
                  </TableCell>
                  <TableCell className="max-w-[22rem] truncate font-medium">{document.name}</TableCell>
                  <TableCell>{document.author}</TableCell>
                  <TableCell>{document.created}</TableCell>
                  <TableCell>
                    <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-800">
                      {document.evaluation}
                    </span>
                  </TableCell>
                  <TableCell>
                    <ScoreRing value={document.scores.coordinator} />
                  </TableCell>
                  <TableCell>
                    <ScoreRing value={document.scores.sme} />
                  </TableCell>
                  <TableCell>
                    <ScoreRing value={document.scores.gad} />
                  </TableCell>
                  <TableCell>
                    <ScoreRing value={document.scores.itso} />
                  </TableCell>
                  <TableCell>
                    <Select>
                      <SelectTrigger
                        className="h-8 w-8 border-0 bg-transparent p-0 shadow-none hover:bg-muted [&>svg:last-child]:hidden"
                        aria-label={`Open actions for ${document.name}`}
                      >
                        <MoreHorizontal className="size-4 text-muted-foreground" aria-hidden="true" />
                      </SelectTrigger>
                      <SelectContent align="end">
                        <SelectItem value="download">Download</SelectItem>
                        <SelectItem value="delete">Delete</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </section>
  );
}
