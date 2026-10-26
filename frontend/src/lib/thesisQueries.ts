// Phase 7k (FR-TH-013): React Query hooks for the caller's own theses. Every response is
// validated with Zod; every write invalidates what it changed.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";

import { apiRequest } from "./apiClient";
import { parse } from "./schemas";
import type {
  DraftResponse,
  KpiCreate,
  KpiUpdate,
  MetricRegistryResponse,
  ThesisCreate,
  ThesisDetail,
  ThesisEvent,
  ThesisKpi,
  ThesisRevision,
  ThesisSummary,
  ThesisUpdate,
} from "../types";

const MINUTE = 60_000;

export function useTheses(ticker?: string, enabled = true): UseQueryResult<ThesisSummary[]> {
  return useQuery({
    queryKey: ["theses", ticker ?? null],
    enabled,
    queryFn: async ({ signal }) => {
      const query = ticker ? `?ticker=${encodeURIComponent(ticker)}` : "";
      const { data } = await apiRequest<unknown>(`/theses${query}`, { signal });
      return parse.theses(data);
    },
  });
}

export function useThesis(id: number | null): UseQueryResult<ThesisDetail> {
  return useQuery({
    queryKey: ["thesis", id],
    enabled: id !== null,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/theses/${id}`, { signal });
      return parse.thesis(data);
    },
  });
}

export function useThesisEvents(id: number | null): UseQueryResult<ThesisEvent[]> {
  return useQuery({
    queryKey: ["thesis-events", id],
    enabled: id !== null,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/theses/${id}/events?limit=100`, { signal });
      return parse.thesisEvents(data);
    },
  });
}

export function useThesisRevisions(id: number | null, enabled: boolean): UseQueryResult<ThesisRevision[]> {
  return useQuery({
    queryKey: ["thesis-revisions", id],
    enabled: enabled && id !== null,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(`/theses/${id}/revisions`, { signal });
      return parse.thesisRevisions(data);
    },
  });
}

export function useMetricRegistry(ticker: string): UseQueryResult<MetricRegistryResponse> {
  return useQuery({
    queryKey: ["thesis-metric-registry", ticker],
    staleTime: 30 * MINUTE,
    queryFn: async ({ signal }) => {
      const { data } = await apiRequest<unknown>(
        `/thesis/metric-registry?ticker=${encodeURIComponent(ticker)}`,
        { signal },
      );
      return parse.metricRegistry(data);
    },
  });
}

/** Everything a thesis write can change: the lists, the thesis, its timeline and history. */
function useRefresh(): (id?: number) => Promise<void> {
  const client = useQueryClient();
  return async (id?: number) => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ["theses"] }),
      ...(id === undefined
        ? []
        : [
            client.invalidateQueries({ queryKey: ["thesis", id] }),
            client.invalidateQueries({ queryKey: ["thesis-events", id] }),
            client.invalidateQueries({ queryKey: ["thesis-revisions", id] }),
          ]),
    ]);
  };
}

export function useCreateThesis(): UseMutationResult<ThesisDetail, Error, ThesisCreate> {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: ThesisCreate) => {
      const { data } = await apiRequest<unknown>("/theses", { method: "POST", body });
      return parse.thesis(data);
    },
    onSuccess: (thesis) => refresh(thesis.id),
  });
}

export function useUpdateThesis(id: number): UseMutationResult<ThesisDetail, Error, ThesisUpdate> {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: ThesisUpdate) => {
      const { data } = await apiRequest<unknown>(`/theses/${id}`, { method: "PATCH", body });
      return parse.thesis(data);
    },
    onSuccess: () => refresh(id),
  });
}

export function useDeleteThesis(): UseMutationResult<void, Error, number> {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiRequest<unknown>(`/theses/${id}`, { method: "DELETE" });
    },
    onSuccess: () => refresh(),
  });
}

export function useAddKpi(thesisId: number): UseMutationResult<ThesisKpi, Error, KpiCreate> {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (body: KpiCreate) => {
      const { data } = await apiRequest<unknown>(`/theses/${thesisId}/kpis`, { method: "POST", body });
      return parse.thesisKpi(data);
    },
    onSuccess: () => refresh(thesisId),
  });
}

export function useUpdateKpi(
  thesisId: number,
): UseMutationResult<ThesisKpi, Error, { id: number; body: KpiUpdate }> {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: KpiUpdate }) => {
      const { data } = await apiRequest<unknown>(`/theses/${thesisId}/kpis/${id}`, { method: "PATCH", body });
      return parse.thesisKpi(data);
    },
    onSuccess: () => refresh(thesisId),
  });
}

export function useDeleteKpi(thesisId: number): UseMutationResult<void, Error, number> {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (id: number) => {
      await apiRequest<unknown>(`/theses/${thesisId}/kpis/${id}`, { method: "DELETE" });
    },
    onSuccess: () => refresh(thesisId),
  });
}

export function useAddNote(thesisId: number): UseMutationResult<ThesisEvent, Error, string> {
  const refresh = useRefresh();
  return useMutation({
    mutationFn: async (note: string) => {
      const { data } = await apiRequest<unknown>(`/theses/${thesisId}/events`, {
        method: "POST",
        body: { note },
      });
      return parse.thesisEvent(data);
    },
    onSuccess: () => refresh(thesisId),
  });
}

/** Suggestions only: nothing is saved (FR-TH-010). */
export function useDraftThesis(): UseMutationResult<DraftResponse, Error, { ticker: string; notes: string }> {
  return useMutation({
    mutationFn: async (body: { ticker: string; notes: string }) => {
      const { data } = await apiRequest<unknown>("/theses/draft", { method: "POST", body });
      return parse.thesisDraft(data);
    },
  });
}
