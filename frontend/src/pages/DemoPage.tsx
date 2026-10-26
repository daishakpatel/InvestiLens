import { ArrowRight } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Container } from "../components/ui/Container";
import { useAuth } from "../lib/auth";
import { SCENARIOS } from "../lib/demo";
import type { DemoScenario } from "../lib/demo";
import { useDemoInfo } from "../lib/queries";
import { useDocumentTitle } from "../lib/useDocumentTitle";

/** `/demo`: the five-minute guided path (NFR-ME-010). On the public demo a scenario signs the
 *  visitor into the shared sandbox first, so the cited question can be asked. */
export default function DemoPage() {
  useDocumentTitle("Demo");
  const { user, enterDemo } = useAuth();
  const demo = useDemoInfo();
  const navigate = useNavigate();
  const [opening, setOpening] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const start = async (scenario: DemoScenario) => {
    setFailure(null);
    setOpening(scenario.title);
    try {
      if (!user && demo.data?.enabled) await enterDemo();
      navigate(scenario.to);
    } catch {
      setFailure("The demo account couldn’t be opened. Try again in a moment.");
    } finally {
      setOpening(null);
    }
  };

  return (
    <Container className="max-w-2xl py-16">
      <h1 className="text-heading font-semibold">Try Assay Desk</h1>
      <p className="mt-2 text-muted">
        Three short paths through NVIDIA’s filings. Everything here comes from stored data and recorded
        answers, so it works the same every time.
      </p>
      <ol className="mt-10 divide-y divide-border border-y border-border">
        {SCENARIOS.map((scenario, index) => (
          <li key={scenario.title} className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:gap-6">
            <span aria-hidden className="text-label tabular-nums text-subtle">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="font-medium text-text">{scenario.title}</h2>
              <p className="mt-1 text-sm text-muted">{scenario.description}</p>
            </div>
            <Button
              variant="secondary"
              loading={opening === scenario.title}
              onClick={() => void start(scenario)}
              aria-label={`Open: ${scenario.title}`}
            >
              Open <ArrowRight aria-hidden className="size-4" />
            </Button>
          </li>
        ))}
      </ol>
      {failure && (
        <p role="alert" className="mt-4 text-sm text-negative">
          {failure}
        </p>
      )}
    </Container>
  );
}
