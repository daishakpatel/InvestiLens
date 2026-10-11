import { DISCLAIMER } from "../lib/config";
import { Container } from "./ui/Container";

/** One quiet line on every page: the not-investment-advice disclaimer (FR-012). */
export function Footer() {
  return (
    <footer className="mt-20 border-t border-border">
      <Container className="py-6">
        <p role="note" className="text-caption text-subtle">
          {DISCLAIMER}
        </p>
      </Container>
    </footer>
  );
}
