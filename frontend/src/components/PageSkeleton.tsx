import { Container } from "./ui/Container";
import { Skeleton } from "./ui/Skeleton";

/** Route-level loading fallback: the outline of a page (title, meta, body) rather than a spinner,
 *  so a lazy route arrives without the layout jumping (UI-002). */
export function PageSkeleton() {
  return (
    <Container className="py-10">
      <div role="status" aria-label="Loading page" className="space-y-8">
        <div className="space-y-3">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="w-40" />
        </div>
        <Skeleton shape="row" className="w-full max-w-xl" />
        <Skeleton shape="chart" />
      </div>
    </Container>
  );
}
